# PyQt Widget Kit

Reusable PyQt6 widgets and settings-window helpers packaged for installation
from GitHub or as a local editable dependency.

## Install

For local development:

```bash
python -m pip install -e ".[dev]"
```

From GitHub after publishing the repository:

```bash
python -m pip install "git+https://github.com/anthony-bouh/pyqt-widget-kit.git"
```

## Quick Use

```python
from PyQt6 import QtWidgets
from pyqt_widget_kit import PillSelector

app = QtWidgets.QApplication([])

selector = PillSelector()
selector.set_pills(["Python", "Qt", "PyQt6", "GUI"])
selector.set_selection_mode("multi")
selector.selectionChanged.connect(print)
selector.show()

app.exec()
```

## Stylesheets

The package enforces core widget proportions in Python code, so imported
widgets have sensible sizes even without any stylesheet. Colors stay under the
host application's control.

Optional QSS stylesheets are bundled for developers who want the package's
palette-based borders and validation visuals:

```python
from PyQt6 import QtWidgets
from pyqt_widget_kit import load_stylesheets

app = QtWidgets.QApplication([])
app.setStyleSheet(load_stylesheets("widgets.qss", "settings.qss"))
```

Available stylesheets:

```python
from pyqt_widget_kit import available_stylesheets

print(available_stylesheets())
```

Settings helpers are available from `pyqt_widget_kit.settings`:

```python
from pyqt_widget_kit.settings import SettingsWindow


class ExportSettingsWindow(SettingsWindow):
    title = "Export Settings"
    show_tree = True

    def __init__(self) -> None:
        super().__init__()
        self.add_text(key="export.name", title="Export name", value="result")
        self.add_bool(key="export.overwrite", title="Overwrite", value=False)
```

`SettingsWindow` can also be configured without subclass attributes:

```python
window = SettingsWindow(
    title="Export Settings",
    show_tree=True,
    modal=False,
    stay_on_top=False,
    apply_default_style=False,
    minimum_size=(600, 400),
)
```

## Project Layout

```text
src/pyqt_widget_kit/        Package source code
src/pyqt_widget_kit/ico/    Bundled icons used by the widgets
tests/                    Automated tests
examples/                 Small runnable examples
docs/                     Longer usage documentation
```
