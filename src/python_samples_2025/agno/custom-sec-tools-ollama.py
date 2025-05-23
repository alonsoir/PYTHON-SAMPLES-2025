import argparse
import datetime
import json
import logging
import os
import re
import subprocess
import time

import requests
from agno.agent import Agent
from agno.utils.log import logger

from custom_agents.ollama_agent import OLLAMA_HOST
from custom_tools.Hydra_agent import HydraAgent
from custom_tools.nikto_agent import NiktoAgent
from custom_tools.nmap_tool import NmapAgent
from custom_tools.searchxploit_agent import SearchsploitAgent

# Configuración de logging
logger.setLevel(logging.DEBUG)
results_dir = "/results"
os.makedirs(results_dir, exist_ok=True)
log_file = os.path.join(results_dir, "combined.log")
file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s [%(name)s] %(levelname)s: %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

def is_ollama_running():
    """Verifica si Ollama está activo."""
    try:
        response = requests.get(f"{OLLAMA_HOST}/", timeout=5)
        return response.status_code == 200
    except requests.ConnectionError:
        return False

def wait_for_ollama(timeout=60):
    """Espera a que Ollama esté listo."""
    start_time = time.time()
    while not is_ollama_running():
        if time.time() - start_time > timeout:
            raise Exception(f"No se pudo conectar a Ollama en {OLLAMA_HOST} tras {timeout}s.")
        logger.info("Esperando a que Ollama esté listo...")
        time.sleep(5)
    logger.info("Ollama está corriendo.")

def list_ollama_models(retries=5, delay=3):
    """Lista los modelos disponibles en Ollama."""
    for attempt in range(retries):
        try:
            response = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
            logger.debug(f"Respuesta de {OLLAMA_HOST}/api/tags: {response.text}")
            response.raise_for_status()
            models_data = response.json().get("models", [])
            models = [model["name"] for model in models_data]
            if models:
                logger.info(f"Modelos encontrados: {', '.join(models)}")
                return models
            logger.warning("No se encontraron modelos en Ollama.")
            return []
        except requests.exceptions.RequestException as e:
            logger.error(f"Intento {attempt + 1}/{retries}: Error al listar modelos: {e}")
            time.sleep(delay)
    raise Exception("No se pudieron obtener los modelos de Ollama tras varios intentos.")

'''
todo
Necesito ésto? creo que ya lo tengo integrado en el contenedor custom-sec
'''
def ensure_wordlist():
    """Asegura que rockyou.txt esté disponible."""
    wordlist_path = "/usr/share/wordlists/rockyou.txt"
    if not os.path.exists(wordlist_path):
        logger.info("rockyou.txt no encontrado. Instalando wordlists...")
        subprocess.run(["apt-get", "update"], check=True)
        subprocess.run(["apt-get", "install", "-y", "wordlists"], check=True)
        if os.path.exists("/usr/share/wordlists/rockyou.txt.gz"):
            subprocess.run(["gunzip", "/usr/share/wordlists/rockyou.txt.gz"], check=True)
        if not os.path.exists(wordlist_path):
            logger.warning("rockyou.txt no disponible. Creando lista por defecto.")
            wordlist_path = os.path.join(results_dir, "default_wordlist.txt")
            with open(wordlist_path, "w") as f:
                f.write("password\nadmin\n123456\n")
    return wordlist_path

def check_tools_in_path():
    """Verifica que las herramientas estén en el PATH."""
    required_tools = ["nmap", "nikto", "hydra", "msfconsole","searchsploit", "sqlmap", "beef-xss", "php","nginx"]
    for tool in required_tools:
        result = subprocess.run(["which", tool], capture_output=True, text=True)
        if not result.stdout:
            logger.error(f"{tool} no está en el PATH. Instálelo o configúrelo.")
            raise Exception(f"{tool} no encontrado.")
        logger.info(f"{tool} encontrado en: {result.stdout.strip()}")
    return True

def generate_report(results: dict, target: str):
    """Genera un reporte final en JSON."""
    report = {
        "timestamp": datetime.datetime.now().isoformat(),
        "target": target,
        **results
    }
    report_file = os.path.join(results_dir, "pentest_report.json")
    with open(report_file, "w") as f:
        json.dump(report, f, indent=2)
    logger.info(f"[+] Reporte generado: {report_file}")

from agno.models.ollama import Ollama
from agno.models.openai import OpenAIChat
from ollama import Client as OllamaClient
from agno.tools.reasoning import ReasoningTools

def main_agno_openAI():
    api_key=os.getenv("OPENAI_API_KEY")
    agent = Agent(
        model=OpenAIChat(api_key=api_key),
        tools=[
            ReasoningTools(), HydraAgent(), NiktoAgent(), NmapAgent(),
        ],
        instructions=[
            "Perform an authorized pentesting analysis on the target 172.18.0.2:80 (HTTP, Linux 4.15 - 5.19).",
            "Use NmapAgent to confirm open ports and services, NiktoAgent to scan for web vulnerabilities, "
            "and SearchsploitAgent to find potential exploits.",
            "Accept that SearchsploitAgent may mark exploits as 'unknown' due to missing Metasploit mappings.",
            "Generate a report in Markdown with tables showing: ports and services, "
            "web vulnerabilities, and potential exploits (including EDB-ID, title, and recommendations).",
            "Assign a confidence score (0.5 for 'unknown' exploits, 0.9 for valid ones).",
            "Handle errors gracefully, logging issues to /results/combined.log without stopping the analysis.",
            "Include a note that the analysis was authorized by the client."
        ],
        markdown=True,
    )
    timestamp = datetime.datetime.now().isoformat()
    report_file = f"/results/pentest_report_{timestamp}.md"
    message=(f"Write a pentesting report for 172.18.0.2 based on Nmap, Nikto, and Searchsploit analysis, "
             f"using /results/nmap_result.json as input.")
    print(message)
    agent.print_response(
        message,
        stream=True,
        show_full_reasoning=True,
        stream_intermediate_steps=True,
        output_file=report_file
    )
    logger.info(f"Reporte generado: {report_file}")

def main_agno():
    agent = Agent(
        model=Ollama(id="llama3.2:1b", client=OllamaClient()),
        tools=[
            ReasoningTools(), HydraAgent(),NiktoAgent(),NmapAgent(),
        ],
        instructions=[
            "Perform an authorized pentesting analysis on the target 172.18.0.2:80 (HTTP, Linux 4.15 - 5.19).",
            "Use NmapAgent to confirm open ports and services, NiktoAgent to scan for web vulnerabilities, "
            "and SearchsploitAgent to find potential exploits.",
            "Accept that SearchsploitAgent may mark exploits as 'unknown' due to missing Metasploit mappings.",
            "Generate a report in Markdown with tables showing: ports and services, "
            "web vulnerabilities, and potential exploits (including EDB-ID, title, and recommendations).",
            "Assign a confidence score (0.5 for 'unknown' exploits, 0.9 for valid ones).",
            "Handle errors gracefully, logging issues to /results/combined.log without stopping the analysis.",
            "Include a note that the analysis was authorized by the client."
        ],
        markdown=True,
    )
    timestamp = datetime.datetime.now().isoformat()
    report_file = f"/results/pentest_report_{timestamp}.md"
    agent.print_response(
        f"Write a pentesting report for 172.18.0.2 based on Nmap, Nikto, and Searchsploit analysis, using /results/nmap_result.json as input.",
        stream=True,
        show_full_reasoning=True,
        stream_intermediate_steps=True,
        output_file=report_file
    )
    logger.info(f"Reporte generado: {report_file}")


def main():
    '''
    En algun momento esto será una shell inicializada con un agente Agno, de manera que tenga inyectada todas las
    herramientas a disposicion.

    Ahora mismo hay un pipeline en el que se sigue un orden de ejecucion de herramientas, primero se inicializa un mapa
    disponible de vulnerabilidades en msfdb, se ejecuta nmap buscando vulnerabilidades para sacar cosas como el SO, una
    lista de vulnerabilidades, puertos abiertos, (revisar el módulo de Nmap, porque ahora de memoria creo que solo busco
    el 80. debo sacar todos los puertos abiertos) para generar un fichero json que se pasa a las siguientes herramientas.

    Se ha desarrollado en un principio con la aplicacion vulnerable-app en mente, pero
    supongo que habrá que actualizarla con nuevas técnicas y otras aplicaciones vulnerables. La idea es poder tener una
    shell en la que le preguntas mediante lenguaje natural para vulnerar una máquina con la que tenemos un contrato por
    parte del cliente para poder ayudarle a cerrar las vulnerabilidades de dicha máquina, o de su red de máquinas.
    :return:
    '''
    # Parsear argumentos
    parser = argparse.ArgumentParser(description="Cybersecurity Agent for pentesting with Ollama")
    parser.add_argument("--target", default=os.getenv("TARGET_HOST", "172.18.0.2"), help="Target IP or hostname")
    args = parser.parse_args()
    target = args.target.strip()
    logger.info(f"Target recibido: '{target}'")

    if not re.match(r'^[a-zA-Z0-9.-_:]+$', target):
        logger.error(f"Target '{target}' no pasa la validación de regex.")
        raise ValueError("Invalid target format")

    # Esperar a Ollama
    wait_for_ollama()

    # Verificar modelos, probablemente no necesite listar los modelos y me quede con llama3.2:1b
    models = list_ollama_models()
    selected_model = "llama3.2:1b"
    if not any(selected_model in model for model in models):
        logger.error(f"Modelo {selected_model} no encontrado. Descargue con 'docker exec ollama ollama pull {selected_model}'.")
        raise Exception(f"Modelo {selected_model} no disponible.")

    # Asegurar wordlist
    wordlist_path = ensure_wordlist()

    # Verificar herramientas
    check_tools_in_path()

    # Ejecutar pipeline
    results = {}
    json_file = os.path.join(results_dir, "nmap_result.json")

    # Nmap
    logger.info(f"Ejecutando Nmap en {target} puerto 80...")
    nmap_agent = NmapAgent()
    nmap_result_raw = nmap_agent.run(target=target, ports="80")
    if "error" in nmap_result_raw:
        logger.error(f"Error en Nmap: {nmap_result_raw['error']}")
        results["nmap"] = nmap_result_raw
    else:
        # Parsear el resultado crudo si está envuelto en "result"
        if "result" in nmap_result_raw and isinstance(nmap_result_raw["result"], str):
            try:
                nmap_result = json.loads(nmap_result_raw["result"].strip())
            except json.JSONDecodeError as e:
                logger.error(f"Error al parsear el resultado de Nmap: {e}")
                results["nmap"] = {"error": f"Error al parsear JSON: {e}"}
                nmap_result = None
        else:
            nmap_result = nmap_result_raw

        if nmap_result:
            with open(json_file, "w") as f:
                json.dump(nmap_result, f, indent=2)
            logger.info(f"Resultado de Nmap guardado en {json_file}")
            results["nmap"] = nmap_result
        print(json.dumps(nmap_result, indent=2))

    # Nikto
    logger.info("Ejecutando Nikto...")
    nikto_agent = NiktoAgent()
    nikto_result = nikto_agent.run(json_file=json_file)
    results["nikto"] = nikto_result
    print(json.dumps(nikto_result, indent=2))

    # Hydra
    logger.info("Ejecutando Hydra...")
    hydra_agent = HydraAgent()
    hydra_result = hydra_agent.run(json_file=json_file)
    results["hydra"] = hydra_result
    print(json.dumps(hydra_result, indent=2))

    # Generar el mapeo de exploits
    # logger.info("Generando mapeo de exploits...")
    # mapping_generator = ExploitMappingGenerator()
    # mapping_generator.run()
    # logger.info("Generado mapeo de exploits...")

    # logger.info("Ejecutando Metasploit...")
    # metasploit_agent = MetasploitAgent()
    # metasploit_result = metasploit_agent.run(json_file=json_file)
    # results["metasploit"] = metasploit_result
    # print(json.dumps(metasploit_result, indent=2))

    logger.info("Módulo de Metasploit desactivado temporalmente")

    logger.info("Ejecutando SearchsploitAgent...")
    searchsploitAgent = SearchsploitAgent()
    searchxploit_result = searchsploitAgent.run(json_file=json_file)
    results["searchxploit_result"] = searchxploit_result
    print(json.dumps(searchxploit_result, indent=2))

    # Generar reporte
    generate_report(results, target)

    # Mantener contenedor vivo
    logger.info("Análisis inicial completado. Manteniendo el contenedor vivo...")
    while True:
        time.sleep(60)

if __name__ == "__main__":
    #main()
    # main_agno()
    main_agno_openAI()