from __future__ import annotations
from local_ai_bridge.i18n import tr as _
import sys
from pathlib import Path


_WINDOWS_ICON_HANDLES: list[int] = []


def _set_windows_app_id() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "BridgAI.Desktop"
        )
    except (AttributeError, OSError):
        pass


def _icon_path() -> Path:
    filename = "app_icon.ico" if sys.platform == "win32" else "app_icon.png"
    return Path(__file__).resolve().parent / "resources" / filename


def _set_windows_taskbar_icon(window, icon_path: Path) -> bool:
    """Apply the ICO directly to the native HWND used by the Windows taskbar."""
    if sys.platform != "win32" or not icon_path.is_file():
        return False

    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        hwnd = wintypes.HWND(int(window.winId()))

        load_image = user32.LoadImageW
        load_image.argtypes = [
            wintypes.HINSTANCE,
            wintypes.LPCWSTR,
            wintypes.UINT,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.UINT,
        ]
        load_image.restype = wintypes.HANDLE

        send_message = user32.SendMessageW
        send_message.argtypes = [
            wintypes.HWND,
            wintypes.UINT,
            wintypes.WPARAM,
            wintypes.LPARAM,
        ]
        send_message.restype = ctypes.c_ssize_t

        get_system_metrics = user32.GetSystemMetrics
        get_system_metrics.argtypes = [ctypes.c_int]
        get_system_metrics.restype = ctypes.c_int

        image_icon = 1
        lr_load_from_file = 0x0010
        wm_seticon = 0x0080
        icon_small = 0
        icon_big = 1
        icon_small2 = 2
        sm_cxicon = 11
        sm_cyicon = 12
        sm_cxsmicon = 49
        sm_cysmicon = 50

        large_width = max(32, get_system_metrics(sm_cxicon))
        large_height = max(32, get_system_metrics(sm_cyicon))
        small_width = max(16, get_system_metrics(sm_cxsmicon))
        small_height = max(16, get_system_metrics(sm_cysmicon))

        large_handle = load_image(
            None,
            str(icon_path),
            image_icon,
            large_width,
            large_height,
            lr_load_from_file,
        )
        small_handle = load_image(
            None,
            str(icon_path),
            image_icon,
            small_width,
            small_height,
            lr_load_from_file,
        )
        if not large_handle or not small_handle:
            return False

        send_message(hwnd, wm_seticon, icon_big, int(large_handle))
        send_message(hwnd, wm_seticon, icon_small, int(small_handle))
        send_message(hwnd, wm_seticon, icon_small2, int(small_handle))

        # Qt sets the normal window icon correctly, but an interpreter-hosted
        # process can leave the native class icon pointing at pythonw.exe.
        # Updating the class icon as well makes the running taskbar button use
        # the BridgAI image instead of the generic application placeholder.
        set_class_icon = getattr(
            user32,
            "SetClassLongPtrW",
            getattr(user32, "SetClassLongW", None),
        )
        if set_class_icon is not None:
            set_class_icon.argtypes = [
                wintypes.HWND,
                ctypes.c_int,
                ctypes.c_ssize_t,
            ]
            set_class_icon.restype = ctypes.c_ssize_t
            set_class_icon(hwnd, -14, int(large_handle))  # GCLP_HICON
            set_class_icon(hwnd, -34, int(small_handle))  # GCLP_HICONSM

        _WINDOWS_ICON_HANDLES.extend(
            [int(large_handle), int(small_handle)]
        )
        return True
    except (AttributeError, OSError, TypeError, ValueError):
        return False


def main() -> int:
    # Windows must receive the explicit application identity before Qt creates
    # any native window or the shell can cache the pythonw.exe identity.
    _set_windows_app_id()

    try:
        from PySide6.QtCore import QTimer
        from PySide6.QtGui import QIcon
        from PySide6.QtWidgets import QApplication
    except ImportError:
        print(_("PySide6 non è installato. Esegui:\n  python -m pip install -r requirements.txt\npoi riavvia con:\n  python run.py"), file=sys.stderr)
        return 2

    from local_ai_bridge.core.settings import SettingsStore
    from local_ai_bridge.ui.main_window import MainWindow
    from local_ai_bridge.web.launcher import start_web_interface, stop_web_interface

    app = QApplication(sys.argv)
    app.setApplicationName("BridgAI")
    app.setOrganizationName("BridgAI")
    icon_path = _icon_path()
    if icon_path.is_file():
        app.setWindowIcon(QIcon(str(icon_path)))
    window = MainWindow()
    if not app.windowIcon().isNull():
        window.setWindowIcon(app.windowIcon())
    window.show()

    if sys.platform == "win32":
        # Reapply once the HWND exists and once more after the first event-loop
        # turn, because Windows/Qt can replace the class icon during show().
        _set_windows_taskbar_icon(window, icon_path)
        QTimer.singleShot(0, lambda: _set_windows_taskbar_icon(window, icon_path))
        QTimer.singleShot(250, lambda: _set_windows_taskbar_icon(window, icon_path))

    settings = SettingsStore().load()
    web_process = None

    def launch_web() -> None:
        nonlocal web_process
        if not settings.web_auto_start:
            return
        try:
            console_options = (
                {"show_console": True}
                if settings.windows_show_diagnostic_consoles
                else {}
            )
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
                **console_options,
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
                _("Interfaccia web disponibile: ") + info_url,
                8000,
            )
        except Exception as exc:
            message = _("Avvio interfaccia web non riuscito: ") + str(exc)
            window.statusBar().showMessage(message, 12000)
            print(message, file=sys.stderr, flush=True)

    def shutdown_web() -> None:
        if settings.web_stop_on_exit:
            stop_web_interface(web_process)

    app.aboutToQuit.connect(shutdown_web)
    QTimer.singleShot(0, launch_web)
    return app.exec()
