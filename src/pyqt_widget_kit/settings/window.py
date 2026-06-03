
from __future__ import annotations

import json
import re
from collections.abc import Mapping
from contextlib import contextmanager
from pathlib import Path

from PyQt6 import QtGui
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
)
from PyQt6.QtWidgets import (
    QLabel,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
    QScrollArea,
    QFrame,
    QTreeWidget,
    QTreeWidgetItem,
    QSplitter,
    QHeaderView,
)
from PyQt6 import QtCore, QtWidgets
from PyQt6.QtCore import Qt, pyqtSignal

from ..buttons import IconButton
from ..combo_boxes import HistoryComboBox
from ..line_edits import RegexLineEdit
from ..resources import load_stylesheets
from .spec import SettingSpec, Validator, _UNSET
from .typed_helpers import SettingsTypedHelpers

_INHERIT = object()


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _guess_setting_type(widget: QWidget) -> str:
    if isinstance(widget, HistoryComboBox):
        return "text"
    if isinstance(widget, QtWidgets.QLineEdit):
        if widget.echoMode() != QtWidgets.QLineEdit.EchoMode.Normal:
            return "password"
        return "text"
    if isinstance(widget, (QtWidgets.QTextEdit, QtWidgets.QPlainTextEdit)):
        return "text"
    if isinstance(widget, QtWidgets.QCheckBox):
        return "bool"
    if isinstance(widget, QtWidgets.QComboBox):
        return "choice"
    if isinstance(widget, QtWidgets.QDoubleSpinBox):
        return "float"
    if isinstance(widget, (QtWidgets.QSpinBox, QtWidgets.QSlider, QtWidgets.QDial)):
        return "int"
    return "custom"


def _coerce_history_texts(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (str, Mapping)):
        raw_items = [value]
    else:
        try:
            raw_items = list(value)
        except TypeError:
            return []

    texts: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        if isinstance(item, Mapping):
            item = item.get("value", "")
        text = str(item).strip()
        if not text:
            continue
        key = text.casefold()
        if key in seen:
            continue
        texts.append(text)
        seen.add(key)
    return texts


def _read_widget_history(widget: QWidget) -> list[str]:
    history = getattr(widget, "history", None)
    if not callable(history):
        return []
    return _coerce_history_texts(history())


def _write_widget_history(widget: QWidget, history: Any) -> None:
    set_history = getattr(widget, "set_history", None)
    if callable(set_history):
        set_history(_coerce_history_texts(history))


def _record_widget_history(widget: QWidget) -> None:
    record_history = getattr(widget, "record_history", None)
    if callable(record_history):
        record_history()


def _section_slug(label: str) -> str:
    """Convert a section label to a URL-safe path segment used internally."""
    slug = re.sub(r"[^a-z0-9]+", "_", label.strip().lower()).strip("_")
    return slug or "section"


class _TreeWidget(QTreeWidget):
    """Tree widget specialized for settings paths and selection callbacks."""

    pathSelected = pyqtSignal(str)
    sectionContextRequested = pyqtSignal(str, QtCore.QPoint)

    def __init__(self, separator: str = "/", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._separator = separator
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setSortingEnabled(False)
        self.setDragDropMode(QtWidgets.QAbstractItemView.DragDropMode.NoDragDrop)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.setAnimated(False)
        self.setUniformRowHeights(True)
        self.setMinimumWidth(0)
        self.setHeaderHidden(True)
        self.setColumnCount(1)
        self.itemClicked.connect(self._emit_path)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._emit_context_menu)

    def populate(self, paths: Iterable[str], labels: Dict[str, str]) -> None:
        """Populate the tree from the provided path list.

        Args:
            paths: Iterable of path strings (e.g. ``"network/proxy"``).
            labels: Mapping of full path → display label.  Every path in
                *paths* must have an entry; missing entries raise :exc:`ValueError`.
        """
        trie: Dict[str, dict] = {}
        for raw in paths:
            if not raw:
                continue
            parts = [p for p in str(raw).split(self._separator) if p]
            node = trie
            for part in parts:
                node = node.setdefault(part, {})

        self.clear()
        self.setColumnCount(1)
        self.setHeaderHidden(True)

        def add_children(parent, subtree: Dict[str, dict], prefix: str = ""):
            for name in sorted(subtree.keys()):
                full_path = f"{prefix}{self._separator}{name}" if prefix else name
                display = labels.get(full_path)
                if not display:
                    raise ValueError(
                        f"No label provided for tree path {full_path!r}. "
                        "Register every section with add_section() before adding widgets."
                    )
                item = QTreeWidgetItem([display])
                item.setData(0, Qt.ItemDataRole.UserRole, full_path)
                item.setToolTip(0, full_path)

                if isinstance(parent, QTreeWidget):
                    parent.addTopLevelItem(item)
                else:
                    parent.addChild(item)

                add_children(item, subtree[name], full_path)

        add_children(self, trie)
        self.expandToDepth(0)

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        """Clear selection on Escape to remove path filtering."""
        if event.key() == Qt.Key.Key_Escape:
            self.clear_selection()
            return
        super().keyPressEvent(event)

    def clear_selection(self) -> None:
        super().clearSelection()
        self.pathSelected.emit("")

    def resize_to_contents(self) -> int:
        header = self.header()
        if header is None:
            return self.width()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.resizeColumnToContents(0)
        column_width = max(self.sizeHintForColumn(0), header.sectionSize(0), 1)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(0, column_width)

        margins = self.contentsMargins()
        width = (
            column_width
            + self.frameWidth() * 2
            + margins.left()
            + margins.right()
            + self.verticalScrollBar().sizeHint().width()
            + 8
        )
        self.setFixedWidth(width)
        return width

    def _emit_path(self, item: QTreeWidgetItem, column: int) -> None:
        path = item.data(0, Qt.ItemDataRole.UserRole) or ""
        self.pathSelected.emit(str(path))

    def _emit_context_menu(self, pos: QtCore.QPoint) -> None:
        item = self.itemAt(pos)
        if item is None:
            return
        self.setCurrentItem(item)
        path = item.data(0, Qt.ItemDataRole.UserRole) or ""
        self.sectionContextRequested.emit(str(path), self.viewport().mapToGlobal(pos))


class _TopMenu(QFrame):
    """Top menu bar with optional search functionality."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("_TopMenu")
        layout = QVBoxLayout()
        layout.setSpacing(3)
        layout.setContentsMargins(6, 6, 6, 6)
        self.setLayout(layout)

    def layout(self) -> QVBoxLayout:
        return super().layout()  # type: ignore[return-value]


class SettingsWindow(SettingsTypedHelpers, QWidget):
    """
    Base class for quick settings windows with optional tree view.

    Example:

    >>> class ProjectSettingsWindow(SettingsWindow):
    ...     title = "My Settings"
    ...
    >>> window = ProjectSettingsWindow()
    >>> name_edit = QtWidgets.QLineEdit()
    >>> section = window.add_section("General")
    >>> section.add_widget(key="general/name", title="Display name", widget=name_edit)
    >>> window.load_json("settings.json")
    >>> window.save_json("settings.json")
    >>> window.show()

    """
    # Public API
    title = "Settings" # Default window title; override by subclassing and setting this attribute.
    show_tree = False # Whether to show the navigation tree; can be toggled at runtime with _set_tree_visible()
    modal = False  # Whether the window blocks interaction with other windows when open
    stay_on_top = False
    apply_default_style = False
    minimum_size: tuple[int, int] | None = (600, 400)

    # Signals
    treePathSelected = pyqtSignal(str) # Emitted when a path is selected in the tree
    settingValidityChanged = pyqtSignal(str, bool)
    validityChanged = pyqtSignal(bool)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        title: str | None = None,
        show_tree: bool | None = None,
        modal: bool | None = None,
        stay_on_top: bool | None = None,
        apply_default_style: bool | None = None,
        minimum_size: tuple[int, int] | None | object = _INHERIT,
    ) -> None:
        super().__init__(parent)
        self._show_tree = self.show_tree if show_tree is None else show_tree
        self._modal = self.modal if modal is None else modal
        self._stay_on_top = self.stay_on_top if stay_on_top is None else stay_on_top
        self._apply_default_style = self.apply_default_style if apply_default_style is None else apply_default_style
        self._minimum_size = self.minimum_size if minimum_size is _INHERIT else minimum_size
        self.settings :List[SettingLayout]= []
        self._active_path_filter: str = ""
        self._tree_refresh_scheduled: bool = False
        self._settings_json_path: Path | None = None
        self._section_labels: Dict[str, str] = {}
        self._validation_buttons: list[QtWidgets.QAbstractButton] = []
        self._init_ui(self.title if title is None else title)
        self._init_layout()
        self._init_connections()
        self.validityChanged.connect(self._set_validation_buttons_enabled)

    def _init_ui(self, title:str) -> None:
        self.setWindowTitle(title)
        flags = self.windowFlags()
        if self._stay_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        if self._modal:
            self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        if self._minimum_size is not None:
            self.setMinimumSize(*self._minimum_size)
        
    def _init_layout(self) -> None:
        if self._apply_default_style:
            self.setStyleSheet(load_stylesheets("widgets.qss", "settings.qss"))

        # Top container
        self.top_menu = _TopMenu()

        # Search bar
        self._search_line_edit = RegexLineEdit()
        self._search_line_edit.setPlaceholderText('Search using regular expression ...')

        # Status label
        self._status_label = QLabel()
        self._status_label.setObjectName("settingsStatusLabel")
        self._status_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._status_label.setVisible(False)

        self._button_container = QWidget()
        self._button_layout = QHBoxLayout()
        self._button_layout.setContentsMargins(0, 0, 0, 0)
        self._button_layout.setSpacing(3)
        self._button_container.setLayout(self._button_layout)
        self._button_layout.addStretch()
        self._button_layout.addWidget(self._status_label)

        # Top menu layout
        self.top_menu.layout().addWidget(self._search_line_edit)
        self.top_menu.layout().addWidget(self._button_container)

        # Body Scroll Area
        self.body = QVBoxLayout()
        self.body.setSpacing(0)
        self.body.setContentsMargins(0,0,0,0)
        self.body.addStretch()

        self.body_widget = QFrame()
        # self.body_widget.setObjectName('bodyWidget')
        self.body_widget.setLayout(self.body)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidget(self.body_widget)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setMinimumHeight(150)
        self.scroll_area.setMinimumWidth(150)

        # Tree
        self.tree = _TreeWidget()

        # Layout
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0,0,0,0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self.top_menu, 0)

        self.splitter = QSplitter(QtCore.Qt.Orientation.Horizontal)
        self.splitter.setHandleWidth(1)
        self.splitter.addWidget(self.tree)
        self.splitter.addWidget(self.scroll_area)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setCollapsible(0, False)
        self.splitter.setCollapsible(1, False)
        main_layout.addWidget(self.splitter, 1)
        self.setLayout(main_layout)

        self._set_tree_visible(self._show_tree)

    def _init_connections(self) -> None:
        self.tree.pathSelected.connect(self.on_tree_path_selected)
        self.tree.sectionContextRequested.connect(self.on_section_context_menu)
        self._search_line_edit.textChanged.connect(self._on_search_text_changed)
        self._search_line_edit.regexEnabledChanged.connect(lambda _: self._on_search_text_changed(self._search_line_edit.text()))
        self._search_line_edit.caseSensitivityChanged.connect(lambda _: self._on_search_text_changed(self._search_line_edit.text()))

    def on_section_context_menu(self, section_path: str, global_pos: QtCore.QPoint) -> None:
        """Show the section context menu populated by subclasses."""
        menu = QtWidgets.QMenu(self)
        section = SettingsSection(self, section_path)
        self.populate_section_context_menu(menu, section)
        if menu.actions():
            menu.exec(global_pos)

    def populate_section_context_menu(
        self,
        menu: QtWidgets.QMenu,
        section: "SettingsSection",
    ) -> None:
        """Hook for subclasses to add actions to a section right-click menu.

        Example::

            def populate_section_context_menu(self, menu, section):
                menu.addAction("Add text setting", lambda: section.add_text(...))
        """

    def on_tree_path_selected(self, selected_path: str) -> None:
        """Filter settings to the selected path and scroll to the first matching widget."""
        self._active_path_filter = selected_path or ""
        self.treePathSelected.emit(self._active_path_filter)
        try:
            self._search_line_edit.textChanged.disconnect(self._on_search_text_changed)
            self._search_line_edit.setText('')
        finally:
            self._search_line_edit.textChanged.connect(self._on_search_text_changed)
        self._apply_filters()

    def _on_search_text_changed(self, text: str) -> None:
        """Filter settings based on search text; clears tree filter when typing."""
        if text.strip():
            self._active_path_filter = ""
        self._apply_filters()

    def _clear_tree_selection(self) -> None:
        self.tree.pathSelected.disconnect(self.on_tree_path_selected)
        self.tree.clear_selection()
        self.tree.pathSelected.connect(self.on_tree_path_selected)

    def _apply_filters(self) -> None:
        """Apply either search filter or tree filter (exclusive)."""

        if self._search_line_edit.text().strip():
            pattern = self._search_line_edit.compiledRegex()
            if pattern is None:
                return
            self._clear_tree_selection()
            for setting in self.settings:
                setting.setVisible(bool(pattern.search(setting.text)))
            return

        if self._active_path_filter:
            for setting in self.settings:
                effective_path = setting.section_path if setting.section_path else setting.path
                setting.setVisible(
                    effective_path == self._active_path_filter
                    or effective_path.startswith(f"{self._active_path_filter}/")
                )
            return

        self.show_all_settings()

    def show_all_settings(self) -> None:
        [setting.setVisible(True) for setting in self.settings]

    def add_button(self, text: str, callback: Callable, *, validate: bool = False) -> QtWidgets.QPushButton:
        """Add a custom button to the menu.

        Args:
            text: Button text
            callback: Function to call when button is clicked
            validate: Disable this button while the settings window is invalid

        Returns:
            The created button instance
        """
        button = QtWidgets.QPushButton(text)
        button.clicked.connect(callback)
        self._button_layout.insertWidget(0, button)
        if validate:
            self.register_validation_button(button)
        return button

    def register_validation_button(self, button: QtWidgets.QAbstractButton) -> QtWidgets.QAbstractButton:
        """Keep a button enabled only while the full settings window is valid."""
        if button not in self._validation_buttons:
            self._validation_buttons.append(button)
        button.setEnabled(self.is_valid())
        return button

    def _set_validation_buttons_enabled(self, enabled: bool) -> None:
        alive_buttons: list[QtWidgets.QAbstractButton] = []
        for button in self._validation_buttons:
            try:
                button.setEnabled(enabled)
            except RuntimeError:
                continue
            alive_buttons.append(button)
        self._validation_buttons = alive_buttons

    def _set_tree_visible(self, visible: bool) -> None:
        self._show_tree = visible
        self.tree.setVisible(visible)
        self._lock_tree_splitter()
        if visible:
            self._adjust_tree_width()

    def _lock_tree_splitter(self) -> None:
        handle = self.splitter.handle(1)
        if handle is not None:
            handle.setEnabled(False)
            handle.setCursor(Qt.CursorShape.ArrowCursor)

    def _adjust_tree_width(self) -> None:
        """Size the visible tree to its contents and keep that pane fixed."""
        if not self._show_tree:
            return
        tree_width = self.tree.resize_to_contents()
        total = max(self.splitter.width(), tree_width + self.scroll_area.minimumWidth())
        self.splitter.setSizes([tree_width, max(self.scroll_area.minimumWidth(), total - tree_width)])
        self._lock_tree_splitter()

    def add_section(self, label: str) -> "SettingsSection":
        """Create a top-level section in the navigation tree and return a proxy.

        Args:
            label: Human-readable section name shown in the tree.

        Returns:
            A :class:`SettingsSection` proxy whose ``add_widget`` and
            ``add_section`` calls attach settings to this node.

        Example::

            general = window.add_section("General")
            general.add_widget(key="general/name", title="Display Name", widget=w)
            indexing = window.add_section("Indexing")
            ocr = indexing.add_section("OCR")
            ocr.add_widget(key="ocr/dpi", title="DPI", widget=spin)
        """
        section_path = self._ensure_section_path(label)
        return SettingsSection(self, section_path)

    def _register_section(self, path: str, label: str) -> None:
        """Register a section path → display label for tree population."""
        self._section_labels[path] = label

    def _ensure_section_path(self, section: str, *, parent_path: str = "") -> str:
        """Register a slash-separated section path and return its internal slug path."""
        current_path = parent_path
        for label in [part.strip() for part in str(section).split("/") if part.strip()]:
            slug = _section_slug(label)
            current_path = f"{current_path}/{slug}" if current_path else slug
            self._register_section(current_path, label)
        return current_path

    def _resolve_section_path(self, section: str | "SettingsSection" | None) -> str:
        if section is None:
            return ""
        if isinstance(section, SettingsSection):
            return section.path
        return self._ensure_section_path(section)

    def set_tree_paths(self) -> None:
        """Populate the tree from registered sections."""
        self.tree.populate(list(self._section_labels.keys()), dict(self._section_labels))
        self._adjust_tree_width()

    def _refresh_tree_paths(self) -> None:
        """Populate tree once after queued additions to avoid repeated refreshes."""
        if not self._tree_refresh_scheduled:
            return
        self._tree_refresh_scheduled = False
        self.set_tree_paths()

    def _schedule_tree_refresh(self) -> None:
        """Defer tree population to the next event loop tick."""
        if self._tree_refresh_scheduled:
            return
        self._tree_refresh_scheduled = True
        QtCore.QTimer.singleShot(0, self._refresh_tree_paths)

    @contextmanager
    def batch_add(self):
        """Context manager that suppresses repaints while bulk-adding settings."""
        self.setUpdatesEnabled(False)
        try:
            yield
        finally:
            self._refresh_tree_paths()  # Flush synchronously; cancels the pending timer callback
            self.setUpdatesEnabled(True)
            layout = self.layout()
            if layout is not None:
                layout.activate()
            self._adjust_tree_width()
            self.update()

    def _add_setting(self, setting: "SettingLayout") -> None:
        self.settings.append(setting)
        self.body.insertWidget(self.body.count()-1, setting)
        self._connect_setting_validation(setting)
        self.refresh_validation()
        self._schedule_tree_refresh()
        self._apply_filters()

    def _connect_setting_validation(self, setting: "SettingLayout") -> None:
        def emit_setting_validity(valid: bool) -> None:
            self.settingValidityChanged.emit(setting.path, valid)

        setting.validityChanged.connect(emit_setting_validity)

        def refresh(*_args: Any) -> None:
            self.refresh_validation()

        setting._validation_refresh = refresh  # Keep the callable alive for Qt.
        setting._window_validity_forwarder = emit_setting_validity
        for signal in self._setting_change_signals(setting.widget):
            try:
                signal.connect(refresh)
            except (TypeError, RuntimeError):
                continue

    def _setting_change_signals(self, widget: QWidget) -> list[Any]:
        signals: list[Any] = []

        def add_signal(candidate: Any) -> None:
            if hasattr(candidate, "connect"):
                signals.append(candidate)

        add_signal(getattr(widget, "validationChanged", None))
        add_signal(getattr(widget, "validityChanged", None))

        if isinstance(widget, QtWidgets.QComboBox):
            add_signal(widget.currentTextChanged)
            add_signal(widget.currentIndexChanged)
            line_edit = widget.lineEdit() if widget.isEditable() else None
            if line_edit is not None:
                add_signal(line_edit.textChanged)
            return signals

        if isinstance(widget, (QtWidgets.QLineEdit, QtWidgets.QTextEdit, QtWidgets.QPlainTextEdit)):
            add_signal(getattr(widget, "textChanged", None))
            return signals

        if isinstance(widget, QtWidgets.QAbstractButton):
            add_signal(widget.toggled)
            return signals

        if isinstance(widget, (QtWidgets.QSpinBox, QtWidgets.QDoubleSpinBox, QtWidgets.QSlider, QtWidgets.QDial)):
            add_signal(widget.valueChanged)
            return signals

        for name in ("valueChanged", "textChanged", "currentTextChanged", "toggled"):
            add_signal(getattr(widget, name, None))
        return signals

    def add_widget(
        self,
        *,
        key: str,
        title: str,
        widget: SettingWidget | QWidget,
        subtitle: str = "",
        description: str = "",
        tooltip: str = "",
        section: str | "SettingsSection" | None = None,
        setting_type: str | None = None,
        default: Any = _UNSET,
        validator: Validator | None = None,
    ) -> "SettingLayout":
        """Add a preconfigured widget as a setting row.

        The optional validator receives the current widget value and should
        return an error message, or None when the value is valid.
        """
        if not str(key).strip():
            raise ValueError("Setting key cannot be empty.")
        if self.setting(key) is not None:
            raise ValueError(f"Duplicate setting key: {key!r}")

        resolved_setting_type = setting_type if setting_type is not None else _guess_setting_type(widget)
        spec = SettingSpec(
            key=key,
            title=title,
            subtitle=subtitle,
            description=description,
            tooltip=tooltip,
            default=default,
            setting_type=resolved_setting_type,
            validator=validator,
        )
        setting = SettingLayout(
            spec=spec,
            widget=widget,
            section_path=self._resolve_section_path(section),
        )
        self._add_setting(setting)
        return setting

    def clear_settings(self) -> None:
        """Remove all setting rows while keeping the bottom stretch item."""
        while self.body.count() > 1:
            item = self.body.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self.settings.clear()
        self._schedule_tree_refresh()

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON state payload for this window."""
        return {
            "version": 1,
            "settings": [
                setting.to_state_dict()
                for setting in self.settings
            ],
        }

    def values_to_dict(self) -> dict[str, Any]:
        """Return only the current values, keyed by setting path."""
        return {setting.path: setting.get_value() for setting in self.settings}

    def values(self) -> dict[str, Any]:
        """Return current setting values keyed by setting key."""
        return self.values_to_dict()

    def set_values(self, values: Mapping[str, Any]) -> None:
        """Apply current values from a flat mapping or JSON state payload."""
        self.apply_values(values)

    def setting(self, key: str) -> "SettingLayout | None":
        """Return the first setting row registered with the given key."""
        return next((setting for setting in self.settings if setting.path == key), None)

    def widget_for_key(self, key: str) -> QWidget | None:
        """Return the widget for the first setting row registered with the given key."""
        setting = self.setting(key)
        return setting.widget if setting is not None else None

    def validate_window(self) -> str | list[str] | dict[str, str] | None:
        """Hook for cross-field validation in subclasses."""
        return None

    def _window_validation_errors(self) -> dict[str, str]:
        result = self.validate_window()
        if result is None:
            return {}
        if isinstance(result, str):
            return {"__window__": result}
        if isinstance(result, list):
            return {
                f"__window__/{index}": message
                for index, message in enumerate(result)
                if message
            }
        return {str(key): value for key, value in result.items() if value}

    def _set_status_errors(
        self,
        setting_errors: Mapping[str, str],
        window_errors: Mapping[str, str],
    ) -> None:
        messages: list[str] = []
        if window_errors:
            messages.extend(str(message) for message in window_errors.values() if message)
        elif setting_errors:
            by_path = {setting.path: setting for setting in self.settings}
            for path, message in setting_errors.items():
                setting = by_path.get(path)
                prefix = setting.title if setting is not None else path
                messages.append(f"{prefix}: {message}")
                if len(messages) >= 2:
                    break
            remaining = len(setting_errors) - len(messages)
            if remaining > 0:
                messages.append(f"{remaining} more invalid setting{'s' if remaining > 1 else ''}.")

        text = " ".join(messages)
        self._status_label.setText(text)
        self._status_label.setToolTip(text)
        self._status_label.setVisible(bool(text))

    def validation_errors(self, *, update_ui: bool = True) -> dict[str, str]:
        """Return validation errors keyed by setting path."""
        setting_errors: dict[str, str] = {}
        for setting in self.settings:
            error = setting.validate()
            if update_ui:
                setting.set_validation_error(error)
            if error is not None:
                setting_errors[setting.path] = error
        window_errors = self._window_validation_errors()
        errors = {**setting_errors, **window_errors}
        if update_ui:
            self._set_status_errors(setting_errors, window_errors)
            self.validityChanged.emit(not errors)
        return errors

    def validate(self, *, update_ui: bool = True) -> bool:
        """Return whether all settings are valid."""
        return not self.validation_errors(update_ui=update_ui)

    def is_valid(self) -> bool:
        """Alias for `validate` for symmetry with `SettingLayout`."""
        return self.validate(update_ui=False)

    def refresh_validation(self) -> bool:
        """Refresh inline validation display and return whether all settings are valid."""
        return self.validate(update_ui=True)

    def apply_state(self, data: Mapping[str, Any]) -> None:
        """Restore saved values/history into already-built setting widgets."""
        if "values" in data and isinstance(data["values"], Mapping):
            histories = data.get("history")
            by_path = {setting.path: setting for setting in self.settings}
            restored_paths: set[str] = set()
            for path, value in data["values"].items():
                path_key = str(path)
                setting = by_path.get(path_key)
                if setting is None:
                    continue
                payload: dict[str, Any] = {"value": value}
                if isinstance(histories, Mapping) and path_key in histories:
                    payload["history"] = histories[path_key]
                setting.restore_state(payload)
                restored_paths.add(path_key)
            if isinstance(histories, Mapping):
                for path, history in histories.items():
                    path_key = str(path)
                    setting = by_path.get(path_key)
                    if setting is not None and path_key not in restored_paths:
                        setting.restore_state({"history": history}, mark_clean=False)
            return

        specs = data.get("settings")
        if isinstance(specs, list):
            by_path = {setting.path: setting for setting in self.settings}
            for item in specs:
                if not isinstance(item, Mapping):
                    continue
                path = str(item.get("key") or item.get("path") or "")
                setting = by_path.get(path)
                if setting is not None:
                    setting.restore_state(item)
            return

        by_path = {setting.path: setting for setting in self.settings}
        for path, value in data.items():
            setting = by_path.get(str(path))
            if setting is not None:
                setting.restore_state({"value": value})

    def apply_values(self, values: Mapping[str, Any]) -> None:
        """Apply current values from a flat mapping or JSON state payload."""
        if "values" in values and isinstance(values["values"], Mapping):
            values = values["values"]
        elif "settings" in values and isinstance(values["settings"], list):
            values = {
                str(item.get("key") or item.get("path")): item.get("value")
                for item in values["settings"]
                if isinstance(item, Mapping) and "value" in item
            }

        by_path = {setting.path: setting for setting in self.settings}
        for path, value in values.items():
            setting = by_path.get(str(path))
            if setting is not None:
                setting.set_value(value)
        self.refresh_validation()

    def load_dict(self, data: Mapping[str, Any]) -> None:
        """Restore values/history into already-built setting widgets."""
        self.apply_state(data)
        self.refresh_validation()

    def save_json(self, path: str | Path, *, indent: int = 2) -> None:
        """Save setting values/history to a JSON state file."""
        json_path = Path(path)
        for setting in self.settings:
            setting.record_history()
        payload = self.to_dict()
        json_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=indent, default=_json_default),
            encoding="utf-8",
        )
        self._settings_json_path = json_path

    def load_json(self, path: str | Path) -> None:
        """Load values/history into already-built setting widgets."""
        json_path = Path(path)
        data = json.loads(json_path.read_text(encoding="utf-8"))
        self.load_dict(data)
        self._settings_json_path = json_path


class SettingLayout(QFrame):
    validityChanged = pyqtSignal(bool)

    def __init__(
        self,
        spec: SettingSpec,
        widget: SettingWidget | QWidget,
        *args,
        section_path: str = "",
        **kwargs,
    ):
        super().__init__(*args, **kwargs)

        spec.set_widget(widget)
        self.spec = spec
        self.section_path = section_path
        self.buttons = {} # Holds all optional buttons added to the setting layout, keyed by their object names.
        self._validation_error: str | None = None
        self._is_invalid = False

        title = spec.title
        subtitle = spec.subtitle
        description = spec.description
        tooltip = spec.tooltip

        self.verticalLayout = QVBoxLayout(self)
        self.verticalLayout.setContentsMargins(12, 6, 12, 6)
        self.verticalLayout.setSpacing(3)

        self.top_layout = QHBoxLayout()
        self.top_layout.setContentsMargins(0, 0, 0, 0)
        self.top_layout.setSpacing(0)

        labelTitle = QLabel(title + ': ' if subtitle else title)
        labelTitle.setStyleSheet("font-weight: bold;")
        if tooltip:
            labelTitle.setToolTip(tooltip)
        self.top_layout.addWidget(labelTitle)

        if subtitle:
            labelSubTitle = QLabel(subtitle)
            labelSubTitle.setStyleSheet("font-style: italic;")
            if tooltip:
                labelSubTitle.setToolTip(tooltip)
            self.top_layout.addWidget(labelSubTitle)
        self.top_layout.addStretch()
        self.verticalLayout.addLayout(self.top_layout)

        if description:
            labelDescription = QLabel(description)
            labelDescription.setWordWrap(True)
            if tooltip:
                labelDescription.setToolTip(tooltip)
            self.verticalLayout.addWidget(labelDescription)

        horizontal_layout = QHBoxLayout()
        horizontal_layout.setContentsMargins(0, 0, 0, 0)
        horizontal_layout.setSpacing(0)
        horizontal_layout.addWidget(self.widget, 1)
        horizontal_layout.addSpacing(100)

        self.verticalLayout.addLayout(horizontal_layout)

        self.error_label = QLabel()
        self.error_label.setObjectName("settingErrorLabel")
        self.error_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.error_label.setVisible(False)
        self.verticalLayout.addWidget(self.error_label)

        self.setMinimumWidth(400)
        if tooltip:
            self.setToolTip(tooltip)

    @property
    def widget(self) -> QWidget:
        if self.spec.widget is None:
            raise ValueError("SettingLayout has no widget")
        return self.spec.widget

    @property
    def path(self) -> str:
        return self.spec.key

    @path.setter
    def path(self, value: str) -> None:
        self.spec.key = value

    @property
    def title(self) -> str:
        return self.spec.title

    @property
    def subtitle(self) -> str:
        return self.spec.subtitle

    @property
    def description(self) -> str:
        return self.spec.description

    @property
    def tooltip(self) -> str:
        return self.spec.tooltip

    @property
    def setting_type(self) -> str:
        return self.spec.setting_type

    @property
    def default(self) -> Any:
        return self.spec.default

    @property
    def text(self) -> str:
        return self._search_text()

    def validate_and_display(self, *_args: Any) -> bool:
        error = self.validate()
        self.set_validation_error(error)
        return error is None

    def set_validation_error(self, error: str | None) -> None:
        changed = error != self._validation_error
        self._validation_error = error
        self.error_label.setText(error or "")
        self.error_label.setVisible(error is not None)
        self._set_invalid(error is not None)
        if changed:
            self.validityChanged.emit(error is None)

    def _set_invalid(self, invalid: bool) -> None:
        if invalid == self._is_invalid:
            return
        self._is_invalid = invalid
        for target in self._validation_style_targets():
            target.setProperty("invalid", invalid)
            style = target.style()
            style.unpolish(target)
            style.polish(target)
            target.update()

    def _validation_style_targets(self) -> list[QWidget]:
        targets = [self, self.widget]
        if isinstance(self.widget, QtWidgets.QComboBox):
            line_edit = self.widget.lineEdit() if self.widget.isEditable() else None
            if line_edit is not None:
                targets.append(line_edit)
        return targets

    def enterEvent(self, event) -> None:
        """Sets buttons visible when you enter."""
        if self.buttons:
            self._setButtonListVisible(True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        """Hides buttons when mouse leaves."""
        if self.buttons:
            self._setButtonListVisible(False)
        super().leaveEvent(event)

    def add_button(self, name:str, toolTip:str, icon:str, callback:Callable) -> None:
        """
        Add button to the top right of the setting frame. You can add as many as you want.
        Use the `callback` function to trigger pressed event.

        Args:
            name (str): Object name of the widget
            toolTip (str): Tool tip
            icon (str): Icon path.
            callback (callable): Callback to trigger pressed event.
            icon_size (int, optional): Icon size. Defaults to 12.
        """

        button = IconButton(icon)
        button.setObjectName(name)
        button.setToolTip(toolTip)
        button.clicked.connect(callback)
        button.setVisible(False)
        self.buttons[name]=button
        self.top_layout.addWidget(button)

    def _setButtonListVisible(self, visible:bool):
        for button in self.buttons.values():
            button.setVisible(visible)

    def _search_text(self) -> str:
        return " ".join(part for part in (self.path, self.title, self.subtitle, self.description) if part)

    def get_value(self) -> Any:
        return self.spec.get_value()

    def set_value(self, value: Any, *, mark_clean: bool = False) -> None:
        self.spec.set_value(value, mark_clean=mark_clean)

    def reset_to_default(self, *, mark_clean: bool = False) -> None:
        self.spec.reset_to_default(mark_clean=mark_clean)

    def mark_clean(self) -> None:
        self.spec.mark_clean()

    def is_dirty(self) -> bool:
        return self.spec.is_dirty()

    def validate(self) -> str | None:
        return self.spec.validate()

    def is_valid(self) -> bool:
        return self.spec.is_valid()

    def to_state_dict(self) -> dict[str, Any]:
        data = self.spec.to_state_dict()
        history = _read_widget_history(self.widget)
        if history:
            data["history"] = history
        return data

    def restore_state(self, data: Mapping[str, Any], *, mark_clean: bool = True) -> None:
        if not isinstance(data, Mapping):
            raise TypeError("SettingLayout.restore_state expected a mapping")

        if "history" in data:
            _write_widget_history(self.widget, data["history"])

        self.spec.restore_state(data, mark_clean=mark_clean)

    def record_history(self) -> None:
        _record_widget_history(self.widget)


class SettingWidget(QWidget):
    """Base class for custom setting widgets.

    Subclasses can implement the same to_dict/from_dict contract used by
    settings_spec.SerializableWidget.
    """

    def to_dict(self) -> Dict[str, Any]:
        raise NotImplementedError()

    def from_dict(self, config: Mapping[str, Any]) -> None:
        raise NotImplementedError()


class SettingsSection(SettingsTypedHelpers):
    """Proxy returned by :meth:`SettingsWindow.add_section` that groups settings
    under a named navigation-tree node.

    Sections can be nested by calling :meth:`add_section` on a section proxy:

    Example::

        class ProjectSettingsWindow(SettingsWindow):
            title = "Settings"
            show_tree = True

        window = ProjectSettingsWindow()

        general = window.add_section("General")
        general.add_widget(key="general/name", title="Display Name", widget=name_edit)

        indexing = window.add_section("Indexing")
        ocr = indexing.add_section("OCR")
        ocr.add_widget(key="ocr/dpi", title="DPI", widget=dpi_spin)

    Clicking ``General`` in the tree shows only the "Display Name" row.
    Clicking ``Indexing`` shows all rows inside it, including children of ``OCR``.
    """

    def __init__(self, window: "SettingsWindow", path: str) -> None:
        self._window = window
        self._path = path

    @property
    def path(self) -> str:
        """Internal slug path that identifies this section in the tree."""
        return self._path

    def add_section(self, label: str) -> "SettingsSection":
        """Create a nested sub-section and return its proxy.

        Args:
            label: Human-readable sub-section name shown in the tree.
        """
        child_path = self._window._ensure_section_path(label, parent_path=self._path)
        return SettingsSection(self._window, child_path)

    def add_widget(
        self,
        *,
        key: str,
        title: str,
        widget: "SettingWidget | QWidget",
        subtitle: str = "",
        description: str = "",
        tooltip: str = "",
        section: str | "SettingsSection" | None = None,
        setting_type: str | None = None,
        default: Any = _UNSET,
        validator: "Validator | None" = None,
    ) -> "SettingLayout":
        """Add a setting row that belongs to this section.

        Accepts the same arguments as :meth:`SettingsWindow.add_widget`.
        """
        if section is None:
            section_path = self._path
        elif isinstance(section, SettingsSection):
            section_path = section.path
        else:
            section_path = self._window._ensure_section_path(section, parent_path=self._path)

        setting = self._window.add_widget(
            key=key,
            title=title,
            widget=widget,
            subtitle=subtitle,
            description=description,
            tooltip=tooltip,
            section=None,
            setting_type=setting_type,
            default=default,
            validator=validator,
        )
        setting.section_path = section_path
        self._window._apply_filters()
        return setting
