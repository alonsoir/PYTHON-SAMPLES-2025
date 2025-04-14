import json
import subprocess
import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_searchsploit_mapping(output_file="/results/exploit_mapping.json"):
    """Genera un mapeo de exploits de searchsploit basado en palabras clave."""
    try:
        logger.debug("Ejecutando searchsploit para generar mapeo...")
        result = subprocess.run(
            ["searchsploit", "-j", "--exclude=dos"],
            capture_output=True,
            text=True,
            check=True
        )
        exploits = json.loads(result.stdout).get("RESULTS_EXPLOIT", [])
        logger.info(f"Encontrados {len(exploits)} exploits en searchsploit")

        # Mapeo simple: palabra clave -> EDB-ID
        mapping = {}
        for exploit in exploits:
            title = exploit.get("Title", "").lower()
            edb_id = exploit.get("EDB-ID", "unknown")
            # Extraer palabras clave comunes
            keywords = title.split()
            for keyword in keywords:
                if keyword in mapping:
                    mapping[keyword].append(edb_id)
                else:
                    mapping[keyword] = [edb_id]

        # Guardar el mapeo
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, "w") as f:
            json.dump(mapping, f, indent=2)
        logger.info(f"Mapeo guardado en {output_file}")
    except Exception as e:
        logger.error(f"Error al generar mapeo de searchsploit: {e}")

if __name__ == "__main__":
    generate_searchsploit_mapping()