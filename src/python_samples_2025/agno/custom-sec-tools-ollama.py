import argparse
import datetime
import json
import os
import re
import subprocess
import time

import requests
from agno.utils.log import logger

from custom_agents.ollama_agent import OLLAMA_HOST
from custom_tools.nmap_tool import NmapAgent
from custom_tools.metasploit_tool import MetasploitAgent


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
    if selected_model not in models:
        print(
            f"Modelo {selected_model} no encontrado. Descargue con 'docker exec ollama ollama pull {selected_model}'.")
        exit(1)
    print(f"Modelo seleccionado: {selected_model}")

    # Asegurar que rockyou.txt esté disponible
    wordlist_path = ensure_wordlist()
    parser = argparse.ArgumentParser(description="Cybersecurity Agent based in Ollama for pentesting")
    parser.add_argument("--target", default="scanme.nmap.org", help="Target IP or hostname")
    args = parser.parse_args()
    target = args.target

    if not re.match(r'^[a-zA-Z0-9\.\-_:]+$', target):
        raise ValueError("Invalid target format")

    # Ejecutar NmapAgent directamente para depuración
    nmap_agent = NmapAgent()
    nmap_result = nmap_agent.run(target=target)
    print(f"Nmap Result: {nmap_result}")
    # Pasar el resultado a MetasploitAgent
    metasploit_agent = MetasploitAgent()
    metasploit_result = metasploit_agent.run(target=target, nmap_data=nmap_result)
    # print(f"Metasploit Result: {metasploit_result}")

    # Mantener el contenedor vivo
    print("Análisis inicial completado. Manteniendo el contenedor vivo...")
    while True:
        time.sleep(60)
    '''    
    agent = Agent(
        model=Ollama(id=selected_model, client=OllamaClient(host=OLLAMA_HOST)),
        description=dedent("""\
                                        The Cybersecurity Agent is a sophisticated automated entity designed to perform in-depth vulnerability assessments on a given system within a controlled and secure containerized environment. The agent operates under the explicit permission of the system owner, ensuring ethical and legal compliance throughout the process. The agent’s primary objective is to identify and analyze potential security weaknesses in the target system, utilizing a wide array of security tools and techniques.

                                Key features include:

                                Secure Containerized Execution: The agent operates within a dedicated, isolated container environment, ensuring that all activities are contained and do not interfere with other systems or networks. This setup ensures the safety of both the target system and the environment in which the agent is running.
                                Comprehensive Vulnerability Scanning: The agent employs industry-standard cybersecurity tools such as Nmap, Metasploit, Nikto, Hydra, and others. These tools are used to conduct various types of scans, including network scans, vulnerability detection, and brute-force attempts, among others, to uncover hidden vulnerabilities.
                                Automated Decision-Making: The agent uses advanced algorithms and, if applicable, AI-driven models to analyze the results of each scan. Based on the findings from one tool, the agent intelligently decides the next appropriate tool or method to use, ensuring a thorough and targeted analysis.
                                Ethical and Permission-Based Operations: All actions are conducted with the explicit consent of the system owner. The agent strictly adheres to ethical guidelines and legal standards, ensuring that the assessment is performed safely and responsibly. The information gathered is intended solely for the improvement of system security, and any findings are reported to the system owner in a clear and actionable format.
                                Detailed Reporting and Documentation: Once the vulnerability assessment is complete, the agent generates comprehensive reports detailing all identified vulnerabilities, their potential risks, and recommended mitigation strategies. These reports are crafted in a way that is understandable for both technical and non-technical stakeholders, ensuring that the system owner has the necessary information to enhance their system's security.
                                Continuous Improvement: The agent is designed to evolve. As new vulnerabilities and attack vectors are discovered, the agent is updated to include the latest tools, techniques, and strategies, ensuring ongoing effectiveness in an ever-changing cybersecurity landscape.
                                By utilizing this agent, system owners can ensure that their systems are thoroughly tested for vulnerabilities, with the ultimate goal of strengthening their security posture and protecting against potential cyber threats.
                                    """),
        instructions=dedent(f"""\
            You are a pentesting agent with permission to analyze {target}.
            1. Execute NmapAgent.run(target='{target}') and show its real output.
            2. Pass the Nmap output to MetasploitAgent.run(target='{target}', nmap_data=<nmap_output>) to generate and run a dynamic Metasploit script.
            3. Show the real output of each tool and use it to decide the next step (e.g., NiktoAgent.run() or HydraAgent.run()).
            Do not invent outputs; only use the actual results from the tools.
            Provide the exact command executed and its output in your response.
        """),
        tools=[ShellTools(), NmapAgent(), MetasploitAgent(), NiktoAgent(), HydraAgent()],
        show_tool_calls=True,
        reasoning=True,
        debug_mode=True,
        monitoring=True,
        markdown=True
    )

    print(f"Ejecutando análisis inicial en {target}...")
    agent.print_response(f"Run a pentesting analysis on {target}")

    # Bucle para aceptar nuevos targets solo si hay terminal interactiva
    if sys.stdin.isatty():
        while True:
            try:
                print(f"Actual target: {target}")
                target = input("Enter the target for the pentesting analysis (or 'exit' to exit): ").strip()
                if target.lower() == "exit":
                    print("Leaving the agent...")
                    break
                if not re.match(r'^[a-zA-Z0-9\.\-_:]+$', target):
                    print("Invalid target format. Use only letters, numbers, '.', '-', '_' or ':'.")
                    continue
                print(f"Running analysis on {target}...")
                agent.print_response(f"Run a pentesting analysis on {target}")
            except KeyboardInterrupt:
                print("Interrupt received. Exiting agent...")
                break
    else:
        print("No terminal interactiva detectada. Manteniendo el contenedor vivo tras el análisis inicial...")
        while True:
            time.sleep(60)
    '''
