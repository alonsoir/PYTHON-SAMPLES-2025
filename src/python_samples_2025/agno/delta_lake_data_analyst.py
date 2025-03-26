import asyncio
import os
from textwrap import dedent
from pyspark.sql import SparkSession
from pyspark.sql.functions import col
from agno.agent import Agent
from agno.models.openai import OpenAIChat
import requests
from dotenv import load_dotenv
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Cargar API key
load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    logging.error("El token de OpenAI no está configurado.")
    raise ValueError("El token de OpenAI no está configurado.")

# Configurar Spark con soporte para Delta Lake en local
spark = SparkSession.builder \
    .appName("LocalDeltaLakeAgent") \
    .master("local[*]") \
    .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
    .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
    .config("spark.jars.packages", "io.delta:delta-spark_2.12:3.3.0") \
    .config("spark.driver.host", "127.0.0.1") \
    .config("spark.driver.bindAddress", "127.0.0.1") \
    .config("spark.delta.logRetentionDuration", "interval 7 days") \
    .config("spark.delta.deletedFileRetentionDuration", "interval 7 days") \
    .getOrCreate()

# Herramienta personalizada para Delta Lake local
class DeltaLakeTools:
    def __init__(self, table_path):
        self.table_path = table_path
        if not os.path.exists(table_path):
            os.makedirs(table_path)

    def initialize_from_remote_csv(self, url):
        local_csv_path = "temp_movies.csv"
        response = requests.get(url)
        with open(local_csv_path, "wb") as f:
            f.write(response.content)
        df = spark.read.option("header", "true").csv(local_csv_path)
        # Inspeccionar columnas originales
        original_columns = df.columns
        logging.info(f"Columnas originales del CSV: {original_columns}")
        # Definir columnas esperadas
        expected_columns = ["Rank", "Title", "Genre", "Description", "Director", "Actors", "Year", "Runtime_Minutes", "Rating", "Votes", "Revenue_Millions", "Metascore"]
        if len(original_columns) != len(expected_columns):
            logging.warning(f"El número de columnas no coincide. Original: {len(original_columns)}, Esperado: {len(expected_columns)}")
        df = df.toDF(*expected_columns[:len(original_columns)])
        df = df.withColumn("Rating", col("Rating").cast("float")).filter(col("Rating").isNotNull())
        df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(self.table_path)
        logging.info(f"Tabla Delta inicializada en {self.table_path} con datos de {url}")
        os.remove(local_csv_path)

    async def query(self, sql_query):
        """Ejecutar consulta sobre la tabla Delta y devolver resultados en Markdown"""
        logging.info(f"Ejecutando consulta: {sql_query}")
        loop = asyncio.get_event_loop()
        df = spark.read.format("delta").load(self.table_path)
        if "AVG" in sql_query.upper():
            result = df.agg({"Rating": "avg"}).toPandas().to_markdown()
        else:
            result = df.orderBy(df.Rating.desc()).limit(5).select("Title", "Rating").toPandas().to_markdown()
        logging.info(f"Resultado de la consulta: {result}")
        return result

    async def update_table(self, url):
        loop = asyncio.get_event_loop()
        local_csv_path = "temp_movies.csv"
        response = requests.get(url)
        with open(local_csv_path, "wb") as f:
            f.write(response.content)
        df = spark.read.option("header", "true").csv(local_csv_path)
        original_columns = df.columns
        logging.info(f"Columnas originales del CSV (actualización): {original_columns}")
        expected_columns = ["Rank", "Title", "Genre", "Description", "Director", "Actors", "Year", "Runtime_Minutes", "Rating", "Votes", "Revenue_Millions", "Metascore"]
        df = df.toDF(*expected_columns[:len(original_columns)])
        df = df.withColumn("Rating", col("Rating").cast("float")).filter(col("Rating").isNotNull())
        await loop.run_in_executor(None, lambda: df.write.format("delta").mode("overwrite").option("overwriteSchema", "true").save(self.table_path))
        logging.info(f"Tabla actualizada con datos de {url}")
        os.remove(local_csv_path)

# Configurar herramientas y agente
local_table_path = "./delta_movies"
delta_tools = DeltaLakeTools(table_path=local_table_path)
delta_tools.initialize_from_remote_csv("https://agno-public.s3.amazonaws.com/demo_data/IMDB-Movie-Data.csv")

agent = Agent(
    model=OpenAIChat(id="gpt-4o", api_key=openai_api_key),
    tools=[delta_tools],
    markdown=True,
    show_tool_calls=True,
    additional_context=dedent("""\
    You have a Delta Lake table at ./delta_movies with IMDB data (columns: Title, Rating, Year, etc.).
    Rating is a numeric column (1-10). Use the 'query' tool for all data requests and return its Markdown result.
    - "What is the average rating?": Call 'query' with "SELECT AVG(Rating) AS Average_Rating FROM default.movies".
    - "List the top 5 movies by rating": Call 'query' with "SELECT Title, Rating FROM default.movies ORDER BY Rating DESC LIMIT 5".
    Do NOT invent data or skip the tool. Return only the Markdown table from 'query'.
    """),
)

# Función para probar consultas y actualizaciones
async def run_local_operations():
    print("Consulta inicial:")
    await agent.aprint_response("What is the average rating of movies?")
    print("\nActualizando tabla...")
    await delta_tools.update_table("https://agno-public.s3.amazonaws.com/demo_data/IMDB-Movie-Data.csv")
    print("\nConsulta tras actualización:")
    await agent.aprint_response("List the top 5 movies by rating.")
    print("\nVerificación manual:")
    result_avg = await delta_tools.query("SELECT AVG(Rating) AS Average_Rating FROM default.movies")
    print("Promedio manual:", result_avg)
    result_top5 = await delta_tools.query("SELECT Title, Rating FROM default.movies ORDER BY Rating DESC LIMIT 5")
    print("Top 5 manual:", result_top5)

# Ejecutar el flujo
asyncio.run(run_local_operations())

# Cerrar la sesión de Spark
spark.stop()