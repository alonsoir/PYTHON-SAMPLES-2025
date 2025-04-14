import json
import os
import subprocess
from typing import Dict, List
from datetime import datetime

from agno.tools.toolkit import Toolkit
from agno.utils.log import logger

import logging

# Configuración de logging
logger.setLevel(logging.DEBUG)
results_dir = "/results"
os.makedirs(results_dir, exist_ok=True)
log_file = "/results/combined.log"
file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s [%(name)s] %(levelname)s: %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)


class SearchsploitAgent(Toolkit):
    def __init__(self):
        super().__init__(name="SearchsploitAgent")
        self.register(self.run)
        self.results_dir = "/results"
        self.exploit_mapping = self.load_exploit_mapping()

    def load_exploit_mapping(self) -> Dict[str, str]:
        """Carga el mapeo de exploits desde el archivo JSON."""
        mapping_file = "/results/exploit_mapping.json"
        try:
            if not os.path.exists(mapping_file):
                logger.warning(f"No se encontró el archivo de mapeo {mapping_file}, usando mapeo vacío")
                return {}

            with open(mapping_file, "r") as f:
                mapping = json.load(f)
            logger.info(f"Cargados {len(mapping)} mapeos desde {mapping_file}")
            return mapping
        except Exception as e:
            logger.error(f"Error al cargar el mapeo desde {mapping_file}: {e}")
            return {}

    def run(self, **kwargs) -> List[Dict[str, str]]:
        json_file = kwargs.get('json_file', '/results/nmap_result.json')
        if not os.path.exists(json_file):
            logger.error(f"No se encontró {json_file}")
            return [{"error": f"No se encontró {json_file}"}]
        try:
            with open(json_file, 'r') as f:
                nmap_data = json.load(f)
        except json.JSONDecodeError:
            logger.error(f"Error al decodificar {json_file}")
            return [{"error": f"Error al decodificar {json_file}"}]
        target_data = nmap_data.get("target", {})
        ip = target_data.get("ip")
        port = target_data.get("port")
        service = target_data.get("service")
        os_info = target_data.get("os", "unknown")
        if not all([ip, port, service]):
            logger.warning("Datos incompletos en 'target' para Searchsploit")
            return [{"warning": "Datos incompletos en 'target' para Searchsploit"}]
        logger.info(f"Buscando exploits para {ip}:{port} ({service}, OS: {os_info}) con searchsploit...")
        try:
            # Ajustar la consulta para incluir OS
            query = [service]
            if "linux" in os_info.lower():
                query.append("linux")
            elif "windows" in os_info.lower():
                query.append("windows")
            cmd = ["searchsploit", "-j"] + query + [f"port {port}"]
            logger.debug(f"Ejecutando comando: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                logger.error(f"Error al ejecutar searchsploit: {result.stderr}")
                return [{"error": f"Error al ejecutar searchsploit: {result.stderr}"}]
            exploits = json.loads(result.stdout).get("RESULTS_EXPLOIT", [])
            if not exploits:
                logger.warning(f"No se encontraron exploits para {service} en el puerto {port}")
                return [{"warning": f"No se encontraron exploits para {service} en el puerto {port}"}]
            mapped_exploits = self.map_to_metasploit(exploits, ip, port, service, os_info)
            logger.info(f"Encontrados {len(mapped_exploits)} exploits potenciales para {ip}:{port}")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"{self.results_dir}/searchsploit_{ip}_{port}_{timestamp}.json"
            with open(output_path, "w") as f:
                json.dump(mapped_exploits, f, indent=2)
            logger.info(f"Resultados de searchsploit guardados en {output_path}")
            return mapped_exploits
        except Exception as e:
            logger.error(f"Error al ejecutar searchsploit: {e}")
            return [{"error": f"Error al ejecutar searchsploit: {e}"}]

    def validate_metasploit_module(self, module_name: str) -> bool:
        """Valida si un módulo de Metasploit existe ejecutando un comando de msfconsole."""
        if os.getenv("ENABLE_METASPLOIT", "true") == "false":
            logger.info(f"Validación de Metasploit desactivada, marcando '{module_name}' como no válido")
            return False
        try:
            temp_script = f"/tmp/validate_module_{datetime.now().strftime('%Y%m%d_%H%M%S')}.rc"
            with open(temp_script, "w") as f:
                f.write(f"use {module_name}\nexit\n")
            command = ["/usr/bin/msfconsole", "-q", "-r", temp_script]
            process = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
            os.remove(temp_script)
            if "Invalid module" in process.stderr or process.returncode != 0:
                logger.warning(f"El módulo de Metasploit '{module_name}' no existe o no es válido")
                return False
            logger.debug(f"El módulo de Metasploit '{module_name}' es válido")
            return True
        except Exception as e:
            logger.error(f"Error al validar el módulo de Metasploit '{module_name}': {e}")
            return False

    def map_to_metasploit(self, exploits: List[Dict], ip: str, port: str, service: str, os_info: str) -> List[
        Dict[str, str]]:
        mapped_exploits = []
        for exploit in exploits[:3]:
            title = exploit.get("Title", "").lower()
            exploit_id = exploit.get("EDB-ID", "unknown")
            exploit_path = exploit.get("Path", "unknown")

            # Buscar en el mapeo de searchsploit
            matched_exploit = None
            for key, edb_ids in self.exploit_mapping.items():
                if key in title and exploit_id in edb_ids:
                    matched_exploit = f"searchsploit:{exploit_id}"
                    break

            if not matched_exploit:
                matched_exploit = "unknown"
                logger.warning(f"No se encontró un mapeo para el exploit '{title}' (EDB-ID: {exploit_id})")
                logger.info(f"Sugerencia: Revisa el exploit manualmente en '{exploit_path}'")

            mapped_exploits.append({
                "exploit": matched_exploit,
                "title": title,
                "edb_id": exploit_id,
                "path": exploit_path,
                "ip": ip,
                "port": port,
                "service": service,
                "os": os_info,
                "recommendation": ("Revisa el exploit manualmente" if matched_exploit == "unknown" else "")
            })
            logger.debug(f"Mapeado exploit '{title}' (EDB-ID: {exploit_id}) a: {matched_exploit}")
        return mapped_exploits