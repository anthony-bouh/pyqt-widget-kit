"""Pill selector widget - flow-layout pill picker with single/multi-selection.

Classes:
    FlowLayout      QLayout subclass that wraps items to the next line when the
                    available width is exhausted. Works like CSS ``flex-wrap``.

    PillButton      Checkable QPushButton representing one pill. Sets a
                    ``selected`` dynamic property so QSS rules can target it.

    PillSelector    Composite QWidget that holds a collection of PillButtons
                    arranged with FlowLayout.

Usage example::

    selector = PillSelector()
    selector.set_pills(["Python", "Qt", "PyQt6", "GUI"])
    selector.set_selection_mode("multi")          # or "single"
    selector.selectionChanged.connect(print)      # emits list[str]

    selector.set_selected_pills(["Qt", "PyQt6"])
    print(selector.selected_pills())              # ["Qt", "PyQt6"]
"""
from __future__ import annotations

from typing import Literal

from PyQt6.QtCore import QPoint, QRect, QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import QLayout, QLayoutItem, QPushButton, QSizePolicy, QStyle, QWidget

SelectionMode = Literal["single", "multi"]


def _refresh_style(widget: QWidget) -> None:
    """Unpolish and re-polish a widget's style, guarding against None."""
    style: QStyle | None = widget.style()
    if style is not None:
        style.unpolish(widget)
        style.polish(widget)


class FlowLayout(QLayout):
    """
    A custom layout that arranges widgets horizontally and wraps them to the next line
    when there is not enough space.
    """

    def __init__(self, parent: QWidget | None = None, margin: int = 0, spacing: int = -1) -> None:
        super().__init__(parent)
        if parent is not None:
            self.setContentsMargins(margin, margin, margin, margin)
        self.setSpacing(spacing)
        self._items: list[QLayoutItem] = []

    def __del__(self) -> None:
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)

    def addItem(self, item: QLayoutItem) -> None:
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int) -> QLayoutItem | None:
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int) -> QLayoutItem | None:
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self) -> Qt.Orientation:
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._do_layout(QRect(0, 0, width, 0), apply_geometry=False)

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self._do_layout(rect, apply_geometry=True)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())

        margins = self.contentsMargins()
        size += QSize(margins.left() + margins.right(), margins.top() + margins.bottom())
        return size

    def _do_layout(self, rect: QRect, apply_geometry: bool) -> int:
        """
        Calculates the layout and optionally applies it.
        Returns the total height required.
        """
        x = rect.x()
        y = rect.y()
        line_height = 0
        spacing = self.spacing()

        for item in self._items:
            widget = item.widget()
            if widget is None:
                continue
            style: QStyle | None = widget.style()
            if style is None:
                continue
            layout_spacing_x = style.layoutSpacing(
                QSizePolicy.ControlType.PushButton,
                QSizePolicy.ControlType.PushButton,
                Qt.Orientation.Horizontal,
            )
            layout_spacing_y = style.layoutSpacing(
                QSizePolicy.ControlType.PushButton,
                QSizePolicy.ControlType.PushButton,
                Qt.Orientation.Vertical,
            )

            actual_spacing_x = spacing if spacing >= 0 else layout_spacing_x
            actual_spacing_y = spacing if spacing >= 0 else layout_spacing_y

            next_x = x + item.sizeHint().width() + actual_spacing_x
            if next_x - actual_spacing_x > rect.right() and line_height > 0:
                x = rect.x()
                y = y + line_height + actual_spacing_y
                next_x = x + item.sizeHint().width() + actual_spacing_x
                line_height = 0

            if apply_geometry:
                item.setGeometry(QRect(QPoint(x, y), item.sizeHint()))

            x = next_x
            line_height = max(line_height, item.sizeHint().height())

        return y + line_height - rect.y()


class PillButton(QPushButton):
    """
    A custom button representing a pill.
    Uses dynamic properties for QSS styling.
    """

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setCheckable(True)
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)

    def set_selected(self, selected: bool) -> None:
        self.setChecked(selected)
        self.setProperty("selected", selected)
        _refresh_style(self)


class PillSelector(QWidget):
    """
    A reusable PyQt6 widget for selecting pills from a list of suggestions.
    Supports single and multi-selection modes.
    """

    selectionChanged = pyqtSignal(list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._selection_mode: SelectionMode = "multi"
        self._pills: dict[str, PillButton] = {}
        self.setContentsMargins(6, 6, 6, 6)
        self._layout = FlowLayout(self)
        self.setLayout(self._layout)

    def set_selection_mode(self, mode: SelectionMode) -> None:
        """Sets the selection mode: 'single' or 'multi'."""
        if mode not in ("single", "multi"):
            raise ValueError("Mode must be 'single' or 'multi'")
        self._selection_mode = mode
        if mode == "single":
            selected = self.selected_pills()
            if len(selected) > 1:
                self.set_selected_pills([selected[0]])

    def add_pill(self, pill: str) -> None:
        """Adds a new pill to the selector."""
        if pill in self._pills:
            return

        btn = PillButton(pill)
        btn.toggled.connect(lambda checked, value=pill: self._on_pill_toggled(value, checked))
        self._pills[pill] = btn
        self._layout.addWidget(btn)
        self._refresh_layout_geometry()

    def remove_pill(self, pill: str) -> None:
        """Removes a pill from the selector."""
        if pill in self._pills:
            btn = self._pills.pop(pill)
            self._layout.removeWidget(btn)
            btn.deleteLater()
            self._refresh_layout_geometry()
            self.selectionChanged.emit(self.selected_pills())

    def set_pills(self, pills: list[str]) -> None:
        """Clears existing pills and sets a new list of suggested pills."""
        previous_block_state = self.blockSignals(True)
        try:
            self.clear_all_pills()
            for pill in pills:
                self.add_pill(pill)
        finally:
            self.blockSignals(previous_block_state)
        self._refresh_layout_geometry()
        self.selectionChanged.emit(self.selected_pills())

    def clear_all_pills(self) -> None:
        """Removes all pills from the widget."""
        if not self._pills:
            return
        previous_block_state = self.blockSignals(True)
        try:
            for pill in list(self._pills.keys()):
                self.remove_pill(pill)
        finally:
            self.blockSignals(previous_block_state)
        self._refresh_layout_geometry()
        self.selectionChanged.emit(self.selected_pills())

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        margins = self.contentsMargins()
        layout_width = max(0, width - margins.left() - margins.right())
        return (
            self._layout.heightForWidth(layout_width)
            + margins.top()
            + margins.bottom()
        )

    def sizeHint(self) -> QSize:
        width = self.width() or self._layout.sizeHint().width()
        return QSize(width, self.heightForWidth(width))

    def minimumSizeHint(self) -> QSize:
        return self._layout.minimumSize()

    def selected_pills(self) -> list[str]:
        """Returns a list of currently selected pills."""
        return [pill for pill, btn in self._pills.items() if btn.isChecked()]

    def set_selected_pills(self, pills: list[str]) -> None:
        """Sets the selection state for the given pills."""
        self.blockSignals(True)

        effective_pills = pills[:1] if self._selection_mode == "single" and len(pills) > 1 else pills

        for pill, btn in self._pills.items():
            selected = pill in effective_pills
            btn.setChecked(selected)
            btn.setProperty("selected", selected)
            _refresh_style(btn)

        self.blockSignals(False)
        self.selectionChanged.emit(self.selected_pills())

    def clear_selection(self) -> None:
        """Deselects all pills."""
        self.set_selected_pills([])

    def _on_pill_toggled(self, pill: str, checked: bool) -> None:
        """Internal handler for pill button toggle events."""
        if checked and self._selection_mode == "single":
            self.blockSignals(True)
            for value, btn in self._pills.items():
                if value != pill:
                    btn.setChecked(False)
                    btn.setProperty("selected", False)
                    _refresh_style(btn)
            self.blockSignals(False)

        btn = self._pills[pill]
        btn.setProperty("selected", checked)
        _refresh_style(btn)

        self.selectionChanged.emit(self.selected_pills())

    def _refresh_layout_geometry(self) -> None:
        self._layout.invalidate()
        self.updateGeometry()
