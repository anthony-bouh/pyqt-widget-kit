from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Literal, TYPE_CHECKING

from PyQt6 import QtWidgets

from .spec import Validator, _UNSET
from ..combo_boxes import HistoryComboBox
from ..line_edits import RegexLineEdit
from ..list_widgets import EditableStringListWidget

if TYPE_CHECKING:
    from .window import SettingLayout, SettingsSection, SettingWidget


PathKind = Literal["folder", "open_file", "save_file", "file"]


class SettingsTypedHelpers:
    """Convenience helpers that create common setting widgets."""

    def add_text(
        self,
        *,
        key: str,
        title: str,
        value: Any = "",
        section: str | "SettingsSection" | None = None,
        subtitle: str = "",
        description: str = "",
        placeholder: str = "",
        tooltip: str = "",
        default: Any = _UNSET,
        validator: Validator | None = None,
    ) -> "SettingLayout":
        widget = QtWidgets.QLineEdit()
        widget.setText("" if value is None else str(value))
        widget.setPlaceholderText(placeholder)
        return self.add_widget(  # type: ignore[attr-defined]
            key=key,
            title=title,
            subtitle=subtitle,
            description=description,
            tooltip=tooltip,
            widget=widget,
            section=section,
            default=value if default is _UNSET else default,
            setting_type="text",
            validator=validator,
        )

    def add_secret(
        self,
        *,
        key: str,
        title: str,
        value: Any = "",
        section: str | "SettingsSection" | None = None,
        subtitle: str = "",
        description: str = "",
        placeholder: str = "",
        tooltip: str = "",
        default: Any = _UNSET,
        validator: Validator | None = None,
    ) -> "SettingLayout":
        widget = QtWidgets.QLineEdit()
        widget.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
        widget.setText("" if value is None else str(value))
        widget.setPlaceholderText(placeholder)
        return self.add_widget(  # type: ignore[attr-defined]
            key=key,
            title=title,
            subtitle=subtitle,
            description=description,
            tooltip=tooltip,
            widget=widget,
            section=section,
            default=value if default is _UNSET else default,
            setting_type="password",
            validator=validator,
        )

    def add_bool(
        self,
        *,
        key: str,
        title: str,
        value: Any = False,
        section: str | "SettingsSection" | None = None,
        subtitle: str = "",
        description: str = "",
        tooltip: str = "",
        default: Any = _UNSET,
        validator: Validator | None = None,
    ) -> "SettingLayout":
        checked = bool(value)
        widget = QtWidgets.QCheckBox()
        widget.setChecked(checked)
        return self.add_widget(  # type: ignore[attr-defined]
            key=key,
            title=title,
            subtitle=subtitle,
            description=description,
            tooltip=tooltip,
            widget=widget,
            section=section,
            default=checked if default is _UNSET else default,
            setting_type="bool",
            validator=validator,
        )

    def add_int(
        self,
        *,
        key: str,
        title: str,
        value: Any = None,
        section: str | "SettingsSection" | None = None,
        minimum: int = 0,
        maximum: int = 1_000_000,
        step: int = 1,
        special_value_text: str = "",
        subtitle: str = "",
        description: str = "",
        tooltip: str = "",
        default: Any = _UNSET,
        validator: Validator | None = None,
    ) -> "SettingLayout":
        resolved_value = minimum if value is None else int(value)
        widget = QtWidgets.QSpinBox()
        widget.setRange(minimum, maximum)
        widget.setSingleStep(step)
        if special_value_text:
            widget.setSpecialValueText(special_value_text)
        widget.setValue(resolved_value)
        return self.add_widget(  # type: ignore[attr-defined]
            key=key,
            title=title,
            subtitle=subtitle,
            description=description,
            tooltip=tooltip,
            widget=widget,
            section=section,
            default=resolved_value if default is _UNSET else default,
            setting_type="int",
            validator=validator,
        )

    def add_float(
        self,
        *,
        key: str,
        title: str,
        value: Any = None,
        section: str | "SettingsSection" | None = None,
        minimum: float = 0.0,
        maximum: float = 1.0,
        step: float = 0.05,
        decimals: int = 3,
        subtitle: str = "",
        description: str = "",
        tooltip: str = "",
        default: Any = _UNSET,
        validator: Validator | None = None,
    ) -> "SettingLayout":
        resolved_value = minimum if value is None else float(value)
        widget = QtWidgets.QDoubleSpinBox()
        widget.setRange(minimum, maximum)
        widget.setDecimals(decimals)
        widget.setSingleStep(step)
        widget.setValue(resolved_value)
        return self.add_widget(  # type: ignore[attr-defined]
            key=key,
            title=title,
            subtitle=subtitle,
            description=description,
            tooltip=tooltip,
            widget=widget,
            section=section,
            default=resolved_value if default is _UNSET else default,
            setting_type="float",
            validator=validator,
        )

    def add_choice(
        self,
        *,
        key: str,
        title: str,
        options: Iterable[Any],
        value: Any = _UNSET,
        section: str | "SettingsSection" | None = None,
        editable: bool = False,
        subtitle: str = "",
        description: str = "",
        tooltip: str = "",
        default: Any = _UNSET,
        validator: Validator | None = None,
    ) -> "SettingLayout":
        widget = QtWidgets.QComboBox()
        widget.setEditable(editable)
        option_values = list(options)
        for option in option_values:
            widget.addItem(str(option), option)

        resolved_value = value
        if resolved_value is _UNSET and option_values:
            resolved_value = option_values[0]
        if resolved_value is not _UNSET:
            _set_combo_value(widget, resolved_value)

        return self.add_widget(  # type: ignore[attr-defined]
            key=key,
            title=title,
            subtitle=subtitle,
            description=description,
            tooltip=tooltip,
            widget=widget,
            section=section,
            default=resolved_value if default is _UNSET else default,
            setting_type="choice",
            validator=validator,
        )

    def add_path(
        self,
        *,
        key: str,
        title: str,
        value: Any = "",
        section: str | "SettingsSection" | None = None,
        kind: PathKind = "open_file",
        subtitle: str = "",
        description: str = "",
        tooltip: str = "",
        default: Any = _UNSET,
        validator: Validator | None = None,
        max_history: int = 10,
        browse_text: str = "Browse",
        browse_icon: str = "ico/folder.png",
    ) -> "SettingLayout":
        widget = HistoryComboBox(max_history=max_history)
        widget.setEditText("" if value is None else str(value))
        setting = self.add_widget(  # type: ignore[attr-defined]
            key=key,
            title=title,
            subtitle=subtitle,
            description=description,
            tooltip=tooltip,
            widget=widget,
            section=section,
            default=value if default is _UNSET else default,
            setting_type="folder" if kind == "folder" else "file",
            validator=validator,
        )
        setting.add_button(
            "browseButton",
            browse_text,
            browse_icon,
            lambda: _browse_path(widget, kind),
        )
        return setting

    def add_regex(
        self,
        *,
        key: str,
        title: str,
        value: Any = "",
        section: str | "SettingsSection" | None = None,
        subtitle: str = "",
        description: str = "",
        placeholder: str = "",
        tooltip: str = "",
        example: str = "",
        regex_enabled: bool = True,
        case_sensitive: bool = True,
        multi_regex_enabled: bool = False,
        default: Any = _UNSET,
        validator: Validator | None = None,
    ) -> "SettingLayout":
        widget = RegexLineEdit(multi_regex_enabled=multi_regex_enabled)
        if placeholder:
            widget.setPlaceholderText(placeholder)
        if example:
            widget.setExample(example)
        widget.setText("" if value is None else str(value))
        widget.setRegexEnabled(regex_enabled)
        widget.setCaseSensitivity(case_sensitive)

        def regex_validator(current_value: Any) -> str | None:
            if not widget.isValid():
                return "Enter a valid regular expression."
            if validator is not None:
                return validator(current_value)
            return None

        return self.add_widget(  # type: ignore[attr-defined]
            key=key,
            title=title,
            subtitle=subtitle,
            description=description,
            tooltip=tooltip,
            widget=widget,
            section=section,
            default=value if default is _UNSET else default,
            setting_type="regex",
            validator=regex_validator,
        )

    def add_list(
        self,
        *,
        key: str,
        title: str,
        values: Iterable[Any] | None = None,
        section: str | "SettingsSection" | None = None,
        subtitle: str = "",
        description: str = "",
        tooltip: str = "",
        default: Any = _UNSET,
        validator: Validator | None = None,
    ) -> "SettingLayout":
        resolved_values = list(values or ())
        widget = EditableStringListWidget()
        for value in resolved_values:
            widget.addRow("" if value is None else str(value))
        return self.add_widget(  # type: ignore[attr-defined]
            key=key,
            title=title,
            subtitle=subtitle,
            description=description,
            tooltip=tooltip,
            widget=widget,
            section=section,
            setting_type="list",
            default=resolved_values if default is _UNSET else default,
            validator=validator,
        )

    def add_custom(
        self,
        *,
        key: str,
        title: str,
        widget: "SettingWidget | QtWidgets.QWidget",
        section: str | "SettingsSection" | None = None,
        subtitle: str = "",
        description: str = "",
        tooltip: str = "",
        setting_type: str = "custom",
        default: Any = _UNSET,
        validator: Validator | None = None,
    ) -> "SettingLayout":
        return self.add_widget(  # type: ignore[attr-defined]
            key=key,
            title=title,
            subtitle=subtitle,
            description=description,
            tooltip=tooltip,
            widget=widget,
            section=section,
            setting_type=setting_type,
            default=default,
            validator=validator,
        )


def _set_combo_value(widget: QtWidgets.QComboBox, value: Any) -> None:
    for index in range(widget.count()):
        if widget.itemData(index) == value or widget.itemText(index) == str(value):
            widget.setCurrentIndex(index)
            return
    if widget.isEditable():
        widget.setCurrentText("" if value is None else str(value))
    else:
        widget.setCurrentIndex(-1)


def _browse_path(widget: HistoryComboBox, kind: PathKind) -> None:
    current = widget.currentText().strip()
    if kind == "folder":
        selected = QtWidgets.QFileDialog.getExistingDirectory(widget, "Select Folder", current)
    elif kind == "save_file":
        selected, _filter = QtWidgets.QFileDialog.getSaveFileName(widget, "Select File", current)
    else:
        selected, _filter = QtWidgets.QFileDialog.getOpenFileName(widget, "Select File", current)
    if selected:
        widget.setEditText(selected)
