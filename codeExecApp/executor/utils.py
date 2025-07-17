import os
import subprocess
import tempfile
import shutil
import platform

def run_code_sandboxed(code: str, language: str, stdin: str = "") -> dict:
    container_image_map = {
        "python": "python:3",
        "cpp": "gcc",
        "javascript": "node",
        "java": "openjdk",
    }

    if language not in container_image_map:
        return {"error": "Unsupported language"}

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

        print(f"Received stdin: {repr(stdin)}")

        docker_flags = ["-i"]

        cmd = [
            "docker", "run", "--rm", *docker_flags,
            "--cpus", "0.5", "--memory", "100m",
            "-v", f"{temp_dir}:/code",
            container_image_map[language],
            *run_command_map[language],
        ]

        if platform.system() == "Windows" and os.environ.get("MSYSTEM") in ["MINGW32", "MINGW64"]:
            cmd = ["winpty"] + cmd

        print(f"Executing command: {' '.join(cmd)}")

        result = subprocess.run(
            cmd,
            input=stdin + "\n" if stdin else "\n",
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
        )

        return {
            "output": result.stdout.strip(),
            "error": result.stderr.strip(),
        }

    except subprocess.TimeoutExpired:
        return {"error": "Execution timed out."}
    except Exception as e:
        return {"error": f"Execution failed: {str(e)}"}
    finally:
        shutil.rmtree(temp_dir)




