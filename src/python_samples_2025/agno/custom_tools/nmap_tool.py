import logging
import subprocess
import os
import json
from agno.tools.toolkit import Toolkit
from agno.utils.log import logger

logger.setLevel(logging.DEBUG)
results_dir = "/results"
os.makedirs(results_dir, exist_ok=True)
log_file = "/results/combined.log"
file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s [%(name)s] %(levelname)s: %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

class NmapAgent(Toolkit):
    def __init__(self):
        super().__init__(name="NmapAgent")
        self.register(self.run)
        self.results_dir = "/results"
        os.makedirs(self.results_dir, exist_ok=True)

    def run(self, target: str, ports: str) -> dict:
        output_xml = os.path.join(self.results_dir, "nmap_output.xml")
        json_file = os.path.join(self.results_dir, "nmap_result.json")
        nmap_to_json_xsl = "/usr/local/share/nmap_to_json.xsl"

        try:
            logger.info(f"[+] Ejecutando Nmap en {target} puertos {ports} con detección de vulnerabilidades y OS...")
            command = [
                "nmap", "-sV", "--script", "vuln", "-O",  # Añadir -O para detección de OS
                "-p", ports, target,
                "-oX", output_xml
            ]
            logger.debug(f" [+] Command: {' '.join(command)}")
            process = subprocess.run(command, capture_output=True, text=True, check=True)

            logger.debug(f" [+] Return code: {process.returncode}")
            logger.debug(f" [+] Stdout: {process.stdout}")
            logger.debug(f" [+] Stderr: {process.stderr}")

            if not os.path.exists(output_xml):
                logger.error(f"[!] No se generó {output_xml}")
                return {"error": "No se generó el archivo XML de Nmap"}

            # Convertir XML a JSON
            xsltproc_command = ["xsltproc", nmap_to_json_xsl, output_xml]
            result = subprocess.run(xsltproc_command, capture_output=True, text=True)
            if result.returncode != 0:
                logger.error(f"[!] Error al convertir XML a JSON: {result.stderr}")
                return {"error": f"Error al convertir XML a JSON: {result.stderr}"}

            nmap_json = result.stdout
            try:
                nmap_data = json.loads(nmap_json)
            except json.JSONDecodeError as e:
                logger.error(f"[!] Error al parsear JSON de Nmap: {e}")
                return {"error": f"Error al parsear JSON: {e}"}

            # Extraer OS del resultado de Nmap
            os_info = None
            for host in nmap_data.get("nmaprun", {}).get("host", []):
                os_section = host.get("os", {})
                os_matches = os_section.get("osmatch", [])
                if os_matches:
                    os_info = os_matches[0].get("name", "unknown").lower()
                    break

            # Estructurar el resultado
            result_dict = {
                "target": {
                    "ip": target,
                    "port": ports,
                    "service": nmap_data.get("service", "unknown"),
                    "version": nmap_data.get("version", "unknown"),
                    "os": os_info or "unknown"  # Añadir OS
                },
                "tools": {
                    "nikto": [f"{target} {ports}"],
                    "hydra": [f"{target} {ports} {nmap_data.get('service', 'unknown')}"],
                    "metasploit": nmap_data.get("metasploit", {})
                }
            }

            with open(json_file, "w") as f:
                json.dump(result_dict, f, indent=2)
            logger.info(f"[+] JSON generado en {json_file}")

            return result_dict

        except subprocess.CalledProcessError as e:
            logger.error(f"[!] Error ejecutando Nmap: {e.stderr}")
            return {"error": f"Error ejecutando Nmap: {e.stderr}"}
        except Exception as e:
            logger.error(f"[!] Error inesperado en Nmap: {e}")
            return {"error": f"Error inesperado: {e}"}


if __name__ == "__main__":
    agent = NmapAgent()
    result = agent.run(target="172.18.0.2", ports="80")
    print(json.dumps(result, indent=2))