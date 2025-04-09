import json
import subprocess
import os
from typing import Dict, List

from agno.tools.toolkit import Toolkit
from agno.utils.log import logger

# Configuración de logging
import logging
logger.setLevel(logging.DEBUG)
results_dir = "/results"
os.makedirs(results_dir, exist_ok=True)
log_file = os.path.join(results_dir, "combined.log")
file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s [%(name)s] %(levelname)s: %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

class NiktoAgent(Toolkit):
    def __init__(self):
        super().__init__(name="NiktoAgent")
        self.register(self.run)

    def run(self, **kwargs) -> Dict[str, Dict[str, str]]:
        """Ejecuta Nikto para cada objetivo en el archivo JSON y recoge resultados parseados."""
        json_file = kwargs.get('json_file', os.path.join(results_dir, 'nmap_result.json'))
        timeout = kwargs.get('timeout', 300)

        # Leer el archivo JSON
        try:
            with open(json_file, 'r') as f:
                nmap_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"[!] Error al leer {json_file}: {e}")
            return {"error": str(e)}

        nikto_targets: List[str] = nmap_data.get("tools", {}).get("nikto", [])
        if not nikto_targets:
            logger.warning("[!] No se encontraron objetivos para Nikto en el JSON")
            return {"warning": "No se encontraron objetivos para Nikto"}

        results = {}
        for target in nikto_targets:
            try:
                ip, port = target.split(" ", 1) if " " in target else (target, "80")
                logger.info(f"[+] Ejecutando Nikto en {ip}:{port}...")

                command = ["/usr/bin/nikto", "-h", ip, "-p", port, "-output", f"{results_dir}/nikto_{ip}_{port}.txt"]
                logger.debug(f" [+] Command: {' '.join(command)}")

                process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    env={"PATH": "/usr/bin:/bin:/usr/local/bin"}
                )
                stdout, stderr = process.communicate(timeout=timeout)

                logger.debug(f" [+] Return code: {process.returncode}")
                logger.debug(f" [+] Stdout: {stdout[:500]}..." if stdout else " [+] Stdout: (vacío)")
                logger.debug(f" [+] Stderr: {stderr[:500]}..." if stderr else " [+] Stderr: (vacío)")

                output_file = f"{results_dir}/nikto_{ip}_{port}.txt"
                if os.path.exists(output_file) and "Nikto" in stdout:
                    with open(output_file, 'r') as f:
                        output = f.read()
                    findings = [line for line in output.splitlines() if line.startswith("+ ")]
                    logger.info(f"[+] Nikto ejecutado en {ip}:{port}. Hallazgos: {len(findings)}")
                    results[target] = {"output": output, "findings": findings}
                else:
                    error_msg = stderr or "Error desconocido"
                    logger.error(f"[!] Error en Nikto para {ip}:{port}: {error_msg}")
                    results[target] = {"error": error_msg}

            except subprocess.TimeoutExpired:
                logger.error(f"[!] Timeout ({timeout}s) en {target}")
                process.kill()
                results[target] = {"error": f"Timeout: {process.communicate()[1] or 'sin detalles'}"}
            except Exception as e:
                logger.error(f"[!] Error en Nikto para {target}: {e}")
                results[target] = {"error": str(e)}

        return results

if __name__ == "__main__":
    agent = NiktoAgent()
    result = agent.run()
    print(json.dumps(result, indent=2))