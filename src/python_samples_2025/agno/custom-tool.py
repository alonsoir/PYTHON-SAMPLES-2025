from typing import List
from agno.agent.agent import Agent
from agno.models.openai.chat import OpenAIChat
from agno.tools.toolkit import Toolkit
from agno.utils.log import logger
from dotenv import load_dotenv
import os

load_dotenv()

openai_api_key = os.getenv("OPENAI_API_KEY")

class ShellTools(Toolkit):
    def __init__(self):
        super().__init__(name="shell_tools")
        self.register(self.run_shell_command)

    def run_shell_command(self, args: List[str], tail: int = 100) -> str:
        """
        Runs a shell command and returns the output or error.

        Args:
            args (List[str]): The command to run as a list of strings.
            tail (int): The number of lines to return from the output.
        Returns:
            str: The output of the command.
        """
        import subprocess

        # Expandir ~ al directorio home si está presente en los argumentos
        expanded_args = [os.path.expanduser(arg) if arg == "~" else arg for arg in args]
        
        logger.info(f"Running shell command: {expanded_args}")
        try:
            result = subprocess.run(expanded_args, capture_output=True, text=True)
            logger.debug(f"Result: {result}")
            logger.debug(f"Return code: {result.returncode}")
            if result.returncode != 0:
                return f"Error: {result.stderr}"
            # Devolver solo las últimas n líneas de la salida
            return "\n".join(result.stdout.split("\n")[-tail:])
        except Exception as e:
            logger.warning(f"Failed to run shell command: {e}")
            return f"Error: {e}"

agent = Agent(
    model=OpenAIChat(id="gpt-4o", api_key=openai_api_key),
    tools=[ShellTools()],
    show_tool_calls=True,
    markdown=True
)
agent.print_response("List all the files in my home directory.")