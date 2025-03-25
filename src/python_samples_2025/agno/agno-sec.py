import os
import subprocess
import json
import logging
from agno.agent import Agent
from agno.models.openai import OpenAIChat
from agno.tools.duckduckgo import DuckDuckGoTools

from dotenv import load_dotenv

# Configurar logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Cargar API key
load_dotenv()
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    logging.error("El token de OpenAI no está configurado.")
    raise ValueError("El token de OpenAI no está configurado.")

# Configurar agente Agno
agent = Agent(
    model=OpenAIChat(id="gpt-4o", api_key=openai_api_key),
    tools=[DuckDuckGoTools()],
    show_tool_calls=True,
    reasoning=True,
    markdown=True,
)

# Archivo de contexto
CONTEXT_FILE = "context.json"

def load_context():
    """Carga el contexto desde un archivo JSON y garantiza que tenga la estructura correcta."""
    if os.path.exists(CONTEXT_FILE):
        try:
            with open(CONTEXT_FILE, "r") as f:
                context = json.load(f)
        except json.JSONDecodeError:
            logging.warning("El archivo de contexto está corrupto. Se creará uno nuevo.")
            context = {}
    else:
        context = {}

    # Asegurar que "scans" esté presente
    if "scans" not in context:
        context["scans"] = []
    
    return context

def save_context(new_data):
    """Guarda datos en el contexto."""
    context = load_context()
    context["scans"].append(new_data)
    try:
        with open(CONTEXT_FILE, "w") as f:
            json.dump(context, f, indent=4)
    except IOError as e:
        logging.error(f"Error al guardar el contexto: {e}")

def run_tool(command):
    """Ejecuta un comando en la terminal y maneja errores."""
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            logging.warning(f"Error ejecutando '{command}': {result.stderr.strip()}")
            return f"Error: {result.stderr.strip()}"
        return result.stdout.strip()
    except Exception as e:
        logging.error(f"Error ejecutando '{command}': {e}")
        return f"Excepción: {e}"

def is_tool_installed(tool_name):
    """Verifica si una herramienta está instalada."""
    return subprocess.run(f"which {tool_name}", shell=True, capture_output=True).returncode == 0

# Paso 1: Verificar dependencias
for tool in ["nmap", "tshark"]:
    if not is_tool_installed(tool):
        logging.warning(f"{tool} no está instalado. Es posible que el script falle.")

# Paso 2: Ejecutar Nmap
target = "127.0.0.1"
nmap_cmd = f"nmap -sV {target}"
logging.info(f"Ejecutando Nmap en {target}...")
nmap_output = run_tool(nmap_cmd)
logging.info(f"Salida de Nmap:\n{nmap_output}")

# Paso 3: Analizar la salida con Agno
prompt = f"Analiza esta salida de Nmap y sugiere la siguiente acción:\n{nmap_output}"
response = agent.print_response(prompt, stream=False, show_full_reasoning=True)
logging.info(f"Análisis de Agno:\n{response}")

# Paso 4: Guardar contexto
new_context = {
    "tool": "nmap",
    "target": target,
    "output": nmap_output,
    "analysis": response
}
save_context(new_context)

# Paso 5: Decidir la siguiente herramienta
prompt = f"Con este contexto:\n{json.dumps(new_context, indent=2)}\n¿Qué herramienta uso después (Wireshark, Tshark) y cómo?"
response = agent.print_response(prompt, stream=False, show_full_reasoning=True)

if response is None:
    logging.error("No se recibió respuesta del agente Agno.")
    response = "No se recibió respuesta válida."

logging.info(f"Sugerencia de la siguiente herramienta:\n{response}")

# Paso 6: Ejecutar Tshark si se recomienda
if response and "tshark" in response.lower():
    tshark_cmd = "tshark -i any -c 100"
    logging.info("Ejecutando Tshark...")
    tshark_output = run_tool(tshark_cmd)
    logging.info(f"Salida de Tshark:\n{tshark_output}")
    save_context({"tool": "tshark", "output": tshark_output})

