"""Run `pip install duckdb` to install dependencies."""

import asyncio
from textwrap import dedent

from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.tools.duckdb import DuckDbTools
from dotenv import load_dotenv
import logging
import os
# Configurar logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Cargar API key
load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    logging.error("El token de OpenAI no está configurado.")
    raise ValueError("El token de OpenAI no está configurado.")

duckdb_tools = DuckDbTools(
    create_tables=False, export_tables=False, summarize_tables=False
)
duckdb_tools.create_table_from_path(
    path="https://agno-public.s3.amazonaws.com/demo_data/IMDB-Movie-Data.csv",
    table="movies",
)

agent = Agent(
    model=OpenAIChat(id="gpt-4o",api_key=openai_api_key),
    tools=[duckdb_tools],
    markdown=True,
    instructions="Always include sources",
    show_tool_calls=True,
    additional_context=dedent("""\
    You have access to the following tables:
    - movies: contains information about movies from IMDB.
    """),
)

prompts = [
    "Cuantas películas tienes guardadas en la base de datos?",
    "Cuales son las mejores peliculas que mas han gustado del director James Cameron?",
    "¿Cuál es la calificación promedio de las películas?",
    "Cuales son las 10 mejores películas que más han gustado al público?",
    "Cuales son las 10 mejores películas de ciencia ficción de todos los tiempos?",
    "Cuales son las 10 mejores películas de animación de todos los tiempos?"
]
for prompt in prompts:
    asyncio.run(agent.aprint_response(prompt, stream=True, show_full_reasoning=True))
