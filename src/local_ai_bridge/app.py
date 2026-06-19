from __future__ import annotations
from local_ai_bridge.i18n import tr as _
import sys
from pathlib import Path


def _set_windows_app_id() -> None:
    if sys.platform != 'win32':
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('LocalAIBridge.Desktop')
    except (AttributeError, OSError):
        pass


def _icon_path() -> Path:
    return Path(__file__).resolve().parent / 'resources' / 'app_icon.png'


def main() -> int:
    try:
        from PySide6.QtCore import QTimer
        from PySide6.QtGui import QIcon
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print(_('PySide6 non è installato. Esegui:\n  python -m pip install -r requirements.txt\npoi riavvia con:\n  python run.py'), file=sys.stderr)
        return 2

    from local_ai_bridge.core.settings import SettingsStore
    from local_ai_bridge.ui.main_window import MainWindow
    from local_ai_bridge.web.launcher import start_web_interface, stop_web_interface

    _set_windows_app_id()
    app = QApplication(sys.argv)
    app.setApplicationName('BridgAI')
    app.setOrganizationName('BridgAI')
    icon_path = _icon_path()
    if icon_path.is_file():
        app.setWindowIcon(QIcon(str(icon_path)))
    window = MainWindow()
    if not app.windowIcon().isNull():
        window.setWindowIcon(app.windowIcon())
    window.show()

    settings = SettingsStore().load()
    web_process = None

    def launch_web() -> None:
        nonlocal web_process
        if not settings.web_auto_start:
            return
        try:
            result = start_web_interface(
                settings.web_port,
                open_browser=settings.web_open_browser,
                workspace_root=settings.web_workspace_root or None,
                remote_access=settings.web_remote_access,
                username=settings.web_username or None,
                password_hash=settings.web_password_hash or None,
                totp_secret=(
                    settings.web_totp_secret
                    if settings.web_totp_enabled else None
                ),
                totp_local_bypass=settings.web_totp_local_bypass,
            )
            web_process = result.process
            info_url = result.url
            if settings.web_remote_access:
                from local_ai_bridge.web.network import local_ipv4_addresses
                ips = local_ipv4_addresses()
                if ips:
                    ips_str = ", ".join(f"http://{ip}:{settings.web_port}/" for ip in ips)
                    info_url = f"{result.url} (Rete locale: {ips_str})"
            window.statusBar().showMessage(
                _('Interfaccia web disponibile: ') + info_url,
                8000,
            )
        except Exception as exc:
            message = _('Avvio interfaccia web non riuscito: ') + str(exc)
            window.statusBar().showMessage(message, 12000)
            print(message, file=sys.stderr, flush=True)

    def shutdown_web() -> None:
        if settings.web_stop_on_exit:
            stop_web_interface(web_process)

    app.aboutToQuit.connect(shutdown_web)
    QTimer.singleShot(0, launch_web)
    return app.exec()
