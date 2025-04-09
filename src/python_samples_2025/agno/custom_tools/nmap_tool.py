import subprocess
import os
from typing import Dict
from agno.tools.toolkit import Toolkit
from agno.utils.log import logger

import logging
logger.setLevel(logging.DEBUG)
# Crear directorio /results si no existe
results_dir = "/results"
os.makedirs(results_dir, exist_ok=True)  # Asegura que el directorio esté listo
# Configurar logging
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

    def run(self, **kwargs) -> Dict[str, str]:
        target = kwargs.get('target', '172.18.0.2')
        ports = str(kwargs.get('ports', '80'))  # Convertir a cadena aquí
        xml_output = f"{self.results_dir}/nmap_output.xml"
        json_output = f"{self.results_dir}/nmap_result.json"
        xsl_file = "/usr/local/share/nmap_to_json.xsl"

        if not os.path.exists(self.results_dir):
            os.makedirs(self.results_dir)

        # Ejecutar Nmap con detección de vulnerabilidades
        command = ["nmap", "-sV", "--script", "vuln", "-p", ports, target, "-oX", xml_output]
        logger.info(f"[+] Ejecutando Nmap en {target} puertos {ports} con detección de vulnerabilidades...")
        logger.debug(f" [+] Command: {' '.join(command)}")

        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = process.communicate(timeout=600)

            logger.debug(f" [+] Return code: {process.returncode}")
            logger.debug(f" [+] Stdout: {stdout[:4096]}..." if stdout else " [+] Stdout: (vacío)")
            logger.debug(f" [+] Stderr: {stderr[:4096]}..." if stderr else " [+] Stderr: (vacío)")

            if process.returncode != 0 or not os.path.exists(xml_output):
                raise Exception(f"Nmap falló: {stderr}")

            # Convertir XML a JSON
            xslt_command = ["xsltproc", xsl_file, xml_output]
            with open(json_output, "w") as f:
                process = subprocess.Popen(xslt_command, stdout=f, stderr=subprocess.PIPE, text=True)
                _, stderr = process.communicate(timeout=30)

            if process.returncode != 0:
                raise Exception(f"XSLT falló: {stderr}")

            logger.info(f"[+] JSON generado en {json_output}")
            with open(json_output, "r") as f:
                return {"result": f.read()}

        except subprocess.TimeoutExpired as e:
            logger.error(f"[!] Timeout (600s) al ejecutar Nmap en {target}")
            process.kill()
            stdout, stderr = process.communicate()
            raise Exception(f"Timeout: {stderr if stderr else 'sin detalles'}")
        except Exception as e:
            logger.error(f"[!] Error en NmapAgent: {e}")
            return {"error": str(e)}


if __name__ == "__main__":
    agent = NmapAgent()
    result = agent.run()
    print(result.get("result", result.get("error")))