import os
import sys
import time
import psutil
import subprocess
from datetime import datetime

MODULES = [
    "ed_module",
    "birthday_module",
    "test_message_module",
    "reminder_module"
]
MODULES_DIR = os.path.join(os.path.dirname(__file__), "modules")
LOGS_DIR = os.path.join(os.path.dirname(__file__), "logs")


def get_module_status():
    status = {}
    for module in MODULES:
        running = False
        pid = None
        start_time = None
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
            cmdline = proc.info.get('cmdline') or []
            if any(f"modules.{module}" in str(arg) for arg in cmdline):
                running = True
                pid = proc.info['pid']
                start_time = datetime.fromtimestamp(proc.info['create_time']).strftime('%Y-%m-%d %H:%M:%S')
                break
        # Get file modified time
        mod_path = os.path.join(MODULES_DIR, f"{module}.py")
        if os.path.exists(mod_path):
            file_modified = time.ctime(os.path.getmtime(mod_path))
        else:
            file_modified = "Not found"
        status[module] = {
            'running': running,
            'pid': pid,
            'start_time': start_time,
            'file_modified': file_modified
        }
    return status

def start_module(module):
    os.makedirs(LOGS_DIR, exist_ok=True)
    logfile = os.path.join(LOGS_DIR, f"{module}_logs.log")
    subprocess.Popen([
        sys.executable, "-m", f"modules.{module}"
    ], stdout=open(logfile, "a"), stderr=subprocess.STDOUT)

def stop_module(module):
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        cmdline = proc.info.get('cmdline') or []
        if any(f"modules.{module}" in str(arg) for arg in cmdline):
            proc.kill()
            print(f"Stopped {module} (PID {proc.info['pid']})")
            return
    print(f"No running process found for {module}.")

def print_status():
    status = get_module_status()
    print(f"{'#':<3} {'Module':<20} {'Status':<10} {'PID':<8} {'Started':<20} {'File Modified':<24}")
    print("-" * 90)
    for idx, (module, info) in enumerate(status.items(), 1):
        print(f"{idx:<3} {module:<20} {'Running' if info['running'] else 'Stopped':<10} "
              f"{str(info['pid']) if info['pid'] else '-':<8} "
              f"{info['start_time'] or '-':<20} {info['file_modified']:<24}")
    return list(status.keys())

def main():
    help_text = (
        "Commands:\n"
        "  status            Show status of all modules\n"
        "  start X           Start module number X (from status table)\n"
        "  start all         Start all modules\n"
        "  stop X            Stop module number X (from status table)\n"
        "  stop all          Stop all modules\n"
        "  help              Show this help message\n"
        "  exit              Exit the orchestrator\n"
    )
    module_names = MODULES[:]
    print("Orchestrator CLI. Type 'help' for commands.")
    print_status()
    while True:
        cmd = input("> ").strip().lower()
        if cmd == "status":
            module_names = print_status()
        elif cmd.startswith("start all"):
            for mod in MODULES:
                start_module(mod)
                print(f"Started {mod}.")
        elif cmd.startswith("stop all"):
            for mod in MODULES:
                stop_module(mod)
        elif cmd.startswith("start "):
            arg = cmd.split(" ", 1)[1].strip()
            if arg.isdigit():
                idx = int(arg) - 1
                if 0 <= idx < len(module_names):
                    start_module(module_names[idx])
                    print(f"Started {module_names[idx]}.")
                else:
                    print("Invalid module number.")
            else:
                print("Usage: start X (where X is the module number from 'status')")
        elif cmd.startswith("stop "):
            arg = cmd.split(" ", 1)[1].strip()
            if arg.isdigit():
                idx = int(arg) - 1
                if 0 <= idx < len(module_names):
                    stop_module(module_names[idx])
                else:
                    print("Invalid module number.")
            else:
                print("Usage: stop X (where X is the module number from 'status')")
        elif cmd == "help":
            print(help_text)
        elif cmd == "exit":
            print("Exiting.")
            break
        elif cmd == "":
            continue
        else:
            print("Unknown command. Type 'help' for a list of commands.")

if __name__ == "__main__":
    main()
