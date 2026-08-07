#!/bin/sh
cd /data/apps

# 停止占用指定 TCP 端口的进程（slim 镜像无 lsof/ss/fuser，用 Python 解析 /proc）
stop_port() {
    port=$1
    pids=$(python3 - "$port" <<'PY'
import os, sys, glob
port_hex = "%04X" % int(sys.argv[1])

def listen_inodes(path):
    inodes = set()
    if not os.path.exists(path):
        return inodes
    with open(path) as f:
        for line in f:
            parts = line.split()
            if len(parts) < 10 or parts[0] == "sl":
                continue
            # 状态 0A=LISTEN，第 2 列为 local_address(IP:端口)
            if parts[3] == "0A" and parts[1].split(":")[-1] == port_hex:
                inodes.add(parts[9])
    return inodes

inodes = listen_inodes("/proc/net/tcp") | listen_inodes("/proc/net/tcp6")
pids = set()
for fd in glob.glob("/proc/[0-9]*/fd/*"):
    try:
        link = os.readlink(fd)
    except OSError:
        continue
    if link.startswith("socket:[") and link[8:-1] in inodes:
        pids.add(fd.split("/")[2])
print(" ".join(sorted(pids)))
PY
    )

    if [ -n "$pids" ]; then
        echo "[entrypoint] 端口 $port 已被进程占用($pids)，先停止..."
        kill $pids 2>/dev/null
        sleep 1
        for pid in $pids; do
            if kill -0 "$pid" 2>/dev/null; then
                echo "[entrypoint] 进程 $pid 未退出，强制终止"
                kill -9 "$pid" 2>/dev/null
            fi
        done
    fi
}

# 若端口已被占用则先停止，再启动服务
for p in 8000 8001 8002; do
    stop_port "$p"
done

# Start API Core (port 8002)
uvicorn api-core.main:app --host 0.0.0.0 --port 8002 &

# Start MCP Core (port 8001) — API_CORE_URL defaults to localhost:8002
uvicorn mcp-core.main:app --host 0.0.0.0 --port 8001 &

# Start Agent Core (port 8000)
uvicorn agent-core.main:app --host 0.0.0.0 --port 8000 &

# Wait for any child to exit
wait
