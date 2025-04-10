import json
import os
import socket
import subprocess
import requests
from typing import Dict, List
from datetime import datetime

from agno.tools.toolkit import Toolkit
from agno.utils.log import logger

import logging

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

    def run(self, ip: str, port: str, service: str) -> List[Dict[str, str]]:
        cmd = ["searchsploit", "-j", service, f"port {port}"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        exploits = json.loads(result.stdout).get("RESULTS_EXPLOIT", [])
        mapped_exploits = self.map_to_metasploit(exploits)
        return mapped_exploits

    def map_to_metasploit(self, exploits: List[Dict]) -> List[Dict[str, str]]:
        mapping = {
            "apache 2.4": "multi/http/apache_mod_cgi_bash_env_exec",
            "php": "multi/http/php_cgi_arg_injection"
        }
        return [{"exploit": mapping.get(e["Title"].lower(), "unknown"), "title": e["Title"]} for e in exploits[:3]]