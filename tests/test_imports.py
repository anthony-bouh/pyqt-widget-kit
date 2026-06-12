from pathlib import Path


def test_public_widgets_import() -> None:
    import pyqt_widget_kit

    assert pyqt_widget_kit.PillSelector.__name__ == "PillSelector"
    assert pyqt_widget_kit.RegexLineEdit.__name__ == "RegexLineEdit"
    assert pyqt_widget_kit.IconButton.__name__ == "IconButton"
    assert pyqt_widget_kit.RightLeftButton.__name__ == "RightLeftButton"
    assert pyqt_widget_kit.BaseFigureWidget.__name__ == "BaseFigureWidget"
    assert pyqt_widget_kit.FigureSettings.__name__ == "FigureSettings"
    assert pyqt_widget_kit.ScatterFigureWidget.__name__ == "ScatterFigureWidget"
    assert pyqt_widget_kit.ScatterPointPayload.__name__ == "ScatterPointPayload"
    assert not any(name.startswith("My") for name in pyqt_widget_kit.__all__)


def test_settings_import() -> None:
    from pyqt_widget_kit.settings import SettingSpec, SettingsWindow

    assert SettingSpec.__name__ == "SettingSpec"
    assert SettingsWindow.__name__ == "SettingsWindow"


def test_resource_path_resolves_packaged_icon() -> None:
    from pyqt_widget_kit import resource_path

    icon_path = Path(resource_path("ico/folder.png"))
    assert icon_path.name == "folder.png"
    assert icon_path.exists()


def test_stylesheets_are_available() -> None:
    from pyqt_widget_kit import available_stylesheets, load_stylesheet, load_stylesheets, stylesheet_path

    stylesheets = available_stylesheets()
    assert stylesheets == ["settings.qss", "widgets.qss"]

    widgets_stylesheet = Path(stylesheet_path("widgets.qss"))
    assert widgets_stylesheet.name == "widgets.qss"
    assert widgets_stylesheet.exists()

    assert "RegexLineEdit" in load_stylesheet("widgets.qss")
    assert "QFrame#_TopMenu" in load_stylesheets("settings.qss", "widgets.qss")
