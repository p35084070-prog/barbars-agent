"""Перезапуск локального прокси и проверка, что он слушает.

Прокси нужен для обхода VPN-туннеля Happ: внутри туннеля TLS-рукопожатие
с github.com / ok.ru / barbars.ru обрывается.
"""
import pathlib, socket, subprocess, sys, time

ROOT = pathlib.Path(__file__).resolve().parents[1]
PORT = 8899
SRC = "192.168.31.207"
LOG = ROOT / "logs_local" / "proxy_out.log"

if not (ROOT / "tools" / "local_proxy.py").exists():
    print("нет tools/local_proxy.py")
    sys.exit(1)


def alive(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=3):
            return True
    except OSError:
        return False


if alive(PORT):
    print(f"прокси уже слушает {PORT}")
else:
    LOG.parent.mkdir(exist_ok=True)
    with open(LOG, "ab") as out:
        subprocess.Popen(
            [sys.executable, "-u", str(ROOT / "tools" / "local_proxy.py"),
             "--interface", SRC, "--port", str(PORT)],
            stdout=out, stderr=subprocess.STDOUT, cwd=str(ROOT))
    for _ in range(20):
        time.sleep(0.5)
        if alive(PORT):
            break
    print("прокси запущен" if alive(PORT) else "прокси НЕ поднялся")
