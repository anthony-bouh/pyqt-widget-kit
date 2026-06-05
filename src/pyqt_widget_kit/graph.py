"""Reusable base class for pyqtgraph-based figure widgets."""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

import numpy as np
from PyQt6 import QtCore, QtGui, QtWidgets
import pyqtgraph as pg


class BaseFigureWidget(QtWidgets.QWidget):
    """
    Common parent for pyqtgraph-driven widgets.

    This class centralizes reusable plot configuration, styling, and helper
    methods so concrete widgets (time-series, scatter, etc.) can share the
    same behaviors. Subclasses can either pass an existing PlotWidget or let
    the base class create one, and can opt out of the auto layout if they need
    a custom container hierarchy.
    """

    DEFAULT_PALETTE = [
        "#d62728",
        "#2ca02c",
        "#1f77b4",
        "#ff7f0e",
        "#9467bd",
        "#8c564b",
        "#e377c2",
        "#7f7f7f",
        "#bcbd22",
        "#17becf",
    ]

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None, *, plot: Optional[pg.PlotWidget] = None,
        auto_layout: bool = True,
        with_legend: bool = True,
    ) -> None:
        super().__init__(parent)

        self.plot: pg.PlotWidget = plot or pg.PlotWidget()
        self.legend: Optional[pg.LegendItem] = self.plot.addLegend() if with_legend else None

        self.color_palette = list(self.DEFAULT_PALETTE)
        self._curves: List[pg.PlotDataItem] = []

        self._grid_alpha = 0.2
        self._mode = "lines"
        self._line_width = 1
        self._marker_size = 6
        self._show_legend = bool(with_legend)
        self._show_grid_x = True
        self._show_grid_y = True

        if auto_layout:
            layout = QtWidgets.QVBoxLayout(self)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(self.plot)

        self._setup_plot_frame()

    # region Properties
    @property
    def mode(self) -> str:
        return self._mode

    @mode.setter
    def mode(self, value: str) -> None:
        allowed = ("lines", "markers", "lines+markers")
        if value in allowed:
            self._mode = value
        else:
            raise ValueError(f"Invalid mode '{value}'. Allowed: {allowed}")

    @property
    def line_width(self) -> int:
        return self._line_width

    @line_width.setter
    def line_width(self, value: int) -> None:
        try:
            self._line_width = max(1, int(value))
        except (TypeError, ValueError):
            self._line_width = 1

    @property
    def marker_size(self) -> int:
        return self._marker_size

    @marker_size.setter
    def marker_size(self, value: int) -> None:
        try:
            self._marker_size = max(1, int(value))
        except (TypeError, ValueError):
            self._marker_size = 6

    @property
    def show_legend(self) -> bool:
        if self.legend is None:
            return False
        return self.legend.isVisible()

    @show_legend.setter
    def show_legend(self, value: bool) -> None:
        self._show_legend = bool(value)
        if self.legend is not None:
            self.legend.setVisible(self._show_legend)

    @property
    def plot_title(self) -> str:
        plot_item = self.plot.getPlotItem()
        if hasattr(plot_item, "titleLabel"):
            return plot_item.titleLabel.text
        return ""

    @plot_title.setter
    def plot_title(self, value: str) -> None:
        self.plot.getPlotItem().setTitle(value)

    @property
    def x_axis_title(self) -> str:
        axis_bottom = self.plot.getPlotItem().getAxis("bottom")
        if hasattr(axis_bottom, "labelText"):
            return axis_bottom.labelText
        return ""

    @x_axis_title.setter
    def x_axis_title(self, value: str) -> None:
        self.plot.getPlotItem().getAxis("bottom").setLabel(value)

    @property
    def y_axis_title(self) -> str:
        axis_left = self.plot.getPlotItem().getAxis("left")
        if hasattr(axis_left, "labelText"):
            return axis_left.labelText
        return ""

    @y_axis_title.setter
    def y_axis_title(self, value: str) -> None:
        self.plot.getPlotItem().getAxis("left").setLabel(value)

    @property
    def show_grid_x(self) -> bool:
        return self._show_grid_x

    @show_grid_x.setter
    def show_grid_x(self, value: bool) -> None:
        self._show_grid_x = bool(value)
        self.plot.showGrid(x=self._show_grid_x, y=self._show_grid_y, alpha=0.2)

    @property
    def show_grid_y(self) -> bool:
        return self._show_grid_y

    @show_grid_y.setter
    def show_grid_y(self, value: bool) -> None:
        self._show_grid_y = bool(value)
        self.plot.showGrid(x=self._show_grid_x, y=self._show_grid_y, alpha=0.2)

    @property
    def curves(self) -> List[pg.PlotDataItem]:
        return self._curves

    # endregion

    # Setup helpers
    def _setup_plot_frame(self) -> None:
        self.plot.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.plot.setStyleSheet("border: none; background: transparent;")
        self.plot.setBackground(None)
        self.plot.showAxis("top", True)
        self.plot.showAxis("right", True)
        self.plot.showGrid(x=True, y=True, alpha=0.25)

        view_box = self.plot.getViewBox()
        if view_box:
            view_box.setBorder(None)
            view_box.setBackgroundColor(None)

        if self.legend:
            self.legend.layout.setColumnMinimumWidth(0, 10)
            self.legend.layout.setContentsMargins(6, 6, 6, 6)
            self.set_legend_position("top-right")
            self.legend.setVisible(self._show_legend)

    # Styling and theme
    def set_theme(self) -> None:
        """Apply palette, axis styling, and legend theme."""
        
        # TODO Theme integration - this is a placeholder until we have a real theme manager
        theme = {
            "text": "#333333",
            "accent": "#0078d4",
        }

        title_style = {"color": theme["text"], "size": "10pt", "font-family": "Segoe UI"}
        plot_item = self.plot.getPlotItem()
        current_title = plot_item.titleLabel.text if hasattr(plot_item, "titleLabel") else ""
        self.plot.setTitle(current_title, **title_style)

        border_pen = pg.mkPen(theme["text"], width=1)
        label_pen = pg.mkPen(theme["text"])
        tick_font = QtGui.QFont("Segoe UI")
        for axis_name in ("left", "bottom", "top", "right"):
            axis = self.plot.getAxis(axis_name)
            if not axis:
                continue
            axis.setPen(border_pen)
            axis.setTextPen(label_pen if axis_name in ("left", "bottom") else pg.mkPen(None))
            axis.setTickFont(tick_font)
            if axis_name in ("top", "right"):
                axis.setStyle(showValues=False, tickLength=5)
            else:
                axis.setStyle(showValues=True)

        if self.legend:
            self.legend.setPen(pg.mkPen(theme["text"], width=1))
            self.legend.setBrush(pg.mkBrush(255, 255, 255, 230))

    def set_legend_visibility(self, show: bool) -> None:
        """Convenience wrapper to toggle legend visibility."""
        self.show_legend = bool(show)

    def set_grid(self, x: Optional[bool] = None, y: Optional[bool] = None, alpha: Optional[float] = None) -> None:
        """Update grid visibility and alpha in one call."""
        if x is not None:
            self._show_grid_x = bool(x)
        if y is not None:
            self._show_grid_y = bool(y)
        if alpha is not None:
            try:
                self._grid_alpha = max(0.0, float(alpha))
            except (TypeError, ValueError):
                pass
        self.plot.showGrid(x=self._show_grid_x, y=self._show_grid_y, alpha=self._grid_alpha)

    def set_titles(self, title: str = "", x: str = "", y: str = "") -> None:
        """Set plot and axis titles in one call."""
        self.plot.setTitle(title)
        self.plot.setLabel("bottom", x)
        self.plot.setLabel("left", y)

    def clear_titles(self) -> None:
        """Clear plot and axis titles."""
        self.set_titles("", "", "")

    def set_color_palette(self, palette: Sequence[str]) -> None:
        """
        Replace the color palette used for new and existing curves.
        """
        if not palette:
            return
        self.color_palette = list(palette)
        for idx, curve in enumerate(self._curves):
            self._style_curve(curve, idx)

    def set_legend_position(self, position: str) -> None:
        """
        Move the legend to one of the four corners.
        Valid values: 'top-left', 'top-right', 'bottom-left', 'bottom-right'.
        """
        if not self.legend:
            return

        pos_key = (position or "").strip().lower().replace("_", "-")
        anchors = {
            "top-left": ((0, 0), (0, 0), QtCore.QPointF(8, 8)),
            "top-right": ((1, 0), (1, 0), QtCore.QPointF(-8, 8)),
            "bottom-left": ((0, 1), (0, 1), QtCore.QPointF(8, -8)),
            "bottom-right": ((1, 1), (1, 1), QtCore.QPointF(-8, -8)),
        }
        if pos_key not in anchors:
            raise ValueError("position must be one of: top-left, top-right, bottom-left, bottom-right")

        item_pos, parent_pos, offset = anchors[pos_key]
        self.legend.anchor(itemPos=item_pos, parentPos=parent_pos, offset=offset)

    # Public API
    def current_settings(self) -> dict:
        """Return a dict snapshot of plot configuration."""
        return {
            "mode": self.mode,
            "line_width": self.line_width,
            "marker_size": self.marker_size,
            "plot_title": self.plot_title,
            "x_axis_title": self.x_axis_title,
            "y_axis_title": self.y_axis_title,
            "show_legend": self.show_legend,
            "show_grid_x": self.show_grid_x,
            "show_grid_y": self.show_grid_y,
        }

    def apply_setting(self, settings: dict) -> None:
        """Apply settings dict directly to the plot widget."""
        self.mode = settings.get("mode", self.mode)

        try:
            self.line_width = int(settings.get("line_width", self.line_width))
        except (TypeError, ValueError):
            pass

        try:
            self.marker_size = int(settings.get("marker_size", self.marker_size))
        except (TypeError, ValueError):
            pass

        plot_title = settings.get("plot_title", "")
        x_axis_title = settings.get("x_axis_title", "")
        y_axis_title = settings.get("y_axis_title", "")
        self.plot.setTitle(plot_title)
        self.plot.setLabel("bottom", x_axis_title)
        self.plot.setLabel("left", y_axis_title)

        self.show_legend = bool(settings.get("show_legend", self.show_legend))
        self.show_grid_x = bool(settings.get("show_grid_x", self.show_grid_x))
        self.show_grid_y = bool(settings.get("show_grid_y", self.show_grid_y))
        self.plot.showGrid(x=self.show_grid_x, y=self.show_grid_y, alpha=0.2)

        for curve in self._curves:
            self._style_curve(curve)

    def add_dataset(
        self,
        y: np.ndarray | Sequence[float],
        x: Optional[np.ndarray | Sequence[float]] = None,
        *,
        name: str = "",
    ) -> pg.PlotDataItem:
        """
        Add a curve with optional x data. If x is None, indices are used.
        """
        if y is None:
            raise ValueError("y cannot be None")

        y_arr = np.asarray(y, dtype=float)
        if y_arr.size == 0:
            raise ValueError("y cannot be empty")

        if y_arr.ndim > 1:
            y_arr = y_arr.flatten()

        x_arr = None
        if x is not None:
            x_arr = np.asarray(x, dtype=float)
            if x_arr.ndim > 1:
                x_arr = x_arr.flatten()
            if x_arr.shape != y_arr.shape:
                raise ValueError("x and y must have the same shape")
        if x_arr is None:
            x_arr = np.arange(y_arr.size, dtype=float)

        curve = self._new_curve(name=name or "Trace")
        curve.setData(x_arr, y_arr)
        curve.setClipToView(True)
        return curve

    def clear_region(self, region: pg.LinearRegionItem) -> None:
        """Remove a specific LinearRegionItem if present."""
        if region in self.plot.items():
            self.plot.removeItem(region)

    def add_vertical_region(
        self,
        start: float,
        end: float,
        *,
        brush: Optional[QtGui.QBrush] = None,
        bounds: Optional[Tuple[Optional[float], Optional[float]]] = None,
    ) -> pg.LinearRegionItem:
        """
        Add a vertical LinearRegionItem with optional bounds.
        """
        min_x, max_x = (None, None) if bounds is None else bounds

        if min_x is None or max_x is None:
            all_x = np.concatenate([item.xData for item in self.plot.listDataItems() if item.xData is not None])
            if all_x.size > 0:
                min_x = float(np.min(all_x))
                max_x = float(np.max(all_x))

        region = pg.LinearRegionItem(
            values=(start, end),
            orientation="vertical",
            movable=True,
            bounds=(min_x, max_x) if (min_x is not None and max_x is not None) else None,
            brush=brush or QtGui.QBrush(QtGui.QColor(200, 200, 255, 50)),
            pen=pg.mkPen((100, 100, 200), width=2),
        )
        self.plot.addItem(region)
        region.setZValue(10)
        return region

    def x_range(self) -> Optional[Tuple[float, float]]:
        """Return current x-axis range (min, max) or None if unavailable."""
        vb = self.plot.getViewBox()
        if vb is None:
            return None
        rng = vb.viewRange()
        if rng and len(rng) == 2:
            return (rng[0][0], rng[0][1])
        return None

    def curve_length(self) -> int:
        """Return maximum length of curves."""
        lengths = [item.xData.size if item.xData is not None else 0 for item in self.plot.listDataItems()]
        return max(lengths) if lengths else 0

    def x_values_range(self) -> Optional[Tuple[float, float]]:
        """Return x value range across all curves."""
        all_x = np.concatenate([item.xData for item in self.plot.listDataItems() if item.xData is not None])
        if all_x.size == 0:
            return None
        return float(np.min(all_x)), float(np.max(all_x))

    def y_values_range(self) -> Optional[Tuple[float, float]]:
        """Return y value range across all curves."""
        all_y = np.concatenate([item.yData for item in self.plot.listDataItems() if item.yData is not None])
        if all_y.size == 0:
            return None
        return float(np.min(all_y)), float(np.max(all_y))

    def to_png(self, file_path: str) -> None:
        """Export the current plot to a PNG file."""
        from pyqtgraph.exporters import ImageExporter

        prev_alpha = self._grid_alpha
        prev_styles = []
        try:
            if self._show_grid_x or self._show_grid_y:
                self.plot.showGrid(x=self._show_grid_x, y=self._show_grid_y, alpha=1.0)

            # Temporarily force opaque pens/brushes for curves
            for curve in self._curves:
                pen = curve.opts.get("pen")
                brush = curve.opts.get("symbolBrush")
                prev_styles.append((curve, pen, brush))

                if pen is not None:
                    color = pen.color()
                    color.setAlpha(255)
                    curve.setPen(pg.mkPen(color, width=pen.width()))
                if brush is not None:
                    bcolor = brush.color() if hasattr(brush, "color") else None
                    if bcolor is not None:
                        bcolor.setAlpha(255)
                        curve.setSymbolBrush(pg.mkBrush(bcolor))

            exp = ImageExporter(self.plot.plotItem)
            exp.parameters()["width"] = 1920
            exp.export(file_path)
        finally:
            if self._show_grid_x or self._show_grid_y:
                self.plot.showGrid(x=self._show_grid_x, y=self._show_grid_y, alpha=prev_alpha)
            # Restore original curve styles
            for curve, pen, brush in prev_styles:
                if pen is not None:
                    curve.setPen(pen)
                if brush is not None:
                    curve.setSymbolBrush(brush)

    def get_data_ranges(self) -> Optional[Tuple[Tuple[float, float], Tuple[float, float]]]:
        """
        Return ((xmin, xmax), (ymin, ymax)) across all curves, or None if no data.
        """
        x_range = self.x_values_range()
        y_range = self.y_values_range()
        if x_range is None and y_range is None:
            return None
        return x_range, y_range

    def set_background(self, color: Optional[str] = None) -> None:
        """Set plot background color (or None for transparent)."""
        self.plot.setBackground(color)

    def repaint(self) -> None: 
        """Force a repaint of the plot."""
        self.plot.repaint()

    def update(self) -> None:
        """Force a redraw of the plot."""
        self.plot.update()

    def clear_trace(self) -> None:
        """Clear all curves from the plot."""
        for c in self._curves:
            self.plot.removeItem(c)
        self._curves.clear()

    def clear_regions(self) -> None:
        """Clear all region selectors from the plot."""
        regions = [item for item in self.plot.items() if isinstance(item, pg.LinearRegionItem)]
        for reg in regions:
            self.plot.removeItem(reg)

    # Internals
    def _new_curve(self, name: str) -> pg.PlotDataItem:
        curve_index = len(self._curves)
        color = self.color_palette[curve_index % len(self.color_palette)]

        curve = pg.PlotDataItem(
            pen=pg.mkPen(color, width=self.line_width) if "lines" in self.mode else None,
            symbol="o" if "markers" in self.mode else None,
            symbolSize=self.marker_size,
            symbolBrush=pg.mkBrush(color),
            name=name,
        )
        self._style_curve(curve, curve_index)
        self.plot.addItem(curve)
        self._curves.append(curve)
        return curve

    def _style_curve(self, curve: pg.PlotDataItem, curve_index: Optional[int] = None) -> None:
        if curve_index is None:
            try:
                curve_index = self._curves.index(curve)
            except ValueError:
                curve_index = 0

        color = self.color_palette[curve_index % len(self.color_palette)]
        pen = pg.mkPen(color, width=self.line_width) if "lines" in self.mode else None
        sym = "o" if "markers" in self.mode else None
        curve.setPen(pen)
        curve.setSymbol(sym)
        if sym:
            curve.setSymbolSize(self.marker_size)
            curve.setSymbolBrush(pg.mkBrush(color))
        curve.setClipToView(True)
