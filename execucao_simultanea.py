import os
import subprocess
import sys


def run_script(script_name):
    script_path = os.path.join(os.path.dirname(__file__), script_name)
    return subprocess.Popen([sys.executable, script_path])


def main():
    processes = [
        run_script("main.py"),
        run_script("Pymodbus_Server.py"),
    ]

    try:
        for process in processes:
            process.wait()
    except KeyboardInterrupt:
        for process in processes:
            if process.poll() is None:
                process.terminate()
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()

    return max((process.returncode or 0) for process in processes)


if __name__ == "__main__":
    raise SystemExit(main())
