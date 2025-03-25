# filepath: /Users/aironman/git/python-samples-2025/src/python_samples_2025/agno/agno-sample.py
import os
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from dotenv import load_dotenv

load_dotenv()
# Obtén el token de la variable de entorno
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    raise ValueError("El token de OpenAI no está configurado. Por favor, define la variable de entorno OPENAI_API_KEY.")

reasoning_agent = Agent(
    model=OpenAIChat(id="gpt-4o", api_key=openai_api_key),  # Pasa el token aquí
    reasoning=True,
    markdown=True,
)

# Pruebas rápidas
prompts = [
    "Explica cómo entrenar un modelo de IA en 5 pasos simples.",
    "Genera un plan de proyecto para usar IA en análisis de sentimientos.",
    "Resuelve este problema: ¿Cuál es el mejor algoritmo para clasificar texto corto?",
    "Resuelva el problema del tranvía. Evalúe múltiples marcos éticos. Incluya un diagrama ASCII de su solución."
]
for prompt in prompts:
    reasoning_agent.print_response(prompt, stream=True, show_full_reasoning=True)
