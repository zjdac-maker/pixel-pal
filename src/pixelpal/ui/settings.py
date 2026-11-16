"""Settings window. Edits a copy of the config and writes it back only on OK."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
                               QHBoxLayout, QHeaderView, QLabel, QPushButton, QSlider, QSpinBox,
                               QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget)

from ..config import COLOUR_PRESETS, Automation, Config, QuickAction
from ..core.personality import REWARDS
from ..platform.base import Platform

KINDS = ("app", "folder", "url")


def _slider(value: float) -> QSlider:
    s = QSlider(Qt.Orientation.Horizontal)
    s.setRange(0, 100)
    s.setValue(round(value * 100))
    return s


def _spin(value: int, lo: int, hi: int, suffix: str = "") -> QSpinBox:
    s = QSpinBox()
    s.setRange(lo, hi)
    s.setValue(value)
    s.setSuffix(suffix)
    return s


class SettingsDialog(QDialog):
    def __init__(self, config: Config, platform: Platform, parent=None) -> None:
        super().__init__(parent)
        self.config, self.platform = config, platform
        self.setWindowTitle("pixel-pal settings")
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint)
        self.setMinimumWidth(520)
        tabs = QTabWidget()
        tabs.addTab(self._general(), "Behaviour")
        tabs.addTab(self._look(), "Look")
        tabs.addTab(self._helpers(), "Timers && alerts")
        tabs.addTab(self._actions(), "Quick actions")
        tabs.addTab(self._automations(), "Automations")
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        layout.addWidget(buttons)

    # -- tabs -------------------------------------------------------------------------------
    def _general(self) -> QWidget:
        c = self.config
        self.activity, self.chattiness = _slider(c.activity), _slider(c.chattiness)
        self.quiet = QCheckBox("Quiet mode (calmer, no unprompted chatter)")
        self.bubbles = QCheckBox("Show speech bubbles")
        self.follow = QCheckBox("Sometimes follow the mouse pointer")
        self.climbing = QCheckBox("Climb walls and windows")
        self.windows = QCheckBox("Walk and sit on application windows")
        self.fullscreen = QCheckBox("Hide while a full-screen app is in front")
        self.autostart = QCheckBox("Launch when I sign in to Windows")
        for box, value in ((self.quiet, c.quiet_mode), (self.bubbles, c.speech_bubbles),
                           (self.follow, c.follow_cursor), (self.climbing, c.climbing),
                           (self.windows, c.window_interaction), (self.fullscreen, c.hide_in_fullscreen)):
            box.setChecked(value)
        self.windows.setEnabled(self.platform.supports_windows)
        self.autostart.setEnabled(self.platform.supports_autostart)
        self.autostart.setChecked(self.platform.supports_autostart and self.platform.autostart_enabled())
        page = QWidget()
        form = QFormLayout(page)
        form.addRow("Activity (lazy ↔ lively)", self.activity)
        form.addRow("Chattiness (silent ↔ chatty)", self.chattiness)
        for box in (self.quiet, self.bubbles, self.follow, self.climbing, self.windows, self.fullscreen,
                    self.autostart):
            form.addRow(box)
        return page

    def _look(self) -> QWidget:
        c = self.config
        self.scale = _spin(c.scale, 2, 8, "×")
        self.colour = c.body_colour
        self.preset = QComboBox()
        for name, value in COLOUR_PRESETS.items():
            self.preset.addItem(name, value)
        self.preset.addItem("Custom…", "")
        idx = self.preset.findData(c.body_colour)
        self.preset.setCurrentIndex(idx if idx >= 0 else self.preset.count() - 1)
        self.preset.activated.connect(self._pick_colour)
        self.swatch = QLabel()
        self.swatch.setFixedSize(48, 22)
        self._show_swatch()
        row = QHBoxLayout()
        row.addWidget(self.preset, 1)
        row.addWidget(self.swatch)
        self.accessory = QComboBox()
        self.accessory.addItem("None", "none")
        for r in REWARDS:
            if c.tasks_done >= r.tasks_needed:
                self.accessory.addItem(r.label.capitalize(), r.accessory)
            else:
                self.accessory.addItem(f"{r.label.capitalize()} (after {r.tasks_needed} finished tasks)", r.accessory)
                self.accessory.model().item(self.accessory.count() - 1).setEnabled(False)
        self.accessory.setCurrentIndex(max(0, self.accessory.findData(c.accessory)))
        page = QWidget()
        form = QFormLayout(page)
        form.addRow("Size", self.scale)
        form.addRow("Colour", row)
        form.addRow("Accessory", self.accessory)
        form.addRow(QLabel(f"Tasks finished together: {c.tasks_done}. Timers and automations earn accessories."))
        return page

    def _pick_colour(self, index: int) -> None:
        value = self.preset.itemData(index)
        if not value:
            chosen = QColorDialog.getColor(QColor(self.colour), self, "Pick a body colour")
            if not chosen.isValid():
                return
            value = chosen.name()
        self.colour = value
        self._show_swatch()

    def _show_swatch(self) -> None:
        self.swatch.setStyleSheet(f"background: {self.colour}; border: 2px solid #3b2a3f;")

    def _helpers(self) -> QWidget:
        c = self.config
        self.pomodoro = _spin(c.pomodoro_minutes, 1, 180, " min")
        self.brk = _spin(c.break_minutes, 1, 60, " min")
        self.auto_break = QCheckBox("Start a break automatically after a focus session")
        self.auto_break.setChecked(c.auto_break)
        self.monitor = QCheckBox("Tell me about low battery and high CPU")
        self.monitor.setChecked(c.monitor_system)
        self.battery = _spin(c.battery_threshold, 5, 90, " %")
        self.cpu = _spin(c.cpu_threshold, 30, 100, " %")
        page = QWidget()
        form = QFormLayout(page)
        form.addRow("Focus session", self.pomodoro)
        form.addRow("Break", self.brk)
        form.addRow(self.auto_break)
        form.addRow(self.monitor)
        form.addRow("Battery warning below", self.battery)
        form.addRow("CPU warning above", self.cpu)
        return page

    def _table(self, headers: list[str]) -> tuple[QWidget, QTableWidget, QPushButton]:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.horizontalHeader().setSectionResizeMode(len(headers) - 1, QHeaderView.ResizeMode.Stretch)
        table.verticalHeader().setVisible(False)
        add, remove = QPushButton("Add"), QPushButton("Remove selected")
        remove.clicked.connect(lambda: table.removeRow(table.currentRow()) if table.currentRow() >= 0 else None)
        row = QHBoxLayout()
        row.addWidget(add)
        row.addWidget(remove)
        row.addStretch(1)
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.addWidget(table)
        layout.addLayout(row)
        return page, table, add

    def _actions(self) -> QWidget:
        page, self.actions_table, add = self._table(["Name", "Kind", "Target (program, folder or https link)"])
        for a in self.config.quick_actions:
            self._add_action(a)
        add.clicked.connect(lambda: self._add_action(QuickAction("New action", "app", "")))
        return page

    def _add_action(self, a: QuickAction) -> None:
        t = self.actions_table
        r = t.rowCount()
        t.insertRow(r)
        t.setItem(r, 0, QTableWidgetItem(a.name))
        kind = QComboBox()
        kind.addItems(KINDS)
        kind.setCurrentText(a.kind if a.kind in KINDS else "app")
        t.setCellWidget(r, 1, kind)
        t.setItem(r, 2, QTableWidgetItem(a.target))

    def _automations(self) -> QWidget:
        page, self.auto_table, add = self._table(["Name", "Command (runs directly, not through a shell)"])
        for a in self.config.automations:
            self._add_automation(a)
        add.clicked.connect(lambda: self._add_automation(Automation("New automation", "")))
        note = QLabel("You are asked to approve each command the first time it runs, and again whenever "
                      "its text changes. Commands run with your own user rights, never as administrator.")
        note.setWordWrap(True)
        page.layout().addWidget(note)
        return page

    def _add_automation(self, a: Automation) -> None:
        t = self.auto_table
        r = t.rowCount()
        t.insertRow(r)
        name = QTableWidgetItem(a.name)
        name.setData(Qt.ItemDataRole.UserRole, a.approved_hash)
        t.setItem(r, 0, name)
        t.setItem(r, 1, QTableWidgetItem(a.command))

    # -- result -----------------------------------------------------------------------------
    def apply(self) -> None:
        """Copy the widgets back into the config (call after the dialog was accepted)."""
        c = self.config
        c.activity, c.chattiness = self.activity.value() / 100, self.chattiness.value() / 100
        c.quiet_mode, c.speech_bubbles = self.quiet.isChecked(), self.bubbles.isChecked()
        c.follow_cursor, c.climbing = self.follow.isChecked(), self.climbing.isChecked()
        c.window_interaction, c.hide_in_fullscreen = self.windows.isChecked(), self.fullscreen.isChecked()
        c.scale, c.body_colour = self.scale.value(), self.colour
        c.accessory = self.accessory.currentData() or "none"
        c.pomodoro_minutes, c.break_minutes = self.pomodoro.value(), self.brk.value()
        c.auto_break, c.monitor_system = self.auto_break.isChecked(), self.monitor.isChecked()
        c.battery_threshold, c.cpu_threshold = self.battery.value(), self.cpu.value()
        t = self.actions_table
        c.quick_actions = [
            QuickAction(t.item(r, 0).text().strip(), t.cellWidget(r, 1).currentText(), t.item(r, 2).text().strip())
            for r in range(t.rowCount()) if t.item(r, 0).text().strip()]
        t = self.auto_table
        c.automations = [
            # The stored approval only stays valid if the command text is unchanged.
            Automation(t.item(r, 0).text().strip(), t.item(r, 1).text().strip(),
                       t.item(r, 0).data(Qt.ItemDataRole.UserRole) or "")
            for r in range(t.rowCount()) if t.item(r, 0).text().strip()]
        if self.platform.supports_autostart:
            try:
                if self.autostart.isChecked() != self.platform.autostart_enabled():
                    self.platform.set_autostart(self.autostart.isChecked())
            except OSError:
                pass
