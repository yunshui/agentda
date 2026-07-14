#!/bin/bash
# ============================================================
# 内网 Kylin Linux 部署脚本
# 将 build.sh 产出的 tar 镜像导入并启动
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
IMAGE_DIR="$SCRIPT_DIR/output"

if [ ! -f "$IMAGE_DIR/agentda.tar" ]; then
  echo "错误: 未找到镜像 tar 文件，请先将 output/ 目录拷贝到本机。"
  echo "预期文件:"
  echo "  $IMAGE_DIR/agentda.tar"
  exit 1
fi

echo "========================================"
echo "1. 校验镜像文件完整性"
echo "========================================"
if [ -f "$IMAGE_DIR/checksum.md5" ]; then
  cd "$IMAGE_DIR"
  if md5sum -c checksum.md5; then
    echo "校验通过。"
  else
    echo "警告: 文件校验不通过，请检查文件是否完整。"
    exit 1
  fi
else
  echo "警告: 未找到 checksum.md5，跳过校验。"
fi

echo ""
echo "========================================"
echo "2. 导入 Docker 镜像"
echo "========================================"
docker load -i "$IMAGE_DIR/agentda.tar"

echo ""
echo "========================================"
echo "3. 创建 docker-compose.yml"
echo "========================================"
cat > "$SCRIPT_DIR/docker-compose.yml" << 'COMPOSE_EOF'
version: "3.8"

services:
  agentda:
    image: agentda:latest
    ports:
      - "8000:8000"
      - "8001:8001"
      - "8002:8002"
    volumes:
      - /home/prdmng/agentda/logs:/data/logs
    environment:
      - API_CORE_URL=http://localhost:8002
    restart: unless-stopped
COMPOSE_EOF

echo ""
echo "========================================"
echo "4. 启动服务"
echo "========================================"
cd "$SCRIPT_DIR"
docker compose up -d

echo ""
echo "========================================"
echo "部署完成!"
echo "========================================"
echo "API Core:    http://localhost:8002/api/health"
echo "MCP Core:    http://localhost:8001/mcp/health"
echo "Agent Core:  http://localhost:8000/agent/health"
echo ""
echo "查看日志: docker compose logs -f"
echo "停止服务: docker compose down"
