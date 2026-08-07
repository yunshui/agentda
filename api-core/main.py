"""
后台 API

提供用户查询接口和财务数据查询接口。
用户编号由调用方（远端 MCP 服务）传递。
"""

import sys
from pathlib import Path

# Ensure project root and service directory are in sys.path
_project_root = str(Path(__file__).resolve().parent.parent)
_service_dir = str(Path(__file__).resolve().parent)
for _p in [_project_root, _service_dir]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fastapi import FastAPI, HTTPException, Header
from typing import Optional
import json
import os

from common.logging_lib import setup_logging, AccessLogMiddleware, user_id_var
from finance_client import (
    FinanceServiceError,
    get_finance_dictionary,
    get_allowed_metrics,
    query_metric_data,
)

app = FastAPI(title="后台 API")

# Setup logging
app_logger, access_logger = setup_logging("api-core", access_log_name="api-acc", log_dir="/data/logs/api-core")
app.add_middleware(AccessLogMiddleware, app_logger=app_logger, access_logger=access_logger)

# 加载用户数据（位于项目根目录 config/ 下，与 api-core 平级）
DATA_FILE = os.path.join(_project_root, "config", "users.json")
with open(DATA_FILE, encoding="utf-8") as f:
    USERS = json.load(f)


# ==================== 公共用户校验 ====================

def _validate_user(user_id: str):
    """
    公共校验：用户编号格式 + 是否存在于本地 users.json。

    校验失败（格式错误 / 用户不存在 / 校验异常）统一返回 200 + errorCode/errorMsg，
    不抛出 HTTP 异常，由调用方直接返回给客户端。

    Returns:
        (user_dict, None): 校验通过
        (None, {"errorCode": ..., "errorMsg": ...}): 校验失败
    """
    try:
        # 1. 格式校验
        if not user_id or not user_id.isdigit() or len(user_id) != 9:
            app_logger.warning(f"用户编号格式错误: {user_id}")
            return None, {"errorCode": "400", "errorMsg": "用户编号必须为9位数字"}

        # 2. 是否存在于本地 users.json
        user = USERS.get(user_id)
        if not user:
            app_logger.warning(f"用户不存在: {user_id}")
            return None, {"errorCode": "404", "errorMsg": "用户不存在"}

        return user, None
    except Exception as e:
        app_logger.error(f"用户校验异常: {e}, user_id={user_id}")
        return None, {"errorCode": "500", "errorMsg": "用户校验异常，请联系管理员"}


# ==================== 用户相关端点 ====================

@app.get("/api/user/{user_id}")
async def get_user(user_id: str):
    """
    查询用户信息

    Args:
        user_id: 9位数字用户编号

    Returns:
        校验失败: 200 + {"errorCode": ..., "errorMsg": ...}
        校验成功: 用户信息字典
    """
    # 公共校验：格式 + 是否存在于 users.json
    user, err = _validate_user(user_id)
    if err:
        return err

    # 设置 MDC 用户上下文
    user_id_var.set(user_id)

    app_logger.info(f"用户信息查询成功: {user_id}")
    return user


@app.get("/api/admin/{user_id}/users")
async def get_all_users(user_id: str):
    """
    管理员查询所有用户信息（不含金额）

    只有 admin 角色的用户才能调用此接口。
    返回所有用户的基本信息，不包含金额字段。

    Args:
        user_id: 9位数字用户编号（调用者）

    Returns:
        校验失败: 200 + {"errorCode": ..., "errorMsg": ...}
        权限不足: 200 + {"errorCode": "403", "errorMsg": "需要管理员权限"}
        校验成功: 用户列表，每个用户包含 user_id, name, department, role
    """
    # 公共校验：格式 + 是否存在于 users.json
    caller, err = _validate_user(user_id)
    if err:
        return err

    # 设置 MDC 用户上下文
    user_id_var.set(user_id)

    # 检查是否为管理员
    if caller.get("role") != "admin":
        app_logger.warning(f"非管理员尝试查询用户列表: {user_id}")
        return {"errorCode": "403", "errorMsg": "需要管理员权限"}

    # 返回所有用户信息（不含金额）
    users_list = []
    for uid, user in USERS.items():
        users_list.append({
            "user_id": user.get("user_id"),
            "name": user.get("name"),
            "department": user.get("department"),
            "role": user.get("role")
        })

    app_logger.info(f"管理员查询用户列表成功: user={user_id}, total={len(users_list)}")
    return {
        "total": len(users_list),
        "users": users_list
    }


# ==================== 财务相关端点 ====================

@app.get("/api/finance/dictionary")
async def get_finance_dictionary_endpoint():
    """
    获取财务指标元数据字典

    数据来自真实环境 FINANCE 服务 get_dictionary 接口。
    该接口返回内容一般不会变化，服务缓存 10 分钟。
    用于 AI 进行语义匹配和指标选择。
    """
    try:
        data = await get_finance_dictionary()
    except FinanceServiceError as e:
        app_logger.error(f"财务字典获取失败: {e}")
        raise HTTPException(e.status_code, e.message)

    app_logger.info(f"财务字典查询成功: metrics={len(data.get('metrics', []))}")
    return data


@app.get("/api/finance/query")
async def query_finance_metrics(
    metric: str,
    year: Optional[int] = None,
    quarter: Optional[int] = None,
    month: Optional[int] = None,
    granularity: str = "yearly",
    x_user_id: str = Header(None, alias="X-User-ID")
):
    """
    查询财务指标数据

    安全措施：
    1. 白名单验证 - 只允许查询字典中定义的指标（白名单来自 FINANCE get_dictionary）
    2. 参数校验 - 防止非法参数
    3. 数据来自真实环境 FINANCE 服务 get_t51_amount 接口

    Args:
        metric: 指标名（必须是字典中的 standard_name）
        year: 年份（如 2025），不指定则返回最近数据
        quarter: 季度（1-4）
        month: 月份（1-12）
        granularity: 聚合粒度（yearly/quarterly/monthly）
        x_user_id: 用户编号（从 Header 传入）

    Returns:
        用户校验失败: 200 + {"errorCode": ..., "errorMsg": ...}
        财务数据结果（FINANCE 服务返回内容）

    Raises:
        400: 参数格式错误
        502: 财务数据服务不可用
    """
    # 1. 公共校验：格式 + 是否存在于 users.json
    _, err = _validate_user(x_user_id)
    if err:
        return err

    # 设置 MDC 用户上下文
    user_id_var.set(x_user_id)

    # 2. 获取指标白名单（FINANCE get_dictionary，带缓存）
    try:
        allowed_metrics = await get_allowed_metrics()
    except FinanceServiceError as e:
        app_logger.error(f"财务字典获取失败: {e}, user={x_user_id}")
        raise HTTPException(e.status_code, e.message)

    # 3. 白名单验证
    if metric not in allowed_metrics:
        app_logger.warning(f"不支持的指标: {metric}, user={x_user_id}")
        raise HTTPException(400, f"不支持的指标: {metric}。请先调用 /api/finance/dictionary 获取支持的指标列表")

    # 4. 参数校验
    if quarter is not None and (quarter < 1 or quarter > 4):
        raise HTTPException(400, "季度必须在 1-4 之间")

    if month is not None and (month < 1 or month > 12):
        raise HTTPException(400, "月份必须在 1-12 之间")

    if granularity not in ["yearly", "quarterly", "monthly"]:
        raise HTTPException(400, "granularity 必须是 yearly/quarterly/monthly")

    # 5. 调用 FINANCE get_t51_amount 查询数据
    try:
        result = await query_metric_data(
            metric=metric,
            year=year,
            quarter=quarter,
            month=month,
            granularity=granularity,
        )
    except FinanceServiceError as e:
        app_logger.error(f"财务数据查询失败: {e}, metric={metric}, user={x_user_id}")
        raise HTTPException(e.status_code, e.message)

    # 6. 检查上游错误码
    if str(result.get("errorCode")) != "0":
        err_msg = result.get("errorMsg") or "财务数据服务返回异常"
        app_logger.warning(
            f"财务数据查询失败: metric={metric}, error={err_msg}, user={x_user_id}"
        )
        raise HTTPException(400, err_msg)

    # 7. 返回 FINANCE 服务结果
    app_logger.info(
        f"财务指标查询成功: metric={metric}, "
        f"year={year}, quarter={quarter}, month={month}, granularity={granularity}, "
        f"data_points={len(result.get('data', []))}"
    )
    return result


# ==================== 健康检查 ====================

@app.get("/api/health")
async def health():
    """健康检查"""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    app_logger.info("启动后台 API 服务, port=8002")
    uvicorn.run(app, host="0.0.0.0", port=8002)
