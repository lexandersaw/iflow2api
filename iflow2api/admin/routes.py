"""Web 管理界面路由"""

import asyncio
import platform
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from .auth import get_auth_manager
from .websocket import get_connection_manager


# 创建路由器
admin_router = APIRouter(prefix="/admin", tags=["Admin"])

# HTTP Bearer 认证方案
security = HTTPBearer(auto_error=False)


# 请求/响应模型
class LoginRequest(BaseModel):
    """登录请求"""
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    """修改密码请求"""
    old_password: str
    new_password: str


class CreateUserRequest(BaseModel):
    """创建用户请求"""
    username: str
    password: str


class SettingsUpdate(BaseModel):
    """设置更新请求"""
    host: Optional[str] = None
    port: Optional[int] = None
    auto_start: Optional[bool] = None
    start_minimized: Optional[bool] = None
    minimize_to_tray: Optional[bool] = None
    auto_run_server: Optional[bool] = None
    theme_mode: Optional[str] = None
    rate_limit_enabled: Optional[bool] = None
    rate_limit_per_minute: Optional[int] = None
    rate_limit_per_hour: Optional[int] = None
    rate_limit_per_day: Optional[int] = None
    preserve_reasoning_content: Optional[bool] = None
    language: Optional[str] = None


# 认证依赖
async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> str:
    """获取当前认证用户"""
    if credentials is None:
        raise HTTPException(status_code=401, detail="未提供认证令牌")
    
    auth_manager = get_auth_manager()
    username = auth_manager.verify_token(credentials.credentials)
    
    if username is None:
        raise HTTPException(status_code=401, detail="无效或过期的令牌")
    
    return username


# ==================== 认证相关 ====================

@admin_router.post("/login")
async def login(request: LoginRequest) -> dict[str, Any]:
    """用户登录"""
    auth_manager = get_auth_manager()
    
    # 如果没有用户，创建第一个用户
    if not auth_manager.has_users():
        auth_manager.create_user(request.username, request.password)
        token = auth_manager.authenticate(request.username, request.password)
        return {
            "success": True,
            "token": token,
            "message": "首次登录，已创建管理员账户",
            "is_first_login": True,
        }
    
    token = auth_manager.authenticate(request.username, request.password)
    if token is None:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    
    return {
        "success": True,
        "token": token,
        "message": "登录成功",
        "is_first_login": False,
    }


@admin_router.post("/logout")
async def logout(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict[str, Any]:
    """用户登出"""
    if credentials:
        auth_manager = get_auth_manager()
        auth_manager.logout(credentials.credentials)
    
    return {"success": True, "message": "已登出"}


@admin_router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    username: str = Depends(get_current_user),
) -> dict[str, Any]:
    """修改密码"""
    auth_manager = get_auth_manager()
    success = auth_manager.change_password(username, request.old_password, request.new_password)
    
    if not success:
        raise HTTPException(status_code=400, detail="原密码错误")
    
    return {"success": True, "message": "密码已修改"}


@admin_router.get("/check-setup")
async def check_setup() -> dict[str, Any]:
    """检查是否需要初始化设置"""
    auth_manager = get_auth_manager()
    return {
        "needs_setup": not auth_manager.has_users(),
        "has_users": auth_manager.has_users(),
    }


# ==================== 用户管理 ====================

@admin_router.get("/users")
async def get_users(username: str = Depends(get_current_user)) -> list[dict]:
    """获取用户列表"""
    auth_manager = get_auth_manager()
    return auth_manager.get_users()


@admin_router.post("/users")
async def create_user(
    request: CreateUserRequest,
    username: str = Depends(get_current_user),
) -> dict[str, Any]:
    """创建新用户"""
    auth_manager = get_auth_manager()
    success = auth_manager.create_user(request.username, request.password)
    
    if not success:
        raise HTTPException(status_code=400, detail="用户名已存在")
    
    return {"success": True, "message": "用户已创建"}


@admin_router.delete("/users/{target_username}")
async def delete_user(
    target_username: str,
    username: str = Depends(get_current_user),
) -> dict[str, Any]:
    """删除用户"""
    if target_username == username:
        raise HTTPException(status_code=400, detail="不能删除自己")
    
    auth_manager = get_auth_manager()
    success = auth_manager.delete_user(target_username)
    
    if not success:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    return {"success": True, "message": "用户已删除"}


# ==================== 系统状态 ====================

def _check_service_health(port: int, host: str = "127.0.0.1") -> tuple[bool, str]:
    """
    检查服务健康状态
    
    Returns:
        (is_healthy, error_message)
    """
    import socket
    import http.client
    
    # 首先检查端口是否在监听
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(1)
            result = s.connect_ex((host, port))
            if result != 0:
                return False, f"端口 {port} 未监听"
    except Exception as e:
        return False, f"端口检查失败: {str(e)}"
    
    # 然后检查 HTTP 健康端点
    try:
        conn = http.client.HTTPConnection(host, port, timeout=2)
        conn.request("GET", "/health")
        response = conn.getresponse()
        if response.status == 200:
            import json
            data = json.loads(response.read().decode())
            conn.close()
            if data.get("status") == "healthy":
                return True, ""
            else:
                return True, f"健康检查返回: {data.get('status')}"
        else:
            conn.close()
            return False, f"健康检查失败: HTTP {response.status}"
    except Exception as e:
        # 端口开放但健康检查失败，服务可能正在启动中
        return True, f"健康检查异常: {str(e)}"


@admin_router.get("/status")
async def get_status(username: str = Depends(get_current_user)) -> dict[str, Any]:
    """获取系统状态"""
    from ..settings import load_settings
    
    # 获取服务器管理器状态
    server_manager = _get_server_manager()
    manager_state = server_manager.state.value if server_manager else "stopped"
    manager_error = server_manager.error_message if server_manager else ""
    
    # 获取配置的端口
    settings = load_settings()
    configured_port = settings.port
    
    # 实际检查服务健康状态
    is_healthy, health_error = _check_service_health(configured_port)
    
    # 确定最终状态
    # 如果服务健康，则显示运行中，否则使用管理器状态
    if is_healthy:
        actual_state = "running"
        actual_error = ""
    else:
        actual_state = manager_state if manager_state != "running" else "stopped"
        actual_error = health_error or manager_error
    
    # 获取系统信息
    system_info = {
        "platform": platform.system(),
        "platform_version": platform.version(),
        "python_version": sys.version,
        "architecture": platform.machine(),
    }
    
    # 获取进程信息
    process_info = {
        "start_time": _get_process_start_time(),
        "uptime": time.time() - _process_start_time,
    }
    
    # 获取连接管理器状态
    connection_manager = get_connection_manager()
    
    return {
        "server": {
            "state": actual_state,
            "error_message": actual_error,
            "manager_state": manager_state,  # 保留管理器状态供调试
            "configured_port": configured_port,
        },
        "system": system_info,
        "process": process_info,
        "connections": {
            "websocket_count": connection_manager.connection_count,
        },
    }


@admin_router.get("/metrics")
async def get_metrics(username: str = Depends(get_current_user)) -> dict[str, Any]:
    """获取性能指标"""
    rate_limit_stats = {}
    proxy_stats = {}
    
    # 获取速率限制统计
    try:
        from ..ratelimit import get_rate_limiter as get_limiter
        limiter = get_limiter()
        if limiter:
            rate_limit_stats = limiter.get_stats()
    except Exception as e:
        rate_limit_stats = {"error": str(e)}
    
    # 获取代理统计
    try:
        from ..app import get_proxy
        proxy = get_proxy()
        if proxy and hasattr(proxy, 'get_stats'):
            proxy_stats = proxy.get_stats()
    except Exception as e:
        proxy_stats = {"error": str(e)}
    
    return {
        "rate_limit": rate_limit_stats,
        "proxy": proxy_stats,
        "timestamp": datetime.now().isoformat(),
    }


# ==================== 配置管理 ====================

@admin_router.get("/settings")
async def get_settings(username: str = Depends(get_current_user)) -> dict[str, Any]:
    """获取应用设置"""
    from ..settings import load_settings
    
    settings = load_settings()
    return {
        "host": settings.host,
        "port": settings.port,
        "auto_start": settings.auto_start,
        "start_minimized": settings.start_minimized,
        "minimize_to_tray": settings.minimize_to_tray,
        "auto_run_server": settings.auto_run_server,
        "theme_mode": settings.theme_mode,
        "rate_limit_enabled": settings.rate_limit_enabled,
        "rate_limit_per_minute": settings.rate_limit_per_minute,
        "rate_limit_per_hour": settings.rate_limit_per_hour,
        "rate_limit_per_day": settings.rate_limit_per_day,
        "preserve_reasoning_content": settings.preserve_reasoning_content,
        "language": settings.language,
        # 不返回敏感信息
    }


@admin_router.put("/settings")
async def update_settings(
    request: SettingsUpdate,
    username: str = Depends(get_current_user),
) -> dict[str, Any]:
    """更新应用设置"""
    from ..settings import load_settings, save_settings
    
    settings = load_settings()
    
    # 更新设置
    if request.host is not None:
        settings.host = request.host
    if request.port is not None:
        settings.port = request.port
    if request.auto_start is not None:
        settings.auto_start = request.auto_start
        # 同时设置系统自启动
        from ..settings import set_auto_start
        set_auto_start(request.auto_start)
    if request.start_minimized is not None:
        settings.start_minimized = request.start_minimized
    if request.minimize_to_tray is not None:
        settings.minimize_to_tray = request.minimize_to_tray
    if request.auto_run_server is not None:
        settings.auto_run_server = request.auto_run_server
    if request.theme_mode is not None:
        settings.theme_mode = request.theme_mode
    if request.rate_limit_enabled is not None:
        settings.rate_limit_enabled = request.rate_limit_enabled
    if request.rate_limit_per_minute is not None:
        settings.rate_limit_per_minute = request.rate_limit_per_minute
    if request.rate_limit_per_hour is not None:
        settings.rate_limit_per_hour = request.rate_limit_per_hour
    if request.rate_limit_per_day is not None:
        settings.rate_limit_per_day = request.rate_limit_per_day
    if request.preserve_reasoning_content is not None:
        settings.preserve_reasoning_content = request.preserve_reasoning_content
    if request.language is not None:
        settings.language = request.language
    
    save_settings(settings)
    
    # 广播设置变更
    connection_manager = get_connection_manager()
    await connection_manager.broadcast({
        "type": "settings_updated",
        "timestamp": datetime.now().isoformat(),
    })
    
    return {"success": True, "message": "设置已保存"}


# ==================== 服务器控制 ====================

@admin_router.post("/server/start")
async def start_server(username: str = Depends(get_current_user)) -> dict[str, Any]:
    """启动服务器"""
    from ..settings import load_settings
    
    server_manager = _get_server_manager()
    if server_manager is None:
        raise HTTPException(status_code=500, detail="服务器管理器未初始化")
    
    settings = load_settings()
    success = server_manager.start(settings)
    
    if not success:
        raise HTTPException(status_code=400, detail=server_manager.error_message or "启动失败")
    
    return {"success": True, "message": "服务器已启动"}


@admin_router.post("/server/stop")
async def stop_server(username: str = Depends(get_current_user)) -> dict[str, Any]:
    """停止服务器"""
    server_manager = _get_server_manager()
    if server_manager is None:
        raise HTTPException(status_code=500, detail="服务器管理器未初始化")
    
    success = server_manager.stop()
    
    if not success:
        raise HTTPException(status_code=400, detail="停止失败")
    
    return {"success": True, "message": "服务器已停止"}


@admin_router.post("/server/restart")
async def restart_server(username: str = Depends(get_current_user)) -> dict[str, Any]:
    """重启服务器"""
    from ..settings import load_settings
    
    server_manager = _get_server_manager()
    if server_manager is None:
        raise HTTPException(status_code=500, detail="服务器管理器未初始化")
    
    # 先停止
    server_manager.stop()
    
    # 等待停止完成
    await asyncio.sleep(1)
    
    # 重新启动
    settings = load_settings()
    success = server_manager.start(settings)
    
    if not success:
        raise HTTPException(status_code=400, detail=server_manager.error_message or "重启失败")
    
    return {"success": True, "message": "服务器已重启"}


# ==================== 日志查看 ====================

@admin_router.get("/logs")
async def get_logs(
    lines: int = 100,
    username: str = Depends(get_current_user),
) -> dict[str, Any]:
    """获取日志"""
    log_path = Path.home() / ".iflow2api" / "logs" / "app.log"
    
    if not log_path.exists():
        return {"logs": [], "message": "日志文件不存在"}
    
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
            recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
        
        return {
            "logs": [line.strip() for line in recent_lines],
            "total_lines": len(all_lines),
        }
    except Exception as e:
        return {"logs": [], "error": str(e)}


# ==================== WebSocket ====================

@admin_router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 连接端点"""
    connection_manager = get_connection_manager()
    await connection_manager.connect(websocket)
    
    try:
        while True:
            # 接收消息
            data = await websocket.receive_json()
            
            # 处理心跳
            if data.get("type") == "ping":
                await connection_manager.send_personal(websocket, {
                    "type": "pong",
                    "timestamp": datetime.now().isoformat(),
                })
            # 处理认证
            elif data.get("type") == "auth":
                token = data.get("token")
                if token:
                    auth_manager = get_auth_manager()
                    username = auth_manager.verify_token(token)
                    if username:
                        await connection_manager.send_personal(websocket, {
                            "type": "auth_success",
                            "username": username,
                        })
                    else:
                        await connection_manager.send_personal(websocket, {
                            "type": "auth_failed",
                            "message": "无效的令牌",
                        })
    except WebSocketDisconnect:
        await connection_manager.disconnect(websocket)
    except Exception:
        await connection_manager.disconnect(websocket)


# ==================== 辅助函数 ====================

# 进程启动时间
_process_start_time = time.time()


def _get_process_start_time() -> str:
    """获取进程启动时间"""
    return datetime.fromtimestamp(_process_start_time).isoformat()


# 服务器管理器引用
_server_manager: Optional[Any] = None


def set_server_manager(manager: Any) -> None:
    """设置服务器管理器引用"""
    global _server_manager
    _server_manager = manager


def _get_server_manager() -> Optional[Any]:
    """获取服务器管理器引用"""
    return _server_manager
