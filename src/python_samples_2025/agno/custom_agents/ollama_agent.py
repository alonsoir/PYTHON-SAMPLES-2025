import os
import requests
from agno.agent.agent import Agent

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")

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
                "num_ctx": 4096,
                "num_batch": 512,
                "num_thread": 8,
            }
        }
        print(f"[+] payload is \n {payload}")
        try:
            response = requests.post(self.ollama_url, json=payload, timeout=600)
            response.raise_for_status()
            print(f" [+] Ollama response: {response}")
            raw_response = response.json().get("response", "Error: Respuesta vacía")

            # Validar y corregir la respuesta si es necesario
            if not self._is_valid_format(raw_response):
                print(f" [!] Ollama response does not match expected format: {raw_response}")
                # Aquí podrías intentar corregir la respuesta o devolver un error
                return "Error: Invalid response format from Ollama"
            return raw_response

        except requests.exceptions.RequestException as e:
            print(f"Error en la solicitud a Ollama: {e}")
            return f"Error en la solicitud a Ollama: {e}"

    def _is_valid_format(self, response: str) -> bool:
        """Valida si la respuesta sigue el formato esperado: ip|hostname|mac;port,state,service,version;cve,score,url"""
        if not response or ";" not in response:
            return False
        parts = response.split(";")
        for part in parts:
            subparts = part.split(",")
            if "|" in part:  # Host part: ip|hostname|mac
                if len(part.split("|")) != 3:
                    return False
            elif len(subparts) == 4:  # Ports part: port,state,service,version
                continue
            elif len(subparts) == 3:  # Vulnerabilities part: cve,score,url
                continue
            else:
                return False
        return True