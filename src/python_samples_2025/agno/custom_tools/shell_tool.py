import logging
import os
import subprocess
from typing import List
from agno.tools.toolkit import Toolkit
from agno.utils.log import logger

# Crear directorio /results si no existe
results_dir = "/results"
os.makedirs(results_dir, exist_ok=True)  # Asegura que el directorio esté listo
# Al inicio de cada script, después de importar logging
log_file = "/results/combined.log"
file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s [%(name)s] %(levelname)s: %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

class ShellTools(Toolkit):
    def __init__(self):
        super().__init__(name="shell_tools")
        self.register(self.run_shell_command)

    def run_shell_command(self, args: List[str], tail: int = 100, timeout: int = 60) -> str:
        """Ejecuta un comando en el shell y captura el resultado."""
        # Si args es una lista con una sola cadena, dividirla en argumentos
        if len(args) == 1 and " " in args[0]:
            expanded_args = args[0].split()
        else:
            expanded_args = [os.path.expanduser(arg) if arg == "~" else arg for arg in args]

        logger.info(f"Running shell command: {expanded_args}")
        logger.info(f"Current PATH: {os.environ['PATH']}")  # Depuración del PATH
        try:
            result = subprocess.run(expanded_args, capture_output=True, text=True, timeout=timeout)
            if result.returncode != 0:
                logger.error(f"Command failed: {result.stderr}")
                return f"Error: {result.stderr}"
            logger.debug(f"Command successful: {result.stdout}")
            return "\n".join(result.stdout.split("\n")[-tail:])
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout after {timeout}s running command: {expanded_args}")
            return f"Timeout after {timeout}s"
        except FileNotFoundError as e:
            logger.error(f"Command not found: {e}")
            return f"Error: Command not found - {e}"
        except Exception as e:
            logger.warning(f"Failed to run shell command: {e}")
            return f"Error: {e}"