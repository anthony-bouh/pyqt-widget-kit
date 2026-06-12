from __future__ import annotations

import os

import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtWidgets
import pyqtgraph as pg

from pyqt_widget_kit.graph import BaseFigureWidget


class FakeHDF5Dataset:
    __module__ = "h5py._hl.dataset"

    def __init__(self, values: object) -> None:
        self._values = np.asarray(values)
        self.dtype = self._values.dtype
        self.ndim = self._values.ndim
        self.shape = self._values.shape
        self.was_read = False

    def __getitem__(self, key: object) -> np.ndarray:
        if key != ():
            raise KeyError(key)
        self.was_read = True
        return self._values


@pytest.fixture(scope="module")
def qapp() -> QtWidgets.QApplication:
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


@pytest.fixture
def figure(qapp: QtWidgets.QApplication) -> BaseFigureWidget:
    widget = BaseFigureWidget()
    yield widget
    widget.close()
    widget.deleteLater()


@pytest.mark.parametrize("y", [5, [[1, 2], [3, 4]]])
def test_add_dataset_rejects_non_1d_y(figure: BaseFigureWidget, y: object) -> None:
    with pytest.raises(ValueError, match="y must be one-dimensional"):
        figure.add_dataset(y)


@pytest.mark.parametrize("x", [5, [[1, 2]]])
def test_add_dataset_rejects_non_1d_x(figure: BaseFigureWidget, x: object) -> None:
    with pytest.raises(ValueError, match="x must be one-dimensional"):
        figure.add_dataset([1, 2], x=x)


def test_add_dataset_accepts_hdf5_dataset_like_inputs(figure: BaseFigureWidget) -> None:
    x = FakeHDF5Dataset([0, 1, 2])
    y = FakeHDF5Dataset([1, 4, 9])

    curve = figure.add_dataset(y, x=x, name="HDF5")

    assert x.was_read
    assert y.was_read
    assert curve.name() == "HDF5"
    np.testing.assert_allclose(curve.xData, [0.0, 1.0, 2.0])
    np.testing.assert_allclose(curve.yData, [1.0, 4.0, 9.0])


def test_add_dataset_numbers_unnamed_traces(figure: BaseFigureWidget) -> None:
    first = figure.add_dataset([1, 2])
    second = figure.add_dataset([3, 4])

    assert first.name() == "Trace 1"
    assert second.name() == "Trace 2"


def test_add_dataset_removes_curve_if_set_data_fails(
    figure: BaseFigureWidget,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_new_curve = figure._new_curve

    def broken_new_curve(name: str, **kwargs: object):
        curve = original_new_curve(name, **kwargs)

        def fail_set_data(*_args, **_kwargs) -> None:
            raise RuntimeError("setData failed")

        monkeypatch.setattr(curve, "setData", fail_set_data)
        return curve

    monkeypatch.setattr(figure, "_new_curve", broken_new_curve)

    with pytest.raises(RuntimeError, match="setData failed"):
        figure.add_dataset([1, 2])

    assert figure.curves == []
    assert figure.plot.listDataItems() == []


def test_empty_ranges_and_regions_do_not_crash(figure: BaseFigureWidget) -> None:
    assert figure.x_values_range() is None
    assert figure.y_values_range() is None
    assert figure.get_data_ranges() is None

    region = figure.add_vertical_region(1.0, 2.0)

    assert region in figure.plot.items()


def test_data_ranges_ignore_nan_values(figure: BaseFigureWidget) -> None:
    figure.add_dataset([1.0, np.nan, 3.0], x=[0.0, 1.0, 2.0])

    assert figure.x_values_range() == (0.0, 2.0)
    assert figure.y_values_range() == (1.0, 3.0)
    assert figure.get_data_ranges() == ((0.0, 2.0), (1.0, 3.0))


def test_apply_settings_preserves_omitted_titles_and_uses_grid_alpha(figure: BaseFigureWidget) -> None:
    figure.set_titles("Title", "X", "Y")

    figure.apply_settings({"show_grid_x": False, "grid_alpha": 0.6})

    assert figure.plot_title == "Title"
    assert figure.x_axis_title == "X"
    assert figure.y_axis_title == "Y"
    assert figure.show_grid_x is False
    assert figure.grid_alpha == 0.6


def test_apply_settings_coerces_persisted_scalar_values(figure: BaseFigureWidget) -> None:
    figure.apply_settings(
        {
            "mode": " Lines + markers ",
            "line_width": "3.0",
            "marker_size": "9",
            "plot_title": "Persisted Plot",
            "x_axis_title": "Elapsed",
            "y_axis_title": "Value",
            "show_legend": "false",
            "show_grid_x": "0",
            "show_grid_y": "yes",
            "grid_alpha": "0.75",
            "log_x": "on",
            "log_y": 1,
        }
    )

    assert figure.mode == "lines+markers"
    assert figure.line_width == 3
    assert figure.marker_size == 9
    assert figure.plot_title == "Persisted Plot"
    assert figure.x_axis_title == "Elapsed"
    assert figure.y_axis_title == "Value"
    assert figure.show_legend is False
    assert figure.show_grid_x is False
    assert figure.show_grid_y is True
    assert figure.grid_alpha == pytest.approx(0.75)
    assert figure.log_x is True
    assert figure.log_y is True


def test_apply_settings_rejects_ambiguous_coercions(figure: BaseFigureWidget) -> None:
    with pytest.raises(ValueError, match="show_grid_x"):
        figure.apply_settings({"show_grid_x": "sometimes"})

    with pytest.raises(ValueError, match="line_width"):
        figure.apply_settings({"line_width": "2.5"})


def test_axis_range_and_log_helpers(figure: BaseFigureWidget) -> None:
    figure.set_axis_visibility(top=False, right=False)
    figure.set_x_range(1.0, 5.0)
    figure.set_y_range(-2.0, 2.0)
    figure.set_log_mode(x=True, y=False)

    view_range = figure.plot.getViewBox().viewRange()
    assert figure.plot.getAxis("top").isVisible() is False
    assert figure.plot.getAxis("right").isVisible() is False
    assert view_range[0] == pytest.approx([1.0, 5.0])
    assert view_range[1] == pytest.approx([-2.0, 2.0])
    assert figure.log_x is True
    assert figure.log_y is False


def test_per_curve_style_overrides_survive_global_style_updates(figure: BaseFigureWidget) -> None:
    curve = figure.add_dataset(
        [1, 2, 3],
        name="Styled",
        color="#123456",
        line_width=4,
        symbol="x",
        marker_size=11,
    )

    figure.apply_settings({"mode": "lines+markers", "line_width": 1, "marker_size": 3})

    assert curve.opts["pen"].color().name() == "#123456"
    assert curve.opts["pen"].width() == 4
    assert curve.opts["symbol"] == "x"
    assert curve.opts["symbolSize"] == 11


def test_curve_management_by_name_or_handle(figure: BaseFigureWidget) -> None:
    first = figure.add_dataset([1, 2, 3], name="First")
    figure.add_dataset([3, 2, 1], name="Second")

    assert figure.curve_names() == ["First", "Second"]
    assert figure.get_curve("First") is first

    figure.update_curve("First", y=[2, 4, 6], color="#654321", visible=False)
    np.testing.assert_allclose(first.yData, [2.0, 4.0, 6.0])
    assert first.opts["pen"].color().name() == "#654321"
    assert first.isVisible() is False

    figure.set_curve_visible(first, True)
    assert first.isVisible() is True

    figure.clear_curve("First")
    assert first.xData is None or first.xData.size == 0
    assert first.yData is None or first.yData.size == 0

    removed = figure.remove_curve("Second")
    assert removed not in figure.curves
    assert figure.curve_names() == ["First"]

    with pytest.raises(KeyError, match="Unknown curve"):
        figure.require_curve("Missing")


def test_crosshair_can_be_enabled_and_disabled(figure: BaseFigureWidget) -> None:
    figure.enable_crosshair(show_label=False)

    assert figure.crosshair_enabled is True
    assert figure._crosshair_vline is not None
    assert figure._crosshair_hline is not None
    assert figure._crosshair_label is not None
    assert figure._crosshair_label.isVisible() is False

    figure.disable_crosshair()

    assert figure.crosshair_enabled is False
    assert figure._crosshair_vline.isVisible() is False
    assert figure._crosshair_hline.isVisible() is False


def test_hover_toolbar_exists_and_is_hidden_by_default(figure: BaseFigureWidget) -> None:
    expected_buttons = {
        "auto_range",
        "legend",
        "grid_x",
        "grid_y",
        "crosshair",
        "clear_regions",
        "clear_curves",
    }

    assert figure.hover_toolbar.parent() is figure
    assert figure.hover_toolbar.isHidden()
    assert set(figure.toolbar_buttons) == expected_buttons

    for button in figure.toolbar_buttons.values():
        assert button.parent() is figure.hover_toolbar
        assert button.icon().isNull() is False


def test_hover_toolbar_can_be_shown_and_syncs_button_state(figure: BaseFigureWidget) -> None:
    figure.set_legend_visibility(False)
    figure.set_grid(x=False, y=False)
    figure.enable_crosshair(True)

    figure._show_hover_toolbar()

    assert figure.hover_toolbar.isHidden() is False
    assert figure.toolbar_buttons["legend"].isChecked() is False
    assert figure.toolbar_buttons["grid_x"].isChecked() is False
    assert figure.toolbar_buttons["grid_y"].isChecked() is False
    assert figure.toolbar_buttons["crosshair"].isChecked() is True


def test_hover_toolbar_buttons_call_basic_features(figure: BaseFigureWidget) -> None:
    figure.add_dataset([1, 2, 3], name="Curve")
    figure.add_vertical_region(0.5, 1.5)

    figure.toolbar_buttons["legend"].click()
    assert figure.show_legend is False

    figure.toolbar_buttons["grid_x"].click()
    assert figure.show_grid_x is False
    assert figure.show_grid_y is True

    figure.toolbar_buttons["grid_y"].click()
    assert figure.show_grid_x is False
    assert figure.show_grid_y is False

    figure.toolbar_buttons["crosshair"].click()
    assert figure.crosshair_enabled is True

    figure.toolbar_buttons["clear_regions"].click()
    assert not any(isinstance(item, pg.LinearRegionItem) for item in figure.plot.items())

    figure.toolbar_buttons["clear_curves"].click()
    assert figure.curves == []
    assert figure.plot.listDataItems() == []
