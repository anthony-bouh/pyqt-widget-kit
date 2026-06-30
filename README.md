# PyQt Widget Kit

[![Latest release](https://img.shields.io/github/v/release/anthony-bouh/pyqt-widget-kit?sort=semver)](https://github.com/anthony-bouh/pyqt-widget-kit/releases/latest)
[![Changelog](https://img.shields.io/badge/changelog-Keep%20a%20Changelog-blue)](CHANGELOG.md)

Reusable PyQt6 widgets and graph helpers packaged for installation from GitHub
or as a local editable dependency.

## Install

For local development:

```bash
python -m pip install -e ".[dev]"
```

From GitHub after publishing the repository:

```bash
python -m pip install "git+https://github.com/anthony-bouh/pyqt-widget-kit.git"
```

From a specific GitHub release tag:

```bash
python -m pip install "git+https://github.com/anthony-bouh/pyqt-widget-kit.git@v3.0.1"
```

Check the version currently installed in the active Python environment:

```bash
python -m pip show pyqt-widget-kit
```

Check the latest version available for download from PyPI:

```bash
python -m pip index versions pyqt-widget-kit
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

Interactive scatter figures are available when points need metadata, click
signals, or rectangular selection:

```python
from pyqt_widget_kit import ScatterFigureWidget

figure = ScatterFigureWidget()
figure.add_points(
    [1.0, 2.0],
    [3.0, 4.0],
    series_name="Batch A",
    metadata=[{"filepath": "a.h5"}, {"filepath": "b.h5"}],
)
figure.pointClicked.connect(print)
figure.show()
```

## Stylesheets

The package enforces core widget proportions in Python code, so imported
widgets have sensible sizes even without any stylesheet. Colors stay under the
host application's control.

An optional QSS stylesheet is bundled for developers who want the package's
palette-based borders and validation visuals:

```python
from PyQt6 import QtWidgets
from pyqt_widget_kit import load_stylesheets

app = QtWidgets.QApplication([])
app.setStyleSheet(load_stylesheets("widgets.qss"))
```

Available stylesheets:

```python
from pyqt_widget_kit import available_stylesheets

print(available_stylesheets())
```

## Releases and Updates

New public versions are announced on
[GitHub Releases](https://github.com/anthony-bouh/pyqt-widget-kit/releases).
To receive notifications, open the repository on GitHub and choose
`Watch` -> `Custom` -> `Releases`.

The project follows [Semantic Versioning](https://semver.org/) for release
numbers:

- `MAJOR` changes can break existing user code.
- `MINOR` changes add backward-compatible features.
- `PATCH` changes fix bugs without changing the public API.

From `1.0.0` onward, breaking public API changes should use a new major
version. Breaking changes are called out in the release notes and in the
[changelog](CHANGELOG.md).

GitHub release notes are generated from merged pull requests. Use labels such
as `breaking-change`, `enhancement`, `bug`, `documentation`, and
`dependencies` to place changes in the right release-note section.

To publish a release, update `pyproject.toml` and `CHANGELOG.md`, commit the
changes, then push the matching version tag:

```bash
git tag -a v3.0.1 -m "v3.0.1"
git push origin main v3.0.1
```

The release workflow runs automatically for pushed `vX.Y.Z` tags. If the tag
event was missed, run the `Release` workflow manually from the commit you want
to release and provide the same tag. If that tag does not exist yet, the manual
workflow creates it from the selected commit before publishing the release.

## Project Layout

```text
src/pyqt_widget_kit/        Package source code
src/pyqt_widget_kit/ico/    Bundled icons used by the widgets
tests/                    Automated tests
examples/                 Small runnable examples
```
