"""配置"""

import os

# 后台 API 地址
API_CORE_URL = os.environ.get("API_CORE_URL", "http://localhost:8002")

# 预期的 Token
EXPECTED_TOKEN = os.environ.get("EXPECTED_TOKEN", "prototype-token")

# 服务端口
PORT = int(os.environ.get("PORT", "8001"))
