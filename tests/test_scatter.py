from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6 import QtWidgets

from pyqt_widget_kit.scatter import ScatterFigureWidget


@pytest.fixture(scope="module")
def qapp() -> QtWidgets.QApplication:
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


@pytest.fixture
def figure(qapp: QtWidgets.QApplication) -> ScatterFigureWidget:
    widget = ScatterFigureWidget()
    yield widget
    widget.close()
    widget.deleteLater()


def test_add_points_stores_series_metadata_and_payloads(figure: ScatterFigureWidget) -> None:
    indices = figure.add_points(
        [1.0, 2.0],
        [3.0, 4.0],
        series_name="Batch A",
        metadata=[
            {"file": "a.h5", "filepath": "/data/a.h5"},
            {"file": "b.h5", "filepath": "/data/b.h5"},
        ],
        auto_range=False,
    )

    assert indices == [0, 1]
    assert figure.series_names() == ["Batch A"]
    assert len(figure.curves) == 1
    assert len(figure.scatter_items) == 1

    points = figure.points_in_rect(0.0, 1.5, 0.0, 3.5)
    assert len(points) == 1
    assert points[0]["series"] == "Batch A"
    assert points[0]["index"] == 0
    assert points[0]["metadata"] == {"file": "a.h5", "filepath": "/data/a.h5"}
    assert points[0]["filepath"] == "/data/a.h5"


def test_add_points_appends_to_existing_series(figure: ScatterFigureWidget) -> None:
    figure.add_points([1.0], [2.0], series_name="Series", metadata=[{"id": "first"}], auto_range=False)
    indices = figure.add_points([3.0], [4.0], series_name="Series", metadata=[{"id": "second"}], auto_range=False)

    assert indices == [1]
    assert figure.series_names() == ["Series"]
    assert len(figure.scatter_items[0].points()) == 2

    points = figure.points_in_rect(2.5, 3.5, 3.5, 4.5)
    assert points[0]["index"] == 1
    assert points[0]["id"] == "second"


def test_apply_settings_updates_curve_and_scatter_style(figure: ScatterFigureWidget) -> None:
    figure.add_points([1.0, 2.0], [3.0, 4.0], series_name="Series", auto_range=False)

    figure.apply_settings({"mode": "lines", "line_width": 3, "marker_size": 12})

    curve = figure.curves[0]
    assert curve.opts["pen"] is not None
    assert curve.opts["pen"].width() == 3
    assert curve.opts["symbol"] is None
    assert figure.scatter_items[0].isVisible() is False
    assert figure.scatter_items[0].opts["size"] == 12

    figure.apply_settings({"mode": "markers"})

    assert figure.curves[0].opts["pen"] is None
    assert figure.curves[0].opts["symbol"] == "o"
    assert figure.scatter_items[0].isVisible() is True


def test_point_click_emits_payload_and_highlights_point(figure: ScatterFigureWidget) -> None:
    figure.add_points(
        [1.0],
        [2.0],
        series_name="Series",
        metadata=[{"filepath": "/data/a.h5"}],
        auto_range=False,
    )
    emitted: list[dict] = []
    figure.pointClicked.connect(emitted.append)

    point = figure.scatter_items[0].points()[0]
    figure._on_point_clicked(figure.scatter_items[0], [point])

    assert emitted == [
        {
            "series": "Series",
            "index": 0,
            "x": 1.0,
            "y": 2.0,
            "metadata": {"filepath": "/data/a.h5"},
            "filepath": "/data/a.h5",
        }
    ]
    assert figure.highlight.isVisible() is True


def test_select_points_in_rect_highlights_and_emits(figure: ScatterFigureWidget) -> None:
    figure.add_points([1.0, 2.0, 3.0], [1.0, 2.0, 3.0], series_name="Series", auto_range=False)
    emitted: list[list[dict]] = []
    figure.pointsSelected.connect(emitted.append)

    selected = figure.select_points_in_rect(0.0, 2.5, 0.0, 2.5)

    assert [point["index"] for point in selected] == [0, 1]
    assert [point["index"] for point in emitted[0]] == [0, 1]
    assert figure.multi_highlight.isVisible() is True


def test_clear_removes_series_and_selection_state(figure: ScatterFigureWidget) -> None:
    figure.add_points([1.0], [2.0], series_name="Series", auto_range=False)
    figure.enable_rectangle_selection(True)

    figure.clear()

    assert figure.series_names() == []
    assert figure.curves == []
    assert figure.scatter_items == []
    assert figure.selection_active is False
    assert figure.highlight in figure.plot.items()
    assert figure.multi_highlight in figure.plot.items()
