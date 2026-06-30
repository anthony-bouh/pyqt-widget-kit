"""Reusable base class for pyqtgraph-based figure widgets."""

from __future__ import annotations

from collections.abc import Mapping
from typing import (
    List,
    Literal,
    Optional,
    Protocol,
    Sequence,
    Tuple,
    TypedDict,
    cast,
)

import numpy as np
from PyQt6 import QtCore, QtGui, QtWidgets
import pyqtgraph as pg

from .buttons import IconButton


class HDF5DatasetLike(Protocol):
    """Minimal h5py.Dataset-compatible surface accepted by add_dataset."""

    dtype: object
    ndim: int
    shape: tuple[int, ...]

    def __getitem__(self, key: object) -> object:
        ...


DatasetInput = np.ndarray | Sequence[float] | HDF5DatasetLike
ColorInput = str | QtGui.QColor | tuple[int, ...]
CurveReference = str | pg.PlotDataItem
FigureMode = Literal["lines", "markers", "lines+markers"]
_UNSET = object()


class FigureSettings(TypedDict, total=False):
    """Visual settings accepted by BaseFigureWidget.apply_settings.

    All keys are optional so callers can apply partial updates.
    """

    mode: FigureMode
    line_width: int
    marker_size: int
    plot_title: str
    x_axis_title: str
    y_axis_title: str
    show_legend: bool
    show_grid_x: bool
    show_grid_y: bool
    grid_alpha: float
    log_x: bool
    log_y: bool


_ALLOWED_MODES: tuple[FigureMode, ...] = ("lines", "markers", "lines+markers")


class BaseFigureWidget(QtWidgets.QWidget):
    """
    Common parent for pyqtgraph-driven widgets.

    This class centralizes reusable plot configuration, styling, and helper
    methods so concrete widgets (time-series, scatter, etc.) can share the
    same behaviors. Subclasses can either pass an existing PlotWidget or let
    the base class create one.
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
    _PLOT_FONT_FAMILY = "Segoe UI"
    _PLOT_TITLE_SIZE = "10pt"

    cursorPositionChanged = QtCore.pyqtSignal(float, float)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None, *, plot: Optional[pg.PlotWidget] = None, with_legend: bool = True) -> None:
        super().__init__(parent)

        self.plot: pg.PlotWidget = plot or pg.PlotWidget()
        self.legend: Optional[pg.LegendItem] = self.plot.addLegend() if with_legend else None

        self.color_palette = list(self.DEFAULT_PALETTE)
        self._curves: List[pg.PlotDataItem] = []

        self._grid_alpha = 0.25
        self._mode: FigureMode = "lines"
        self._line_width = 1
        self._marker_size = 6
        self._show_legend = bool(with_legend)
        self._show_grid_x = True
        self._show_grid_y = True
        self._log_x = False
        self._log_y = False
        self._crosshair_enabled = False
        self._crosshair_label_visible = True
        self._crosshair_vline: Optional[pg.InfiniteLine] = None
        self._crosshair_hline: Optional[pg.InfiniteLine] = None
        self._crosshair_label: Optional[pg.TextItem] = None
        self._hover_toolbar_watched: list[QtCore.QObject] = []

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.plot)

        self.hover_toolbar = QtWidgets.QWidget(self)
        self.toolbar_buttons: dict[str, IconButton] = {}
        self._setup_hover_toolbar()

        self.plot.setProperty("pyqtWidgetKitRole", "base-figure-plot")
        self.plot.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.plot.setBackground(None)
        self.plot.showAxis("top", True)
        self.plot.showAxis("right", True)

        view_box = self.plot.getViewBox()
        if view_box:
            view_box.setBorder(None)
            view_box.setBackgroundColor(None)

        self._style_plot()
        self._apply_grid()

        if self.legend:
            self.legend.layout.setColumnMinimumWidth(0, 10)
            self.legend.layout.setContentsMargins(6, 6, 6, 6)
            self.set_legend_position("top-right")
            self.legend.setVisible(self._show_legend)

        self._install_hover_toolbar_filter(self)
        self._install_hover_toolbar_filter(self.plot)
        self._position_hover_toolbar()

    # region Properties
    @property
    def mode(self) -> FigureMode:
        return self._mode

    @mode.setter
    def mode(self, value: object) -> None:
        self._mode = self._coerce_mode(value)

    @property
    def line_width(self) -> int:
        return self._line_width

    @line_width.setter
    def line_width(self, value: object) -> None:
        self._line_width = self._coerce_positive_int(value, "line_width")

    @property
    def marker_size(self) -> int:
        return self._marker_size

    @marker_size.setter
    def marker_size(self, value: object) -> None:
        self._marker_size = self._coerce_positive_int(value, "marker_size")

    @property
    def show_legend(self) -> bool:
        if self.legend is None:
            return False
        return self.legend.isVisible()

    @show_legend.setter
    def show_legend(self, value: object) -> None:
        self._show_legend = self._coerce_bool(value, "show_legend")
        if self.legend is not None:
            self.legend.setVisible(self._show_legend)
        self._sync_hover_toolbar_buttons()

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
    def show_grid_x(self, value: object) -> None:
        self._show_grid_x = self._coerce_bool(value, "show_grid_x")
        self._apply_grid()
        self._sync_hover_toolbar_buttons()

    @property
    def show_grid_y(self) -> bool:
        return self._show_grid_y

    @show_grid_y.setter
    def show_grid_y(self, value: object) -> None:
        self._show_grid_y = self._coerce_bool(value, "show_grid_y")
        self._apply_grid()
        self._sync_hover_toolbar_buttons()

    @property
    def grid_alpha(self) -> float:
        return self._grid_alpha

    @grid_alpha.setter
    def grid_alpha(self, value: object) -> None:
        self._grid_alpha = self._coerce_unit_float(value, "grid_alpha")
        self._apply_grid()

    @property
    def log_x(self) -> bool:
        return self._log_x

    @property
    def log_y(self) -> bool:
        return self._log_y

    @property
    def crosshair_enabled(self) -> bool:
        return self._crosshair_enabled

    @property
    def curves(self) -> List[pg.PlotDataItem]:
        return self._curves

    # endregion

    def eventFilter(self, watched: QtCore.QObject, event: QtCore.QEvent) -> bool:
        if watched in self._hover_toolbar_watched:
            if event.type() in (QtCore.QEvent.Type.Enter, QtCore.QEvent.Type.HoverEnter):
                self._show_hover_toolbar()
            elif event.type() in (QtCore.QEvent.Type.Leave, QtCore.QEvent.Type.HoverLeave):
                QtCore.QTimer.singleShot(0, self._hide_hover_toolbar_if_needed)
        return super().eventFilter(watched, event)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        self._position_hover_toolbar()

    def _setup_hover_toolbar(self) -> None:
        self.hover_toolbar.setObjectName("BaseFigureWidgetHoverToolbar")
        self.hover_toolbar.setAttribute(QtCore.Qt.WidgetAttribute.WA_StyledBackground, True)

        layout = QtWidgets.QHBoxLayout(self.hover_toolbar)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(3)

        actions = [
            ("auto_range", "Auto range", 'ico/full-screen.png', self._toolbar_auto_range, False),
            ("legend", "Toggle legend", 'ico/case.png', self._toolbar_toggle_legend, True),
            ("grid_x", "Toggle grid X", 'ico/grip-lines-vertical.png', self._toolbar_toggle_grid_x, True),
            ("grid_y", "Toggle grid Y", 'ico/grip-lines-horizontal.png', self._toolbar_toggle_grid_y, True),
            ("crosshair", "Toggle crosshair", 'ico/square-crosshair.png', self._toolbar_toggle_crosshair, True),
            ("export_png", "Export PNG", 'ico/camera.png', self._toolbar_export_png, False),
            ("add_region", "Add region", 'ico/square-dashed-circle-plus.png', self._toolbar_add_region, False),
            ("clear_regions", "Clear regions", 'ico/square-dashed-circle-minus.png', self.clear_regions, False),
            ("clear_curves", "Clear curves", 'ico/cross.png', self.clear_trace, False),
        ]
        for key, tooltip, icon, callback, checkable in actions:
            button = IconButton(
                icon,
                tooltip,
                self.hover_toolbar,
                button_size=24,
                icon_size=14,
            )
            button.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
            button.setCheckable(checkable)
            button.clicked.connect(lambda _checked=False, cb=callback: cb())
            layout.addWidget(button)
            self.toolbar_buttons[key] = button
            self._install_hover_toolbar_filter(button)

        self.toolbar_buttons["legend"].setEnabled(self.legend is not None)
        self._install_hover_toolbar_filter(self.hover_toolbar)
        self.hover_toolbar.adjustSize()
        self.hover_toolbar.hide()
        self._sync_hover_toolbar_buttons()

    def _install_hover_toolbar_filter(self, widget: QtCore.QObject) -> None:
        if widget in self._hover_toolbar_watched:
            return
        widget.installEventFilter(self)
        self._hover_toolbar_watched.append(widget)

    def _show_hover_toolbar(self) -> None:
        self._sync_hover_toolbar_buttons()
        self._position_hover_toolbar()
        self.hover_toolbar.show()
        self.hover_toolbar.raise_()

    def _hide_hover_toolbar_if_needed(self) -> None:
        if self.rect().contains(self.mapFromGlobal(QtGui.QCursor.pos())):
            return
        self.hover_toolbar.hide()

    def _position_hover_toolbar(self) -> None:
        if not hasattr(self, "hover_toolbar"):
            return
        size = self.hover_toolbar.sizeHint()
        self.hover_toolbar.resize(size)
        margin = 8
        x = max(margin, self.width() - size.width() - margin)
        y = margin
        self.hover_toolbar.move(x, y)

    def _sync_hover_toolbar_buttons(self) -> None:
        if not hasattr(self, "toolbar_buttons"):
            return
        states = {
            "legend": self.show_legend,
            "grid_x": self.show_grid_x,
            "grid_y": self.show_grid_y,
            "crosshair": self.crosshair_enabled,
        }
        for key, checked in states.items():
            button = self.toolbar_buttons.get(key)
            if button is None:
                continue
            button.blockSignals(True)
            button.setChecked(checked)
            button.blockSignals(False)

    def _toolbar_auto_range(self) -> None:
        self.auto_range(padding=0.08)

    def _toolbar_toggle_legend(self) -> None:
        self.set_legend_visibility(not self.show_legend)

    def _toolbar_toggle_grid_x(self) -> None:
        self.set_grid(x=not self.show_grid_x)

    def _toolbar_toggle_grid_y(self) -> None:
        self.set_grid(y=not self.show_grid_y)

    def _toolbar_toggle_crosshair(self) -> None:
        self.enable_crosshair(not self.crosshair_enabled)

    def _toolbar_add_region(self) -> None:
        x_range = self.x_range()
        if x_range is None:
            return

        minimum, maximum = x_range
        span = maximum - minimum
        self.add_vertical_region(
            minimum + 0.4 * span,
            minimum + 0.6 * span,
        )

    def _toolbar_export_png(self) -> None:
        file_path, _selected_filter = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export chart as PNG",
            "",
            "PNG images (*.png)",
        )
        if not file_path:
            return
        if not file_path.lower().endswith(".png"):
            file_path = f"{file_path}.png"
        self.to_png(file_path)

    # Styling
    def _style_plot(self) -> None:
        """Apply the pyqtgraph-specific styling that QSS cannot reach."""
        text_color = self.palette().color(QtGui.QPalette.ColorRole.WindowText)
        base_color = self.palette().color(QtGui.QPalette.ColorRole.Base)
        title_style = {
            "color": text_color.name(),
            "size": self._PLOT_TITLE_SIZE,
            "family": self._PLOT_FONT_FAMILY,
        }
        plot_item = self.plot.getPlotItem()
        if hasattr(plot_item, "titleLabel"):
            for key, value in title_style.items():
                plot_item.titleLabel.setAttr(key, value)
            current_title = plot_item.titleLabel.text
            if current_title:
                self.plot.setTitle(current_title, **title_style)

        border_pen = pg.mkPen(text_color, width=1)
        label_pen = pg.mkPen(text_color)
        tick_font = QtGui.QFont(self._PLOT_FONT_FAMILY)
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
            legend_background = QtGui.QColor(base_color)
            legend_background.setAlpha(230)
            self.legend.setPen(border_pen)
            self.legend.setBrush(pg.mkBrush(legend_background))

    def set_legend_visibility(self, show: bool) -> None:
        """Convenience wrapper to toggle legend visibility."""
        self.show_legend = show

    def set_grid(self, x: Optional[object] = None, y: Optional[object] = None, alpha: Optional[object] = None) -> None:
        """Update grid visibility and alpha in one call."""
        if x is not None:
            self._show_grid_x = self._coerce_bool(x, "show_grid_x")
        if y is not None:
            self._show_grid_y = self._coerce_bool(y, "show_grid_y")
        if alpha is not None:
            self._grid_alpha = self._coerce_unit_float(alpha, "grid_alpha")
        self._apply_grid()
        self._sync_hover_toolbar_buttons()

    def set_axis_visibility(
        self,
        *,
        left: Optional[bool] = None,
        bottom: Optional[bool] = None,
        top: Optional[bool] = None,
        right: Optional[bool] = None,
    ) -> None:
        """Show or hide individual plot axes without changing their labels."""
        for axis_name, visible in {
            "left": left,
            "bottom": bottom,
            "top": top,
            "right": right,
        }.items():
            if visible is not None:
                self.plot.showAxis(axis_name, bool(visible))

    def set_x_range(self, minimum: float, maximum: float, *, padding: float = 0.0) -> None:
        """Set the visible x-axis range."""
        self.plot.setXRange(float(minimum), float(maximum), padding=float(padding))

    def set_y_range(self, minimum: float, maximum: float, *, padding: float = 0.0) -> None:
        """Set the visible y-axis range."""
        self.plot.setYRange(float(minimum), float(maximum), padding=float(padding))

    def set_ranges(
        self,
        *,
        x: Optional[Tuple[float, float]] = None,
        y: Optional[Tuple[float, float]] = None,
        padding: float = 0.0,
    ) -> None:
        """Set x and/or y visible ranges in one call."""
        if x is not None:
            self.set_x_range(x[0], x[1], padding=padding)
        if y is not None:
            self.set_y_range(y[0], y[1], padding=padding)

    def auto_range(self, *, x: bool = True, y: bool = True, padding: Optional[float] = None) -> None:
        """Auto-fit the view to the current data."""
        kwargs = {}
        if padding is not None:
            kwargs["padding"] = float(padding)
        self.plot.enableAutoRange(axis="x", enable=bool(x))
        self.plot.enableAutoRange(axis="y", enable=bool(y))
        self.plot.autoRange(**kwargs)

    def set_log_mode(self, *, x: object = False, y: object = False) -> None:
        """Enable or disable logarithmic display for each axis."""
        self._log_x = self._coerce_bool(x, "log_x")
        self._log_y = self._coerce_bool(y, "log_y")
        self.plot.setLogMode(x=self._log_x, y=self._log_y)

    def enable_crosshair(self, enabled: bool = True, *, show_label: bool = True) -> None:
        """Show a mouse-following crosshair and emit cursorPositionChanged."""
        enabled = bool(enabled)
        self._crosshair_label_visible = bool(show_label)
        if enabled == self._crosshair_enabled:
            self._set_crosshair_items_visible(enabled)
            return

        if enabled:
            self._ensure_crosshair_items()
            self.plot.scene().sigMouseMoved.connect(self._on_mouse_moved)
            self._crosshair_enabled = True
            self._set_crosshair_items_visible(True)
        else:
            try:
                self.plot.scene().sigMouseMoved.disconnect(self._on_mouse_moved)
            except (TypeError, RuntimeError):
                pass
            self._crosshair_enabled = False
            self._set_crosshair_items_visible(False)
        self._sync_hover_toolbar_buttons()

    def disable_crosshair(self) -> None:
        """Hide and disconnect the crosshair."""
        self.enable_crosshair(False)

    def set_titles(self, title: str = "", x: str = "", y: str = "") -> None:
        """Set plot and axis titles in one call."""
        self.plot.setTitle(title)
        self.plot.setLabel("bottom", x)
        self.plot.setLabel("left", y)

    def clear_titles(self) -> None:
        """Clear plot and axis titles."""
        self.set_titles("", "", "")

    def set_color_palette(self, palette: Sequence[str]) -> None:
        """Replace the color palette used for new and existing curves."""
        if not palette:
            return
        self.color_palette = list(palette)
        for idx, curve in enumerate(self._curves):
            self._style_curve(curve, idx)

    def set_legend_position(self, position: str) -> None:
        """Move the legend to one of the four corners. Valid values: 'top-left', 'top-right', 'bottom-left', 'bottom-right'."""
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
    def current_settings(self) -> FigureSettings:
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
            "grid_alpha": self.grid_alpha,
            "log_x": self.log_x,
            "log_y": self.log_y,
        }

    def apply_settings(self, settings: Mapping[str, object]) -> None:
        """Apply visual settings to the plot widget.

        Unknown keys are ignored. Common persisted scalar values are coerced.
        """
        if not isinstance(settings, Mapping):
            raise TypeError("settings must be a mapping")

        if "mode" in settings:
            self.mode = settings["mode"]

        if "line_width" in settings:
            self.line_width = settings["line_width"]

        if "marker_size" in settings:
            self.marker_size = settings["marker_size"]

        if "plot_title" in settings:
            self.plot_title = self._coerce_text(settings["plot_title"], "plot_title")
        if "x_axis_title" in settings:
            self.x_axis_title = self._coerce_text(settings["x_axis_title"], "x_axis_title")
        if "y_axis_title" in settings:
            self.y_axis_title = self._coerce_text(settings["y_axis_title"], "y_axis_title")

        if "show_legend" in settings:
            self.show_legend = settings["show_legend"]

        grid_x = (
            self._coerce_bool(settings["show_grid_x"], "show_grid_x")
            if "show_grid_x" in settings
            else None
        )
        grid_y = (
            self._coerce_bool(settings["show_grid_y"], "show_grid_y")
            if "show_grid_y" in settings
            else None
        )
        grid_alpha = (
            self._coerce_unit_float(settings["grid_alpha"], "grid_alpha")
            if "grid_alpha" in settings
            else None
        )
        if grid_x is not None or grid_y is not None or grid_alpha is not None:
            self.set_grid(x=grid_x, y=grid_y, alpha=grid_alpha)

        if "log_x" in settings or "log_y" in settings:
            self.set_log_mode(
                x=(
                    self._coerce_bool(settings["log_x"], "log_x")
                    if "log_x" in settings
                    else self.log_x
                ),
                y=(
                    self._coerce_bool(settings["log_y"], "log_y")
                    if "log_y" in settings
                    else self.log_y
                ),
            )

        for curve in self._curves:
            self._style_curve(curve)

    def add_dataset(
        self,
        y: DatasetInput,
        x: Optional[DatasetInput] = None,
        *,
        name: str = "",
        color: Optional[ColorInput] = None,
        line_width: Optional[int] = None,
        symbol: Optional[str] = "auto",
        marker_size: Optional[int] = None,
        visible: bool = True,
    ) -> pg.PlotDataItem:
        """
        Add a curve with optional x data. If x is None, indices are used.
        h5py Dataset objects are accepted and read eagerly.

        Optional style arguments override the widget defaults for this curve.
        Use symbol="auto" to follow the widget mode, or symbol=None to force
        markers off for this curve.
        """
        if y is None:
            raise ValueError("y cannot be None")

        y_arr = self._to_1d_float_array(y, "y")
        if y_arr.size == 0:
            raise ValueError("y cannot be empty")

        x_arr = None
        if x is not None:
            x_arr = self._to_1d_float_array(x, "x")
            if x_arr.shape != y_arr.shape:
                raise ValueError("x and y must have the same shape")
        if x_arr is None:
            x_arr = np.arange(y_arr.size, dtype=float)

        curve = self._new_curve(
            name=name or f"Trace {len(self._curves) + 1}",
            color=color,
            line_width=line_width,
            symbol=symbol,
            marker_size=marker_size,
            visible=visible,
        )
        try:
            curve.setData(x_arr, y_arr)
            curve.setClipToView(True)
        except Exception:
            if curve in self._curves:
                self._remove_curve_item(curve)
            elif curve in self.plot.items():
                self.plot.removeItem(curve)
            raise
        return curve

    def get_curve(self, curve: CurveReference) -> Optional[pg.PlotDataItem]:
        """Return a curve by item or name, or None when it is not present."""
        if isinstance(curve, pg.PlotDataItem):
            return curve if curve in self._curves else None

        for item in self._curves:
            if item.name() == curve:
                return item
        return None

    def require_curve(self, curve: CurveReference) -> pg.PlotDataItem:
        """Return a curve by item or name, raising KeyError when missing."""
        item = self.get_curve(curve)
        if item is None:
            raise KeyError(f"Unknown curve: {curve!r}")
        return item

    def curve_names(self) -> list[str]:
        """Return non-empty curve names in display order."""
        return [curve.name() for curve in self._curves if curve.name()]

    def remove_curve(self, curve: CurveReference) -> pg.PlotDataItem:
        """Remove a curve by item or name and return the removed item."""
        item = self.require_curve(curve)
        self._remove_curve_item(item)
        return item

    def clear_curve(self, curve: CurveReference) -> pg.PlotDataItem:
        """Clear one curve's data without removing its style or legend entry."""
        item = self.require_curve(curve)
        item.setData([], [])
        return item

    def set_curve_visible(self, curve: CurveReference, visible: bool) -> pg.PlotDataItem:
        """Show or hide one curve by item or name."""
        item = self.require_curve(curve)
        item.setVisible(bool(visible))
        return item

    def update_curve(
        self,
        curve: CurveReference,
        y: Optional[DatasetInput] = None,
        x: Optional[DatasetInput] = None,
        *,
        name: Optional[str] = None,
        color: object = _UNSET,
        line_width: object = _UNSET,
        symbol: object = _UNSET,
        marker_size: object = _UNSET,
        visible: Optional[bool] = None,
    ) -> pg.PlotDataItem:
        """Update one curve's data, style, name, or visibility."""
        item = self.require_curve(curve)

        if y is not None:
            y_arr = self._to_1d_float_array(y, "y")
            if y_arr.size == 0:
                raise ValueError("y cannot be empty")

            if x is not None:
                x_arr = self._to_1d_float_array(x, "x")
                if x_arr.shape != y_arr.shape:
                    raise ValueError("x and y must have the same shape")
            elif item.xData is not None and item.xData.shape == y_arr.shape:
                x_arr = item.xData
            else:
                x_arr = np.arange(y_arr.size, dtype=float)
            item.setData(x_arr, y_arr)
        elif x is not None:
            if item.yData is None:
                raise ValueError("cannot update x without existing y data")
            x_arr = self._to_1d_float_array(x, "x")
            if x_arr.shape != item.yData.shape:
                raise ValueError("x and y must have the same shape")
            item.setData(x_arr, item.yData)

        if name is not None:
            old_name = item.name()
            item.opts["name"] = name
            if self.legend is not None and old_name:
                try:
                    self.legend.removeItem(old_name)
                    self.legend.addItem(item, name)
                except Exception:
                    pass

        style = self._curve_style(item)
        if color is not _UNSET:
            style["color"] = color
        if line_width is not _UNSET:
            style["line_width"] = line_width
        if symbol is not _UNSET:
            style["symbol"] = symbol
        if marker_size is not _UNSET:
            style["marker_size"] = marker_size
        if any(value is not _UNSET for value in (color, line_width, symbol, marker_size)):
            self._style_curve(item)

        if visible is not None:
            item.setVisible(bool(visible))

        return item

    @staticmethod
    def _to_1d_float_array(data: DatasetInput, label: str) -> np.ndarray:
        if BaseFigureWidget._is_hdf5_dataset(data):
            data = data[()]

        arr = np.asarray(data, dtype=float)
        if arr.ndim != 1:
            raise ValueError(f"{label} must be one-dimensional")
        return arr

    @staticmethod
    def _is_hdf5_dataset(data: object) -> bool:
        return type(data).__module__.startswith("h5py.") and hasattr(data, "__getitem__")

    def clear_region(self, region: pg.LinearRegionItem) -> None:
        """Remove a specific LinearRegionItem if present."""
        if region in self.plot.items():
            self.plot.removeItem(region)

    def add_vertical_region(self, start: float, end: float, *, brush: Optional[QtGui.QBrush] = None, bounds: Optional[Tuple[Optional[float], Optional[float]]] = None) -> pg.LinearRegionItem:
        """Add a vertical LinearRegionItem with optional bounds."""
        min_x, max_x = (None, None) if bounds is None else bounds

        if min_x is None or max_x is None:
            data_range = self.x_values_range()
            if data_range is not None:
                min_x, max_x = data_range

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
        return self._data_range("xData")

    def y_values_range(self) -> Optional[Tuple[float, float]]:
        """Return y value range across all curves."""
        return self._data_range("yData")

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
        if x_range is None or y_range is None:
            return None
        return x_range, y_range

    def set_background(self, color: Optional[str] = None) -> None:
        """Set plot background color (or None for transparent)."""
        self.plot.setBackground(color)

    def repaint(self, *args: object) -> None:
        """Force a repaint of the plot."""
        super().repaint(*args)
        self.plot.repaint()

    def update(self, *args: object) -> None:
        """Force a redraw of the plot."""
        super().update(*args)
        self.plot.update()

    def clear_trace(self) -> None:
        """Clear all curves from the plot."""
        for curve in list(self._curves):
            self._remove_curve_item(curve)

    def clear_regions(self) -> None:
        """Clear all region selectors from the plot."""
        regions = [item for item in self.plot.items() if isinstance(item, pg.LinearRegionItem)]
        for reg in regions:
            self.plot.removeItem(reg)

    # Internals
    @staticmethod
    def _coerce_mode(value: object) -> FigureMode:
        if not isinstance(value, str):
            raise ValueError(f"mode must be one of: {_ALLOWED_MODES}")

        normalized = value.strip().lower().replace("_", "-").replace(" ", "")
        if normalized in _ALLOWED_MODES:
            return cast(FigureMode, normalized)
        raise ValueError(f"mode must be one of: {_ALLOWED_MODES}")

    @staticmethod
    def _coerce_positive_int(value: object, label: str) -> int:
        if isinstance(value, bool):
            raise ValueError(f"{label} must be an integer")
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{label} must be an integer") from exc

        if not np.isfinite(number) or not number.is_integer():
            raise ValueError(f"{label} must be an integer")
        return max(1, int(number))

    @staticmethod
    def _coerce_unit_float(value: object, label: str) -> float:
        if isinstance(value, bool):
            raise ValueError(f"{label} must be a number between 0 and 1")
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{label} must be a number between 0 and 1") from exc

        if not np.isfinite(number):
            raise ValueError(f"{label} must be a number between 0 and 1")
        return max(0.0, min(1.0, number))

    @staticmethod
    def _coerce_bool(value: object, label: str) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, np.bool_):
            return bool(value)
        if isinstance(value, (int, np.integer)):
            if value in (0, 1):
                return bool(value)
            raise ValueError(f"{label} must be boolean-like")
        if isinstance(value, (float, np.floating)):
            if value in (0.0, 1.0):
                return bool(value)
            raise ValueError(f"{label} must be boolean-like")
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "t", "yes", "y", "on"}:
                return True
            if normalized in {"0", "false", "f", "no", "n", "off", ""}:
                return False
        raise ValueError(f"{label} must be boolean-like")

    @staticmethod
    def _coerce_text(value: object, label: str) -> str:
        if value is None:
            raise ValueError(f"{label} must be text")
        return str(value)

    def _apply_grid(self) -> None:
        self.plot.showGrid(x=self._show_grid_x, y=self._show_grid_y, alpha=self._grid_alpha)

    def _new_curve(
        self,
        name: str,
        *,
        color: Optional[ColorInput] = None,
        line_width: Optional[int] = None,
        symbol: Optional[str] = "auto",
        marker_size: Optional[int] = None,
        visible: bool = True,
    ) -> pg.PlotDataItem:
        curve_index = len(self._curves)

        curve = pg.PlotDataItem(name=name)
        curve._pyqt_widget_kit_style = {  # type: ignore[attr-defined]
            "color": color,
            "line_width": line_width,
            "symbol": symbol,
            "marker_size": marker_size,
        }
        self._style_curve(curve, curve_index)
        curve.setVisible(bool(visible))
        self.plot.addItem(curve)
        self._curves.append(curve)
        return curve

    def _style_curve(self, curve: pg.PlotDataItem, curve_index: Optional[int] = None) -> None:
        if curve_index is None:
            try:
                curve_index = self._curves.index(curve)
            except ValueError:
                curve_index = 0

        style = self._curve_style(curve)
        color = style.get("color") or self.color_palette[curve_index % len(self.color_palette)]
        line_width = self._positive_int(style.get("line_width"), self.line_width)
        marker_size = self._positive_int(style.get("marker_size"), self.marker_size)
        symbol = style.get("symbol", "auto")

        pen = pg.mkPen(color, width=line_width) if "lines" in self.mode else None
        if symbol == "auto":
            sym = "o" if "markers" in self.mode else None
        else:
            sym = symbol

        if pen is None:
            curve.setPen(None)
            curve.opts["pen"] = None
        else:
            curve.setPen(pen)
        curve.setSymbol(sym)
        if sym:
            curve.setSymbolSize(marker_size)
            curve.setSymbolBrush(pg.mkBrush(color))
        curve.setClipToView(True)

    def _curve_style(self, curve: pg.PlotDataItem) -> dict:
        style = getattr(curve, "_pyqt_widget_kit_style", None)
        if style is None:
            style = {}
            curve._pyqt_widget_kit_style = style  # type: ignore[attr-defined]
        return style

    def _remove_curve_item(self, curve: pg.PlotDataItem) -> None:
        if self.legend is not None and curve.name():
            try:
                self.legend.removeItem(curve.name())
            except Exception:
                pass
        if curve in self.plot.items():
            self.plot.removeItem(curve)
        if curve in self._curves:
            self._curves.remove(curve)

    def _data_range(self, attribute: str) -> Optional[Tuple[float, float]]:
        arrays = []
        for item in self._curves:
            data = getattr(item, attribute, None)
            if data is None:
                continue
            arr = np.asarray(data, dtype=float).reshape(-1)
            if arr.size:
                arrays.append(arr)

        if not arrays:
            return None

        values = np.concatenate(arrays)
        values = values[np.isfinite(values)]
        if values.size == 0:
            return None
        return float(np.min(values)), float(np.max(values))

    @staticmethod
    def _positive_int(value: object, default: int) -> int:
        try:
            return max(1, int(value))
        except (TypeError, ValueError):
            return default

    def _ensure_crosshair_items(self) -> None:
        if self._crosshair_vline is not None and self._crosshair_hline is not None:
            return

        pen = pg.mkPen(QtGui.QColor(80, 80, 80, 180), width=1, style=QtCore.Qt.PenStyle.DashLine)
        self._crosshair_vline = pg.InfiniteLine(angle=90, movable=False, pen=pen)
        self._crosshair_hline = pg.InfiniteLine(angle=0, movable=False, pen=pen)
        self._crosshair_label = pg.TextItem(
            anchor=(1, 1),
            fill=pg.mkBrush(255, 255, 255, 220),
            border=pg.mkPen(QtGui.QColor(80, 80, 80, 180)),
        )

        plot_item = self.plot.getPlotItem()
        plot_item.addItem(self._crosshair_vline, ignoreBounds=True)
        plot_item.addItem(self._crosshair_hline, ignoreBounds=True)
        plot_item.addItem(self._crosshair_label, ignoreBounds=True)
        self._set_crosshair_items_visible(False)

    def _set_crosshair_items_visible(self, visible: bool) -> None:
        for item in (self._crosshair_vline, self._crosshair_hline):
            if item is not None:
                item.setVisible(bool(visible))
        if self._crosshair_label is not None:
            self._crosshair_label.setVisible(bool(visible and self._crosshair_label_visible))

    def _on_mouse_moved(self, pos: QtCore.QPointF) -> None:
        if not self._crosshair_enabled:
            return

        view_box = self.plot.getViewBox()
        if view_box is None or not view_box.sceneBoundingRect().contains(pos):
            self._set_crosshair_items_visible(False)
            return

        mouse_point = view_box.mapSceneToView(pos)
        x = float(mouse_point.x())
        y = float(mouse_point.y())

        if self._crosshair_vline is not None:
            self._crosshair_vline.setPos(x)
        if self._crosshair_hline is not None:
            self._crosshair_hline.setPos(y)
        if self._crosshair_label is not None:
            self._crosshair_label.setText(f"x={x:.6g}\ny={y:.6g}")
            self._crosshair_label.setPos(x, y)

        self._set_crosshair_items_visible(True)
        self.cursorPositionChanged.emit(x, y)
