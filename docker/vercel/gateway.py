#!/usr/bin/env python3
"""Hold cold-start requests until Talebook is ready, then proxy to Nginx."""

import json
import select
import socket
import socketserver
import time


LISTEN = ("0.0.0.0", 80)
UPSTREAM = ("127.0.0.1", 8081)
TORNADO = ("127.0.0.1", 8000)
STATUS_PATH = "/tmp/talebook/status/status.json"
STARTUP_TIMEOUT = 60


def is_ready():
    try:
        with open(STATUS_PATH, encoding="utf-8") as status_file:
            if json.load(status_file).get("phase") != "ready":
                return False
        with socket.create_connection(TORNADO, timeout=0.1):
            return True
    except (OSError, ValueError):
        return False


def wait_for_ready():
    deadline = time.monotonic() + STARTUP_TIMEOUT
    while time.monotonic() < deadline:
        if is_ready():
            return True
        time.sleep(0.05)
    return False


class GatewayHandler(socketserver.BaseRequestHandler):
    def handle(self):
        if not wait_for_ready():
            self.request.sendall(
                b"HTTP/1.1 503 Service Unavailable\r\n"
                b"Content-Type: text/plain\r\n"
                b"Content-Length: 27\r\n"
                b"Connection: close\r\n\r\n"
                b"Talebook startup timed out\n"
            )
            return

        with socket.create_connection(UPSTREAM, timeout=5) as upstream:
            sockets = (self.request, upstream)
            while True:
                readable, _, _ = select.select(sockets, (), (), 60)
                if not readable:
                    return
                for source in readable:
                    data = source.recv(65536)
                    if not data:
                        return
                    target = upstream if source is self.request else self.request
                    target.sendall(data)


class GatewayServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == "__main__":
    print("[vercel-gateway] listening on 0.0.0.0:80", flush=True)
    with GatewayServer(LISTEN, GatewayHandler) as server:
        server.serve_forever()
