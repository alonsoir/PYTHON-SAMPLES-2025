import json
import subprocess
from textwrap import dedent

from agno.tools.toolkit import Toolkit
from agno.utils.log import logger

from custom_agents.ollama_agent import OllamaAgent


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