import os
import requests
from dotenv import load_dotenv
from pyspark.sql import SparkSession
from pyspark.sql.functions import col
from agno.agent.agent import Agent
from agno.tools.toolkit import Toolkit
from agno.models.openai.chat import OpenAIChat
import pandas as pd
import asyncio
from textwrap import dedent

# Cargar variables de entorno
load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")

# Configurar Spark para Delta Lake
def create_spark_session():
    try:
        spark = (
            SparkSession.builder
            .appName("DeltaLakeDemo")
            .master("local[*]")
            .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
            .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
            .config("spark.jars.packages", "io.delta:delta-spark_2.12:3.3.0")  # Delta Lake 3.3.0
            .config("spark.driver.host", "127.0.0.1")  # Forzar uso de localhost
            .config("spark.driver.bindAddress", "127.0.0.1")  # Evitar conflictos de red
            .config("spark.driver.port", "7077")  # Puerto fijo para el driver
            .getOrCreate()
        )
        print("SparkContext inicializado correctamente")
        return spark
    except Exception as e:
        print(f"Error inicializando Spark: {e}")
        raise

spark = create_spark_session()

class DeltaLakeTools(Toolkit):
    def __init__(self, table_path):
        super().__init__(name="delta_lake_tools")
        self.table_path = table_path
        if not os.path.exists(table_path):
            os.makedirs(table_path)
        self.register(self.query)

    def load_data_from_csv(self, url):
        try:
            # Descargar CSV
            response = requests.get(url)
            local_csv_path = "temp_movies.csv"
            with open(local_csv_path, "wb") as f:
                f.write(response.content)

            # Leer CSV con manejo de comillas
            df = spark.read.option("header", "true").option("quote", "\"").csv(local_csv_path)
            
            # Inspeccionar datos crudos
            print("Datos crudos:")
            df.show(5, truncate=False)
            
            # Renombrar columnas problemáticas
            df = df.withColumnRenamed("Runtime (Minutes)", "Runtime_Minutes") \
                   .withColumnRenamed("Revenue (Millions)", "Revenue_Millions")
            
            # Inspeccionar después de renombrar
            print("Columnas después de renombrar:", df.columns)
            
            # Castear columnas a tipos adecuados
            df = (
                df.withColumn("Rating", col("Rating").cast("float"))
                .withColumn("Year", col("Year").cast("int"))
                .withColumn("Runtime_Minutes", col("Runtime_Minutes").cast("float"))
                .withColumn("Revenue_Millions", col("Revenue_Millions").cast("float"))
                .filter(col("Rating").isNotNull())
            )
            
            # Inspeccionar después de transformaciones
            print("Datos transformados:")
            df.show(5, truncate=False)
            df.printSchema()
            
            # Guardar como Delta Lake
            df.write.format("delta").mode("overwrite").save(self.table_path)
            os.remove(local_csv_path)
            print(f"Datos cargados en: {self.table_path}")
        except Exception as e:
            print(f"Error cargando datos: {e}")

    def query(self, sql_query: str) -> str:
        """
        Ejecutar una consulta SQL contra la tabla Delta Lake local.
        
        Args:
            sql_query (str): Consulta SQL a ejecutar.
        Returns:
            str: Resultados en formato Markdown.
        """
        try:
            df = spark.read.format("delta").load(self.table_path)
            df.createOrReplaceTempView("movies")
            result_df = spark.sql(sql_query)
            return result_df.toPandas().to_markdown(index=False)
        except Exception as e:
            return f"Error: {e}"

async def main():
    # Configurar Delta Lake
    table_path = "./delta_movies_demo"
    delta_tools = DeltaLakeTools(table_path)
    
    # Cargar datos desde la URL pública
    url = "https://agno-public.s3.amazonaws.com/demo_data/IMDB-Movie-Data.csv"
    delta_tools.load_data_from_csv(url)
    
    # Configurar agente
    agent = Agent(
        model=OpenAIChat(id="gpt-4o", api_key=openai_api_key),
        tools=[delta_tools],
        markdown=True,
        show_tool_calls=True,
        additional_context=dedent("""\
        Tienes una tabla Delta Lake con datos de películas de IMDB.
        Usa la herramienta 'query' para consultar los datos con SQL.
        Ejemplos:
        - 'SELECT AVG(Rating) AS PromedioRating FROM movies'
        - 'SELECT Title, Rating FROM movies ORDER BY Rating DESC LIMIT 5'
        - 'SELECT Title, Year, Rating FROM movies WHERE Year > 2010 ORDER BY Rating DESC'
        Solo devuelve los resultados en Markdown.
        """)
    )
    
    # Ejemplos de consultas en lenguaje natural
    queries = [
        "¿Cuál es el promedio de rating de las películas?",
        "Dame las 5 mejores películas por rating",
        "Muéstrame las mejores películas después del año 2010"
    ]
    
    for query in queries:
        print(f"\nConsulta: {query}")
        await agent.aprint_response(query)

if __name__ == "__main__":
    asyncio.run(main())