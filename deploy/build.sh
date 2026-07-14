#!/bin/bash
# ============================================================
# 构建离线 Docker 镜像
# 在能连外网的机器上执行，产出 tar 文件用于内网部署
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
OUTPUT_DIR="$SCRIPT_DIR/output"

# 镜像标签
API_CORE_TAG="bankda-api-core:latest"
MCP_CORE_TAG="bankda-mcp-core:latest"
AGENT_CORE_TAG="bankda-agent-core:latest"

mkdir -p "$OUTPUT_DIR"

echo "========================================"
echo "1. 构建 api-core 镜像"
echo "========================================"
docker build -t "$API_CORE_TAG" \
  -f "$SCRIPT_DIR/docker/api-core/Dockerfile" \
  "$PROJECT_DIR"

echo ""
echo "========================================"
echo "2. 构建 mcp-core 镜像"
echo "========================================"
docker build -t "$MCP_CORE_TAG" \
  -f "$SCRIPT_DIR/docker/mcp-core/Dockerfile" \
  "$PROJECT_DIR"

echo ""
echo "========================================"
echo "3. 构建 agent-core 镜像"
echo "========================================"
docker build -t "$AGENT_CORE_TAG" \
  -f "$SCRIPT_DIR/docker/agent-core/Dockerfile" \
  "$PROJECT_DIR"

echo ""
echo "========================================"
echo "4. 导出镜像为 tar 文件"
echo "========================================"
docker save -o "$OUTPUT_DIR/bankda-api-core.tar" "$API_CORE_TAG"
docker save -o "$OUTPUT_DIR/bankda-mcp-core.tar" "$MCP_CORE_TAG"
docker save -o "$OUTPUT_DIR/bankda-agent-core.tar" "$AGENT_CORE_TAG"

echo ""
echo "========================================"
echo "5. 生成 md5 校验文件"
echo "========================================"
cd "$OUTPUT_DIR"
md5sum *.tar > checksum.md5

echo ""
echo "========================================"
echo "构建完成，产出文件:"
echo "========================================"
ls -lh "$OUTPUT_DIR"
echo ""
echo "将 output/ 目录下所有文件拷贝到内网 Kylin 机器即可。"
