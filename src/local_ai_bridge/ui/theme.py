from __future__ import annotations


def application_style(dark: bool = False) -> str:
    if dark:
        colors = {
            "window": "#111827", "surface": "#1f2937", "surface_alt": "#263244",
            "text": "#f3f4f6", "muted": "#aeb8c7", "border": "#3b4759",
            "primary": "#60a5fa", "primary_hover": "#3b82f6", "primary_soft": "#1e3a5f",
            "success": "#34d399", "success_hover": "#10b981", "danger": "#ef4444", "danger_hover": "#dc2626", "disabled": "#303b4b",
            "disabled_text": "#7f8a9b", "selection": "#315f96", "banner": "#172f4d",
            "banner_border": "#315f96", "banner_text": "#dbeafe",
        }
    else:
        colors = {
            "window": "#f4f6f8", "surface": "#ffffff", "surface_alt": "#f8fafc",
            "text": "#1f2937", "muted": "#667085", "border": "#d7dde5",
            "primary": "#2563eb", "primary_hover": "#1d4ed8", "primary_soft": "#e8f0ff",
            "success": "#059669", "success_hover": "#047857", "danger": "#dc2626", "danger_hover": "#b91c1c", "disabled": "#f3f4f6",
            "disabled_text": "#9ca3af", "selection": "#bfdbfe", "banner": "#eef6ff",
            "banner_border": "#bfdbfe", "banner_text": "#1e3a8a",
        }

    return f"""
    QMainWindow, QDialog, QWidget {{
        font-family: "Segoe UI", "Inter", sans-serif;
        font-size: 10pt;
        color: {colors['text']};
    }}
    QMainWindow, QDialog {{ background: {colors['window']}; }}
    QWidget#workflowPage, QWidget#operationsPage {{ background: {colors['window']}; }}
    QToolBar {{
        background: {colors['surface']}; border: 0; border-bottom: 1px solid {colors['border']};
        spacing: 8px; padding: 8px 12px;
    }}
    QToolButton {{ color: {colors['text']}; padding: 7px 10px; border-radius: 7px; }}
    QToolButton:hover {{ background: {colors['surface_alt']}; }}
    QTabWidget::pane {{ border: 0; background: {colors['window']}; }}
    QScrollArea#settingsScrollArea, QScrollArea#advancedScrollArea,
    QScrollArea#operationsScrollArea {{
        background: {colors['window']}; border: 0;
    }}
    QScrollArea#settingsScrollArea > QWidget > QWidget,
    QScrollArea#advancedScrollArea > QWidget > QWidget,
    QScrollArea#operationsScrollArea > QWidget > QWidget,
    QWidget#settingsScrollContent, QWidget#advancedScrollContent,
    QWidget#operationsScrollContent {{
        background: {colors['window']};
    }}
    QTabBar::tab {{
        background: transparent; padding: 10px 16px; margin-right: 4px;
        color: {colors['muted']}; border-bottom: 2px solid transparent;
    }}
    QTabBar::tab:selected {{ color: {colors['primary']}; border-bottom-color: {colors['primary']}; font-weight: 600; }}
    QGroupBox {{
        color: {colors['text']}; background: transparent; border: 1px solid {colors['border']};
        border-radius: 8px; margin-top: 10px; padding: 10px 10px 8px 10px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin; subcontrol-position: top left; left: 10px;
        padding: 0 5px; color: {colors['text']}; background: {colors['window']};
    }}
    QGroupBox[class="card"] {{
        background: {colors['surface']}; border: 1px solid {colors['border']};
        border-radius: 12px; margin-top: 0;
    }}
    QGroupBox[class="operationsCard"] {{
        background: {colors['surface']}; border: 1px solid {colors['border']};
        border-radius: 12px; margin-top: 10px;
    }}
    QGroupBox[class="operationsCard"]::title {{
        background: {colors['surface']}; color: {colors['text']};
        font-weight: 700; padding: 0 7px;
    }}
    QWidget[class="operationsFlow"] {{
        background: {colors['surface']}; border: 1px solid {colors['border']};
        border-radius: 12px;
    }}
    QLabel[class="flowPill"] {{
        background: {colors['primary_soft']}; color: {colors['primary']};
        border-radius: 14px; padding: 7px 10px; font-weight: 650;
    }}
    QLabel[class="stateBadge"] {{
        background: {colors['surface_alt']}; color: {colors['muted']};
        border: 1px solid {colors['border']}; border-radius: 11px;
        padding: 3px 10px; font-weight: 700;
    }}
    QLabel[class="stateBadge"][state="ready"] {{
        background: {colors['primary_soft']}; color: {colors['primary']};
        border-color: {colors['primary']};
    }}
    QLabel {{ color: {colors['text']}; background: transparent; }}
    QLabel[class="pageTitle"] {{ font-size: 22pt; font-weight: 700; color: {colors['text']}; }}
    QLabel[class="pageSubtitle"] {{ font-size: 11pt; color: {colors['muted']}; padding-bottom: 2px; }}
    QLabel[class="stepBadge"] {{
        background: {colors['primary_soft']}; color: {colors['primary']}; border-radius: 17px;
        font-weight: 700; font-size: 12pt;
    }}
    QLabel[class="stepTitle"] {{ font-size: 13pt; font-weight: 650; color: {colors['text']}; }}
    QLabel[class="stepDescription"], QLabel[class="muted"] {{ color: {colors['muted']}; }}
    QLabel[class="infoBanner"] {{
        background: {colors['banner']}; border: 1px solid {colors['banner_border']};
        border-radius: 10px; color: {colors['banner_text']}; padding: 12px 14px;
    }}
    QFrame[class="speechNote"] {{
        background: {colors['surface_alt']}; border: 1px solid {colors['border']}; border-radius: 10px;
    }}
    QPlainTextEdit, QTextEdit, QLineEdit, QComboBox {{
        min-height: 18px;
        background: {colors['surface']}; color: {colors['text']}; border: 1px solid {colors['border']};
        border-radius: 8px; padding: 8px; selection-background-color: {colors['selection']};
    }}
    QPlainTextEdit:focus, QTextEdit:focus, QLineEdit:focus, QComboBox:focus {{ border: 2px solid {colors['primary']}; }}
    QComboBox::drop-down {{
        subcontrol-origin: padding; subcontrol-position: top right;
        width: 26px; border: 0; background: transparent;
    }}
    QComboBox::down-arrow {{
        width: 0; height: 0; margin-right: 10px;
        border-left: 4px solid transparent; border-right: 4px solid transparent;
        border-top: 5px solid {colors['muted']};
    }}
    QComboBox QAbstractItemView {{
        background: {colors['surface']}; color: {colors['text']}; border: 1px solid {colors['border']};
        border-radius: 8px; outline: 0; selection-background-color: {colors['selection']};
        selection-color: {colors['text']}; padding: 4px;
    }}
    QTextEdit#operationsPlanPreview {{
        background: {colors['banner']}; color: {colors['banner_text']};
        border-color: {colors['banner_border']};
    }}
    QTextEdit#operationsWebStatus {{ background: {colors['surface_alt']}; }}
    QListWidget#operationsHistoryList::item {{ padding: 8px; }}
    QPushButton {{
        min-height: 34px; padding: 0 14px; border: 1px solid {colors['border']};
        border-radius: 8px; background: {colors['surface']}; color: {colors['text']}; font-weight: 600;
    }}
    QPushButton:hover {{ background: {colors['surface_alt']}; }}
    QPushButton[role="primary"] {{ background: {colors['primary']}; color: white; border-color: {colors['primary']}; }}
    QPushButton[role="primary"]:hover {{ background: {colors['primary_hover']}; }}
    QPushButton[role="success"] {{ background: {colors['success']}; color: white; border-color: {colors['success']}; }}
    QPushButton[role="success"]:hover {{ background: {colors['success_hover']}; }}
    QPushButton[role="danger"] {{ background: {colors['danger']}; color: white; border-color: {colors['danger']}; }}
    QPushButton[role="danger"]:hover {{ background: {colors['danger_hover']}; }}
    QPushButton[role="icon"] {{
        min-width: 38px; max-width: 38px; min-height: 38px; max-height: 38px;
        padding: 0; border-radius: 19px; font-size: 16pt;
        background: {colors['primary_soft']}; color: {colors['primary']}; border-color: transparent;
    }}
    QPushButton[role="icon"]:hover {{ border-color: {colors['primary']}; }}
    QPushButton[role="chip"] {{
        min-height: 24px; padding: 3px 12px; border-radius: 13px; font-weight: 600;
        background: {colors['primary_soft']}; color: {colors['primary']}; border: 1px solid transparent;
    }}
    QPushButton[role="chip"]:hover {{ background: {colors['selection']}; }}
    QPushButton:disabled {{ background: {colors['disabled']}; color: {colors['disabled_text']}; border-color: {colors['border']}; }}
    QListWidget#superpowerLibraryList {{ padding: 4px; }}
    QListWidget#superpowerLibraryList::item {{ border: 0; margin-bottom: 2px; }}
    QListWidget#superpowerLibraryList::item:selected {{ background: transparent; }}
    QTreeView, QTableWidget, QListWidget {{ background: {colors['surface']}; color: {colors['text']}; border: 1px solid {colors['border']}; border-radius: 8px; }}
    QTreeView::item:selected, QTableWidget::item:selected, QListWidget::item:selected {{
        background: {colors['selection']}; color: {colors['text']};
    }}
    QHeaderView::section {{ background: {colors['surface_alt']}; color: {colors['text']}; border: 0; border-bottom: 1px solid {colors['border']}; padding: 6px; }}
    QStatusBar {{ background: {colors['surface']}; border-top: 1px solid {colors['border']}; color: {colors['muted']}; }}
    QCheckBox {{ color: {colors['text']}; spacing: 8px; }}
    QScrollBar:vertical {{ background: {colors['window']}; width: 12px; margin: 0; }}
    QScrollBar::handle:vertical {{ background: {colors['border']}; min-height: 28px; border-radius: 6px; }}
    """
