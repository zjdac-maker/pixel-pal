"""Builds the compact right-click / tray menu from ability MenuItems."""
from __future__ import annotations

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu

from ..abilities.base import MenuItem

STYLE = """
QMenu { background: #fffcf0; color: #3b2a3f; border: 2px solid #3b2a3f; padding: 3px; font-weight: bold; }
QMenu::item { padding: 4px 22px 4px 18px; }
QMenu::item:selected { background: #8fd9a8; }
QMenu::item:disabled { color: #a79aa8; }
QMenu::separator { height: 2px; background: #e6dcc8; margin: 3px 6px; }
"""


def build_menu(items: list[MenuItem], parent=None) -> QMenu:
    menu = QMenu(parent)
    menu.setStyleSheet(STYLE)
    _fill(menu, items)
    return menu


def _fill(menu: QMenu, items: list[MenuItem]) -> None:
    for item in items:
        if item.separator:
            menu.addSeparator()
        elif item.children:
            sub = menu.addMenu(item.label)
            sub.setStyleSheet(STYLE)
            _fill(sub, item.children)
        else:
            action = QAction(item.label, menu)
            action.setEnabled(item.enabled and item.action is not None)
            if item.checked is not None:
                action.setCheckable(True)
                action.setChecked(item.checked)
            if item.action is not None:
                action.triggered.connect(lambda _checked=False, fn=item.action: fn())
            menu.addAction(action)
