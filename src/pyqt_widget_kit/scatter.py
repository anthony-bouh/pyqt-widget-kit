"""Interactive scatter plot widget built on BaseFigureWidget."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Optional, TypedDict

import numpy as np
from PyQt6 import QtCore, QtGui, QtWidgets
import pyqtgraph as pg

from .graph import BaseFigureWidget, ColorInput, DatasetInput


class ScatterPointPayload(TypedDict, total=False):
    """Payload emitted when a scatter point is clicked or selected."""

    series: str
    index: int
    x: float
    y: float
    metadata: dict[str, object]


@dataclass
class _ScatterSeries:
    name: str
    x: np.ndarray
    y: np.ndarray
    metadata: list[dict[str, object]]
    color: ColorInput
    curve: pg.PlotDataItem
    scatter: pg.ScatterPlotItem


class ScatterFigureWidget(BaseFigureWidget):
    """
    Interactive scatter figure with per-point metadata and rectangular selection.

    The widget deliberately does not load files or know application-specific
    concepts. Callers provide x/y values and optional metadata dictionaries.
    """

    pointClicked = QtCore.pyqtSignal(dict)
    pointsSelected = QtCore.pyqtSignal(list)

    def __init__(
        self,
        parent: Optional[QtWidgets.QWidget] = None,
        *,
        plot: Optional[pg.PlotWidget] = None,
        with_legend: bool = True,
    ) -> None:
        super().__init__(parent, plot=plot, with_legend=with_legend)

        self.mode = "markers"
        self._scatter_series: list[_ScatterSeries] = []
        self._scatter_by_name: dict[str, _ScatterSeries] = {}
        self._selection_active = False

        self.highlight = pg.ScatterPlotItem(
            size=max(8, self.marker_size + 6),
            pen=pg.mkPen("k", width=2),
            brush=pg.mkBrush(255, 255, 0, 200),
            symbol="o",
        )
        self.highlight.setVisible(False)
        self.plot.addItem(self.highlight)

        self.multi_highlight = pg.ScatterPlotItem(
            size=max(8, self.marker_size + 6),
            pen=pg.mkPen("r", width=2),
            brush=pg.mkBrush(255, 100, 100, 200),
            symbol="o",
        )
        self.multi_highlight.setVisible(False)
        self.plot.addItem(self.multi_highlight)

        self.selection_roi = pg.RectROI([0, 0], [1, 1], pen=pg.mkPen("g", width=2))
        self.selection_roi.setZValue(10)
        self.selection_roi.addScaleHandle([0, 0], [1, 1])
        self.selection_roi.addScaleHandle([1, 1], [0, 0])

    @property
    def scatter_items(self) -> list[pg.ScatterPlotItem]:
        """Return scatter items in series order."""
        return [series.scatter for series in self._scatter_series]

    @property
    def selection_active(self) -> bool:
        """Whether rectangular point selection is enabled."""
        return self._selection_active

    def series_names(self) -> list[str]:
        """Return scatter series names in display order."""
        return [series.name for series in self._scatter_series]

    def add_points(
        self,
        x: DatasetInput,
        y: DatasetInput,
        *,
        series_name: str = "Series",
        color: Optional[ColorInput] = None,
        metadata: Optional[Sequence[Mapping[str, object] | None]] = None,
        auto_range: bool = True,
    ) -> list[int]:
        """Add points to a named series and return their series-local indices."""
        x_arr = self._to_1d_float_array(x, "x")
        y_arr = self._to_1d_float_array(y, "y")
        if x_arr.shape != y_arr.shape:
            raise ValueError("x and y must have the same shape")
        if x_arr.size == 0:
            return []

        metadata_values = self._normalize_metadata(metadata, x_arr.size)
        series_key = series_name or f"Series {len(self._scatter_series) + 1}"
        series = self._scatter_by_name.get(series_key)

        if series is None:
            series = self._new_scatter_series(series_key, x_arr, y_arr, metadata_values, color)
            start_idx = 0
        else:
            start_idx = int(series.x.size)
            series.x = np.concatenate([series.x, x_arr])
            series.y = np.concatenate([series.y, y_arr])
            series.metadata.extend(metadata_values)
            if color is not None:
                series.color = color
                self._curve_style(series.curve)["color"] = color
            series.curve.setData(series.x, series.y)

        points = [
            {
                "pos": (float(x_value), float(y_value)),
                "data": self._point_payload(series.name, start_idx + idx, float(x_value), float(y_value), meta),
            }
            for idx, (x_value, y_value, meta) in enumerate(zip(x_arr, y_arr, metadata_values))
        ]
        series.scatter.addPoints(points)
        self._sync_scatter_style()

        if auto_range:
            self.auto_range(padding=0.08)
        return list(range(start_idx, start_idx + x_arr.size))

    def clear(self) -> None:
        """Clear scatter series, highlights, and selection state."""
        self.enable_rectangle_selection(False)
        self.clear_trace()

        for series in self._scatter_series:
            if series.scatter in self.plot.items():
                self.plot.removeItem(series.scatter)
        self._scatter_series.clear()
        self._scatter_by_name.clear()
        self.clear_highlight()

        if self.highlight not in self.plot.items():
            self.plot.addItem(self.highlight)
        if self.multi_highlight not in self.plot.items():
            self.plot.addItem(self.multi_highlight)

    def remove_series(self, series_name: str) -> None:
        """Remove a scatter series by name."""
        series = self._scatter_by_name.pop(series_name)
        if series.scatter in self.plot.items():
            self.plot.removeItem(series.scatter)
        self.remove_curve(series.curve)
        self._scatter_series.remove(series)

    def set_series_visible(self, series_name: str, visible: bool) -> None:
        """Show or hide one scatter series."""
        series = self._scatter_by_name[series_name]
        series.curve.setVisible(bool(visible))
        series.scatter.setVisible(bool(visible) and "markers" in self.mode)

    def clear_highlight(self) -> None:
        """Hide single and multi-point highlights."""
        self.highlight.setData(x=[], y=[])
        self.highlight.setVisible(False)
        self.multi_highlight.setData(x=[], y=[])
        self.multi_highlight.setVisible(False)

    def highlight_point(self, x: float, y: float) -> None:
        """Highlight one point."""
        self.highlight.setData(x=[float(x)], y=[float(y)])
        self.highlight.setVisible(True)

    def clear_multi_selection(self) -> None:
        """Hide rectangular-selection highlights."""
        self.multi_highlight.setData(x=[], y=[])
        self.multi_highlight.setVisible(False)

    def enable_rectangle_selection(self, enabled: bool = True) -> None:
        """Enable or disable a draggable rectangular selection ROI."""
        enabled = bool(enabled)
        if enabled == self._selection_active:
            return

        if enabled:
            self.clear_highlight()
            self.plot.addItem(self.selection_roi)
            self.selection_roi.sigRegionChangeFinished.connect(self._on_selection_changed)
            self._selection_active = True
            self._center_selection_roi()
        else:
            if self.selection_roi in self.plot.items():
                self.plot.removeItem(self.selection_roi)
            try:
                self.selection_roi.sigRegionChangeFinished.disconnect(self._on_selection_changed)
            except TypeError:
                pass
            self._selection_active = False
            self.clear_multi_selection()

    def toggle_rectangle_selection(self) -> None:
        """Toggle rectangular selection mode."""
        self.enable_rectangle_selection(not self._selection_active)

    def points_in_rect(
        self,
        x_min: float,
        x_max: float,
        y_min: float,
        y_max: float,
    ) -> list[ScatterPointPayload]:
        """Return point payloads inside a rectangular data region."""
        if x_min > x_max:
            x_min, x_max = x_max, x_min
        if y_min > y_max:
            y_min, y_max = y_max, y_min

        selected: list[ScatterPointPayload] = []
        for series in self._scatter_series:
            mask = (
                np.isfinite(series.x)
                & np.isfinite(series.y)
                & (series.x >= x_min)
                & (series.x <= x_max)
                & (series.y >= y_min)
                & (series.y <= y_max)
            )
            for idx in np.flatnonzero(mask):
                selected.append(
                    self._point_payload(
                        series.name,
                        int(idx),
                        float(series.x[idx]),
                        float(series.y[idx]),
                        series.metadata[idx],
                    )
                )
        return selected

    def select_points_in_rect(
        self,
        x_min: float,
        x_max: float,
        y_min: float,
        y_max: float,
        *,
        emit: bool = True,
    ) -> list[ScatterPointPayload]:
        """Highlight and optionally emit points inside a rectangular data region."""
        selected = self.points_in_rect(x_min, x_max, y_min, y_max)
        if selected:
            self.multi_highlight.setData(
                x=[point["x"] for point in selected],
                y=[point["y"] for point in selected],
            )
            self.multi_highlight.setVisible(True)
            if emit:
                self.pointsSelected.emit(selected)
        else:
            self.clear_multi_selection()
        return selected

    def apply_settings(self, settings: Mapping[str, object]) -> None:
        """Apply visual settings and sync scatter interaction layers."""
        super().apply_settings(settings)
        self._sync_scatter_style()

    def _new_scatter_series(
        self,
        name: str,
        x: np.ndarray,
        y: np.ndarray,
        metadata: list[dict[str, object]],
        color: Optional[ColorInput],
    ) -> _ScatterSeries:
        series_color = color or self.color_palette[len(self._scatter_series) % len(self.color_palette)]
        curve = self._new_curve(
            name=name,
            color=series_color,
            symbol="auto",
            marker_size=self.marker_size,
        )
        curve.setData(x, y)

        scatter = pg.ScatterPlotItem(
            size=self.marker_size,
            pen=pg.mkPen(None),
            brush=self._scatter_brush(series_color),
            symbol="o",
        )
        scatter.sigClicked.connect(self._on_point_clicked)
        self.plot.addItem(scatter)

        series = _ScatterSeries(
            name=name,
            x=x.copy(),
            y=y.copy(),
            metadata=list(metadata),
            color=series_color,
            curve=curve,
            scatter=scatter,
        )
        self._scatter_series.append(series)
        self._scatter_by_name[name] = series
        return series

    def _sync_scatter_style(self) -> None:
        marker_visible = "markers" in self.mode
        for series in self._scatter_series:
            self._style_curve(series.curve)
            series.scatter.setSize(self.marker_size)
            series.scatter.setBrush(self._scatter_brush(series.color))
            series.scatter.setVisible(series.curve.isVisible() and marker_visible)

        highlight_size = max(8, self.marker_size + 6)
        self.highlight.setSize(highlight_size)
        self.multi_highlight.setSize(highlight_size)

    def _on_point_clicked(self, _scatter: pg.ScatterPlotItem, points: Sequence[object]) -> None:
        if points is None or len(points) == 0:
            return

        point = points[0]
        point_data = point.data()
        if not isinstance(point_data, dict):
            return
        self.highlight_point(float(point_data["x"]), float(point_data["y"]))
        self.pointClicked.emit(dict(point_data))

    def _on_selection_changed(self) -> None:
        if not self._selection_active:
            return

        rect = self.selection_roi.boundingRect()
        pos = self.selection_roi.pos()
        x_min = float(pos.x())
        y_min = float(pos.y())
        self.select_points_in_rect(
            x_min,
            x_min + float(rect.width()),
            y_min,
            y_min + float(rect.height()),
        )

    def _center_selection_roi(self) -> None:
        view_range = self.plot.viewRange()
        x_min, x_max = view_range[0]
        y_min, y_max = view_range[1]
        x_width = (x_max - x_min) / 4
        y_height = (y_max - y_min) / 4
        self.selection_roi.setPos(
            [
                x_min + (x_max - x_min - x_width) / 2,
                y_min + (y_max - y_min - y_height) / 2,
            ]
        )
        self.selection_roi.setSize([x_width, y_height])

    @staticmethod
    def _normalize_metadata(
        metadata: Optional[Sequence[Mapping[str, object] | None]],
        count: int,
    ) -> list[dict[str, object]]:
        if metadata is None:
            return [{} for _ in range(count)]
        if len(metadata) != count:
            raise ValueError("metadata must have the same length as x and y")
        return [dict(item or {}) for item in metadata]

    @staticmethod
    def _point_payload(
        series: str,
        index: int,
        x: float,
        y: float,
        metadata: Mapping[str, object],
    ) -> ScatterPointPayload:
        payload: ScatterPointPayload = {
            "series": series,
            "index": index,
            "x": x,
            "y": y,
            "metadata": dict(metadata),
        }
        payload.update(metadata)
        return payload

    @staticmethod
    def _scatter_brush(color: ColorInput) -> QtGui.QBrush:
        qcolor = pg.mkColor(color)
        qcolor.setAlpha(120)
        return pg.mkBrush(qcolor)
