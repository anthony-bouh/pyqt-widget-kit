# Settings UI Module

The `pyqt_widget_kit.settings` package helps developers build settings dialogs quickly while
keeping full control over the real Qt widgets.

Use typed helpers for common fields, and use `add_widget()` for custom or already
configured widgets. The design rule is:

- **helpers** create common widgets quickly
- **widgets** carry their own constraints and behavior
- **keys** identify values and must be unique inside a window
- **sections** group rows in the navigation tree
- **window instances** own their state, which matters for MDI windows

## Minimal Window

```python
from pyqt_widget_kit.settings import SettingsWindow


class ExportSettingsWindow(SettingsWindow):
    title = "Export Settings"
    show_tree = True

    def __init__(self) -> None:
        super().__init__()

        self.output_folder = self.add_path(
            key="export.output_folder",
            title="Output folder",
            kind="folder",
            section="Paths",
            description="Folder where exported files will be written.",
        ).widget

        self.separator = self.add_text(
            key="export.separator",
            title="Separator",
            value=",",
            section="CSV",
            validator=lambda value: None if len(value) == 1 else "Use one character.",
        ).widget

        self.apply_button = self.add_button("Apply", self.apply, validate=True)

    def apply(self) -> None:
        values = self.values()
        print(values["export.output_folder"])
        print(values["export.separator"])
```

## Typed Helpers

Typed helpers create a real Qt widget, add it as a row, and return the
`SettingLayout`. Access `.widget` when you want to customize the widget further.

```python
self.factor = self.add_int(
    key="decimate.factor",
    title="Decimation factor",
    value=10,
    minimum=2,
    maximum=1000,
    section="Parameters",
).widget

self.factor.setMaximumWidth(80)
```

Available helpers:

```python
self.add_text(...)
self.add_secret(...)
self.add_bool(...)
self.add_int(...)
self.add_float(...)
self.add_choice(...)
self.add_path(...)
self.add_regex(...)
self.add_list(...)
self.add_custom(...)
```

## Custom Widgets

Use `add_widget()` when the widget needs custom setup, custom signals, or custom
constraints.

```python
from pyqt_widget_kit import RegexLineEdit

self.dataset_regex = RegexLineEdit(multi_regex_enabled=True)
self.dataset_regex.setPlaceholderText("Dataset regex")
self.dataset_regex.setExample("post/truncate/.*/data")

self.add_widget(
    key="decimate.dataset_regex",
    title="Datasets to Decimate",
    section="Selection",
    description="Regex used to select datasets.",
    widget=self.dataset_regex,
)
```

Custom widgets can participate in settings values by exposing one of these APIs:

```python
to_dict() / from_dict(mapping)
to_list() / from_list(values)
text() / setText(value)
value() / setValue(value)
get_value() / set_value(value)
```

Custom widgets can participate in validation by exposing:

```python
validate() -> str | None
```

If the widget emits `validityChanged`, `validationChanged`, `textChanged`,
`valueChanged`, `currentTextChanged`, or `toggled`, the settings window will
automatically refresh validation when it changes.

## Sections

Sections are UI navigation only. They are not persistence keys.

Use a slash-separated shortcut:

```python
self.add_bool(
    key="plot.show_grid_x",
    title="Show Grid X",
    value=True,
    section="Formatting/Grid",
)
```

Or keep section handles when that is clearer:

```python
formatting = self.add_section("Formatting")
axis = formatting.add_section("Axis")

self.x_axis_title = axis.add_text(
    key="plot.x_axis_title",
    title="X Axis Title",
    value=self.fig.x_axis_title,
).widget
```

The setting key should remain unique:

```python
# Good
key="plot.x_axis_title"

# Avoid
key="Formatting/Axis"
key=""
```

## Section Context Menus

Override `populate_section_context_menu()` to add right-click actions on tree
sections. Actions can add widgets dynamically through the section proxy.

```python
from PyQt6 import QtWidgets


class DynamicSettingsWindow(SettingsWindow):
    title = "Dynamic Settings"
    show_tree = True

    def populate_section_context_menu(self, menu, section) -> None:
        menu.addAction("Add text setting", lambda: self.add_user_text(section))

    def add_user_text(self, section) -> None:
        title, ok = QtWidgets.QInputDialog.getText(
            self,
            "Add Setting",
            "Setting name:",
        )
        if not ok or not title.strip():
            return

        base = title.strip().lower().replace(" ", "_")
        key = f"dynamic.{section.path.replace('/', '.')}.{base}"
        index = 2
        while self.setting(key) is not None:
            key = f"dynamic.{section.path.replace('/', '.')}.{base}_{index}"
            index += 1

        setting = section.add_text(key=key, title=title.strip())
        self.scroll_area.ensureWidgetVisible(setting)
```

If dynamic settings must persist, recreate their definitions first, then call
`load_dict()` or `load_json()` so saved values have matching widgets.

## Reading And Writing Values

```python
values = self.values()

self.set_values({
    "plot.show_grid_x": True,
    "plot.line_width": 2,
})
```

`values()` returns a flat dictionary keyed by setting key.

```python
{
    "plot.show_grid_x": True,
    "plot.line_width": 2,
    "plot.mode": "lines",
}
```

## Validation

Prefer validation close to the field:

```python
def requires_token(token: str):
    def validator(value) -> str | None:
        return None if token in str(value) else f"Missing required token: {token}"
    return validator


self.output_name = self.add_text(
    key="decimate.output_name",
    title="Output Name",
    value="post/decimate/{group}/{dataset}",
    validator=requires_token("{dataset}"),
).widget
```

Use `validate_window()` for cross-field rules:

```python
class ResampleSettingsWindow(SettingsWindow):
    title = "Resample"

    def __init__(self) -> None:
        super().__init__()

        self.sample_count = self.add_int(
            key="resample.sample_count",
            title="Sample count",
            value=0,
            minimum=0,
        ).widget

        self.target_dataset = self.add_regex(
            key="resample.target_dataset",
            title="Target dataset",
        ).widget

        self.apply_button = self.add_button("Apply", self.apply, validate=True)

    def validate_window(self) -> str | None:
        has_samples = self.sample_count.value() != 0
        has_target = self.target_dataset.text().strip() != ""
        if has_samples == has_target:
            return "Use either sample count or target dataset, but not both."
        return None
```

If `validate_window()` depends on external state that is not a widget, refresh
validation when that state changes:

```python
def selection_changed(self, nodes) -> None:
    self.files = [node.path for node in nodes]
    self.refresh_validation()
```

## MDI Windows

Do not store MDI settings in module globals. Multiple instances of the same
settings window can exist at once.

Read the current state from the object being edited:

```python
class PlotSettingsWindow(SettingsWindow):
    title = "Plot Settings"
    show_tree = True

    def __init__(self, fig) -> None:
        super().__init__()
        self.fig = fig
        state = fig.current_settings()

        self.mode = self.add_choice(
            key="mode",
            title="Plot Type",
            options=["lines", "markers", "lines+markers"],
            value=state["mode"],
            section="Formatting/Plot Type",
        ).widget

        self.line_width = self.add_int(
            key="line_width",
            title="Line Width",
            value=state["line_width"],
            minimum=1,
            maximum=10,
            section="Formatting/Plot Type",
        ).widget

        self.add_button("Apply", self.apply)

    def apply(self) -> None:
        self.fig.apply_settings(self.values())
```

If users need shared defaults or presets, add explicit actions such as
"Save as Default" or "Load Preset" instead of auto-saving from every MDI window.

## Presets And Persistence

The settings window already supports JSON state:

```python
self.save_json("my_preset.json")
self.load_json("my_preset.json")
```

For future persistence work, keep these scopes separate:

- `QSettings`: local user defaults and last-used values
- JSON presets: portable reusable setups
- current object state: per-window MDI state
- HDF5 attributes: processing provenance

## Full Example

```python
from pyqt_widget_kit.settings import SettingsWindow


class DecimateSettingsWindow(SettingsWindow):
    title = "Decimate Datasets"
    show_tree = True

    def __init__(self, files: list[str]) -> None:
        super().__init__()
        self.files = files

        self.dataset_regex = self.add_regex(
            key="decimate.dataset_regex",
            title="Datasets",
            section="Selection",
            placeholder="Regex used to select datasets",
            example="post/truncate/.*/data",
        ).widget

        self.output_name = self.add_text(
            key="decimate.output_name",
            title="Output Name",
            value="post/decimate/{group}/{dataset}",
            section="Output",
            validator=self._requires_dataset_token,
        ).widget

        self.overwrite = self.add_bool(
            key="decimate.overwrite",
            title="Overwrite",
            value=False,
            section="Output",
        ).widget

        self.factor = self.add_int(
            key="decimate.factor",
            title="Decimation factor",
            value=10,
            minimum=2,
            maximum=1000,
            section="Parameters",
        ).widget
        self.factor.setMaximumWidth(80)

        self.apply_button = self.add_button("Apply", self.apply, validate=True)

    def _requires_dataset_token(self, value) -> str | None:
        return None if "{dataset}" in str(value) else "Missing required token: {dataset}"

    def validate_window(self) -> str | None:
        if not self.files:
            return "Select at least one file."
        return None

    def apply(self) -> None:
        values = self.values()
        dataset_regex = values["decimate.dataset_regex"]
        output_name = values["decimate.output_name"]
        overwrite = values["decimate.overwrite"]
        factor = values["decimate.factor"]

        print(dataset_regex, output_name, overwrite, factor)
```
