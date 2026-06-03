from __future__ import annotations

import operator
import re
from dataclasses import dataclass
from typing import Any, List, Optional, Pattern

from PyQt6 import QtWidgets
from PyQt6.QtCore import QEvent, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QIcon

from .buttons import DEFAULT_ICON_BUTTON_SIZE, DEFAULT_ICON_SIZE, IconButton
from .resources import resource_path

COMPACT_CONTROL_HEIGHT = DEFAULT_ICON_BUTTON_SIZE
COMPACT_ICON_SIZE = DEFAULT_ICON_SIZE


# Operators for string filter parsing/evaluation
NUMERIC_OPS = {
    "<": operator.lt,
    ">": operator.gt,
    "<=": operator.le,
    ">=": operator.ge,
    "==": operator.eq,
    "=": operator.eq,
    "!=": operator.ne,
    "<>": operator.ne,
}

STRING_ORDER_OPS = {
    "<": operator.lt,
    ">": operator.gt,
    "<=": operator.le,
    ">=": operator.ge,
}


@dataclass
class Condition:
    key_pattern: Pattern
    op: str
    value: Any
    is_numeric: bool
    value_pattern: Optional[Pattern] = None


class RegexLineEdit(QtWidgets.QFrame):
    """
    Composite line edit with regex-aware validation, toggles, and signals.
    
    Features:
    - Regex toggle button to switch between regex mode and plain text (auto-escapes when off).
    - Case-sensitivity toggle button (`Aa`) that drives the compiled pattern flags.
    - Multi-regex toggle to allow `;`-separated patterns.
    - Live validation with border feedback and `validityChanged` signal.
    - Helper APIs: `setTextWithoutValidation`, `setExample`, `compiledRegex`, `isValid`.
    
    Example of use:
    
    >>> regex_line_edit = RegexLineEdit()
    >>> regex_line_edit.setPlaceholderText("Enter regex...")
    >>> regex_line_edit.validityChanged.connect(lambda is_valid: print("Valid" if is_valid else "Invalid"))
    >>> regex_line_edit.textChanged.connect(lambda text: print(f"Text changed: {text}"))
    >>> regex_line_edit.caseSensitivityChanged.connect(lambda cs: print("Case Sensitive" if cs else "Case Insensitive"))
        
    """

    validityChanged = pyqtSignal(bool)
    textChanged = pyqtSignal(str)
    regexEnabledChanged = pyqtSignal(bool)
    caseSensitivityChanged = pyqtSignal(bool)
    multiRegexEnabledChanged = pyqtSignal(bool)

    def __init__(
        self,
        parent: QtWidgets.QWidget | None = None,
        multi_regex_enabled: bool = False,
    ) -> None:
        
        super().__init__(parent)
        
        self._current_valid = True
        self._regex_enabled = True
        self._case_sensitive = True
        self._multi_regex_enabled = multi_regex_enabled
        self._example = ''
        self._forced_invalid = False

        self.setObjectName('RegexLineEdit')
        self.setProperty('focused', False)
        self.setFixedHeight(COMPACT_CONTROL_HEIGHT)

        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(1, 0, 1, 0)
        layout.setSpacing(1)

        self._line_edit = QtWidgets.QLineEdit()
        self._line_edit.setFixedHeight(COMPACT_CONTROL_HEIGHT)
        self._line_edit.installEventFilter(self)
        self._line_edit.textChanged.connect(self._handle_text_change)
        layout.addWidget(self._line_edit)

        self._button_case = IconButton(icon=resource_path('ico/case.png'), tooltip='Match case enabled.')
        self._button_case.setCheckable(True)
        self._button_case.setChecked(True)
        self._button_case.toggled.connect(self._toggle_case_mode)
        layout.addWidget(self._button_case)

        self._button_multi_regex = IconButton(icon=resource_path('ico/multiple-alt.png'), tooltip='Multiple regex disabled.')
        self._button_multi_regex.setCheckable(True)
        self._button_multi_regex.setChecked(multi_regex_enabled)
        self._button_multi_regex.setVisible(multi_regex_enabled)
        self._button_multi_regex.toggled.connect(self._toggle_multi_regex_mode)
        layout.addWidget(self._button_multi_regex)
        
        self._button_regex = IconButton(icon=resource_path('ico/regex.png'), tooltip='Regex search enabled.')
        self._button_regex.setCheckable(True)
        self._button_regex.setChecked(True)
        self._button_regex.toggled.connect(self._toggle_regex_mode)
        layout.addWidget(self._button_regex)
        
        self.setLayout(layout)

        self._update_status('Enter a Python regular expression (optional).', True)

    def _handle_text_change(self, text: str) -> None:
        self.textChanged.emit(text)
        if self._regex_enabled:
            self._validate_regex(text)
        else:
            self._update_status('Regex disabled; using plain text search.', True)

    def _validate_regex(self, text: str) -> None:
        if not self._regex_enabled:
            return
        stripped = text.strip()
        if not stripped:
            self._update_status(self._example or 'Regex not set.', True)
            return
        patterns = self._split_patterns(stripped)
        if not patterns:
            self._update_status(self._example or 'Regex not set.', True)
            return

        flags = 0 if self._case_sensitive else re.IGNORECASE
        for part in patterns:
            try:
                re.compile(part, flags)
            except re.error as exc:
                self._update_status(f'Invalid regex: {exc}', False)
                return
        self._update_status('Regex is valid.', True)

    def _update_status(self, tooltip: str, is_valid: bool | None) -> None:
        self._line_edit.setToolTip(tooltip)
        if is_valid is None:
            return
        effective_valid = is_valid and (not self._forced_invalid)
        # self.setInvalid(not effective_valid)
        if self._current_valid != effective_valid:
            self._current_valid = effective_valid
            self.validityChanged.emit(effective_valid)

    def _toggle_regex_mode(self, enabled: bool) -> None:
        self._regex_enabled = enabled
        if enabled:
            self._button_regex.setToolTip('Regex search enabled.')
            self._validate_regex(self.text())
        else:
            self._button_regex.setToolTip('Regex search disabled.')
            self._update_status('Regex disabled; using plain text search.', True)
        self.regexEnabledChanged.emit(enabled)
        self.textChanged.emit(self.text())

    def _toggle_case_mode(self, enabled: bool) -> None:
        self._case_sensitive = enabled
        self._button_case.setToolTip('Match case enabled.' if enabled else 'Match case disabled.')
        self.caseSensitivityChanged.emit(enabled)
        if self._regex_enabled:
            self._validate_regex(self.text())

    def _toggle_multi_regex_mode(self, enabled: bool) -> None:
        self._multi_regex_enabled = enabled
        tooltip = 'Multiple regex enabled (use ";" to separate).' if enabled else 'Multiple regex disabled.'
        self._button_multi_regex.setToolTip(tooltip)
        self.multiRegexEnabledChanged.emit(enabled)
        if self._regex_enabled:
            self._validate_regex(self.text())

    def _set_focus_state(self, focused: bool) -> None:
        if self.property('focused') == focused:
            return
        self.setProperty('focused', focused)
        for widget in [self, *self.findChildren(QtWidgets.QWidget)]:
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.update()

    def eventFilter(self, obj, event) -> bool:
        if obj is self._line_edit:
            if event.type() == QEvent.Type.FocusIn:
                self._set_focus_state(True)
            elif event.type() == QEvent.Type.FocusOut:
                self._set_focus_state(False)
            elif event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape:
                self._line_edit.clear()
                return True
        return super().eventFilter(obj, event)

    def setPlaceholderText(self, text: str) -> None:
        self._line_edit.setPlaceholderText(text)

    def setText(self, text: str) -> None:
        self._line_edit.setText(text)
    
    def setTextWithoutValidation(self, text: str) -> None:
        """Set text without emitting validation or change signals."""
        try:
            self._line_edit.blockSignals(True)
            self._line_edit.setText(text)
        finally:
            self._line_edit.blockSignals(False)
        self._current_valid = True
        tooltip = self._example if not text.strip() and self._example else ('Regex not set.' if not text.strip() else 'Regex is valid.')
        self._update_status(tooltip, True)

    def text(self) -> str:
        return self._line_edit.text()

    def setRegexEnabled(self, enabled: bool) -> None:
        self._button_regex.setChecked(enabled)

    def isRegexEnabled(self) -> bool:
        return self._regex_enabled

    def setCaseSensitivity(self, enabled: bool) -> None:
        self._button_case.setChecked(enabled)

    def isCaseSensitive(self) -> bool:
        return self._case_sensitive

    def setMultiRegexEnabled(self, enabled: bool) -> None:
        self._button_multi_regex.setVisible(enabled)
        self._button_multi_regex.setChecked(enabled)

    def isMultiRegexEnabled(self) -> bool:
        return self._multi_regex_enabled

    def setExample(self, example: str) -> None:
        """Set an example placeholder and tooltip when empty."""
        self._example = example or ''
        if not self._line_edit.text():
            self._line_edit.setPlaceholderText(self._example)
            self._line_edit.setToolTip(self._example)

    def lineEdit(self) -> QtWidgets.QLineEdit:
        """Expose the underlying line edit."""
        return self._line_edit

    def isValid(self) -> bool:
        """Return whether the current regex is valid."""
        return self._current_valid
    
    def isInvalid(self) -> bool:
        """Return whether the current regex is invalid."""
        return not self._current_valid

    def setForcedInvalid(self, invalid: bool = True, reason: str | None = None) -> None:
        """
        Force an invalid state regardless of regex correctness, useful for external checks.
        Clearing it re-evaluates the current text to restore regular validation.
        """
        self._forced_invalid = invalid
        if invalid:
            tooltip = reason or self._line_edit.toolTip() or 'Invalid input.'
            self._update_status(tooltip, False)
            return
        # Re-run validation without emitting textChanged
        if self._regex_enabled:
            self._validate_regex(self.text())
        else:
            self._update_status('Regex disabled; using plain text search.', True)
    
    def compiledRegex(self) -> re.Pattern | None:
        """Return a compiled pattern honoring regex enable state and case sensitivity."""
        if not self._current_valid:
            return None
        raw = self.text().strip()
        if not raw:
            return None
        flags = 0 if self._case_sensitive else re.IGNORECASE
        try:
            parts = self._split_patterns(raw)
            if not parts:
                return None
            if self._regex_enabled:
                escaped_parts = parts
            else:
                escaped_parts = [re.escape(part) for part in parts]
            pattern = self._join_patterns(escaped_parts)
            return re.compile(pattern, flags)
        except re.error:
            return None

    def _split_patterns(self, text: str) -> list[str]:
        if not self._multi_regex_enabled:
            return [text]
        return [part.strip() for part in text.split(';') if part.strip()]

    def _join_patterns(self, parts: list[str]) -> str:
        if len(parts) == 1:
            return parts[0]
        return '|'.join(f'(?:{part})' for part in parts)


class StringFilterLineEdit(QtWidgets.QFrame):
    """
    Line edit with quick parsing/validation of string/numeric filter expressions.

    Examples of accepted filters (separated by ';'):
        sensor/temperature >= 30
        status == ok; cycle < 10
        name == foo.*bar              # when regex mode enabled (value uses regex)

    Example of use:
        >>> f = StringFilterLineEdit()
        >>> f.setText("sensor/temperature>=30;status==ok")
        >>> f.isValid()
        True
        >>> f.conditions()
        [Condition(...), ...]
        >>> f.matches({"sensor/temperature": 32, "status": "ok"})
        True
    """

    validityChanged = pyqtSignal(bool)
    textChanged = pyqtSignal(str)
    regexEnabledChanged = pyqtSignal(bool)
    enabledChanged = pyqtSignal(bool)
    conditionsChanged = pyqtSignal(list)

    def __init__(
        self,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._current_valid = True
        self._regex_enabled = True
        self._enabled = True
        self._cached_conditions: list[Condition] = []

        self.setObjectName('StringFilterLineEdit')
        self.setFixedHeight(COMPACT_CONTROL_HEIGHT)

        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(2, 0, 2, 0)
        layout.setSpacing(3)

        self._line_edit = QtWidgets.QLineEdit()
        self._line_edit.setFixedHeight(COMPACT_CONTROL_HEIGHT)
        self._line_edit.setPlaceholderText("key==value; other>=10")
        self._line_edit.textChanged.connect(self._handle_text_change)
        layout.addWidget(self._line_edit)

        self._button_regex = QtWidgets.QPushButton()
        self._button_regex.setFixedSize(COMPACT_CONTROL_HEIGHT, COMPACT_CONTROL_HEIGHT)
        self._button_regex.setIconSize(QSize(COMPACT_ICON_SIZE, COMPACT_ICON_SIZE))
        self._button_regex.setCheckable(True)
        self._button_regex.setChecked(True)
        self._button_regex.setToolTip('Regex comparison enabled for keys/values.')
        self._button_regex.setIcon(QIcon(resource_path('ico/regex.png')))
        self._button_regex.toggled.connect(self._toggle_regex_mode)
        layout.addWidget(self._button_regex)

        self.setLayout(layout)
        self._update_status('Enter filters like key==value; key2>=5', True)

    def _toggle_regex_mode(self, enabled: bool) -> None:
        self._regex_enabled = enabled
        self._button_regex.setToolTip('Regex comparison enabled for keys/values.' if enabled else 'Regex disabled; using plain text.')
        self.regexEnabledChanged.emit(enabled)
        self._handle_text_change(self.text())

    def _handle_text_change(self, text: str) -> None:
        self.textChanged.emit(text)
        if not self._enabled:
            self._cached_conditions = []
            self._update_status('Filter disabled.', True)
            self.conditionsChanged.emit([])
            return

        stripped = text.strip()
        if not stripped:
            self._cached_conditions = []
            self._update_status('No filter set.', True)
            self.conditionsChanged.emit([])
            return

        try:
            conditions = self.parse_conditions(stripped)
        except (ValueError, re.error) as exc:
            self._cached_conditions = []
            self._update_status(f'Invalid filter: {exc}', False)
            self.conditionsChanged.emit([])
        else:
            self._cached_conditions = conditions
            self._update_status('Filters are valid.', True)
            self.conditionsChanged.emit(conditions)

    def _update_status(self, tooltip: str, is_valid: bool) -> None:
        self._line_edit.setToolTip(tooltip)
        # self.setInvalid(not is_valid)
        if self._current_valid != is_valid:
            self._current_valid = is_valid
            self.validityChanged.emit(is_valid)

    def build_condition(self, key: str, op: str, value: str) -> Condition:
        if op not in NUMERIC_OPS and op not in STRING_ORDER_OPS and op not in ('==', '=', '!=', '<>'):
            raise ValueError(f"Unsupported operator '{op}'")

        try:
            numeric_value = float(value)
            is_numeric = True
            final_value: Any = numeric_value
            value_pattern = None
        except ValueError:
            is_numeric = False
            final_value = value
            try:
                value_pattern = re.compile(value) if self._regex_enabled else None
            except re.error as exc:
                raise ValueError(f"Invalid value regex: {exc}") from exc

        try:
            key_pattern = re.compile(key) if self._regex_enabled else re.compile(re.escape(key))
        except re.error as exc:
            raise ValueError(f"Invalid key regex: {exc}") from exc
        return Condition(key_pattern=key_pattern, op=op, value=final_value, is_numeric=is_numeric, value_pattern=value_pattern)

    def parse_conditions(self, text: str) -> List[Condition]:
        """
        Parse a filter string into Condition objects.

        Format: `<key> <op> <value>` separated by ';'.
        """
        conditions: List[Condition] = []
        parts = [p.strip() for p in text.split(';') if p.strip()]
        if not parts:
            return conditions

        pattern = re.compile(r"(.+?)(<=|>=|==|!=|<>|<|>|=)(.+)")
        for raw in parts:
            match = pattern.match(raw)
            if not match:
                raise ValueError(f"Cannot parse '{raw}'")
            key, op, value = (s.strip() for s in match.groups())
            if not key or not value:
                raise ValueError(f"Missing key/value in '{raw}'")
            condition = self.build_condition(key, op, value)
            conditions.append(condition)

        return conditions

    def conditions(self) -> List[Condition]:
        """Return last parsed conditions (empty if invalid/disabled)."""
        return list(self._cached_conditions)

    def isValid(self) -> bool:
        return self._current_valid
    
    def isInvalid(self) -> bool:
        return not self._current_valid

    def isEnabledFilter(self) -> bool:
        return self._enabled

    def setText(self, text: str) -> None:
        self._line_edit.setText(text)

    def text(self) -> str:
        return self._line_edit.text()

    def setPlaceholderText(self, text: str) -> None:
        self._line_edit.setPlaceholderText(text)

    def setRegexEnabled(self, enabled: bool) -> None:
        self._button_regex.setChecked(enabled)

    def isRegexEnabled(self) -> bool:
        return self._regex_enabled

    def setFilterEnabled(self, enabled: bool) -> None:
        self._enabled = enabled
        self.enabledChanged.emit(enabled)
        self._handle_text_change(self.text())

    def regexButton(self) -> QtWidgets.QPushButton:
        return self._button_regex

    def matches(self, values: dict[str, Any]) -> bool:
        """
        Evaluate the current conditions against a mapping of values.

        A condition matches if any key in the mapping satisfies the key pattern
        and the corresponding value passes the comparison.
        """
        conditions = self.conditions()
        if not conditions:
            return True

        for cond in conditions:
            condition_matched = False
            op_func = NUMERIC_OPS.get(cond.op) or STRING_ORDER_OPS.get(cond.op) or NUMERIC_OPS.get(cond.op)

            for key, raw_val in values.items():
                if not cond.key_pattern.search(str(key)):
                    continue

                try:
                    if cond.is_numeric:
                        val = float(raw_val)
                        condition_matched = bool(op_func(val, cond.value))
                    else:
                        sval = str(raw_val)
                        if cond.value_pattern:
                            if cond.op in ('==', '='):
                                condition_matched = bool(cond.value_pattern.search(sval))
                            elif cond.op in ('!=', '<>'):
                                condition_matched = not bool(cond.value_pattern.search(sval))
                            elif cond.op in STRING_ORDER_OPS:
                                condition_matched = bool(op_func(sval, str(cond.value)))
                        else:
                            if cond.op in ('==', '='):
                                condition_matched = (sval == str(cond.value))
                            elif cond.op in ('!=', '<>'):
                                condition_matched = (sval != str(cond.value))
                            elif cond.op in STRING_ORDER_OPS and op_func:
                                condition_matched = bool(op_func(sval, str(cond.value)))
                    if condition_matched:
                        break
                except Exception:
                    # Ignore values that cannot be coerced and continue searching
                    continue

            if not condition_matched:
                return False

        return True
