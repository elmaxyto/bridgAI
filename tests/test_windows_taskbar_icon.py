from __future__ import annotations

from pathlib import Path
import sys
import types


i18n_stub = types.ModuleType("local_ai_bridge.i18n")
i18n_stub.tr = lambda text: text
sys.modules.setdefault("local_ai_bridge.i18n", i18n_stub)

import local_ai_bridge.app as app_module


class _NativeFunction:
    def __init__(self, result=None):
        self.result = result
        self.calls: list[tuple[object, ...]] = []
        self.argtypes = None
        self.restype = None

    def __call__(self, *args):
        self.calls.append(args)
        if callable(self.result):
            return self.result(*args)
        return self.result


class _FakeUser32:
    def __init__(self):
        self.GetSystemMetrics = _NativeFunction(
            lambda metric: {11: 32, 12: 32, 49: 16, 50: 16}[metric]
        )
        self.LoadImageW = _NativeFunction(
            lambda _instance, _path, _kind, width, _height, _flags: (
                101 if width >= 32 else 202
            )
        )
        self.SendMessageW = _NativeFunction(0)
        self.SetClassLongPtrW = _NativeFunction(0)


class _FakeWindow:
    def winId(self) -> int:
        return 777


def test_native_windows_icon_is_sent_to_window_and_class(monkeypatch, tmp_path: Path):
    icon = tmp_path / "app.ico"
    icon.write_bytes(b"ico")
    user32 = _FakeUser32()

    import ctypes

    monkeypatch.setattr(app_module.sys, "platform", "win32")
    monkeypatch.setattr(ctypes, "windll", type("Windll", (), {"user32": user32})(), raising=False)
    app_module._WINDOWS_ICON_HANDLES.clear()

    assert app_module._set_windows_taskbar_icon(_FakeWindow(), icon) is True

    assert [call[2:] for call in user32.SendMessageW.calls] == [
        (1, 101),
        (0, 202),
        (2, 202),
    ]
    assert [call[1:] for call in user32.SetClassLongPtrW.calls] == [
        (-14, 101),
        (-34, 202),
    ]
    assert app_module._WINDOWS_ICON_HANDLES == [101, 202]


def test_native_windows_icon_is_skipped_outside_windows(monkeypatch, tmp_path: Path):
    icon = tmp_path / "app.ico"
    icon.write_bytes(b"ico")
    monkeypatch.setattr(app_module.sys, "platform", "linux")

    assert app_module._set_windows_taskbar_icon(_FakeWindow(), icon) is False
