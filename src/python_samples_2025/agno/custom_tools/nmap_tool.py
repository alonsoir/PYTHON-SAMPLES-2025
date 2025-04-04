import json
import subprocess

from agno.tools.toolkit import Toolkit
from agno.utils.log import logger


class NmapAgent(Toolkit):
    def __init__(self):
        super().__init__(name="NmapAgent")  # Cambié "Nmap Agent" a "NmapAgent" por consistencia con otros nombres
        self.register(self.run)

    def run(self, **kwargs) -> dict:
        target = kwargs.get('target', 'localhost')
        timeout = kwargs.get('timeout', 600)
        # command = ["nmap", "-sV", "--script=vuln", "-oX", "nmap_results.xml", target]
        # por debug
        # command = ["nmap", "-sV", "-oX", "nmap_results.xml", target]
        command = ["nmap", "-sV", "-p", "22,80", "-oX", "nmap_results.xml", target]  # Solo puertos 22 y 80

        print(f"\n[+] Running: {' '.join(command)}")
        try:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            stdout, stderr = process.communicate(timeout=timeout)
            print(stdout)
            if process.returncode != 0:
                print(f"[-] Error: {stderr}")
                logger.error(f"[!] Error running Nmap: {stderr}")
                return {"error": f"Error running Nmap: {stderr}"}
            logger.info("[+] Nmap executed successfully.")
            report = NmapParser.parse_fromfile("nmap_results.xml")
            nmap_data = {
                "hosts": [
                    {
                        "address": host.address,
                        "ports": {
                            str(service.port): {
                                "state": service.state,
                                "service": service.service if service.service else "unknown",
                                "version": getattr(service, "version", None)
                            } for service in host.services
                        }
                    } for host in report.hosts if hasattr(host, 'services') and host.services
                ]
            }
            print(f"[+] Parsed Nmap result:\n{json.dumps(nmap_data, indent=2)}")
            return json.dumps(nmap_data)
        except subprocess.TimeoutExpired:
            logger.error(f"[!] Timeout ({timeout}s) during Nmap execution.")
            print(f"[-] Timeout after {timeout}s")
            return {"error": "Timeout during Nmap execution"}
        except FileNotFoundError as e:
            logger.error(f"[!] Nmap not found: {e}")
            print(f"[-] Error: {e}")
            return {"error": f"Nmap not found - {e}"}
        except Exception as e:
            logger.error(f"[!] Error processing Nmap results: {e}")
            print(f"[-] Error: {e}")
            return {"error": f"Error processing Nmap results: {str(e)}"}