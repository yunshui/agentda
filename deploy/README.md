# Bankda 离线 Docker 部署指南

适用于 **Kylin Linux Advanced Server V10 (Halberd)** x86_64 内网环境，Python 3.12。

---

## 整体流程

```
有网机器（任意 x86_64 Linux）          Kylin 内网机器
┌─────────────────────┐              ┌─────────────────────┐
│  1. docker build     │              │  4. 安装 Docker      │
│  2. docker save      │  ───USB──►  │  5. docker load      │
│  3. 产出 tar 包      │              │  6. docker compose   │
└─────────────────────┘              └─────────────────────┘
```

---

## 第一步：在有网机器上构建镜像

### 1.1 安装 Docker（如未安装）

```bash
curl -fsSL https://get.docker.com | bash
sudo systemctl enable docker
sudo systemctl start docker
```

### 1.2 执行构建脚本

```bash
cd bankda/deploy
bash build.sh
```

脚本会自动完成：
- 构建 `bankda-api-core:latest`、`bankda-mcp-core:latest`、`bankda-agent-core:latest` 三个镜像
- 导出为 tar 文件到 `deploy/output/` 目录
- 生成 MD5 校验文件

### 1.3 产出物

```
deploy/output/
├── bankda-api-core.tar       # API Core 镜像
├── bankda-mcp-core.tar       # MCP Core 镜像
├── bankda-agent-core.tar     # Agent Core 镜像
└── checksum.md5              # 完整性校验文件
```

> **注意**：如果内网无法访问 `pypi.tuna.tsinghua.edu.cn`，修改 Dockerfile 中的 `-i` 参数，换成可用的 PyPI 镜像源。

---

## 第二步：传输到内网 Kylin 机器

将 `deploy/output/` 目录下的所有文件通过 U 盘或内部文件服务器拷贝到 Kylin 内网机器上。

建议存放路径：`/opt/bankda/output/`

---

## 第三步：在 Kylin 内网机器上安装 Docker

### 3.1 检查内核版本

```bash
uname -r
# 预期输出: 4.19.90-89.40.v2401.ky10.x86_64
```

### 3.2 安装 Docker（离线 RPM 方式）

在有网机器上下载 Docker RPM 包（需 CentOS 8 / Kylin V10 兼容环境）：

```bash
# 安装 yum-utils
sudo yum install -y yum-utils

# 添加 Docker 源
sudo yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo

# 下载 RPM 包（不安装）
mkdir -p /tmp/docker-rpm
sudo yum install --downloadonly --downloaddir=/tmp/docker-rpm docker-ce docker-ce-cli containerd.io docker-compose-plugin
```

将 `/tmp/docker-rpm/` 目录传到内网 Kylin 机器。

在内网 Kylin 机器上执行：

```bash
cd /path/to/docker-rpm
sudo rpm -ivh *.rpm --nodeps
sudo systemctl enable docker
sudo systemctl start docker
sudo docker --version  # 验证安装
```

### 3.3 验证 Docker 可用

```bash
docker info
docker compose version  # 确认 docker compose 插件可用
```

---

## 第四步：导入并启动服务

### 4.1 部署文件准备

将 `deploy/` 目录完整拷贝到 Kylin 机器，或手动创建以下结构：

```
/path/to/bankda/deploy/
├── deploy.sh              # 部署脚本
├── output/
│   ├── bankda-api-core.tar
│   ├── bankda-mcp-core.tar
│   ├── bankda-agent-core.tar
│   └── checksum.md5
```

### 4.2 执行部署

```bash
cd /path/to/bankda/deploy
bash deploy.sh
```

脚本执行内容：

```
1. 校验镜像文件完整性 (MD5)
2. 导入 Docker 镜像 (docker load)
3. 生成 docker-compose.yml
4. 启动服务 (docker compose up -d)
```

### 4.3 验证服务

```bash
# 检查容器运行状态
docker ps

# 测试 API Core
curl http://localhost:8002/api/health
# 预期: {"status":"ok"}

# 测试 MCP Core
curl http://localhost:8001/mcp/health
# 预期: {"status":"ok"}

# 测试 Agent Core
curl http://localhost:8000/agent/health
# 预期: {"status":"ok"}
```

---

## 第五步：配置 MCP 客户端连接

### 5.1 获取 Refresh Token

项目中预置了 Refresh Token，查看方式：

```bash
cat tools/refresh_token.txt
# 输出: MCP_REFRESH_TOKEN=<base64字符串>
```

### 5.2 配置 MCP 客户端

在 MCP 客户端（如 Claude Desktop、VS Code 等）的配置文件中添加：

```json
{
  "mcpServers": {
    "bankda-finance": {
      "url": "http://<kylin-ip>:8001/mcp",
      "env": {
        "MCP_REFRESH_TOKEN": "<从 refresh_token.txt 获取的完整值>"
      }
    }
  }
}
```

> 将 `<kylin-ip>` 替换为 Kylin 内网机器的实际 IP 地址。
> MCP 客户端会自动使用 Refresh Token 换取 Access Token 进行认证。

---

## 日常管理命令

```bash
# 查看实时日志
cd /path/to/bankda/deploy
docker compose logs -f

# 查看特定服务日志
docker compose logs -f api-core
docker compose logs -f mcp-core
docker compose logs -f agent-core

# 重启服务
docker compose restart

# 停止服务
docker compose down

# 更新镜像（当获取到新 tar 包时）
docker load -i output/bankda-api-core.tar
docker load -i output/bankda-mcp-core.tar
docker load -i output/bankda-agent-core.tar
docker compose up -d

# 进入容器内部调试
docker exec -it bankda-deploy_api-core_1 sh
```

---

## 常见问题

### Q: docker compose 命令不存在

```bash
# 检查 docker compose 插件是否安装
docker compose version

# 如未安装，使用 docker-compose（旧版）
docker-compose up -d
```

### Q: 端口被占用

修改 `deploy/docker-compose.yml` 中的端口映射：

```yaml
ports:
  - "18000:8000"   # 将宿主机 18000 映射到容器 8000
```

### Q: 容器启动后立即退出

```bash
# 查看日志
docker compose logs

# 常见原因：端口冲突、依赖包缺失
```

### Q: 内网 PyPI 镜像

如果使用内网 PyPI 镜像，修改 Dockerfile 中的 pip 参数：

```dockerfile
RUN pip install --no-cache-dir -r requirements.txt -i http://<内网镜像地址>/simple --trusted-host <内网镜像地址>
```

---

## 文件说明

```
deploy/
├── README.md                       # 本文件：部署操作步骤
├── build.sh                        # [有网] 构建镜像并导出 tar
├── deploy.sh                       # [内网] 导入 tar 并启动服务
├── docker-compose.yml              # 容器编排配置
└── docker/
    ├── api-core/Dockerfile         # API Core 镜像构建文件
    ├── mcp-core/Dockerfile         # MCP Core 镜像构建文件
    └── agent-core/Dockerfile       # Agent Core 镜像构建文件
```
