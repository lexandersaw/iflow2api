"""Flet GUI 应用"""

import flet as ft
from datetime import datetime
from typing import Optional
import threading

from .settings import (
    AppSettings,
    load_settings,
    save_settings,
    set_auto_start,
    get_auto_start,
    import_from_iflow_cli,
)
from .server import ServerManager, ServerState
from .tray import TrayManager, is_tray_available
from .i18n import t, set_language, get_available_languages
from .ratelimit import RateLimitConfig, get_rate_limiter, update_rate_limiter_settings
import webbrowser
import asyncio


class IFlow2ApiApp:
    """iflow2api GUI 应用"""

    def __init__(self, page: ft.Page):
        self.page = page
        self.settings = load_settings()

        # 设置语言
        set_language(self.settings.language)

        # 设置 pubsub 用于线程安全的 UI 更��
        self.page.pubsub.subscribe(self._on_pubsub_message)

        self.server = ServerManager(
            on_state_change=self._on_server_state_change_threadsafe
        )

        # 系统托盘
        self.tray: Optional[TrayManager] = None
        self._is_quitting = False

        # UI 组件
        self.status_icon: Optional[ft.Icon] = None
        self.status_text: Optional[ft.Text] = None
        self.host_field: Optional[ft.TextField] = None
        self.port_field: Optional[ft.TextField] = None
        self.api_key_field: Optional[ft.TextField] = None
        self.base_url_field: Optional[ft.TextField] = None
        self.start_btn: Optional[ft.Button] = None
        self.stop_btn: Optional[ft.Button] = None
        self.log_list: Optional[ft.ListView] = None

        self._setup_page()
        self._build_ui()
        self._setup_tray()

        # 启动时自动运行服务
        if self.settings.auto_run_server:
            self._start_server(None)

        # 启动时最小化
        if self.settings.start_minimized:
            self.page.window.minimized = True

    def _setup_page(self):
        """设置页面"""
        self.page.title = "iflow2api"
        self.page.window.width = 500
        self.page.window.height = 800
        self.page.window.resizable = True
        self.page.window.min_width = 400
        self.page.window.min_height = 500
        self.page.padding = 20

        # 设置主题
        self._apply_theme()

        # 窗口关闭事件
        self.page.window.on_event = self._on_window_event

    def _apply_theme(self):
        """应用主题设置"""
        theme_mode = self.settings.theme_mode
        if theme_mode == "system":
            # 跟随系统主题
            self.page.theme_mode = ft.ThemeMode.SYSTEM
        elif theme_mode == "dark":
            self.page.theme_mode = ft.ThemeMode.DARK
        else:
            self.page.theme_mode = ft.ThemeMode.LIGHT

    def _on_window_event(self, e):
        """窗口事件处理"""
        if e.data == "close":
            # 检查是否最小化到托盘
            if self.settings.minimize_to_tray and is_tray_available():
                # 最小化到托盘而非退出
                self.page.window.minimized = True
                self.page.window.prevent_close = True
            else:
                # 停止服务并退出
                self._quit_app()

    def _setup_tray(self):
        """设置系统托盘"""
        if not is_tray_available():
            return

        self.tray = TrayManager(
            on_show_window=self._show_window_from_tray,
            on_start_server=self._start_server_from_tray,
            on_stop_server=self._stop_server_from_tray,
            on_quit=self._quit_app_from_tray,
        )
        self.tray.start()

    def _show_window_from_tray(self):
        """从托盘显示主窗口"""
        try:
            self.page.window.minimized = False
            self.page.window.focused = True
            self.page.update()
        except Exception:
            pass

    def _start_server_from_tray(self):
        """从托盘启动服务"""
        self._start_server(None)

    def _stop_server_from_tray(self):
        """从托盘停止服务"""
        self._stop_server(None)

    def _quit_app_from_tray(self):
        """从托盘退出应用"""
        self._is_quitting = True
        self._quit_app()

    def _quit_app(self):
        """退出应用"""
        self.server.stop()
        if self.tray:
            self.tray.stop()
        try:
            self.page.window.prevent_close = False
            self.page.window.close()
        except Exception:
            pass

    def _build_ui(self):
        """构建 UI"""
        # 状态栏
        self.status_icon = ft.Icon(ft.Icons.CIRCLE, color=ft.Colors.GREY, size=16)
        self.status_text = ft.Text(t("server.status_stopped"), size=14)

        status_row = ft.Container(
            content=ft.Row([self.status_icon, self.status_text]),
            padding=10,
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            border_radius=8,
        )

        # 服务器配置
        self.host_field = ft.TextField(
            label=t("server.host"),
            value=self.settings.host,
            hint_text="0.0.0.0",
            expand=True,
        )
        self.port_field = ft.TextField(
            label=t("server.port"),
            value=str(self.settings.port),
            hint_text="28000",
            keyboard_type=ft.KeyboardType.NUMBER,
            width=120,
        )

        server_config = ft.Container(
            content=ft.Column(
                [
                    ft.Text(t("server.config"), weight=ft.FontWeight.BOLD),
                    ft.Row([self.host_field, self.port_field]),
                ]
            ),
            padding=15,
            border=ft.Border.all(1, ft.Colors.OUTLINE),
            border_radius=8,
        )

        # iFlow 配置
        self.api_key_field = ft.TextField(
            label=t("iflow.api_key"),
            value=self.settings.api_key,
            password=True,
            can_reveal_password=True,
            expand=True,
        )
        self.base_url_field = ft.TextField(
            label=t("iflow.base_url"),
            value=self.settings.base_url,
            hint_text="https://apis.iflow.cn/v1",
        )

        import_btn = ft.TextButton(
            t("iflow.import_from_cli"),
            icon=ft.Icons.DOWNLOAD,
            on_click=self._import_from_cli,
        )

        oauth_login_btn = ft.Button(
            t("iflow.login_with_iflow"),
            icon=ft.Icons.LOGIN,
            on_click=self._login_with_iflow_oauth,
            style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE, color=ft.Colors.WHITE),
        )

        iflow_config = ft.Container(
            content=ft.Column(
                [
                    ft.Text(t("iflow.config"), weight=ft.FontWeight.BOLD),
                    self.api_key_field,
                    self.base_url_field,
                    ft.Row(
                        [import_btn, oauth_login_btn],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                ]
            ),
            padding=15,
            border=ft.Border.all(1, ft.Colors.OUTLINE),
            border_radius=8,
        )

        # 应用设置按钮
        settings_btn = ft.Button(
            t("settings.app_settings"),
            icon=ft.Icons.SETTINGS,
            on_click=self._show_settings_dialog,
            style=ft.ButtonStyle(
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            ),
        )

        app_settings_row = ft.Container(
            content=ft.Row(
                [settings_btn],
                alignment=ft.MainAxisAlignment.START,
            ),
        )

        # 操作按钮
        self.start_btn = ft.Button(
            t("button.start"),
            icon=ft.Icons.PLAY_ARROW,
            on_click=self._start_server,
            style=ft.ButtonStyle(bgcolor=ft.Colors.GREEN, color=ft.Colors.WHITE),
        )
        self.stop_btn = ft.Button(
            t("button.stop"),
            icon=ft.Icons.STOP,
            on_click=self._stop_server,
            disabled=True,
            style=ft.ButtonStyle(bgcolor=ft.Colors.RED, color=ft.Colors.WHITE),
        )
        save_btn = ft.Button(
            t("button.save"),
            icon=ft.Icons.SAVE,
            on_click=self._save_settings,
        )

        buttons_row = ft.Row(
            [self.start_btn, self.stop_btn, save_btn],
            alignment=ft.MainAxisAlignment.CENTER,
        )

        # 日志区域
        self.log_list = ft.ListView(
            expand=True,
            spacing=2,
            auto_scroll=True,
        )

        log_container = ft.Container(
            content=ft.Column(
                [
                    ft.Text(t("log_title"), weight=ft.FontWeight.BOLD),
                    ft.Container(
                        content=self.log_list,
                        height=150,
                        border=ft.Border.all(1, ft.Colors.OUTLINE),
                        border_radius=8,
                        padding=10,
                    ),
                ]
            ),
        )

        # 组装页面
        self.page.add(
            ft.Column(
                [
                    status_row,
                    server_config,
                    iflow_config,
                    app_settings_row,
                    buttons_row,
                    log_container,
                ],
                spacing=15,
                expand=True,
            )
        )

        self._add_log(t("log.app_started"))

    def _show_snack_bar(self, message: str, color: str = ft.Colors.GREEN):
        """显示 SnackBar 提示"""
        sb = ft.SnackBar(content=ft.Text(message), bgcolor=color)
        if hasattr(self.page, "open"):
            try:
                self.page.open(sb)
            except Exception:
                self.page.snack_bar = sb
                sb.open = True
                self.page.update()
        else:
            self.page.snack_bar = sb
            sb.open = True
            self.page.update()

    def _add_log(self, message: str):
        """添加日志"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_list.controls.append(
            ft.Text(f"[{timestamp}] {message}", size=12, selectable=True)
        )
        # 限制日志数量
        if len(self.log_list.controls) > 100:
            self.log_list.controls.pop(0)
        self.page.update()

    def _on_pubsub_message(self, message):
        """处理 pubsub 消息 - 在主线程中执行"""
        if not isinstance(message, dict):
            return
        
        msg_type = message.get("type")
        
        if msg_type == "server_state":
            state = message["state"]
            msg = message["message"]
            self._on_server_state_change(state, msg)
        
        elif msg_type == "oauth_success":
            # OAuth 登录成功，更新 UI
            api_key = message.get("api_key", "")
            base_url = message.get("base_url", "")
            self.api_key_field.value = api_key
            self.base_url_field.value = base_url
            self.settings.api_key = api_key
            self.settings.base_url = base_url
            self._add_log(t("log.config_updated"))
            self._show_snack_bar(t("message.login_success"))
            self.page.update()
        
        elif msg_type == "add_log":
            # 从后台线程添加日志
            log_msg = message.get("message", "")
            self._add_log(log_msg)

    def _on_server_state_change_threadsafe(self, state: ServerState, message: str):
        """服务状态变化回调 - 线程安全版本，从后台线程调用"""
        # 通过 pubsub 发送消息到主线程
        try:
            self.page.pubsub.send_all(
                {"type": "server_state", "state": state, "message": message}
            )
        except Exception:
            pass

    def _on_server_state_change(self, state: ServerState, message: str):
        """服务状态变化回调 - 必须在主线程调用"""
        state_config = {
            ServerState.STOPPED: (ft.Colors.GREY, t("server.status_stopped")),
            ServerState.STARTING: (ft.Colors.ORANGE, t("server.status_starting")),
            ServerState.RUNNING: (
                ft.Colors.GREEN,
                t("server.status_running", url=f"http://{self.settings.host}:{self.settings.port}"),
            ),
            ServerState.STOPPING: (ft.Colors.ORANGE, t("server.status_stopping")),
            ServerState.ERROR: (ft.Colors.RED, t("server.status_error", error=message)),
        }

        color, text = state_config.get(state, (ft.Colors.GREY, t("server.status_unknown")))
        self.status_icon.color = color
        self.status_text.value = text

        # 更新按钮状态
        is_running = state == ServerState.RUNNING
        is_busy = state in (ServerState.STARTING, ServerState.STOPPING)
        self.start_btn.disabled = is_running or is_busy
        self.stop_btn.disabled = not is_running or is_busy

        # 更新托盘状态
        if self.tray:
            if state == ServerState.STARTING:
                self.tray.update_status(False, "starting")
            elif state == ServerState.RUNNING:
                self.tray.update_status(True, "normal")
            elif state == ServerState.ERROR:
                self.tray.update_status(False, "error")
            else:
                self.tray.update_status(False, "normal")

        self._add_log(text)
        self.page.update()

    def _start_server(self, e):
        """启动服务"""
        self._update_settings_from_ui()
        if self.server.start(self.settings):
            self._add_log(t("log.server_starting"))

    def _stop_server(self, e):
        """停止服务"""
        if self.server.stop():
            self._add_log(t("log.server_stopping"))

    def _save_settings(self, e):
        """保存配置"""
        self._update_settings_from_ui()
        save_settings(self.settings)
        self._add_log(t("log.settings_saved"))

        # 显示提示
        self._show_snack_bar(t("message.settings_saved"))

    def _show_settings_dialog(self, e):
        """显示应用设置对话框"""
        # 创建对话框中的设置组件
        # === 启动设置 ===
        auto_start_checkbox = ft.Checkbox(
            label=t("settings.auto_start"),
            value=get_auto_start(),
        )
        start_minimized_checkbox = ft.Checkbox(
            label=t("settings.start_minimized"),
            value=self.settings.start_minimized,
        )
        minimize_to_tray_checkbox = ft.Checkbox(
            label=t("settings.minimize_to_tray"),
            value=self.settings.minimize_to_tray,
            disabled=not is_tray_available(),
        )
        auto_run_checkbox = ft.Checkbox(
            label=t("settings.auto_run_server"),
            value=self.settings.auto_run_server,
        )
        
        # === 内容处理设置 ===
        preserve_reasoning_checkbox = ft.Checkbox(
            label=t("settings.preserve_reasoning_content"),
            value=self.settings.preserve_reasoning_content,
            tooltip=t("settings.preserve_reasoning_content_hint"),
        )
        
        # === 外观设置 ===
        theme_dropdown = ft.Dropdown(
            label=t("settings.theme_mode"),
            options=[
                ft.dropdown.Option("system", t("settings.theme.system")),
                ft.dropdown.Option("light", t("settings.theme.light")),
                ft.dropdown.Option("dark", t("settings.theme.dark")),
            ],
            value=self.settings.theme_mode,
            width=200,
        )

        # 语言下拉框
        available_languages = get_available_languages()
        language_dropdown = ft.Dropdown(
            label=t("settings.language"),
            options=[
                ft.dropdown.Option(lang_code, lang_name)
                for lang_code, lang_name in available_languages.items()
            ],
            value=self.settings.language,
            width=200,
        )
        
        # === 速率限制设置 ===
        rate_limit_enabled_checkbox = ft.Checkbox(
            label=t("settings.rate_limit_enabled"),
            value=self.settings.rate_limit_enabled,
        )
        
        requests_per_minute_field = ft.TextField(
            label=t("settings.requests_per_minute"),
            value=str(self.settings.rate_limit_per_minute),
            keyboard_type=ft.KeyboardType.NUMBER,
            width=150,
        )
        
        requests_per_hour_field = ft.TextField(
            label=t("settings.requests_per_hour"),
            value=str(self.settings.rate_limit_per_hour),
            keyboard_type=ft.KeyboardType.NUMBER,
            width=150,
        )
        
        requests_per_day_field = ft.TextField(
            label=t("settings.requests_per_day"),
            value=str(self.settings.rate_limit_per_day),
            keyboard_type=ft.KeyboardType.NUMBER,
            width=150,
        )

        def on_save(e):
            """保存设置"""
            # 更新开机自启动
            if auto_start_checkbox.value != get_auto_start():
                success = set_auto_start(auto_start_checkbox.value)
                if not success:
                    self._add_log(t("log.auto_start_failed"))
            
            # 更新其他设置
            self.settings.start_minimized = start_minimized_checkbox.value
            self.settings.minimize_to_tray = minimize_to_tray_checkbox.value
            self.settings.auto_run_server = auto_run_checkbox.value
            self.settings.preserve_reasoning_content = preserve_reasoning_checkbox.value
            self.settings.theme_mode = theme_dropdown.value or "system"
            
            # 更新语言设置
            new_language = language_dropdown.value or "zh"
            if new_language != self.settings.language:
                self.settings.language = new_language
                set_language(new_language)
                self._add_log(t("log.language_changed", language=available_languages.get(new_language, new_language)))
            
            # 更新速率限制设置
            try:
                per_minute = int(requests_per_minute_field.value or "60")
                per_hour = int(requests_per_hour_field.value or "1000")
                per_day = int(requests_per_day_field.value or "10000")
            except ValueError:
                per_minute, per_hour, per_day = 60, 1000, 10000
            
            self.settings.rate_limit_enabled = rate_limit_enabled_checkbox.value
            self.settings.rate_limit_per_minute = per_minute
            self.settings.rate_limit_per_hour = per_hour
            self.settings.rate_limit_per_day = per_day
            
            # 更新全局速率限制器
            update_rate_limiter_settings(per_minute, per_hour, per_day)
            
            # 应用主题
            self._apply_theme()
            
            # 保存设置到文件
            save_settings(self.settings)
            
            self._add_log(t("log.settings_saved"))
            self._show_snack_bar(t("message.settings_saved"))
            
            # 关闭对话框
            if hasattr(self.page, "close"):
                self.page.close(dlg)
            else:
                dlg.open = False
                self.page.update()

        def on_cancel(e):
            """取消"""
            if hasattr(self.page, "close"):
                self.page.close(dlg)
            else:
                dlg.open = False
                self.page.update()

        # 创建可滚动的内容
        settings_content = ft.Column(
            [
                # 启动设置
                ft.Text(t("settings.section.startup"), weight=ft.FontWeight.BOLD, size=14),
                auto_start_checkbox,
                start_minimized_checkbox,
                minimize_to_tray_checkbox,
                auto_run_checkbox,
                
                ft.Divider(),
                
                # 内容处理设置
                ft.Text(t("settings.section.content"), weight=ft.FontWeight.BOLD, size=14),
                preserve_reasoning_checkbox,
                
                ft.Divider(),
                
                # 外观设置
                ft.Text(t("settings.section.appearance"), weight=ft.FontWeight.BOLD, size=14),
                ft.Row([theme_dropdown], alignment=ft.MainAxisAlignment.START),
                ft.Row([language_dropdown], alignment=ft.MainAxisAlignment.START),
                
                ft.Divider(),
                
                # 速率限制设置
                ft.Text(t("settings.section.rate_limit"), weight=ft.FontWeight.BOLD, size=14),
                rate_limit_enabled_checkbox,
                ft.Row(
                    [requests_per_minute_field, requests_per_hour_field],
                    alignment=ft.MainAxisAlignment.START,
                ),
                ft.Row(
                    [requests_per_day_field],
                    alignment=ft.MainAxisAlignment.START,
                ),
            ],
            spacing=10,
        )

        dlg = ft.AlertDialog(
            title=ft.Text(t("settings.title")),
            content=ft.Container(
                content=ft.Column(
                    [settings_content],
                    scroll=ft.ScrollMode.AUTO,
                ),
                width=400,
                height=450,
            ),
            actions=[
                ft.TextButton(t("button.cancel"), on_click=on_cancel),
                ft.TextButton(t("button.confirm"), on_click=on_save),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        # 打开对话框
        if hasattr(self.page, "open"):
            self.page.open(dlg)
        else:
            dlg.open = True
            self.page.add(dlg)
            self.page.update()

    def _update_settings_from_ui(self):
        """从 UI 更新配置"""
        self.settings.host = self.host_field.value or "0.0.0.0"
        try:
            self.settings.port = int(self.port_field.value or "28000")
        except ValueError:
            self.settings.port = 28000
        self.settings.api_key = self.api_key_field.value or ""
        self.settings.base_url = self.base_url_field.value or "https://apis.iflow.cn/v1"

    def _import_from_cli(self, e):
        """从 iFlow CLI 导入配置"""
        config = import_from_iflow_cli()
        if config:
            self.api_key_field.value = config.api_key
            self.base_url_field.value = config.base_url
            self.page.update()
            self._add_log(t("log.import_success"))
            self._show_snack_bar(t("message.import_success"))
        else:
            self._add_log(t("log.import_failed"))
            self._show_snack_bar(t("message.import_failed"), color=ft.Colors.RED)

    def _add_log_threadsafe(self, message: str):
        """线程安全的添加日志 - 从后台线程调用"""
        try:
            self.page.pubsub.send_all({"type": "add_log", "message": message})
        except Exception:
            pass

    def _login_with_iflow_oauth(self, e):
        """使用 iFlow OAuth 登录"""
        from .oauth_login import OAuthLoginHandler

        def on_login_success(config):
            """OAuth 登录成功后的回调 - 在后台线程中执行"""
            # 通过 pubsub 发送消息到主线程更新 UI
            try:
                self.page.pubsub.send_all({
                    "type": "oauth_success",
                    "api_key": config.api_key,
                    "base_url": config.base_url,
                })
            except Exception:
                pass

        handler = OAuthLoginHandler(self._add_log_threadsafe, success_callback=on_login_success)
        handler.start_login()


def main(page: ft.Page):
    """Flet 应用入口"""
    IFlow2ApiApp(page)


if __name__ == "__main__":
    ft.run(main)
