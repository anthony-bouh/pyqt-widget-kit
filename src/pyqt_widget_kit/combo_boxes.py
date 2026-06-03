from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from PyQt6 import QtGui, QtWidgets
from PyQt6.QtCore import QSettings, QSortFilterProxyModel, Qt, pyqtSignal


class AutoWidthComboBox(QtWidgets.QComboBox):
    
    def __init__(self, *arg, **kwargs) -> None:
        super().__init__(*arg, **kwargs)
        self.setEditable(True)
        line_edit = self.lineEdit()
        if line_edit:
            line_edit.setPlaceholderText("Select an option...")
        self.currentIndexChanged.connect(self.on_selection_changed)

    def addItems(self, items: Iterable[str]) -> None:
        super().addItems([str(item) for item in items])
        self.adjustMinimumWidth()

    def addItem(self, item: str, userData: Any = None) -> None:
        super().addItem(str(item), userData)
        self.adjustMinimumWidth()

    def adjustMinimumWidth(self) -> None:
        font_metrics = self.fontMetrics()
        max_width = max((font_metrics.horizontalAdvance(self.itemText(i)) for i in range(self.count())), default=0)
        self.setMinimumWidth(max_width + 40)  # Add padding for dropdown arrow

    def on_selection_changed(self, index) -> None:
        pass
       
        
class SearchableComboBox(QtWidgets.QComboBox):

    def __init__(self, parent=None, max_visible_items: int = 10) -> None:
        super(SearchableComboBox, self).__init__(parent)

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setEditable(True)
        
        # Set maximum visible items in dropdown
        self.setMaxVisibleItems(max_visible_items)
        
        # Set size adjust policy to prevent expansion with long text
        self.setSizeAdjustPolicy(QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        
        # Set a reasonable minimum contents length
        self.setMinimumContentsLength(20)

        # add a filter model to filter matching items
        self.pFilterModel = QSortFilterProxyModel(self)
        self.pFilterModel.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.pFilterModel.setSourceModel(self.model())

        # add a completer, which uses the filter model
        completer = QtWidgets.QCompleter(self.pFilterModel, self)
        completer.setCompletionMode(QtWidgets.QCompleter.CompletionMode.UnfilteredPopupCompletion)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        
        # Set max width for completer popup to prevent it from being too wide
        completer.popup().setStyleSheet("""
            QListView {
                min-width: 200px;
                max-width: 600px;
            }
        """)

        # connect signals
        if self.lineEdit() is None:
            raise RuntimeError("LineEdit is not set for the combo box.")
        
        line_edit = self.lineEdit()
        line_edit.setPlaceholderText("Type to filter...") # pyright: ignore[reportOptionalMemberAccess]
        line_edit.textEdited.connect(self.pFilterModel.setFilterFixedString)  # pyright: ignore[reportOptionalMemberAccess]
        completer.activated.connect(self.on_completer_activated)
        self.setCompleter(completer)
        
        # Enable text elision in the line edit for long text
        if line_edit:
            line_edit.setCursorPosition(0)  # Show beginning of text when too long

    def addItem(self, text: str, userData=None) -> None:
        """Override addItem to add tooltip for long items."""
        super().addItem(text, userData)
        index = self.count() - 1
        if len(text) > 50:  # If text is longer than 50 characters, add tooltip
            self.setItemData(index, text, Qt.ItemDataRole.ToolTipRole)
    
    def addItems(self, texts) -> None:
        """Override addItems to add tooltips for long items."""
        for text in texts:
            self.addItem(text)

    def on_completer_activated(self, text) -> None:
        # on selection of an item from the completer, select the corresponding item from combobox
        if text:
            index = self.findText(text)
            self.setCurrentIndex(index)
            self.activated.emit(index)
            
            # Scroll line edit to show beginning of text
            line_edit = self.lineEdit()
            if line_edit:
                line_edit.setCursorPosition(0)

    def setModel(self, model) -> None:
        # on model change, update the models of the filter and completer as well
        super(SearchableComboBox, self).setModel(model)
        self.pFilterModel.setSourceModel(model)
        self.completer().setModel(self.pFilterModel) # type: ignore[reportOptionalMemberAccess]

    def setModelColumn(self, column) -> None:
        # on model column change, update the model column of the filter and completer as well
        self.completer().setCompletionColumn(column) # type: ignore[reportOptionalMemberAccess]
        self.pFilterModel.setFilterKeyColumn(column)
        super(SearchableComboBox, self).setModelColumn(column)
    
    def setCurrentIndex(self, index: int) -> None:
        """Override to scroll to beginning when selecting an item."""
        super().setCurrentIndex(index)
        line_edit = self.lineEdit()
        if line_edit:
            line_edit.setCursorPosition(0)
    
    def setCurrentText(self, text: str) -> None:
        """Override to scroll to beginning when setting text."""
        super().setCurrentText(text)
        line_edit = self.lineEdit()
        if line_edit:
            line_edit.setCursorPosition(0)


class HistoryComboBox(QtWidgets.QComboBox):
    """
    Editable QComboBox with text history.

    Features:
    - User can type free text.
    - Press Enter to submit/store text.
    - Most recent entries are shown first.
    - Duplicate entries are moved to the top.
    - History length is limited.
    - Optional persistence with QSettings.
    - Up/Down arrows browse history when the popup is closed.
    """

    historySubmitted = pyqtSignal(str)

    def __init__(
        self,
        parent: QtWidgets.QWidget | None = None,
        *,
        max_history: int = 50,
        settings: QSettings | None = None,
        settings_key: str = "history",
        case_sensitive: bool = False,
    ):
        super().__init__(parent)

        self._max_history = max(1, max_history)
        self._settings = settings
        self._settings_key = settings_key
        self._case_sensitive = case_sensitive

        self._browse_index = -1
        self._draft_text = ""

        self.setEditable(True)

        # We manage history insertion ourselves.
        self.setInsertPolicy(QtWidgets.QComboBox.InsertPolicy.NoInsert)

        # Prevent user-created duplicates through normal QComboBox behavior.
        # Programmatic insertion still needs to be handled manually.
        self.setDuplicatesEnabled(False)

        self.lineEdit().returnPressed.connect(self.commit_text)

        if self._settings is not None:
            self.load_history()

    def _key(self, text: str) -> str:
        return text if self._case_sensitive else text.casefold()

    def history(self) -> list[str]:
        return [self.itemText(i) for i in range(self.count())]

    def set_history(self, items: Iterable[str]) -> None:
        cleaned: list[str] = []
        seen: set[str] = set()

        for item in items:
            text = str(item).strip()
            if not text:
                continue

            key = self._key(text)
            if key in seen:
                continue

            cleaned.append(text)
            seen.add(key)

            if len(cleaned) >= self._max_history:
                break

        old_state = self.blockSignals(True)
        self.clear()
        self.addItems(cleaned)
        self.setCurrentIndex(-1)
        self.setEditText("")
        self.blockSignals(old_state)

        self._browse_index = -1
        self._draft_text = ""

    def add_to_history(self, text: str) -> None:
        text = text.strip()
        if not text:
            return

        key = self._key(text)

        # Remove existing duplicate so it can be moved to the top.
        for i in range(self.count()):
            if self._key(self.itemText(i)) == key:
                self.removeItem(i)
                break

        self.insertItem(0, text)

        while self.count() > self._max_history:
            self.removeItem(self.count() - 1)

        self.setCurrentIndex(0)
        self.save_history()

    def record_history(self) -> None:
        text = self.currentText().strip()
        if not text:
            return

        self.add_to_history(text)
        self.setEditText(text)

        self._browse_index = -1
        self._draft_text = ""

    def commit_text(self) -> None:
        text = self.currentText().strip()
        if not text:
            return

        self.record_history()
        self.historySubmitted.emit(text)

    def clear_history(self) -> None:
        self.clear()
        self.setEditText("")
        self._browse_index = -1
        self._draft_text = ""
        self.save_history()

    def load_history(self) -> None:
        if self._settings is None:
            return

        value = self._settings.value(self._settings_key, [])

        if value is None:
            items = []
        elif isinstance(value, str):
            items = [value]
        else:
            items = list(value)

        self.set_history(items)

    def save_history(self) -> None:
        if self._settings is not None:
            self._settings.setValue(self._settings_key, self.history())

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        # Let the popup handle navigation normally when visible.
        if self.view().isVisible():
            super().keyPressEvent(event)
            return

        key = event.key()

        if key == Qt.Key.Key_Up:
            self._browse_previous()
            return

        if key == Qt.Key.Key_Down:
            self._browse_next()
            return

        super().keyPressEvent(event)

    def _browse_previous(self) -> None:
        if self.count() == 0:
            return

        if self._browse_index == -1:
            self._draft_text = self.currentText()
            self._browse_index = 0
        else:
            self._browse_index = max(0, self._browse_index - 1)

        self.setEditText(self.itemText(self._browse_index))

    def _browse_next(self) -> None:
        if self.count() == 0 or self._browse_index == -1:
            return

        if self._browse_index >= self.count() - 1:
            self._browse_index = -1
            self.setEditText(self._draft_text)
        else:
            self._browse_index += 1
            self.setEditText(self.itemText(self._browse_index))
