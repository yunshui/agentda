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
from datetime import datetime, timezone
import json
import os

from logging_lib import setup_logging, AccessLogMiddleware, user_id_var

app = FastAPI(title="后台 API")

# Setup logging
app_logger, access_logger = setup_logging("api-core", access_log_name="api-acc", log_dir="/data/logs/api-core")
app.add_middleware(AccessLogMiddleware, app_logger=app_logger, access_logger=access_logger, skip_path_prefix="/api")

# 加载模拟用户数据
DATA_FILE = os.path.join(os.path.dirname(__file__), "users.json")
with open(DATA_FILE, encoding="utf-8") as f:
    USERS = json.load(f)

# 导入财务配置
from dictionary import (
    FINANCE_DICTIONARY,
    ALLOWED_METRICS,
    USER_BRANCH_MAPPING,
    get_metric_unit,
    get_metric_display_name,
    get_simulated_data,
)


# ==================== 用户相关端点 ====================

@app.get("/api/user/{user_id}")
async def get_user(user_id: str):
    """
    查询用户信息

    Args:
        user_id: 9位数字用户编号

    Returns:
        用户信息字典

    Raises:
        400: 用户编号格式错误
        404: 用户不存在
    """
    # 验证用户编号格式
    if not user_id.isdigit() or len(user_id) != 9:
        app_logger.warning(f"用户编号格式错误: {user_id}")
        raise HTTPException(400, "用户编号必须为9位数字")

    # 设置 MDC 用户上下文
    user_id_var.set(user_id)

    # 查询用户
    user = USERS.get(user_id)
    if not user:
        app_logger.warning(f"用户不存在: {user_id}")
        raise HTTPException(404, "用户不存在")

    app_logger.info(f"用户信息查询成功: {user_id}")
    return user


@app.get("/api/admin/{user_id}/users")
async def get_all_users(user_id: str):
    """
    管理员查询所有用户信息（不含金额）

    只有 admin 角色的用户才能调用此接口。
    返回所有用户的基本信息，不包括 balance 字段。

    Args:
        user_id: 9位数字用户编号（调用者）

    Returns:
        用户列表，每个用户包含 user_id, name, department, role

    Raises:
        400: 用户编号格式错误
        403: 非管理员用户
        404: 用户不存在
    """
    # 验证用户编号格式
    if not user_id.isdigit() or len(user_id) != 9:
        app_logger.warning(f"用户编号格式错误: {user_id}")
        raise HTTPException(400, "用户编号必须为9位数字")

    # 设置 MDC 用户上下文
    user_id_var.set(user_id)

    # 查询调用者
    caller = USERS.get(user_id)
    if not caller:
        app_logger.warning(f"用户不存在: {user_id}")
        raise HTTPException(404, "用户不存在")

    # 检查是否为管理员
    if caller.get("role") != "admin":
        app_logger.warning(f"非管理员尝试查询用户列表: {user_id}")
        raise HTTPException(403, "需要管理员权限")

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
async def get_finance_dictionary():
    """
    获取财务指标元数据字典

    纯静态返回，无需数据库查询。
    用于 AI 进行语义匹配和指标选择。
    """
    return FINANCE_DICTIONARY


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
    1. 白名单验证 - 只允许查询字典中定义的指标
    2. RLS 行级安全 - 强制过滤 branch_id
    3. 参数化查询 - 防止 SQL 注入

    Args:
        metric: 指标名（必须是字典中的 standard_name）
        year: 年份（如 2025），不指定则返回最近数据
        quarter: 季度（1-4）
        month: 月份（1-12）
        granularity: 聚合粒度（yearly/quarterly/monthly）
        x_user_id: 用户编号（从 Header 传入）

    Returns:
        财务数据结果

    Raises:
        400: 参数格式错误
    """
    # 1. 验证用户编号
    if not x_user_id or not x_user_id.isdigit() or len(x_user_id) != 9:
        app_logger.warning(f"用户编号格式错误: {x_user_id}")
        raise HTTPException(400, "用户编号格式错误")

    # 设置 MDC 用户上下文
    user_id_var.set(x_user_id)

    # 2. 白名单验证
    if metric not in ALLOWED_METRICS:
        app_logger.warning(f"不支持的指标: {metric}, user={x_user_id}")
        raise HTTPException(400, f"不支持的指标: {metric}。请先调用 /api/finance/dictionary 获取支持的指标列表")

    # 3. 参数校验
    if quarter is not None and (quarter < 1 or quarter > 4):
        raise HTTPException(400, "季度必须在 1-4 之间")

    if month is not None and (month < 1 or month > 12):
        raise HTTPException(400, "月份必须在 1-12 之间")

    if granularity not in ["yearly", "quarterly", "monthly"]:
        raise HTTPException(400, "granularity 必须是 yearly/quarterly/monthly")

    # 4. RLS：获取机构代码
    branch_id = USER_BRANCH_MAPPING.get(x_user_id, "BR000")

    # 5. 获取模拟数据
    data = get_simulated_data(
        metric=metric,
        branch_id=branch_id,
        year=year,
        quarter=quarter,
        month=month,
        granularity=granularity
    )

    # 6. 构造返回结果
    app_logger.info(
        f"财务指标查询成功: metric={metric}, branch={branch_id}, "
        f"year={year}, quarter={quarter}, month={month}, granularity={granularity}, "
        f"data_points={len(data)}"
    )
    return {
        "metric": metric,
        "metric_name": get_metric_display_name(metric),
        "unit": get_metric_unit(metric),
        "branch_id": branch_id,
        "granularity": granularity,
        "data": data,
        "query_time": datetime.now(timezone.utc).isoformat()
    }


# ==================== 健康检查 ====================

@app.get("/api/health")
async def health():
    """健康检查"""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    app_logger.info("启动后台 API 服务, port=8002")
    uvicorn.run(app, host="0.0.0.0", port=8002)
