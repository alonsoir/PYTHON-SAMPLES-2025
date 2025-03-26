import asyncio
import os
from textwrap import dedent
from pyspark.sql import SparkSession
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
        self.table_name = "movies"
        if not os.path.exists(table_path):
            os.makedirs(table_path)

    def clean_column_names(self, df):
        """Renombrar columnas para eliminar caracteres no permitidos"""
        new_columns = [col.replace(" ", "_").replace("(", "").replace(")", "") for col in df.columns]
        return df.toDF(*new_columns)

    def initialize_from_remote_csv(self, url):
        local_csv_path = "temp_movies.csv"
        response = requests.get(url)
        with open(local_csv_path, "wb") as f:
            f.write(response.content)
        df = spark.read.option("header", "true").csv(local_csv_path)
        df_cleaned = self.clean_column_names(df)
        df_cleaned.write.format("delta").mode("overwrite").save(self.table_path)
        spark.sql(f"CREATE TABLE IF NOT EXISTS {self.table_name} USING DELTA LOCATION '{self.table_path}'")
        os.remove(local_csv_path)
        logging.info(f"Tabla Delta inicializada en {self.table_path} con datos de {url}")

    async def query(self, sql_query):
        """Ejecutar consulta SQL y devolver resultados en Markdown"""
        logging.info(f"Ejecutando consulta: {sql_query}")
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, lambda: spark.sql(sql_query).toPandas().to_markdown())
        logging.info(f"Resultado de la consulta: {result}")
        return result

    async def update_table(self, url):
        loop = asyncio.get_event_loop()
        local_csv_path = "temp_movies.csv"
        response = requests.get(url)
        with open(local_csv_path, "wb") as f:
            f.write(response.content)
        new_df = spark.read.option("header", "true").csv(local_csv_path)
        new_df_cleaned = self.clean_column_names(new_df)
        await loop.run_in_executor(None, lambda: new_df_cleaned.write.format("delta").mode("overwrite").save(self.table_path))
        os.remove(local_csv_path)
        logging.info(f"Tabla actualizada con datos de {url}")

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
    You have access to a Delta Lake table called 'movies', stored locally in ./delta_movies.
    This table contains IMDB movie data with columns like 'Title', 'Rating', 'Runtime_Minutes', etc.
    Column names have been cleaned (e.g., 'Runtime (Minutes)' is now 'Runtime_Minutes').
    Use the 'query' tool to execute SQL queries directly on this table and return the results in Markdown format.
    When asked to provide data (e.g., averages or lists), ALWAYS execute the appropriate SQL query using the 'query' tool and return the actual result in Markdown format.
    Do NOT invent or guess results; always use the 'query' tool to get real data from the table.
    Examples:
    - If asked "What is the average rating?", execute "SELECT AVG(Rating) AS Average_Rating FROM movies" and return "| Average_Rating | 6.35 |" (with the real value).
    - If asked "List the top 5 movies by rating", execute "SELECT Title, Rating FROM movies ORDER BY Rating DESC LIMIT 5" and return a Markdown table with the actual titles and ratings, like:
      ```
      | Title                | Rating |
      |----------------------|--------|
      | The Dark Knight      | 9.0    |
      | Inception            | 8.8    |
      | Interstellar         | 8.6    |
      | The Empire Strikes Back | 8.7 |
      | The Matrix           | 8.7    |
      ```
    Do not describe the query without executing it; always show the real results from the table.
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

# Ejecutar el flujo
asyncio.run(run_local_operations())

# Cerrar la sesión de Spark
spark.stop()