import json
import os
import subprocess
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

class HydraAgent(Toolkit):
    def __init__(self):
        super().__init__(name="HydraAgent")
        self.register(self.run)

    def run(self, **kwargs) -> Dict[str, Dict[str, str]]:
        """Ejecuta Hydra para fuerza bruta usando objetivos del JSON."""
        json_file = kwargs.get('json_file', os.path.join(results_dir, 'nmap_result.json'))
        username = kwargs.get('username', 'admin')
        password_file = kwargs.get('password_file', "/usr/share/wordlists/rockyou.txt")
        login_path = kwargs.get('login_path', '/login.php')  # Configurable
        timeout = kwargs.get('timeout', 300)

        if not os.path.exists(password_file):
            logger.error(f"[!] Archivo de contraseñas {password_file} no encontrado")
            return {"error": f"Archivo de contraseñas {password_file} no encontrado"}

        try:
            with open(json_file, 'r') as f:
                nmap_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"[!] Error al leer {json_file}: {e}")
            return {"error": str(e)}

        hydra_targets: List[str] = nmap_data.get("tools", {}).get("hydra", [])
        if not hydra_targets:
            logger.warning("[!] No se encontraron objetivos para Hydra en el JSON")
            return {"warning": "No se encontraron objetivos para Hydra"}

        results = {}
        for target_entry in hydra_targets:
            try:
                ip, port, service = target_entry.split(" ", 2)
                logger.info(f"[+] Ejecutando Hydra en {ip}:{port} ({service})...")

                output_file = f"{results_dir}/hydra_{ip}_{port}.txt"
                if service == "http":
                    command = [
                        "/usr/bin/hydra",
                        "-l", username,
                        "-P", password_file,
                        "-o", output_file,
                        ip,
                        "http-post-form",
                        f"{login_path}:username=^USER^&password=^PASS^:Login failed"
                    ]
                    if port != "80":
                        command.extend(["-s", port])
                else:
                    command = [
                        "/usr/bin/hydra",
                        "-l", username,
                        "-P", password_file,
                        "-o", output_file,
                        f"{service}://{ip}"
                    ]
                    if port != ( "22" if service == "ssh" else "80" ):
                        command.extend(["-s", port])

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
                logger.debug(f" [+] Stdout: {stdout[:2000]}..." if stdout else " [+] Stdout: (vacío)")
                logger.debug(f" [+] Stderr: {stderr[:2000]}..." if stderr else " [+] Stderr: (vacío)")

                if os.path.exists(output_file):
                    with open(output_file, 'r') as f:
                        output = f.read()
                    credentials = [line.strip() for line in output.splitlines() if "password:" in line]
                    logger.info(f"[+] Hydra en {target_entry}: {len(credentials)} credenciales encontradas")
                    results[target_entry] = {"output": output, "credentials": credentials}
                else:
                    error_msg = stderr or "Error desconocido"
                    logger.error(f"[!] Error en Hydra para {target_entry}: {error_msg}")
                    results[target_entry] = {"error": error_msg}

            except subprocess.TimeoutExpired:
                logger.error(f"[!] Timeout ({timeout}s) en {target_entry}")
                process.kill()
                results[target_entry] = {"error": f"Timeout: {process.communicate()[1] or 'sin detalles'}"}
            except ValueError:
                logger.error(f"[!] Formato inválido en {target_entry}")
                results[target_entry] = {"error": "Formato inválido"}
            except Exception as e:
                logger.error(f"[!] Error en Hydra para {target_entry}: {e}")
                results[target_entry] = {"error": str(e)}

        return results

if __name__ == "__main__":
    agent = HydraAgent()
    result = agent.run()
    print(json.dumps(result, indent=2))