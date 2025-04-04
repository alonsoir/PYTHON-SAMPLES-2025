import subprocess

from agno.tools.toolkit import Toolkit
from agno.utils.log import logger


class NiktoAgent(Toolkit):
    def __init__(self):
        super().__init__(name="NiktoAgent")
        self.register(self.run)

    def run(self, **kwargs) -> str:
        """Ejecuta Nikto y recoge los resultados."""
        target = kwargs.get('target', 'localhost')
        timeout = kwargs.get('timeout', 120)
        logger.info(f"[+] Ejecutando Nikto en {target}...")
        command = ["nikto", "-h", target]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
            if result.returncode != 0:
                logger.error(f"[!] Error al ejecutar Nikto: {result.stderr}")
                return f"Error: {result.stderr}"
            logger.info("[+] Nikto ejecutado con éxito.")
            return result.stdout if result.stdout else "No output"
        except subprocess.TimeoutExpired:
            logger.error(f"[!] Timeout ({timeout}s) al ejecutar Nikto.")
            return "Timeout"
        except Exception as e:
            logger.error(f"[!] Error en Nikto: {e}")
            return f"Error: {e}"