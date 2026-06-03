import inspect
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol, TypeAlias, runtime_checkable

from PyQt6 import QtWidgets


_UNSET = object()
Validator: TypeAlias = Callable[[Any], str | None]


@runtime_checkable
class SerializableWidget(Protocol):
    """Interface for custom widgets that serialize their own internal state."""

    def to_dict(self) -> dict[str, Any]:
        ...

    def from_dict(self, data: Mapping[str, Any]) -> None:
        ...


@runtime_checkable
class ValidatableWidget(Protocol):
    """Interface for custom widgets that validate their own current state."""

    def validate(self) -> str | None:
        ...


@dataclass
class SettingSpec:
    key: str = ""
    title: str = ""
    subtitle: str = ""
    description: str = ""
    tooltip: str = ""
    default: Any = _UNSET
    setting_type: str = "custom"
    validator: Validator | None = field(default=None, repr=False, compare=False)
    widget: QtWidgets.QWidget | None = field(default=None, repr=False, compare=False)
    _baseline_value: Any = field(default=_UNSET, init=False, repr=False, compare=False)

    def set_widget(self, widget: QtWidgets.QWidget, *, mark_clean: bool = True, apply_default: bool = False) -> None:  # fmt: skip
        self.widget = widget
        if apply_default and self.default is not _UNSET:
            self.set_value(self.default)
        if mark_clean:
            self.mark_clean()

    def get_value(self) -> Any:
        if self.widget is None:
            raise ValueError("SettingSpec has no widget")
        return _read_widget_value(self.widget)

    def set_value(self, value: Any, *, mark_clean: bool = False, validate_value: bool = False) -> None:  # fmt: skip
        if self.widget is None:
            raise ValueError("SettingSpec has no widget")
        if validate_value:
            self.ensure_valid(value)
        _write_widget_value(self.widget, value)
        if mark_clean:
            self.mark_clean()

    def initial_value(self) -> Any:
        return self.default

    def reset_to_default(self, *, mark_clean: bool = False) -> None:
        if self.default is _UNSET:
            raise ValueError("SettingSpec has no default value")
        self.set_value(self.default, mark_clean=mark_clean)

    def mark_clean(self) -> None:
        if self.widget is None:
            self._baseline_value = _UNSET
            return
        self._baseline_value = _snapshot_value(self.get_value())

    def is_dirty(self) -> bool:
        if self.widget is None:
            return False
        baseline = self._baseline_value
        if baseline is _UNSET:
            baseline = self.default
        if baseline is _UNSET:
            return False
        return self.get_value() != baseline

    def validate(self, value: Any = _UNSET) -> str | None:
        if value is _UNSET and isinstance(self.widget, ValidatableWidget):
            # @runtime_checkable only checks attribute existence, not signature.
            # QAbstractSpinBox subclasses (QSpinBox, QDoubleSpinBox, etc.) also
            # have validate(input, pos), which would fail if called with no args.
            # inspect.signature raises ValueError for PyQt6 C-extension methods,
            # so we use that to skip them and only call pure-Python overrides
            # whose signatures confirm no required arguments.
            bound_validate = self.widget.validate
            try:
                sig = inspect.signature(bound_validate)
            except ValueError:
                pass  # C-extension method — not our custom ValidatableWidget
            else:
                required = [
                    p for p in sig.parameters.values()
                    if p.default is inspect.Parameter.empty
                    and p.kind not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
                ]
                if not required:
                    error = bound_validate()
                    if error is not None:
                        return error
        if self.validator is None:
            return None
        if value is _UNSET:
            value = self.get_value()
        return self.validator(value)

    def is_valid(self) -> bool:
        return self.validate() is None

    def ensure_valid(self, value: Any = _UNSET) -> None:
        error = self.validate(value)
        if error is not None:
            raise ValueError(error)

    def to_state_dict(self) -> dict[str, Any]:
        if self.widget is None:
            raise ValueError("SettingSpec has no widget")

        data: dict[str, Any] = {
            "key": self.key,
            "value": self.get_value(),
        }
        return data

    def to_dict(self, *, include_value: bool = True) -> dict[str, Any]:
        data: dict[str, Any] = {
            "key": self.key,
            "title": self.title,
            "subtitle": self.subtitle,
            "description": self.description,
            "tooltip": self.tooltip,
        }

        if self.default is not _UNSET:
            data["default"] = self.default
        if self.setting_type:
            data["setting_type"] = self.setting_type
        if self.widget is not None:
            data["widget_type"] = _widget_type_name(self.widget)
            if include_value:
                data["value"] = self.get_value()
        return data

    def from_dict(self, data: Mapping[str, Any], *, mark_clean: bool = True) -> None:
        if not isinstance(data, Mapping):
            raise TypeError("SettingSpec.from_dict expected a mapping")

        self.key = str(data.get("key") or data.get("path") or self.key)
        self.title = str(data.get("title", self.title))
        self.subtitle = str(data.get("subtitle", data.get("suptitle", self.subtitle)))
        self.description = str(data.get("description", self.description))
        self.tooltip = str(data.get("tooltip", self.tooltip))
        if "default" in data:
            self.default = data["default"]
        self.setting_type = str(data.get("setting_type", data.get("type", self.setting_type)))

        widget_type = data.get("widget_type")
        value = data["value"] if "value" in data else _UNSET
        has_widget_payload = widget_type is not None or value is not _UNSET
        if not has_widget_payload:
            return

        if self.widget is None:
            raise ValueError("SettingSpec.from_dict requires set_widget() before loading a widget value")
        if widget_type is not None and not _is_compatible_widget_type(self.widget, str(widget_type)):
            raise TypeError(
                f"Cannot restore {widget_type} value into {type(self.widget).__name__}"
            )
        if value is not _UNSET:
            self.set_value(value, mark_clean=mark_clean)
        elif mark_clean:
            self.mark_clean()

    def restore_state(self, data: Mapping[str, Any], *, mark_clean: bool = True) -> None:
        if not isinstance(data, Mapping):
            raise TypeError("SettingSpec.restore_state expected a mapping")

        if "value" not in data:
            if mark_clean:
                self.mark_clean()
            return

        self.set_value(data["value"], mark_clean=mark_clean)


def _read_widget_value(widget: QtWidgets.QWidget) -> Any:
    if isinstance(widget, SerializableWidget):
        return widget.to_dict()
    to_list = getattr(widget, "to_list", None)
    if callable(to_list):
        return to_list()
    if isinstance(widget, QtWidgets.QLineEdit):
        return widget.text()
    if isinstance(widget, QtWidgets.QTextEdit):
        return widget.toPlainText()
    if isinstance(widget, QtWidgets.QPlainTextEdit):
        return widget.toPlainText()
    if isinstance(widget, QtWidgets.QCheckBox):
        return widget.isChecked()
    if isinstance(widget, QtWidgets.QComboBox):
        data = widget.currentData()
        return widget.currentText() if data is None else data
    if isinstance(
        widget,
        (
            QtWidgets.QSpinBox,
            QtWidgets.QDoubleSpinBox,
            QtWidgets.QSlider,
            QtWidgets.QDial,
        ),
    ):
        return widget.value()
    if hasattr(widget, "text"):
        text = getattr(widget, "text")
        return text() if callable(text) else text
    if hasattr(widget, "rating"):
        rating = getattr(widget, "rating")
        return rating() if callable(rating) else rating
    if hasattr(widget, "get_value"):
        return widget.get_value()
    if hasattr(widget, "value"):
        value = getattr(widget, "value")
        return value() if callable(value) else value
    raise TypeError(f"Cannot read value from widget type {type(widget).__name__}")


def _widget_type_name(widget: QtWidgets.QWidget) -> str:
    return type(widget).__name__


def _is_compatible_widget_type(widget: QtWidgets.QWidget, widget_type: str) -> bool:
    return widget_type in {widget_class.__name__ for widget_class in type(widget).__mro__}


def _snapshot_value(value: Any) -> Any:
    try:
        return deepcopy(value)
    except Exception:
        return value


def _write_widget_value(widget: QtWidgets.QWidget, value: Any) -> None:
    if isinstance(widget, SerializableWidget):
        if value is None:
            widget.from_dict({})
            return
        if isinstance(value, Mapping):
            widget.from_dict(value)
            return
        raise TypeError(f"Cannot restore {type(widget).__name__} from {type(value).__name__}")
    from_list = getattr(widget, "from_list", None)
    if callable(from_list):
        from_list([] if value is None else value)
        return
    to_list = getattr(widget, "to_list", None)
    add_row = getattr(widget, "addRow", None)
    clear = getattr(widget, "clear", None)
    if callable(to_list) and callable(add_row) and callable(clear):
        clear()
        if value is None:
            return
        if isinstance(value, str):
            rows = [value]
        else:
            rows = list(value)
        for row in rows:
            add_row("" if row is None else str(row))
        return
    if isinstance(widget, QtWidgets.QLineEdit):
        widget.setText("" if value is None else str(value))
        return
    if isinstance(widget, QtWidgets.QTextEdit):
        widget.setPlainText("" if value is None else str(value))
        return
    if isinstance(widget, QtWidgets.QPlainTextEdit):
        widget.setPlainText("" if value is None else str(value))
        return
    if isinstance(widget, QtWidgets.QCheckBox):
        widget.setChecked(_coerce_bool(value))
        return
    if isinstance(widget, QtWidgets.QComboBox):
        for index in range(widget.count()):
            if widget.itemData(index) == value or widget.itemText(index) == str(value):
                widget.setCurrentIndex(index)
                return
        if widget.isEditable():
            widget.setCurrentText("" if value is None else str(value))
        else:
            widget.setCurrentIndex(-1)
        return
    if isinstance(widget, QtWidgets.QSpinBox):
        widget.setValue(int(value or 0))
        return
    if isinstance(widget, QtWidgets.QDoubleSpinBox):
        widget.setValue(float(value or 0))
        return
    if isinstance(widget, (QtWidgets.QSlider, QtWidgets.QDial)):
        widget.setValue(int(value or 0))
        return
    if hasattr(widget, "set_rating"):
        widget.set_rating(value)
        return
    if hasattr(widget, "setText"):
        widget.setText("" if value is None else str(value))
        return
    if hasattr(widget, "set_value"):
        widget.set_value(value)
        return
    if hasattr(widget, "setValue"):
        widget.setValue(value)
        return
    raise TypeError(f"Cannot write value to widget type {type(widget).__name__}")


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on", "checked"}
    return bool(value)
