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
IMAGE_TAG="agentda:latest"

mkdir -p "$OUTPUT_DIR"

echo "========================================"
echo "1. 构建 agentda 镜像"
echo "========================================"
docker build -t "$IMAGE_TAG" \
  -f "$SCRIPT_DIR/docker/Dockerfile" \
  "$PROJECT_DIR"

echo ""
echo "========================================"
echo "2. 导出镜像为 tar 文件"
echo "========================================"
docker save -o "$OUTPUT_DIR/agentda.tar" "$IMAGE_TAG"

echo ""
echo "========================================"
echo "3. 生成 md5 校验文件"
echo "========================================"
cd "$OUTPUT_DIR"
md5sum agentda.tar > checksum.md5

echo ""
echo "========================================"
echo "构建完成，产出文件:"
echo "========================================"
ls -lh "$OUTPUT_DIR"
echo ""
echo "将 output/ 目录下所有文件拷贝到内网 Kylin 机器即可。"
