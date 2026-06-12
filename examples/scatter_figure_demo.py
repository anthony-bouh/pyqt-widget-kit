"""Run a small ScatterFigureWidget demo."""

from __future__ import annotations

import sys

import numpy as np
from PyQt6 import QtWidgets

from pyqt_widget_kit import ScatterFigureWidget


class ScatterFigureDemo(QtWidgets.QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ScatterFigureWidget Demo")

        self.figure = ScatterFigureWidget()
        self.figure.set_titles("Batch Measurements", "Temperature", "Pressure")
        self.figure.set_legend_position("top-right")

        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.addItem("Markers", "markers")
        self.mode_combo.addItem("Lines", "lines")
        self.mode_combo.addItem("Lines + markers", "lines+markers")

        self.line_width_spin = QtWidgets.QSpinBox()
        self.line_width_spin.setRange(1, 8)
        self.line_width_spin.setValue(self.figure.line_width)

        self.marker_size_spin = QtWidgets.QSpinBox()
        self.marker_size_spin.setRange(2, 20)
        self.marker_size_spin.setValue(self.figure.marker_size)

        self.legend_check = QtWidgets.QCheckBox("Legend")
        self.legend_check.setChecked(self.figure.show_legend)

        self.grid_x_check = QtWidgets.QCheckBox("Grid X")
        self.grid_x_check.setChecked(self.figure.show_grid_x)

        self.grid_y_check = QtWidgets.QCheckBox("Grid Y")
        self.grid_y_check.setChecked(self.figure.show_grid_y)

        self.selection_check = QtWidgets.QCheckBox("Rectangle")
        self.add_button = QtWidgets.QPushButton("Add Series")
        self.select_button = QtWidgets.QPushButton("Select Center")
        self.clear_selection_button = QtWidgets.QPushButton("Clear Selection")
        self.clear_button = QtWidgets.QPushButton("Clear")
        self.status_label = QtWidgets.QLabel("Ready")
        self.status_label.setMinimumWidth(340)

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
        controls.addWidget(self.clear_button)

        feature_controls = QtWidgets.QHBoxLayout()
        feature_controls.addWidget(self.selection_check)
        feature_controls.addWidget(self.add_button)
        feature_controls.addWidget(self.select_button)
        feature_controls.addWidget(self.clear_selection_button)
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
        self.selection_check.toggled.connect(self._toggle_rectangle_selection)
        self.add_button.clicked.connect(lambda: self._add_series())
        self.select_button.clicked.connect(lambda: self._select_center_points())
        self.clear_selection_button.clicked.connect(lambda: self.figure.clear_highlight())
        self.clear_button.clicked.connect(lambda: self._clear())
        self.figure.pointClicked.connect(self._show_clicked_point)
        self.figure.pointsSelected.connect(self._show_selected_points)

        self._series_counter = 0
        self._add_initial_data()
        self.resize(980, 620)

    def _apply_style(self, *_args: object) -> None:
        self.figure.apply_settings(
            {
                "mode": self.mode_combo.currentData(),
                "line_width": self.line_width_spin.value(),
                "marker_size": self.marker_size_spin.value(),
                "show_legend": self.legend_check.isChecked(),
                "show_grid_x": self.grid_x_check.isChecked(),
                "show_grid_y": self.grid_y_check.isChecked(),
            }
        )

    def _add_initial_data(self) -> None:
        self._add_series("Batch A", "#0b7285", phase=0.0)
        self._add_series("Batch B", "#c92a2a", phase=0.7)
        self._set_status("Initial scatter series loaded")

    def _add_series(
        self,
        name: str | None = None,
        color: str | None = None,
        *,
        phase: float | None = None,
    ) -> None:
        self._series_counter += 1
        series_name = name or f"Batch {self._series_counter}"
        series_phase = phase if phase is not None else self._series_counter * 0.45

        x = np.linspace(18.0, 82.0, 28)
        y = 48.0 + 0.28 * x + 7.0 * np.sin(x / 9.0 + series_phase)
        y += (self._series_counter % 3 - 1) * 4.0
        metadata = [
            {
                "sample": f"{series_name}-{idx + 1:02d}",
                "filepath": f"/demo/{series_name.lower().replace(' ', '_')}_{idx + 1:02d}.h5",
            }
            for idx in range(x.size)
        ]

        self.figure.add_points(
            x,
            y,
            series_name=series_name,
            color=color,
            metadata=metadata,
        )
        self._set_status(f"Added {series_name}")

    def _toggle_rectangle_selection(self, checked: bool) -> None:
        self.figure.enable_rectangle_selection(checked)
        self._set_status(f"Rectangle selection: {checked}")

    def _select_center_points(self) -> None:
        x_range = self.figure.x_values_range()
        y_range = self.figure.y_values_range()
        if x_range is None or y_range is None:
            self._set_status("No points to select")
            return

        x_mid = (x_range[0] + x_range[1]) / 2.0
        y_mid = (y_range[0] + y_range[1]) / 2.0
        x_width = (x_range[1] - x_range[0]) * 0.35
        y_height = (y_range[1] - y_range[0]) * 0.35
        selected = self.figure.select_points_in_rect(
            x_mid - x_width / 2.0,
            x_mid + x_width / 2.0,
            y_mid - y_height / 2.0,
            y_mid + y_height / 2.0,
        )
        self._set_status(f"Selected {len(selected)} center points")

    def _clear(self) -> None:
        self.figure.clear()
        self.selection_check.setChecked(False)
        self._series_counter = 0
        self._set_status("Cleared scatter data")

    def _show_clicked_point(self, point: dict) -> None:
        sample = point.get("sample", f"{point.get('series', 'Series')} #{point.get('index', '?')}")
        self._set_status(f"Clicked {sample}: x={point['x']:.2f} y={point['y']:.2f}")

    def _show_selected_points(self, points: list[dict]) -> None:
        self._set_status(f"Rectangle selected {len(points)} points")

    def _set_status(self, text: str) -> None:
        self.status_label.setText(text)


def main() -> int:
    app = QtWidgets.QApplication(sys.argv)
    window = ScatterFigureDemo()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
