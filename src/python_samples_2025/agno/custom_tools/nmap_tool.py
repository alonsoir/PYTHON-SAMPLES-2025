import json
import subprocess
from textwrap import dedent

from agno.tools.toolkit import Toolkit
from agno.utils.log import logger

from custom_agents.ollama_agent import OllamaAgent


class NmapAgent(Toolkit):
    def __init__(self):
        super().__init__(name="NmapAgent")
        self.register(self.run)
        self.ollama_agent = OllamaAgent(
            model="llama3.2:1b",
            description="Helper agent to parse Nmap output with vulnerability scanning",
            instructions=dedent("""\
                You are an expert in parsing Nmap output for an authorized penetration test.
                Given a fragment of Nmap output, parse it into a compact format:
                - Host: ip|hostname|mac
                - Ports: port,state,service,version
                - Vulnerabilities: cve,score,url
                Separate entries with semicolons (;). Return ONLY the parsed data in this exact format. 
                Do NOT include explanations, narratives, or any extra text beyond the specified format.
            """)
        )

    def run(self, **kwargs) -> dict:
        target = kwargs.get("target", "localhost")
        ports = kwargs.get("ports", None)
        scan_open_ports = kwargs.get("scan_open_ports", False)

        print(f"[DEBUG] Target: {target}, Ports: {ports}, Scan_open_ports: {scan_open_ports}")

        if not ports or scan_open_ports:
            command = f"nmap -F {target}"
            try:
                process = subprocess.run(command.split(), capture_output=True, text=True, check=True)
                stdout = process.stdout
                logger.info("[+] Open ports scan executed successfully.")
                ports = self._extract_open_ports(stdout)
                if not ports:
                    return {"error": "No open ports detected"}
            except subprocess.CalledProcessError as e:
                logger.error(f"[!] Open ports scan failed: {e.stderr}")
                return {"error": f"Open ports scan failed: {e.stderr}"}

        command = f"nmap -sV --script vuln -p {ports} {target}"
        logger.info(f"[+] Running: {command}")

        try:
            process = subprocess.run(command.split(), capture_output=True, text=True, check=True)
            stdout = process.stdout
            logger.info("[+] Nmap executed successfully.")
            logger.debug(f"[DEBUG] Nmap stdout length: {len(stdout)}")

            fragments = self._split_output(stdout)
            logger.info(f"[DEBUG] Split into {len(fragments)} fragments")

            nikto_inputs = []
            hydra_inputs = []
            metasploit_inputs = []

            for i, fragment in enumerate(fragments):
                prompt = f"""[INST] Parse this Nmap output fragment into a compact format:
                - Host: ip|hostname|mac
                - Ports: port,state,service,version
                - Vulnerabilities: cve,score,url
                Separate entries with semicolons (;). Return only the parsed data, no extra text.
                Fragment:
                \n{fragment}"""
                logger.info(f"[DEBUG] Sending fragment {i+1}/{len(fragments)} to Ollama (length: {len(prompt)})")
                result = self.ollama_agent.run(prompt)
                logger.info(f"[DEBUG] Ollama raw response for fragment {i+1}: {result}")

                try:
                    for line in result.split(";"):
                        if not line.strip():
                            continue
                        parts = line.split("|")
                        if len(parts) == 3:  # Host
                            ip, hostname, mac = parts
                        elif len(parts) == 1:  # Ports o Vulnerabilities (split por comas)
                            subparts = parts[0].split(",")
                            if len(subparts) == 4:  # Port
                                port, state, service, version = subparts
                                if service in ["http", "https"]:
                                    nikto_inputs.append(f"{ip} {port}")
                                    hydra_inputs.append(f"{ip} {port} {service}")
                                elif service in ["ssh", "ftp", "telnet"]:
                                    hydra_inputs.append(f"{ip} {port} {service}")
                                metasploit_inputs.append(f"{ip} {port}")
                            elif len(subparts) == 3:  # Vulnerability
                                cve, score, url = subparts
                                metasploit_inputs.append(f"{ip} {port} {cve}")
                except Exception as e:
                    logger.error(f"[!] Failed to parse fragment {i+1}: {str(e)} - Raw: {result}")
                    continue

            result = {
                "nikto": list(set(nikto_inputs)),
                "hydra": list(set(hydra_inputs)),
                "metasploit": list(set(metasploit_inputs))
            }
            logger.info(f"[DEBUG] Final result: {json.dumps(result, indent=2)}")
            return result

        except subprocess.CalledProcessError as e:
            logger.error(f"[!] Nmap failed: {e.stderr}")
            return {"error": f"Nmap failed: {e.stderr}"}
        except Exception as e:
            logger.error(f"[!] Error in NmapAgent: {str(e)}")
            return {"error": f"Error in NmapAgent: {str(e)}"}

    def _extract_open_ports(self, nmap_output: str) -> str:
        open_ports = []
        for line in nmap_output.splitlines():
            if "/tcp" in line and "open" in line:
                port = line.split("/")[0].strip()
                open_ports.append(port)
        return ",".join(open_ports) if open_ports else "80"

    def _split_output(self, output: str) -> list[str]:
        """Divide el output de Nmap por bloques de puertos y vulnerabilidades."""
        lines = output.splitlines()
        fragments = []
        current_fragment = []
        in_port_section = False

        for line in lines:
            if "/tcp" in line and "open" in line:  # Inicio de un puerto
                if current_fragment and in_port_section:
                    fragments.append("\n".join(current_fragment))
                    current_fragment = []
                current_fragment.append(line)
                in_port_section = True
            elif in_port_section and line.strip() == "":  # Fin de sección de puerto
                fragments.append("\n".join(current_fragment))
                current_fragment = []
                in_port_section = False
            elif in_port_section:
                current_fragment.append(line)
            else:
                current_fragment.append(line)  # Encabezado o pie del output

        if current_fragment:
            fragments.append("\n".join(current_fragment))
        return fragments