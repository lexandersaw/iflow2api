"""服务管理 - 在后台线程运行 uvicorn"""

import asyncio
import threading
import time
from enum import Enum
from typing import Callable, Optional

import uvicorn

from .settings import AppSettings


class ServerState(Enum):
    """服务状态"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


class ServerManager:
    """服务管理器"""

    def __init__(self, on_state_change: Optional[Callable[[ServerState, str], None]] = None):
        self._state = ServerState.STOPPED
        self._thread: Optional[threading.Thread] = None
        self._server: Optional[uvicorn.Server] = None
        self._on_state_change = on_state_change
        self._error_message = ""
        self._settings: Optional[AppSettings] = None

    @property
    def state(self) -> ServerState:
        return self._state

    @property
    def error_message(self) -> str:
        return self._error_message

    def _set_state(self, state: ServerState, message: str = ""):
        self._state = state
        self._error_message = message
        if self._on_state_change:
            self._on_state_change(state, message)

    def start(self, settings: AppSettings) -> bool:
        """启动服务"""
        if self._state in (ServerState.RUNNING, ServerState.STARTING):
            return False

        if not settings.api_key:
            self._set_state(ServerState.ERROR, "API Key 未配置")
            return False

        self._settings = settings
        self._set_state(ServerState.STARTING)

        self._thread = threading.Thread(target=self._run_server, daemon=True)
        self._thread.start()
        return True

    def stop(self) -> bool:
        """停止服务"""
        if self._state not in (ServerState.RUNNING, ServerState.STARTING):
            return False

        self._set_state(ServerState.STOPPING)

        if self._server:
            self._server.should_exit = True

        # 等待线程结束
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

        self._set_state(ServerState.STOPPED)
        return True

    def _run_server(self):
        """在线程中运行服务"""
        try:
            # 动态设置配置
            from . import config as config_module
            from .config import IFlowConfig

            # 创建自定义配置
            custom_config = IFlowConfig(
                api_key=self._settings.api_key,
                base_url=self._settings.base_url,
            )

            # 替换 load_iflow_config 函数
            original_load = config_module.load_iflow_config

            def patched_load():
                return custom_config

            config_module.load_iflow_config = patched_load

            # 重置全局代理实例
            from . import app as app_module
            app_module._proxy = None
            app_module._config = None

            # 配置 uvicorn
            config = uvicorn.Config(
                "iflow2api.app:app",
                host=self._settings.host,
                port=self._settings.port,
                log_level="info",
                access_log=True,
            )

            self._server = uvicorn.Server(config)
            self._set_state(ServerState.RUNNING)

            # 运行服务
            asyncio.run(self._server.serve())

        except Exception as e:
            self._set_state(ServerState.ERROR, str(e))
        finally:
            self._server = None
            if self._state != ServerState.ERROR:
                self._set_state(ServerState.STOPPED)
