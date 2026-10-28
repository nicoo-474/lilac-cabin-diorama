"""Client for the dsh-blender-plugin socket bridge (127.0.0.1:9876).

The addon keeps the socket open after replying, so we must parse exactly one
JSON object out of the stream instead of waiting for EOF.

Usage:
    python dsh.py ping
    python dsh.py info
    python dsh.py run <code_file.py>      # exec file contents inside Blender
"""
import json
import socket
import sys
import time

HOST, PORT = "127.0.0.1", 9876
DEC = json.JSONDecoder()


def send(payload, timeout=1800.0):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    s.connect((HOST, PORT))
    s.sendall(json.dumps(payload).encode("utf-8"))
    buf = ""
    while True:
        chunk = s.recv(65536)
        if not chunk:
            raise RuntimeError("connection closed with no data")
        buf += chunk.decode("utf-8", "replace")
        try:
            obj, _end = DEC.raw_decode(buf)
        except ValueError:
            continue
        s.close()
        return obj


def run_code(code, timeout=1800.0):
    return send({"type": "execute_code", "params": {"code": code}}, timeout)


def main():
    if len(sys.argv) < 2:
        print("usage: dsh.py ping|info|run <file>")
        return 1
    cmd = sys.argv[1]
    if cmd == "ping":
        res = send({"type": "ping"}, timeout=30)
    elif cmd == "info":
        res = send({"type": "get_addon_info"}, timeout=30)
    elif cmd == "run":
        with open(sys.argv[2], "r", encoding="utf-8") as f:
            code = f.read()
        t0 = time.time()
        res = run_code(code)
        print(f"-- {time.time() - t0:.1f}s --")
    else:
        print("unknown cmd")
        return 1
    with open("last_result.json", "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False)[:6000], flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
