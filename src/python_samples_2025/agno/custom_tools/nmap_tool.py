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
            description="Helper agent to parse Nmap output with vulnerability scanning for ethical penetration testing",
            instructions=dedent("""\
                You are an expert in parsing Nmap output for an authorized penetration test. 
                The system owner has given explicit permission for this analysis to identify vulnerabilities and improve security. 
                Given the raw output of an Nmap command with the `--script vuln` option, parse the output and extract the following information in JSON format:
                - "host": {"ip": "", "hostname": "", "mac": ""}
                - "ports": [{"port": 0, "state": "", "service": "", "version": ""}]
                - "vulnerabilities": [{"cve": "", "score": 0.0, "url": ""}]
                If the output contains errors or no relevant data, return a JSON with an "error" key describing the issue.
                Do not invent data; base your parsing only on the provided Nmap output.
                Return only valid JSON, no extra text or explanations.
            """)
        )

    def run(self, **kwargs) -> dict:
        target = kwargs.get("target", "localhost")
        ports = kwargs.get("ports", None)
        scan_open_ports = kwargs.get("scan_open_ports", False)

        print(f"[DEBUG] Target: {target}, Ports: {ports}, Scan_open_ports: {scan_open_ports}")

        if not ports or scan_open_ports:
            print(f"\n[+] Scanning for open ports on {target}")
            command = f"nmap -F {target}"
            try:
                process = subprocess.run(
                    command.split(),
                    capture_output=True,
                    text=True,
                    check=True
                )
                stdout = process.stdout
                logger.info("[+] Open ports scan executed successfully.")
                ports = self._extract_open_ports(stdout)
                if not ports:
                    return {"error": "No open ports detected"}
            except subprocess.CalledProcessError as e:
                logger.error(f"[!] Open ports scan failed: {e.stderr}")
                return {"error": f"Open ports scan failed: {e.stderr}"}

        # Vulnerability scan
        command = f"nmap -sV --script vuln -p {ports} {target}"
        logger.info(f"[+] Running: {command}")

        try:
            process = subprocess.run(
                command.split(),
                capture_output=True,
                text=True,
                check=True
            )
            stdout = process.stdout
            logger.info("[+] Nmap executed successfully.")
            logger.debug(f"[DEBUG] Nmap stdout length: {len(stdout)}")

            # Prepare prompt
            prompt = f"""[INST] Parse the following Nmap output into a JSON object with this exact structure:
            {{
                "host": {{"ip": "", "hostname": "", "mac": ""}},
                "ports": [{{"port": 0, "state": "", "service": "", "version": ""}}],
                "vulnerabilities": [{{"cve": "", "score": 0.0, "url": ""}}]
            }}
            Return only valid JSON, no extra text. Here’s the Nmap output:
            \n{stdout}"""
            prompt_length = len(prompt)
            logger.info(f"[DEBUG] Sending prompt to Ollama (length: {prompt_length})")
            if prompt_length > 8000:  # Warn if near context limit
                logger.warning("[!] Prompt length exceeds 8000 chars, may truncate.")

            # Call Ollama
            result = self.ollama_agent.run(prompt)
            logger.info(f"[DEBUG] Ollama raw response: {result}")

            # Parse result
            try:
                parsed_result = json.loads(result)
                logger.info(f"[DEBUG] Parsed JSON: {json.dumps(parsed_result, indent=2)}")
                return parsed_result
            except json.JSONDecodeError as e:
                logger.error(f"[!] Failed to parse LLM response: {str(e)} - Raw: {result}")
                return {"error": f"Failed to parse LLM response: {str(e)}"}

        except subprocess.CalledProcessError as e:
            logger.error(f"[!] Nmap failed: {e.stderr}")
            print(f"[-] Error: {e.stderr}")
            return {"error": f"Nmap failed: {e.stderr}"}
        except Exception as e:
            logger.error(f"[!] Error in NmapAgent: {str(e)}")
            print(f"[DEBUG] Exception: {str(e)}")
            return {"error": f"Error in NmapAgent: {str(e)}"}

    def _extract_open_ports(self, nmap_output: str) -> str:
        """Extract open ports from Nmap output as a comma-separated string."""
        open_ports = []
        for line in nmap_output.splitlines():
            if "/tcp" in line and "open" in line:
                port = line.split("/")[0].strip()
                open_ports.append(port)
        return ",".join(open_ports) if open_ports else "80"