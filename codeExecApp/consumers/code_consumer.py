import json
import asyncio
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from executor.utils import run_code_sandboxed

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class CodeConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        logger.debug("WebSocket connection attempt")
        try:
            await self.accept()
            logger.debug("WebSocket connected")
        except Exception as e:
            logger.error(f"WebSocket connection failed: {str(e)}")
            await self.close()

    async def disconnect(self, close_code):
        logger.debug(f"WebSocket disconnected with code: {close_code}")
        # Clean up any running processes
        if hasattr(self, 'processes'):
            for process_id, process in self.processes.items():
                if process and process.poll() is None:
                    process.terminate()
                    logger.debug(f"Terminated process {process_id}")

    async def receive(self, text_data):
        logger.debug(f"Received data: {text_data}")
        try:
            data = json.loads(text_data)
            action = data.get("action")

            if action == "run":
                code = data.get("code")
                language = data.get("language")
                stdin = data.get("stdin", "")
                self.processes = self.processes if hasattr(self, 'processes') else {}

                async for output in run_code_sandboxed(code, language, stdin):
                    process_id = output.get("process_id")
                    if process_id and process_id not in self.processes:
                        self.processes[process_id] = output.get("process")
                    logger.debug(f"Sending output: {output}")
                    await self.send(text_data=json.dumps(output))
                    if output.get("prompt"):
                        input_data = await self.receive_json()
                        logger.debug(f"Received input: {input_data}")
                        if input_data.get("action") == "input":
                            process = self.processes.get(process_id)
                            if process:
                                process.next_stdin = input_data.get("stdin", "")
                            else:
                                await self.send(text_data=json.dumps({
                                    "error": "No active process found",
                                    "process_id": process_id
                                }))
            elif action == "input":
                process_id = data.get("process_id")
                process = self.processes.get(process_id) if hasattr(self, 'processes') else None
                if process:
                    process.next_stdin = data.get("stdin", "")
                else:
                    await self.send(text_data=json.dumps({
                        "error": "No active process found",
                        "process_id": process_id
                    }))
            else:
                await self.send(text_data=json.dumps({"error": "Invalid action"}))
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {str(e)}")
            await self.send(text_data=json.dumps({"error": f"Invalid JSON: {str(e)}"}))
        except Exception as e:
            logger.error(f"WebSocket error: {str(e)}")
            await self.send(text_data=json.dumps({"error": f"WebSocket error: {str(e)}"}))

    async def receive_json(self):
        text_data = await self.receive()
        return json.loads(text_data)