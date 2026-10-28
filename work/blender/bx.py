"""Fire-and-forget sender: queue code inside Blender, never block on the reply."""
import json
import socket
import sys

HOST, PORT = "127.0.0.1", 9876


def fire(code):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(5.0)
    s.connect((HOST, PORT))
    s.sendall(json.dumps({"type": "execute_code", "params": {"code": code}}).encode("utf-8"))
    s.close()


if __name__ == "__main__":
    with open(sys.argv[1], "r", encoding="utf-8") as f:
        fire(f.read())
    print("queued", sys.argv[1])
