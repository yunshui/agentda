"""
FINANCE 财务数据服务客户端

调用真实环境财务数据接口（完整地址见 config/settings.json）：
- get_dictionary: 财务指标字典，返回内容一般不会变化，服务缓存 10 分钟
- get_t51_amount: 指标金额数据

两个接口的完整地址（含 flowActionName）由用户在 config/settings.json 中分别配置：
FINANCE_DICTIONARY_URL / FINANCE_QUERY_URL，代码直接调用配置的地址。
"""

import json
import logging
import time

import httpx

from config import FINANCE_DICTIONARY_URL, FINANCE_QUERY_URL, DICTIONARY_CACHE_TTL

# 模块日志记录器：向上传播到 "api-core" 应用日志（含 MDC 上下文），无需重复配置 handler
logger = logging.getLogger("api-core.finance_client")

# 请求超时（秒）
TIMEOUT_SECONDS = 30.0


class FinanceServiceError(Exception):
    """FINANCE 财务数据服务调用异常"""

    def __init__(self, message: str, status_code: int = 502):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


# 字典缓存（get_dictionary 内容基本不变，缓存 10 分钟）
_dict_cache: dict = {"data": None, "fetched_at": 0.0}


async def _get(url: str, params: dict) -> dict:
    """向 FINANCE 服务指定地址发起 GET 请求，统一异常处理"""
    start = time.monotonic()
    logger.info(f"调用 FINANCE 接口: url={url}, params={params}")
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
        elapsed_ms = int((time.monotonic() - start) * 1000)
        logger.info(f"FINANCE 接口调用成功: url={url}, status={resp.status_code}, elapsed={elapsed_ms}ms")
        return data
    except httpx.TimeoutException as e:
        logger.error(f"FINANCE 接口调用超时: url={url}, params={params}, error={e}")
        raise FinanceServiceError("财务数据服务响应超时")
    except httpx.ConnectError as e:
        logger.error(f"无法连接财务数据服务: url={url}, error={e}")
        raise FinanceServiceError("无法连接财务数据服务")
    except httpx.HTTPStatusError as e:
        logger.error(f"FINANCE 接口返回错误状态: url={url}, status={e.response.status_code}")
        raise FinanceServiceError(f"财务数据服务返回错误状态: {e.response.status_code}")
    except json.JSONDecodeError as e:
        logger.error(f"FINANCE 接口返回无效响应: url={url}, error={e}")
        raise FinanceServiceError("财务数据服务返回了无效的响应")
    except Exception:
        # 未知异常：记录堆栈后原样抛出，保持调用方原有行为
        logger.exception(f"FINANCE 接口调用发生未知异常: url={url}, params={params}")
        raise


async def _fetch_dictionary() -> dict:
    """向 FINANCE 请求财务指标字典（get_dictionary），并更新缓存"""
    data = await _get(FINANCE_DICTIONARY_URL, {})
    _dict_cache["data"] = data
    _dict_cache["fetched_at"] = time.time()
    logger.info(f"财务字典刷新缓存成功: metrics={len(data.get('metrics', []))}")
    return data


async def get_finance_dictionary() -> dict:
    """获取财务指标字典，带 10 分钟缓存"""
    now = time.time()
    data = _dict_cache["data"]
    if data is not None and now - _dict_cache["fetched_at"] < DICTIONARY_CACHE_TTL:
        logger.info(f"财务字典命中缓存: cached_seconds={int(now - _dict_cache['fetched_at'])}")
        return data

    return await _fetch_dictionary()


async def get_allowed_metrics() -> set:
    """获取指标白名单（standard_name 集合）"""
    data = await get_finance_dictionary()
    return {m["standard_name"] for m in data.get("metrics", [])}


async def query_metric_data(
    metric: str,
    year: int = None,
    quarter: int = None,
    month: int = None,
    granularity: str = "yearly",
) -> dict:
    """查询指标金额数据（get_t51_amount）"""
    params = {
        "metric": metric,
        "granularity": granularity,
    }
    if year:
        params["year"] = year
    if quarter:
        params["quarter"] = quarter
    if month:
        params["month"] = month

    return await _get(FINANCE_QUERY_URL, params)
