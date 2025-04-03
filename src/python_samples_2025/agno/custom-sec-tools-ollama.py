import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import time
from textwrap import dedent
from typing import List, Optional

import requests
from agno.agent.agent import Agent
from agno.models.ollama import Ollama
from agno.tools.toolkit import Toolkit
from agno.utils.log import logger
from ollama import Client as OllamaClient

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


class ShellTools(Toolkit):
    def __init__(self):
        super().__init__(name="shell_tools")
        self.register(self.run_shell_command)

    def run_shell_command(self, args: List[str], tail: int = 100, timeout: int = 60) -> str:
        """Ejecuta un comando en el shell y captura el resultado."""
        # Si args es una lista con una sola cadena, dividirla en argumentos
        if len(args) == 1 and " " in args[0]:
            expanded_args = args[0].split()
        else:
            expanded_args = [os.path.expanduser(arg) if arg == "~" else arg for arg in args]

        logger.info(f"Running shell command: {expanded_args}")
        logger.info(f"Current PATH: {os.environ['PATH']}")  # Depuración del PATH
        try:
            result = subprocess.run(expanded_args, capture_output=True, text=True, timeout=timeout)
            if result.returncode != 0:
                logger.error(f"Command failed: {result.stderr}")
                return f"Error: {result.stderr}"
            logger.debug(f"Command successful: {result.stdout}")
            return "\n".join(result.stdout.split("\n")[-tail:])
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout after {timeout}s running command: {expanded_args}")
            return f"Timeout after {timeout}s"
        except FileNotFoundError as e:
            logger.error(f"Command not found: {e}")
            return f"Error: Command not found - {e}"
        except Exception as e:
            logger.warning(f"Failed to run shell command: {e}")
            return f"Error: {e}"


class NmapAgent(Toolkit):
    def __init__(self):
        super().__init__(name="NmapAgent")  # Cambié "Nmap Agent" a "NmapAgent" por consistencia con otros nombres
        self.register(self.run)

    def run(self, **kwargs) -> dict:
        target = kwargs.get('target', 'localhost')
        timeout = kwargs.get('timeout', 600)
        # command = ["nmap", "-sV", "--script=vuln", "-oX", "nmap_results.xml", target]
        # por debug
        # command = ["nmap", "-sV", "-oX", "nmap_results.xml", target]
        command = ["nmap", "-sV", "-p", "22,80", "-oX", "nmap_results.xml", target]  # Solo puertos 22 y 80

        print(f"\n[+] Running: {' '.join(command)}")
        try:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            stdout, stderr = process.communicate(timeout=timeout)
            print(stdout)
            if process.returncode != 0:
                print(f"[-] Error: {stderr}")
                logger.error(f"[!] Error running Nmap: {stderr}")
                return {"error": f"Error running Nmap: {stderr}"}
            logger.info("[+] Nmap executed successfully.")
            report = NmapParser.parse_fromfile("nmap_results.xml")
            nmap_data = {
                "hosts": [
                    {
                        "address": host.address,
                        "ports": {
                            str(service.port): {
                                "state": service.state,
                                "service": service.service if service.service else "unknown",
                                "version": getattr(service, "version", None)
                            } for service in host.services
                        }
                    } for host in report.hosts if hasattr(host, 'services') and host.services
                ]
            }
            print(f"[+] Parsed Nmap result:\n{json.dumps(nmap_data, indent=2)}")
            return json.dumps(nmap_data)
        except subprocess.TimeoutExpired:
            logger.error(f"[!] Timeout ({timeout}s) during Nmap execution.")
            print(f"[-] Timeout after {timeout}s")
            return {"error": "Timeout during Nmap execution"}
        except FileNotFoundError as e:
            logger.error(f"[!] Nmap not found: {e}")
            print(f"[-] Error: {e}")
            return {"error": f"Nmap not found - {e}"}
        except Exception as e:
            logger.error(f"[!] Error processing Nmap results: {e}")
            print(f"[-] Error: {e}")
            return {"error": f"Error processing Nmap results: {str(e)}"}


class MetasploitAgent(Toolkit):
    def __init__(self):
        super().__init__(name="MetasploitAgent")
        self.register(self.run)
        self.ollama_agent = OllamaAgent(
            model="llama3.2:1b",
            description="Helper agent to generate Metasploit commands",
            instructions=dedent("""\
                You are a Metasploit expert. Given Nmap scan results (ports, services, versions),
                generate a Metasploit script (.rc file content) with:
                1. A list of relevant exploits to try based on the open ports and services.
                2. For each exploit, include 'use', 'set RHOSTS', and 'run' commands.
                3. Prioritize exploits by likelihood of success (e.g., well-known vulnerabilities first).
                4. If no specific exploits match, suggest a generic payload like 'multi/handler'.
                Return the script as a single string with commands separated by newlines.
                Do not invent data; base your suggestions only on the provided Nmap results.
            """)
        )

    def run(self, **kwargs) -> str:
        """Ejecuta Metasploit con comandos generados dinámicamente por el LLM."""
        target = kwargs.get('target', 'localhost')
        nmap_data_raw = kwargs.get('nmap_data')  # JSON string from NmapAgent
        timeout = kwargs.get('timeout', 300)
        print(f"\n [+] Running MetasploitAgent ")
        print(f"\n [+] target is {target}")
        print(f"\n [+] nmap_data_raw is {nmap_data_raw}")
        print(f"\n [+] timeout is {timeout}")
        # Validar y parsear nmap_data
        if not nmap_data_raw:
            logger.error("[!] No nmap_data provided.")
            return "Error: No Nmap data available"
        try:
            nmap_data = json.loads(nmap_data_raw) if isinstance(nmap_data_raw, str) else nmap_data_raw
            if not isinstance(nmap_data, dict):
                raise ValueError("nmap_data must be a dictionary")
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"[!] Invalid nmap_data: {e}")
            return f"Error: Invalid Nmap data - {e}"

        # Mostrar datos de entrada para depuración
        print(f"[+] Nmap Data recibido:\n{json.dumps(nmap_data, indent=2)}")

        # Consultar al LLM para generar el script de Metasploit
        prompt = f"Generate a Metasploit script based on this Nmap data following strict instrucctions given to {self.ollama_agent}:\n{json.dumps(nmap_data, indent=2)}"
        commands = self.ollama_agent.run(prompt)
        if "Error" in commands:
            logger.error(f"[!] Failed to generate Metasploit commands: {commands}")
            return commands

        # Mostrar el script generado
        print(f"\n[+] Script de Metasploit generado por el LLM:\n{commands}")

        # Guardar y ejecutar el script
        try:
            with open("msf_script.rc", "w") as f:
                f.write(commands)
            print(f"\n[+] Ejecutando: msfconsole -r msf_script.rc")
            process = subprocess.Popen(
                ["msfconsole", "-r", "msf_script.rc"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = process.communicate(timeout=timeout)
            print(stdout)  # Mostrar salida en tiempo real
            if process.returncode != 0:
                print(f"[-] Error: {stderr}")
                logger.error(f"[!] Error en Metasploit: {stderr}")
                return f"Error: {stderr}"
            logger.info("[+] Metasploit ejecutado con éxito.")
            return stdout if stdout else "No output"
        except subprocess.TimeoutExpired:
            logger.error(f"[!] Timeout ({timeout}s) al ejecutar Metasploit.")
            print(f"[-] Timeout tras {timeout}s")
            return "Timeout"
        except Exception as e:
            logger.error(f"[!] Error en Metasploit: {e}")
            print(f"[-] Error: {e}")
            return f"Error: {e}"


class NiktoAgent(Toolkit):
    def __init__(self):
        super().__init__(name="NiktoAgent")
        self.register(self.run)

    def run(self, **kwargs) -> str:
        """Ejecuta Nikto y recoge los resultados."""
        target = kwargs.get('target', 'localhost')
        timeout = kwargs.get('timeout', 120)
        logger.info(f"[+] Ejecutando Nikto en {target}...")
        command = ["nikto", "-h", target]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
            if result.returncode != 0:
                logger.error(f"[!] Error al ejecutar Nikto: {result.stderr}")
                return f"Error: {result.stderr}"
            logger.info("[+] Nikto ejecutado con éxito.")
            return result.stdout if result.stdout else "No output"
        except subprocess.TimeoutExpired:
            logger.error(f"[!] Timeout ({timeout}s) al ejecutar Nikto.")
            return "Timeout"
        except Exception as e:
            logger.error(f"[!] Error en Nikto: {e}")
            return f"Error: {e}"


class HydraAgent(Toolkit):
    def __init__(self):
        super().__init__(name="HydraAgent")
        self.register(self.run)

    def run(self, **kwargs) -> str:
        """Ejecuta Hydra para pruebas de fuerza bruta."""
        target = kwargs.get('target', 'localhost')
        username = kwargs.get('username', 'admin')
        password_file = kwargs.get('password_file', "/usr/share/wordlists/rockyou.txt")
        service = kwargs.get('service', 'ssh')
        timeout = kwargs.get('timeout', 120)
        if not os.path.exists(password_file):
            logger.error(f"[!] Archivo de contraseñas {password_file} no encontrado.")
            return "Error: Password file not found"
        logger.info(f"[+] Ejecutando Hydra en {target} ({service})...")
        command = ["hydra", "-l", username, "-P", password_file, f"{service}://{target}"]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
            if result.returncode != 0:
                logger.error(f"[!] Error en Hydra: {result.stderr}")
                return f"Error: {result.stderr}"
            logger.info("[+] Hydra ejecutado con éxito.")
            return result.stdout if result.stdout else "No output"
        except subprocess.TimeoutExpired:
            logger.error(f"[!] Timeout ({timeout}s) al ejecutar Hydra.")
            return "Timeout"
        except Exception as e:
            logger.error(f"[!] Error en Hydra: {e}")
            return f"Error: {e}"


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
    print(f"Metasploit Result: {metasploit_result}")

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
