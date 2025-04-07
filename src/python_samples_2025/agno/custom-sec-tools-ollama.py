import argparse
import datetime
import json
import logging
import os
import re
import subprocess
import time

import requests
from agno.utils.log import logger

from custom_agents.ollama_agent import OLLAMA_HOST
from custom_tools.nmap_tool import NmapAgent
from custom_tools.metasploit_tool import MetasploitAgent

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def is_ollama_running():
    try:
        response = requests.get(f"{OLLAMA_HOST}/", timeout=5)
        return response.status_code == 200
    except requests.ConnectionError:
        return False


def wait_for_ollama(timeout=60):
    start_time = time.time()
    while not is_ollama_running():
        if time.time() - start_time > timeout:
            raise Exception(f"No se pudo conectar a Ollama en {OLLAMA_HOST} tras {timeout}s.")
        print("Esperando a que Ollama esté listo...")
        time.sleep(5)
    print("Ollama está corriendo.")


def list_ollama_models(retries=5, delay=3):
    for attempt in range(retries):
        try:
            response = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
            print(f"Respuesta de {OLLAMA_HOST}/api/tags: {response.text}")
            response.raise_for_status()
            models_data = response.json().get("models", [])
            models = [model["name"] for model in models_data]
            if models:
                return models
            print("No se encontraron modelos en Ollama.")
            return []
        except requests.exceptions.RequestException as e:
            print(f"Intento {attempt + 1}/{retries}: Error al listar modelos de Ollama: {e}")
            time.sleep(delay)
    print("No se pudieron obtener los modelos de Ollama tras varios intentos.")
    return []


def select_model(models):
    """Permite seleccionar un modelo de la lista disponible."""
    if not models:
        print("No hay modelos disponibles en Ollama.")
        download = input("¿Desea descargar un modelo? (s/n): ").strip().lower()
        if download == "s":
            model_name = input("Ingrese el nombre del modelo a descargar: ").strip()
            # Aquí podrías usar la API para pull, pero por simplicidad lo dejamos manual
            print(f"Por favor, ejecute 'docker exec ollama ollama pull {model_name}' manualmente.")
            return None
        return None

    print("Modelos disponibles en Ollama:")
    for idx, model in enumerate(models, 1):
        print(f"{idx}. {model}")
    while True:
        try:
            choice = int(input("Seleccione un modelo por número: "))
            if 1 <= choice <= len(models):
                return models[choice - 1]
            else:
                print("Selección fuera de rango.")
        except ValueError:
            print("Entrada inválida. Introduzca un número.")


def ensure_wordlist():
    # Verificar si rockyou.txt existe, si no, instalarlo
    wordlist_path = "/usr/share/wordlists/rockyou.txt"
    if not os.path.exists(wordlist_path):
        print("rockyou.txt no encontrado. Instalando wordlists...")
        os.system("apt-get update && apt-get install -y wordlists")
        if os.path.exists("/usr/share/wordlists/rockyou.txt.gz"):
            os.system("gunzip /usr/share/wordlists/rockyou.txt.gz")
        if not os.path.exists(wordlist_path):
            print("Advertencia: rockyou.txt no disponible. Usando lista por defecto.")
            wordlist_path = "/tmp/default_wordlist.txt"
            with open(wordlist_path, "w") as f:
                f.write("password\nadmin\n123456\n")
    return wordlist_path


# Verificación de herramientas en el PATH
def check_tools_in_path():
    required_tools = ["nmap", "msfconsole", "nikto", "hydra"]

    for tool in required_tools:
        result = subprocess.run(["which", tool], capture_output=True, text=True)
        if not result.stdout:
            logger.error(f"{tool} is not in your PATH. Please install or configure it.")
            return False
        logger.info(f"{tool} found in: {result.stdout.strip()}")
    return True


# Generar reporte final
def generate_report(results: dict):
    report = {
        "timestamp": datetime.datetime.now().isoformat(),
        "target": target,
        **results
    }
    with open("pentest_report.json", "w") as f:
        json.dump(report, f, indent=2)
    logger.info("[+] Generated report: pentest_report.json")


# Instalación de python-libnmap
try:
    from libnmap.parser import NmapParser
except ImportError:
    logger.error("python-libnmap is not installed. Installing...")
    subprocess.run(["pip3", "install", "python-libnmap"])
    from libnmap.parser import NmapParser

# Uso del agente
if __name__ == "__main__":
    wait_for_ollama()
    models = list_ollama_models()
    selected_model = "llama3.2:1b"
    if not any(selected_model in model for model in models):
        print(
            f"Modelo {selected_model} no encontrado. Descargue con 'docker exec ollama ollama pull {selected_model}'.")
        exit(1)
    print(f"Modelo seleccionado: {selected_model}")

    # Asegurar que rockyou.txt esté disponible
    wordlist_path = ensure_wordlist()
    parser = argparse.ArgumentParser(description="Cybersecurity Agent based in Ollama for pentesting")
    parser.add_argument("--target", default=os.getenv("TARGET_HOST", "172.18.0.2"), help="Target IP or hostname")
    args = parser.parse_args()
    target = args.target.strip()
    print(f"Target recibido: '{target}'")
    print(f"Target en bytes: {repr(target)}")

    if not re.match(r'^[a-zA-Z0-9.-_:]+$', target):
        print(f"Target '{target}' no pasa la validación de regex.")
        raise ValueError("Invalid target format")

    # Ejecutar NmapAgent directamente para depuración
    nmap_agent = NmapAgent()
    nmap_result = nmap_agent.run(target=target, ports=80)
    print(json.dumps(nmap_result, indent=2))


    # Mantener el contenedor vivo
    print("Análisis inicial completado. Manteniendo el contenedor vivo...")
    while True:
        time.sleep(60)