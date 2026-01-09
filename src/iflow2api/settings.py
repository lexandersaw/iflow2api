"""应用配置管理 - 保存/加载用户配置"""

import json
import sys
import winreg
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from .config import load_iflow_config, IFlowConfig


class AppSettings(BaseModel):
    """应用配置"""
    # 服务器配置
    host: str = "0.0.0.0"
    port: int = 8000

    # iFlow 配置
    api_key: str = ""
    base_url: str = "https://apis.iflow.cn/v1"

    # 应用设置
    auto_start: bool = False  # 开机自启动
    start_minimized: bool = False  # 启动时最小化
    auto_run_server: bool = False  # 启动时自动运行服务


def get_config_dir() -> Path:
    """获取配置目录"""
    return Path.home() / ".iflow2api"


def get_config_path() -> Path:
    """获取配置文件路径"""
    return get_config_dir() / "config.json"


def load_settings() -> AppSettings:
    """加载配置"""
    config_path = get_config_path()

    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return AppSettings(**data)
        except Exception:
            pass

    # 尝试从 iFlow CLI 配置导入
    settings = AppSettings()
    try:
        iflow_config = load_iflow_config()
        settings.api_key = iflow_config.api_key
        settings.base_url = iflow_config.base_url
    except Exception:
        pass

    return settings


def save_settings(settings: AppSettings) -> None:
    """保存配置"""
    config_dir = get_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)

    config_path = get_config_path()
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(settings.model_dump(), f, indent=2, ensure_ascii=False)


def get_exe_path() -> str:
    """获取当前可执行文件路径"""
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包后
        return sys.executable
    else:
        # 开发模式
        return f'"{sys.executable}" -m iflow2api.gui'


def set_auto_start(enabled: bool) -> bool:
    """设置开机自启动 (Windows)"""
    if sys.platform != "win32":
        return False

    app_name = "iflow2api"
    exe_path = get_exe_path()

    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE
        )

        if enabled:
            winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, exe_path)
        else:
            try:
                winreg.DeleteValue(key, app_name)
            except FileNotFoundError:
                pass

        winreg.CloseKey(key)
        return True
    except Exception:
        return False


def get_auto_start() -> bool:
    """检查是否已设置开机自启动"""
    if sys.platform != "win32":
        return False

    app_name = "iflow2api"

    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0,
            winreg.KEY_QUERY_VALUE
        )

        try:
            winreg.QueryValueEx(key, app_name)
            winreg.CloseKey(key)
            return True
        except FileNotFoundError:
            winreg.CloseKey(key)
            return False
    except Exception:
        return False


def import_from_iflow_cli() -> Optional[IFlowConfig]:
    """从 iFlow CLI 导入配置"""
    try:
        return load_iflow_config()
    except Exception:
        return None
