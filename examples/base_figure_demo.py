"""Run a small BaseFigureWidget demo."""

from __future__ import annotations

import sys

import numpy as np
from PyQt6 import QtWidgets

from pyqt_widget_kit import BaseFigureWidget


class BaseFigureDemo(QtWidgets.QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("BaseFigureWidget Demo")

        self.figure = BaseFigureWidget()
        self.figure.set_titles("Signal Preview", "Time (s)", "Amplitude")
        self.figure.set_legend_position("top-right")

        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.addItem("Lines", "lines")
        self.mode_combo.addItem("Markers", "markers")
        self.mode_combo.addItem("Lines + markers", "lines+markers")

        self.line_width_spin = QtWidgets.QSpinBox()
        self.line_width_spin.setRange(1, 8)
        self.line_width_spin.setValue(self.figure.line_width)

        self.marker_size_spin = QtWidgets.QSpinBox()
        self.marker_size_spin.setRange(2, 16)
        self.marker_size_spin.setValue(self.figure.marker_size)

        self.legend_check = QtWidgets.QCheckBox("Legend")
        self.legend_check.setChecked(self.figure.show_legend)

        self.grid_x_check = QtWidgets.QCheckBox("Grid X")
        self.grid_x_check.setChecked(self.figure.show_grid_x)

        self.grid_y_check = QtWidgets.QCheckBox("Grid Y")
        self.grid_y_check.setChecked(self.figure.show_grid_y)

        self.add_button = QtWidgets.QPushButton("Add Curve")
        self.region_button = QtWidgets.QPushButton("Add Region")
        self.clear_button = QtWidgets.QPushButton("Clear")

        self.styled_button = QtWidgets.QPushButton("Styled Curve")
        self.update_button = QtWidgets.QPushButton("Update Sine")
        self.visibility_button = QtWidgets.QPushButton("Toggle Cosine")
        self.remove_button = QtWidgets.QPushButton("Remove Last")
        self.range_button = QtWidgets.QPushButton("Focus Range")
        self.auto_range_button = QtWidgets.QPushButton("Auto Range")
        self.crosshair_check = QtWidgets.QCheckBox("Crosshair")
        self.log_y_check = QtWidgets.QCheckBox("Log Y")
        self.status_label = QtWidgets.QLabel("Ready")
        self.status_label.setMinimumWidth(260)

        controls = QtWidgets.QHBoxLayout()
        controls.addWidget(QtWidgets.QLabel("Mode"))
        controls.addWidget(self.mode_combo)
        controls.addWidget(QtWidgets.QLabel("Line"))
        controls.addWidget(self.line_width_spin)
        controls.addWidget(QtWidgets.QLabel("Marker"))
        controls.addWidget(self.marker_size_spin)
        controls.addWidget(self.legend_check)
        controls.addWidget(self.grid_x_check)
        controls.addWidget(self.grid_y_check)
        controls.addStretch()
        controls.addWidget(self.add_button)
        controls.addWidget(self.region_button)
        controls.addWidget(self.clear_button)

        feature_controls = QtWidgets.QHBoxLayout()
        feature_controls.addWidget(QtWidgets.QLabel("Feature tests"))
        feature_controls.addWidget(self.styled_button)
        feature_controls.addWidget(self.update_button)
        feature_controls.addWidget(self.visibility_button)
        feature_controls.addWidget(self.remove_button)
        feature_controls.addWidget(self.range_button)
        feature_controls.addWidget(self.auto_range_button)
        feature_controls.addWidget(self.crosshair_check)
        feature_controls.addWidget(self.log_y_check)
        feature_controls.addStretch()
        feature_controls.addWidget(self.status_label)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(controls)
        layout.addLayout(feature_controls)
        layout.addWidget(self.figure)

        self.mode_combo.currentIndexChanged.connect(self._apply_style)
        self.line_width_spin.valueChanged.connect(self._apply_style)
        self.marker_size_spin.valueChanged.connect(self._apply_style)
        self.legend_check.toggled.connect(self._apply_style)
        self.grid_x_check.toggled.connect(self._apply_style)
        self.grid_y_check.toggled.connect(self._apply_style)
        self.add_button.clicked.connect(self._add_curve)
        self.region_button.clicked.connect(self._add_region)
        self.clear_button.clicked.connect(self._clear)
        self.styled_button.clicked.connect(self._add_styled_curve)
        self.update_button.clicked.connect(self._update_sine)
        self.visibility_button.clicked.connect(self._toggle_cosine)
        self.remove_button.clicked.connect(self._remove_last_curve)
        self.range_button.clicked.connect(self._focus_range)
        self.auto_range_button.clicked.connect(self._auto_range)
        self.crosshair_check.toggled.connect(self._toggle_crosshair)
        self.log_y_check.toggled.connect(self._toggle_log_y)
        self.figure.cursorPositionChanged.connect(self._show_cursor_position)

        self._add_initial_data()
        self.resize(980, 620)

    def _apply_style(self, *_args: object) -> None:
        settings = self.figure.current_settings()
        settings.update(
            {
                "mode": self.mode_combo.currentData(),
                "line_width": self.line_width_spin.value(),
                "marker_size": self.marker_size_spin.value(),
                "show_legend": self.legend_check.isChecked(),
                "show_grid_x": self.grid_x_check.isChecked(),
                "show_grid_y": self.grid_y_check.isChecked(),
            }
        )
        self.figure.apply_settings(settings)

    def _add_initial_data(self) -> None:
        x = np.linspace(0.0, 8.0, 400)
        self.figure.add_dataset(np.sin(2.0 * np.pi * 0.5 * x), x, name="Sine")
        self.figure.add_dataset(0.7 * np.cos(2.0 * np.pi * 0.75 * x), x, name="Cosine")
        self.figure.add_dataset(np.exp(-x / 5.0) * np.sin(2.0 * np.pi * 1.25 * x), x, name="Damped")
        self._set_status("Initial curves loaded")

    def _add_curve(self) -> None:
        x = np.linspace(0.0, 8.0, 400)
        curve_count = len(self.figure.curves) + 1
        y = np.sin(2.0 * np.pi * (0.2 + curve_count * 0.15) * x) / max(1, curve_count / 2)
        curve = self.figure.add_dataset(y, x)
        if self.log_y_check.isChecked():
            self.figure.set_curve_visible(curve, False)
        self._set_status(f"Added {curve.name()}")

    def _add_region(self) -> None:
        self.figure.add_vertical_region(2.0, 3.25)
        self._set_status("Added vertical region")

    def _clear(self) -> None:
        self.figure.clear_regions()
        self.figure.clear_trace()
        self.log_y_check.setChecked(False)
        self._set_status("Cleared curves and regions")

    def _add_styled_curve(self) -> None:
        x = np.linspace(0.0, 8.0, 160)
        y = 0.45 * np.sin(2.0 * np.pi * 1.8 * x)
        curve = self.figure.add_dataset(
            y,
            x,
            name="Styled",
            color="#7f3fbf",
            line_width=3,
            symbol="t",
            marker_size=9,
        )
        if self.log_y_check.isChecked():
            self.figure.set_curve_visible(curve, False)
        self._set_status("Added styled curve")

    def _update_sine(self) -> None:
        if self.figure.get_curve("Sine") is None:
            self._set_status("Sine curve is missing")
            return

        x = np.linspace(0.0, 8.0, 400)
        y = 0.9 * np.sin(2.0 * np.pi * 0.35 * x + 0.6)
        self.figure.update_curve(
            "Sine",
            y=y,
            x=x,
            color="#0b7285",
            line_width=3,
            symbol=None,
            visible=True,
        )
        self._set_status("Updated Sine data and style")

    def _toggle_cosine(self) -> None:
        curve = self.figure.get_curve("Cosine")
        if curve is None:
            self._set_status("Cosine curve is missing")
            return

        visible = not curve.isVisible()
        self.figure.set_curve_visible(curve, visible)
        self._set_status(f"Cosine visible: {visible}")

    def _remove_last_curve(self) -> None:
        if not self.figure.curves:
            self._set_status("No curve to remove")
            return

        curve = self.figure.curves[-1]
        name = curve.name() or "last curve"
        self.figure.remove_curve(curve)
        self._set_status(f"Removed {name}")

    def _focus_range(self) -> None:
        self.figure.set_ranges(x=(1.0, 4.0), y=(-1.0, 1.0), padding=0.02)
        self._set_status("Focused x/y range")

    def _auto_range(self) -> None:
        self.figure.auto_range(padding=0.08)
        self._set_status("Auto range applied")

    def _toggle_crosshair(self, checked: bool) -> None:
        self.figure.enable_crosshair(checked)
        self._set_status(f"Crosshair enabled: {checked}")

    def _toggle_log_y(self, checked: bool) -> None:
        self.figure.set_log_mode(y=checked)
        if checked and self.figure.get_curve("Log Demo") is None:
            x = np.linspace(1.0, 8.0, 200)
            y = np.exp(x / 2.5)
            self.figure.add_dataset(
                y,
                x,
                name="Log Demo",
                color="#2b8a3e",
                line_width=2,
                symbol=None,
            )
        for name in ("Sine", "Cosine", "Damped", "Styled"):
            curve = self.figure.get_curve(name)
            if curve is not None:
                self.figure.set_curve_visible(curve, not checked)
        if checked:
            self.figure.set_curve_visible("Log Demo", True)
        elif self.figure.get_curve("Log Demo") is not None:
            self.figure.set_curve_visible("Log Demo", False)
        self.figure.auto_range(padding=0.08)
        self._set_status(f"Log Y enabled: {checked}")

    def _show_cursor_position(self, x: float, y: float) -> None:
        self.status_label.setText(f"x={x:.3f} y={y:.3f}")

    def _set_status(self, text: str) -> None:
        self.status_label.setText(text)


def main() -> int:
    app = QtWidgets.QApplication(sys.argv)
    window = BaseFigureDemo()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
