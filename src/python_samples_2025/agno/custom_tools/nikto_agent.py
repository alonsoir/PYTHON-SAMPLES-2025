import json
import subprocess
import os
from typing import Dict, List

from agno.tools.toolkit import Toolkit
from agno.utils.log import logger

# Forzar nivel de logging a DEBUG
import logging
logger.setLevel(logging.DEBUG)


class NiktoAgent(Toolkit):
    def __init__(self):
        super().__init__(name="NiktoAgent")
        self.register(self.run)

    def run(self, **kwargs) -> Dict[str, str]:
        """Ejecuta Nikto para cada objetivo en el archivo JSON y recoge los resultados."""
        json_file = kwargs.get('json_file', 'nmap_result.json')
        timeout = kwargs.get('timeout', 300)  # Aumentamos a 300 segundos por seguridad

        # Leer el archivo JSON
        try:
            with open(json_file, 'r') as f:
                nmap_data = json.load(f)
        except FileNotFoundError:
            logger.error(f"[!] No se encontró el archivo {json_file}")
            return {"error": f"No se encontró el archivo {json_file}"}
        except json.JSONDecodeError:
            logger.error(f"[!] Error al decodificar el archivo JSON {json_file}")
            return {"error": f"Error al decodificar el archivo JSON {json_file}"}

        nikto_targets: List[str] = nmap_data.get("nikto", [])
        if not nikto_targets:
            logger.warning("[!] No se encontraron objetivos para Nikto en el archivo JSON")
            return {"warning": "No se encontraron objetivos para Nikto"}

        results = {}
        for target in nikto_targets:
            try:
                # Extraer IP y puerto del target (e.g., "172.18.0.2 80")
                parts = target.split(" ")
                ip = parts[0]
                port = parts[1] if len(parts) > 1 else "80"  # Puerto por defecto 80 si no se especifica
                logger.info(f"[+] Ejecutando Nikto en {ip} puerto {port}...")

                # Construir el comando con el puerto
                command = ["/usr/bin/nikto", "-h", ip, "-p", port]
                logger.debug(f" [+] Command: {' '.join(command)}")

                # Usamos Popen sin shell=True para mejor control
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

                # Consideramos éxito si hay salida en stdout, independientemente del returncode
                if stdout and "Nikto" in stdout:  # Verificamos que sea una salida válida de Nikto
                    logger.info(f"[+] Nikto ejecutado con éxito en {ip} puerto {port} (returncode: {process.returncode}).")
                    results[target] = stdout
                else:
                    error_msg = stderr if stderr else "Error desconocido (sin stderr)"
                    logger.error(f"[!] Error al ejecutar Nikto en {ip} puerto {port}: {error_msg}")
                    results[target] = f"Error: {error_msg}"

            except subprocess.TimeoutExpired as e:
                logger.error(f"[!] Timeout ({timeout}s) al ejecutar Nikto en {target}")
                process.kill()
                stdout, stderr = process.communicate()
                results[target] = f"Timeout: {stderr if stderr else 'sin detalles'}"
            except Exception as e:
                logger.error(f"[!] Error inesperado en Nikto para {target}: {e}")
                results[target] = f"Error: {e}"

        return results


if __name__ == "__main__":
    agent = NiktoAgent()
    result = agent.run(json_file="nmap_result.json")
    print(json.dumps(result, indent=2))