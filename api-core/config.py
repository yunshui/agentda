"""api-core 配置

配置值从项目根目录 config/settings.json 读取，可通过环境变量覆盖。
取值优先级：环境变量 > config/settings.json。
FINANCE_DICTIONARY_URL / FINANCE_QUERY_URL 为真实环境地址，不预留在代码中，必须由 settings.json 或环境变量提供。
"""

import json
import os
from pathlib import Path

_CONFIG_FILE = Path(__file__).resolve().parent.parent / "config" / "settings.json"

# DICTIONARY_CACHE_TTL 兜底默认值（非敏感配置）
_DEFAULT_CACHE_TTL = 600


def _load_file_config() -> dict:
    """读取 config/settings.json，文件不存在或解析失败时返回空字典"""
    try:
        with open(_CONFIG_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


_file_config = _load_file_config()


def _get(name: str, default=None, cast=None):
    """取值优先级：环境变量 > config/settings.json"""
    value = os.environ.get(name)
    if value is None:
        value = _file_config.get(name, default)
    if cast is not None and value is not None:
        value = cast(value)
    return value


# FINANCE 财务数据服务字典接口完整地址（真实地址，仅配置于 config/settings.json，环境变量可覆盖）
FINANCE_DICTIONARY_URL = _get("FINANCE_DICTIONARY_URL")
# FINANCE 财务数据服务查询接口完整地址（真实地址，仅配置于 config/settings.json，环境变量可覆盖）
FINANCE_QUERY_URL = _get("FINANCE_QUERY_URL")
if not FINANCE_DICTIONARY_URL or not FINANCE_QUERY_URL:
    raise RuntimeError(
        "FINANCE_DICTIONARY_URL / FINANCE_QUERY_URL 未配置：请在 config/settings.json 中设置，或通过环境变量提供"
    )

# get_dictionary 接口缓存时间（秒），默认 10 分钟
DICTIONARY_CACHE_TTL = _get("DICTIONARY_CACHE_TTL", _DEFAULT_CACHE_TTL, int)
