import json
import os
import subprocess
from typing import Dict, List

from agno.tools.toolkit import Toolkit
from agno.utils.log import logger

# Forzar nivel de logging a DEBUG
import logging
logger.setLevel(logging.DEBUG)


class HydraAgent(Toolkit):
    def __init__(self):
        super().__init__(name="HydraAgent")
        self.register(self.run)

    def run(self, **kwargs) -> Dict[str, str]:
        """Ejecuta Hydra para pruebas de fuerza bruta usando los objetivos del archivo JSON."""
        json_file = kwargs.get('json_file', 'nmap_result.json')
        username = kwargs.get('username', 'admin')
        password_file = kwargs.get('password_file', "/usr/share/wordlists/rockyou.txt")
        timeout = kwargs.get('timeout', 300)

        if not os.path.exists(password_file):
            logger.error(f"[!] Archivo de contraseñas {password_file} no encontrado.")
            return {"error": f"Archivo de contraseñas {password_file} no encontrado"}

        try:
            with open(json_file, 'r') as f:
                nmap_data = json.load(f)
        except FileNotFoundError:
            logger.error(f"[!] No se encontró el archivo {json_file}")
            return {"error": f"No se encontró el archivo {json_file}"}
        except json.JSONDecodeError:
            logger.error(f"[!] Error al decodificar el archivo JSON {json_file}")
            return {"error": f"Error al decodificar el archivo JSON {json_file}"}

        hydra_targets: List[str] = nmap_data.get("hydra", [])
        if not hydra_targets:
            logger.warning("[!] No se encontraron objetivos para Hydra en el archivo JSON")
            return {"warning": "No se encontraron objetivos para Hydra"}

        results = {}
        for target_entry in hydra_targets:
            try:
                ip, port, service = target_entry.split(" ", 2)
                target = ip
                logger.info(f"[+] Ejecutando Hydra en {target} puerto {port} ({service})...")

                if service == "http":
                    command = [
                        "/usr/bin/hydra",
                        "-l", username,
                        "-P", password_file,
                        target,
                        "http-post-form",
                        "/login.php:username=^USER^&password=^PASS^:Login failed"
                    ]
                    if port != "80":
                        command.extend(["-s", port])
                else:
                    command = ["/usr/bin/hydra", "-l", username, "-P", password_file, f"{service}://{target}"]
                    if port != "22" and service == "ssh":
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
                logger.debug(f" [+] Stdout: {stdout[:2000]}..." if stdout else " [+] Stdout: (vacío)")  # Aumentado a 2000 caracteres
                logger.debug(f" [+] Stderr: {stderr[:2000]}..." if stderr else " [+] Stderr: (vacío)")

                if process.returncode == 0 and stdout and "Hydra" in stdout:
                    passwords = [line.split("password: ")[1] for line in stdout.splitlines() if "password: " in line]
                    if passwords:
                        logger.info(f"[+] Contraseñas encontradas para {target_entry}: {', '.join(passwords)}")
                    else:
                        logger.info(f"[+] Hydra completado en {target_entry}, sin contraseñas encontradas.")
                    results[target_entry] = stdout
                else:
                    error_msg = stderr if stderr else "Error desconocido (sin stderr)"
                    logger.error(f"[!] Error en Hydra para {target_entry}: {error_msg}")
                    results[target_entry] = f"Error: {error_msg}"

            except subprocess.TimeoutExpired as e:
                logger.error(f"[!] Timeout ({timeout}s) al ejecutar Hydra en {target_entry}")
                process.kill()
                stdout, stderr = process.communicate()
                results[target_entry] = f"Timeout: {stderr if stderr else 'sin detalles'}"
            except ValueError:
                logger.error(f"[!] Formato inválido en entrada de Hydra: {target_entry}")
                results[target_entry] = "Error: Formato inválido en entrada"
            except Exception as e:
                logger.error(f"[!] Error inesperado en Hydra para {target_entry}: {e}")
                results[target_entry] = f"Error: {e}"

        return results


if __name__ == "__main__":
    agent = HydraAgent()
    result = agent.run(json_file="nmap_result.json")
    print(json.dumps(result, indent=2))