"""Локальный CONNECT-прокси, привязанный к сетевому интерфейсу (Wi-Fi).

Зачем: на машине стоит VPN (Happ/sing-box, интерфейс happ-tun). Весь трафик
идёт в туннель, и часть доменов (github.com, api.github.com, ok.ru,
barbars.ru) там ломается — TLS-рукопожатие обрывается. Прямой выход через
Wi-Fi с теми же доменами работает.

Этот прокси принимает CONNECT на 127.0.0.1 и дальше подключается к цели
с исходным адресом интерфейса Wi-Fi. Никакой фильтрации и логирования.

Запуск:
    python tools\\local_proxy.py --interface 192.168.31.207 --port 8899
Использование:
    set HTTPS_PROXY=http://127.0.0.1:8899
    set HTTP_PROXY=http://127.0.0.1:8899
"""
from __future__ import annotations

import argparse
import socket
import socketserver
import struct
import threading

# Windows: IP_UNICAST_IF (31) заставляет сокет слать трафик через конкретный
# интерфейс, обходя маршрут по умолчанию (нужно, чтобы уйти из VPN-туннеля).
IP_UNICAST_IF = 31
IPPROTO_IP = socket.IPPROTO_IP


def bind_interface(sock: socket.socket, ifindex: int) -> None:
    """Принудительно отправить трафик через интерфейс с номером ifindex."""
    if not ifindex:
        return
    sock.setsockopt(IPPROTO_IP, IP_UNICAST_IF, struct.pack("I", ifindex))


def relay(src: socket.socket, dst: socket.socket, tag: str) -> None:
    total = 0
    try:
        while True:
            data = src.recv(65536)
            if not data:
                break
            total += len(data)
            dst.sendall(data)
    except OSError as exc:
        print(f"[proxy] {tag}: обрыв после {total} байт: {exc}", flush=True)
    finally:
        for s in (src, dst):
            try:
                s.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            s.close()


class ProxyHandler(socketserver.BaseRequestHandler):
    server: "ProxyServer"

    def handle(self) -> None:
        client = self.request
        client.settimeout(30)
        try:
            header = b""
            while b"\r\n\r\n" not in header and len(header) < 65536:
                chunk = client.recv(4096)
                if not chunk:
                    return
                header += chunk
        except OSError:
            return

        first = header.split(b"\r\n", 1)[0].decode("latin-1", "replace")
        parts = first.split()
        if len(parts) < 2 or parts[0].upper() != "CONNECT":
            client.sendall(b"HTTP/1.1 405 Method Not Allowed\r\n\r\n")
            return

        host, _, port_s = parts[1].rpartition(":")
        port = int(port_s or 443)

        try:
            upstream = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            upstream.settimeout(30)
            # Привязка к адресу Wi-Fi уводит пакеты из VPN-туннеля:
            # в туннеле TLS-рукопожатие с github.com/ok.ru обрывается.
            if self.server.source_ip:
                upstream.bind((self.server.source_ip, 0))
            upstream.connect((host, port))
            print(f"[proxy] {host}:{port} подключено с {upstream.getsockname()}", flush=True)
        except OSError as exc:
            client.sendall(
                b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\n\r\n")
            print(f"[proxy] не удалось подключиться к {host}:{port}: {exc}", flush=True)
            return

        client.sendall(b"HTTP/1.1 200 Connection established\r\n\r\n")
        client.settimeout(None)
        upstream.settimeout(None)
        # Клиент->апстрим в этом потоке, апстрим->клиент — в отдельном.
        # Поток обработчика не должен завершаться раньше обмена: иначе
        # socketserver закроет клиентский сокет.
        back = threading.Thread(target=relay, args=(upstream, client, f"{host} апстрим->клиент"),
                                daemon=True)
        back.start()
        relay(client, upstream, f"{host} клиент->апстрим")
        back.join(timeout=5)


class ProxyServer(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, addr, source_ip: str, ifindex: int):
        self.source_ip = source_ip
        self.ifindex = ifindex
        super().__init__(addr, ProxyHandler)


def main() -> int:
    ap = argparse.ArgumentParser(description="CONNECT-прокси с привязкой к интерфейсу")
    ap.add_argument("--interface", default="", help="исходный IP (например 192.168.31.207)")
    ap.add_argument("--ifindex", type=int, default=0, help="номер интерфейса Windows")
    ap.add_argument("--port", type=int, default=8899)
    args = ap.parse_args()

    server = ProxyServer(("127.0.0.1", args.port), args.interface, args.ifindex)
    print(f"[proxy] слушаю 127.0.0.1:{args.port}, source_ip={args.interface or 'авто'}, "
          f"ifindex={args.ifindex}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
