import os
import subprocess

from agno.tools.toolkit import Toolkit
from agno.utils.log import logger


class HydraAgent(Toolkit):
    def __init__(self):
        super().__init__(name="HydraAgent")
        self.register(self.run)

    def run(self, **kwargs) -> str:
        """Ejecuta Hydra para pruebas de fuerza bruta."""
        target = kwargs.get('target', 'localhost')
        username = kwargs.get('username', 'admin')
        password_file = kwargs.get('password_file', "/usr/share/wordlists/rockyou.txt")
        service = kwargs.get('service', 'ssh')
        timeout = kwargs.get('timeout', 120)
        if not os.path.exists(password_file):
            logger.error(f"[!] Archivo de contraseñas {password_file} no encontrado.")
            return "Error: Password file not found"
        logger.info(f"[+] Ejecutando Hydra en {target} ({service})...")
        command = ["hydra", "-l", username, "-P", password_file, f"{service}://{target}"]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
            if result.returncode != 0:
                logger.error(f"[!] Error en Hydra: {result.stderr}")
                return f"Error: {result.stderr}"
            logger.info("[+] Hydra ejecutado con éxito.")
            return result.stdout if result.stdout else "No output"
        except subprocess.TimeoutExpired:
            logger.error(f"[!] Timeout ({timeout}s) al ejecutar Hydra.")
            return "Timeout"
        except Exception as e:
            logger.error(f"[!] Error en Hydra: {e}")
            return f"Error: {e}"
