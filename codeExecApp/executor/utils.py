# import os
# import subprocess
# import tempfile
# import shutil
# import platform

# def run_code_sandboxed(code: str, language: str, stdin: str = "") -> dict:
#     container_image_map = {
#         "python": "python:3",
#         "cpp": "gcc",
#         "javascript": "node",
#         "java": "openjdk",
#     }

#     if language not in container_image_map:
#         return {"error": "Unsupported language"}

#     filename_map = {
#         "python": "script.py",
#         "cpp": "main.cpp",
#         "javascript": "script.js",
#         "java": "Main.java",
#     }

#     run_command_map = {
#         "python": ["python", f"/code/{filename_map[language]}"],
#         "cpp": ["sh", "-c", f"g++ /code/{filename_map[language]} -o /code/a.out && /code/a.out"],
#         "javascript": ["node", f"/code/{filename_map[language]}"],
#         "java": ["sh", "-c", f"javac /code/{filename_map[language]} && java -cp /code Main"],
#     }

#     temp_dir = tempfile.mkdtemp()
#     filename = filename_map[language]
#     filepath = os.path.join(temp_dir, filename)

#     try:
#         with open(filepath, "w", encoding="utf-8") as f:
#             f.write(code)

#         print(f"Received stdin: {repr(stdin)}")

#         docker_flags = ["-i"]

#         cmd = [
#             "docker", "run", "--rm", *docker_flags,
#             "--cpus", "0.5", "--memory", "100m",
#             "-v", f"{temp_dir}:/code",
#             container_image_map[language],
#             *run_command_map[language],
#         ]

#         if platform.system() == "Windows" and os.environ.get("MSYSTEM") in ["MINGW32", "MINGW64"]:
#             cmd = ["winpty"] + cmd

#         print(f"Executing command: {' '.join(cmd)}")

#         result = subprocess.run(
#             cmd,
#             input=stdin + "\n" if stdin else "\n",
#             capture_output=True,
#             text=True,
#             encoding="utf-8",
#             timeout=10,
#         )

#         return {
#             "output": result.stdout.strip(),
#             "error": result.stderr.strip(),
#         }

#     except subprocess.TimeoutExpired:
#         return {"error": "Execution timed out."}
#     except Exception as e:
#         return {"error": f"Execution failed: {str(e)}"}
#     finally:
#         shutil.rmtree(temp_dir)



























import os
import subprocess
import tempfile
import shutil
import platform
import asyncio
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def run_code_sandboxed(code: str, language: str, stdin: str = "") -> dict:
    container_image_map = {
        "python": "python:3",
        "cpp": "gcc",
        "javascript": "node",
        "java": "openjdk",
    }

    if language not in container_image_map:
        logger.error(f"Unsupported language: {language}")
        yield {"error": "Unsupported language"}
        return

    filename_map = {
        "python": "script.py",
        "cpp": "main.cpp",
        "javascript": "script.js",
        "java": "Main.java",
    }

    run_command_map = {
        "python": ["python", f"/code/{filename_map[language]}"],
        "cpp": ["sh", "-c", f"g++ /code/{filename_map[language]} -o /code/a.out && /code/a.out"],
        "javascript": ["node", f"/code/{filename_map[language]}"],
        "java": ["sh", "-c", f"javac /code/{filename_map[language]} && java -cp /code Main"],
    }

    temp_dir = tempfile.mkdtemp()
    filename = filename_map[language]
    filepath = os.path.join(temp_dir, filename)

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(code)

        logger.debug(f"Received initial stdin: {repr(stdin)}")

        docker_flags = ["-i", "--network", "none"]

        cmd = [
            "docker", "run", "--rm", *docker_flags,
            "--cpus", "0.5", "--memory", "100m",
            "-v", f"{temp_dir}:/code",
            container_image_map[language],
            *run_command_map[language],
        ]

        if platform.system() == "Windows" and os.environ.get("MSYSTEM") in ["MINGW32", "MINGW64"]:
            cmd = ["winpty"] + cmd

        logger.debug(f"Executing command: {' '.join(cmd)}")

        process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

        process_id = id(process)
        yield {"process_id": process_id}

        if stdin:
            process.stdin.write(stdin + "\n")
            process.stdin.flush()
            logger.debug(f"Wrote initial stdin: {repr(stdin)}")

        timeout = 30
        start_time = asyncio.get_event_loop().time()
        while process.poll() is None:
            try:
                stdout = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(None, process.stdout.readline),
                    timeout=1.0
                )
                if stdout:
                    is_prompt = (
                        stdout.strip().endswith(": ") or
                        "enter" in stdout.lower() or
                        stdout.strip().endswith("? ") or
                        stdout.strip() == ""
                    )
                    logger.debug(f"Stdout: {stdout.strip()}, Prompt: {is_prompt}")
                    yield {"output": stdout.strip(), "prompt": is_prompt, "process_id": process_id}
                    if is_prompt and hasattr(process, "next_stdin"):
                        process.stdin.write(process.next_stdin + "\n")
                        process.stdin.flush()
                        logger.debug(f"Wrote stdin: {repr(process.next_stdin)}")
                        delattr(process, "next_stdin")

                stderr = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(None, process.stderr.readline),
                    timeout=1.0
                )
                if stderr:
                    logger.debug(f"Stderr: {stderr.strip()}")
                    yield {"error": stderr.strip(), "process_id": process_id}

            except asyncio.TimeoutError:
                if asyncio.get_event_loop().time() - start_time > timeout:
                    logger.error("Execution timed out")
                    yield {"error": "Execution timed out", "process_id": process_id}
                    break

        stdout, stderr = process.communicate(timeout=2)
        if stdout:
            logger.debug(f"Final stdout: {stdout.strip()}")
            yield {"output": stdout.strip(), "process_id": process_id}
        if stderr:
            logger.debug(f"Final stderr: {stderr.strip()}")
            yield {"error": stderr.strip(), "process_id": process_id}

    except subprocess.TimeoutExpired:
        logger.error("Process communication timed out")
        yield {"error": "Process communication timed out", "process_id": process_id if 'process' in locals() else None}
        if process.poll() is None:
            process.terminate()
    except Exception as e:
        logger.error(f"Execution failed: {str(e)}")
        yield {"error": f"Execution failed: {str(e)}", "process_id": process_id if 'process' in locals() else None}
    finally:
        shutil.rmtree(temp_dir)
        if 'process' in locals() and process.poll() is None:
            process.terminate()
            logger.debug("Process terminated")