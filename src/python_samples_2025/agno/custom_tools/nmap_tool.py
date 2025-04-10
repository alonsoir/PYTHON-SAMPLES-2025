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
                "nmap", "-sV", "--script", "vuln", "-O",
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

            # Usar directamente los datos del XSL, ajustando solo lo necesario
            result_dict = {
                "target": nmap_data.get("target", {}),  # Conservar todo el target del XSL
                "tools": nmap_data.get("tools", {})     # Conservar todas las herramientas
            }

            # Asegurar que 'target' tenga todos los campos esperados
            result_dict["target"]["ip"] = target
            result_dict["target"]["port"] = ports
            if "os" not in result_dict["target"]:
                result_dict["target"]["os"] = "unknown"

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