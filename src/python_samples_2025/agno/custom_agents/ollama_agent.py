import os

import requests
from agno.agent.agent import Agent

# Obtener el host de Ollama desde la variable de entorno
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

class OllamaAgent(Agent):
    def __init__(self, model="llama3.2:1b", description=None, instructions=None, tools=None, show_tool_calls=False,
                 markdown=False, **kwargs):
        super().__init__(description=description, instructions=instructions, tools=tools,
                         show_tool_calls=show_tool_calls, markdown=markdown, **kwargs)
        self.model = model
        self.ollama_url = f"{OLLAMA_HOST}/api/generate"
        print(f"model is {self.model}")

    def run(self, message: str, **kwargs) -> str:
        print(f"[+] Running OllamaAgent {self.model}")

        payload = {
            "model": self.model,
            "prompt": message,
            "stream": False,
            "options": {
                "num_ctx": 2048,  # Reduce el contexto
                "num_batch": 512,  # Reduce el batch size
                "num_thread": 2,  # Usa solo 2 hilos
            }
        }
        try:
            response = requests.post(self.ollama_url, json=payload)
            response.raise_for_status()
            return response.json().get("response", "Error: Respuesta vacía")
        except requests.exceptions.RequestException as e:
            return f"Error en la solicitud a Ollama: {e}"
