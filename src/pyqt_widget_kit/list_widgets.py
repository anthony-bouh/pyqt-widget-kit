from __future__ import annotations

from typing import Callable, List

from PyQt6 import QtWidgets
from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QCursor, QIcon

from .combo_boxes import SearchableComboBox
from .resources import resource_path


class EditableStringListWidget(QtWidgets.QListWidget):
    
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        
        self.setMinimumHeight(30)  # Initial height
        self.setDragDropMode(QtWidgets.QListWidget.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSelectionMode(QtWidgets.QListWidget.SelectionMode.SingleSelection)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setMaximumHeight(200)  # Set a maximum height to ensure scrollbar visibility
        self.setMinimumWidth(200)
        self.setSpacing(0)
        
        self.itemHeight = self.sizeHintForRow(0) if self.count() > 0 else 30
        # self.updateHeight()

    def updateHeight(self) -> None:
        """Update the height of the list widget based on the number of items."""
        item_count = self.count()
        new_height = item_count * self.itemHeight
        self.setFixedHeight(new_height)

    def addRow(self, text:str='', row:int=0) -> None:
        """Add a new row with a text input and buttons for reorder, remove, and duplicate."""
        
        PushButtonIconStyle = """
        /* ───────────── Base Icon‑Only Button ───────────── */
        QPushButton {
            text-align:        center;
            padding:           1px;
            min-width:         14px;
            min-height:        14px;
            max-width:         14px;
            max-height:        14px;
            qproperty-iconSize: 14px 14px;
            border:            none; 
            border-radius:     4px;
            color:             transparent;
            outline:           none;
        }

        QPushButton:hover {
            background-color:  transparent;
        }

        QPushButton:pressed {
            background-color:  palette(highlight);
            border:            1px solid palette(highlight);
        }
        
        QPushButton:focus {
            /* custom focus ring */
            border:            2px solid palette(highlight);
        }

        QPushButton:default {
            border:            2px solid palette(highlight);
        }

        QPushButton::menu-indicator {
            subcontrol-origin:      padding;
            subcontrol-position:    center right;
            width:                  0px;
            height:                 0px;
            image:                  none;
        }
        """

        # Layout for the item widget
        item_widget = QtWidgets.QWidget()
        item_widget.setObjectName('itemWidget')
        item_widget.setStyleSheet("""
            QWidget#itemWidget {             
                border:             1px solid palette(mid);
                border-top:         0px;
                border-right:       0px;
                border-left:        0px;   
            }
        """)
        
        layout = QtWidgets.QHBoxLayout(item_widget)
        layout.setContentsMargins(0,3,0,3)
        layout.setSpacing(3)
        
        # Reorder Button
        reorder_button = QtWidgets.QPushButton()
        reorder_button.setObjectName("reorderButton")
        reorder_button.setIcon(QIcon(resource_path('ico/grip-lines.png')))
        reorder_button.setStyleSheet(PushButtonIconStyle+"QPushButton {qproperty-iconSize: 10px 10px;}")
        reorder_button.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        layout.addWidget(reorder_button, 0)
        
        # Add Widget
        line_edit = QtWidgets.QLineEdit(text)
        line_edit.setObjectName('lineEdit')
        line_edit.setStyleSheet("""
            QLineEdit {
                border:                 none;
                border-radius:          none;
                background:             transparent;
        
                /* padding inside the field */
                padding:                0px;
                
                /* dimensions */
                height:                 16px; /* Adjusted height */
                max-height:             16px; /* Adjusted height */
                min-height:             16px; /* Added minimum height */
        }
        """)
        layout.addWidget(line_edit, 1)
        
        # Bin Button
        bin_button = QtWidgets.QPushButton()
        bin_button.setObjectName("binButton")
        bin_button.setStyleSheet(PushButtonIconStyle)
        bin_button.setIcon(QIcon(resource_path('ico/bin-red.png')))
        bin_opacity = QtWidgets.QGraphicsOpacityEffect()
        bin_opacity.setOpacity(0)
        bin_button.setGraphicsEffect(bin_opacity)
        bin_button.setVisible(True)
        bin_button.clicked.connect(lambda: self.remove(item))
        layout.addWidget(bin_button, 0)

        # Duplicate Button
        dup_button = QtWidgets.QPushButton()
        dup_button.setObjectName("dupButton")
        dup_button.setStyleSheet(PushButtonIconStyle)
        dup_button.setIcon(QIcon(resource_path('ico/duplicate.png')))
        dup_opacity = QtWidgets.QGraphicsOpacityEffect()
        dup_opacity.setOpacity(0)
        dup_button.setGraphicsEffect(dup_opacity)
        dup_button.setVisible(True)
        dup_button.clicked.connect(lambda: self.duplicate(item))
        layout.addWidget(dup_button, 0)
        
        item = QtWidgets.QListWidgetItem()
        item.setSizeHint(item_widget.sizeHint())
        if row>0 and row < self.count():
            self.insertItem(row, item)
        else:
            self.addItem(item)
        self.setItemWidget(item, item_widget)
        
    def eventFilter(self, source, event) -> bool:
        """Filter events to show/hide buttons on hover."""
        if isinstance(source, QtWidgets.QWidget):
            bin_button = source.findChild(QtWidgets.QPushButton, "binButton")
            if bin_button:
                dup_button = source.findChild(QtWidgets.QPushButton, "dupButton")
                if event.type() == QEvent.Type.Enter:
                    bin_button.graphicsEffect().setOpacity(1)
                    dup_button.graphicsEffect().setOpacity(1)
                elif event.type() == QEvent.Type.Leave:
                    bin_button.graphicsEffect().setOpacity(0)
                    dup_button.graphicsEffect().setOpacity(0)
        return super().eventFilter(source, event)

    def remove(self, item: QtWidgets.QListWidgetItem) -> None:
        row_index = self.row(item)
        self.takeItem(row_index)
        viewport = self.viewport()
        if viewport is None:
            raise RuntimeError("Viewport is not set. Cannot map global position.")
        pos = viewport.mapFromGlobal(QCursor.pos())
        item_under_mouse = self.itemAt(pos)
        if item_under_mouse:
            widget = self.itemWidget(item_under_mouse)
            if widget:
                enter_event = QEvent(QEvent.Type.Enter)
                QtWidgets.QApplication.postEvent(widget, enter_event)
                
    def duplicate(self, item: QtWidgets.QListWidgetItem) -> None:
        """Duplicate the item and add it below the original."""
        if not item:
            return
        # Create a new item with the same text as the original
        row_index = self.row(item)
        widget = self.itemWidget(item)
        if widget:
            text = widget.findChild(QtWidgets.QLineEdit, 'lineEdit').text()
            self.addRow(text, row_index+1) # Add below

    def to_list(self) -> List[str]:
        texts = []
        for row in range(self.count()):
            widget = self.itemWidget(self.item(row))
            if widget:
                line_edit = widget.findChild(QtWidgets.QLineEdit, 'lineEdit')
                if line_edit:
                    texts.append(line_edit.text())
        return texts


class DynamicRowListWidget(QtWidgets.QListWidget):
    
    def __init__(self, widget_factory: Callable[[], List[QtWidgets.QWidget]], parent=None) -> None:
        """
        Initialize DynamicRowListWidget with a factory function.
        
        Args:
            widget_factory: A callable that returns a list of new widget instances for each row.
                           This function is called every time a new row is added.
            parent: Parent widget
            
        Example - Basic usage:
            def create_widgets():
                combo = AutoWidthComboBox()
                combo.addItems(["Option A", "Option B", "Option C"])
                return [QtWidgets.QLineEdit(), combo, QtWidgets.QSpinBox()]
            
            dynamic_list = DynamicRowListWidget(create_widgets, self)
        
        Example - Load saved data:
            dynamic_list = DynamicRowListWidget(create_widgets, self)
            # Load previously saved data
            saved_data = [
                ["Text 1", "Option A", 10],
                ["Text 2", "Option B", 20]
            ]
            dynamic_list.from_list(saved_data)
        
        Example - Save data:
            data = dynamic_list.to_list()
            # Returns: [["Text 1", "Option A", 10], ["Text 2", "Option B", 20]]
        """
        super().__init__(parent)
        
        self.setMinimumHeight(30)  # Initial height
        self.setDragDropMode(QtWidgets.QListWidget.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSelectionMode(QtWidgets.QListWidget.SelectionMode.SingleSelection)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setMinimumWidth(200)
        self.setSpacing(0)
        self.setStyleSheet("""
            QListWidget { 
                border:                 1px solid palette(mid);
                border-radius:          4px; 
                padding:                4px;
            }
            QListWidget::item { 
                background-color:       transparent;
                padding-right:          15px;
            }
            QListWidget::item:selected { 
                background-color:       transparent; 
            }
        """)
        
        self.itemHeight = self.sizeHintForRow(0) if self.count() > 0 else 30
        self.widget_factory = widget_factory
        # self.updateHeight()

    def updateHeight(self) -> None:
        """Update the height of the list widget based on the number of items."""
        item_count = self.count()
        new_height = item_count * self.itemHeight
        self.setFixedHeight(new_height)

    def addRow(self, row:int=0) -> None:
        """Add a new row with a text input and buttons for reorder, remove, and duplicate."""
        
        PushButtonIconStyle = """
        /* ───────────── Base Icon‑Only Button ───────────── */
        QPushButton {
            text-align:        center;
            padding:           1px;
            min-width:         14px;
            min-height:        14px;
            max-width:         14px;
            max-height:        14px;
            qproperty-iconSize: 14px 14px;
            border:            none; 
            border-radius:     4px;
            color:             transparent;
            outline:           none;
        }

        QPushButton:hover {
            background-color:  transparent;
        }

        QPushButton:pressed {
            background-color:  palette(highlight);
            border:            1px solid palette(highlight);
        }
        
        QPushButton:focus {
            /* custom focus ring */
            border:            2px solid palette(highlight);
        }

        QPushButton:default {
            border:            2px solid palette(highlight);
        }

        QPushButton::menu-indicator {
            subcontrol-origin:      padding;
            subcontrol-position:    center right;
            width:                  0px;
            height:                 0px;
            image:                  none;
        }
        """

        # Layout for the item widget
        container = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(container)
        layout.setContentsMargins(0,3,0,3)
        layout.setSpacing(3)
        
        # Left container with reorder button and widgets container
        left_container = QtWidgets.QWidget()
        left_container.setObjectName('left_container')
        left_layout = QtWidgets.QHBoxLayout(left_container)
        left_layout.setContentsMargins(0,0,0,0)
        left_layout.setSpacing(3)
        
        # Reorder Button
        reorder_button = QtWidgets.QPushButton()
        reorder_button.setObjectName("reorderButton")
        reorder_button.setIcon(QIcon(resource_path('ico/grip-lines.png')))
        reorder_button.setStyleSheet(PushButtonIconStyle+"QPushButton {qproperty-iconSize: 10px 10px;}")
        reorder_button.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        left_layout.addWidget(reorder_button, 0)
        
        # Widgets container - dedicated container for factory widgets only
        widgets_container = QtWidgets.QWidget()
        widgets_container.setObjectName('widgets_container')
        widgets_layout = QtWidgets.QHBoxLayout(widgets_container)
        widgets_layout.setContentsMargins(0,0,0,0)
        widgets_layout.setSpacing(3)
        
        # Add widgets from factory to the dedicated container
        widgets = self.widget_factory()
        for widget in widgets:
            widgets_layout.addWidget(widget)
        
        left_layout.addWidget(widgets_container, 1)
        layout.insertWidget(0, left_container, 1)
    
        # Bin Button
        bin_button = QtWidgets.QPushButton()
        bin_button.setObjectName("binButton")
        bin_button.setStyleSheet(PushButtonIconStyle)
        bin_button.setIcon(QIcon(resource_path('ico/bin-red.png')))
        bin_opacity = QtWidgets.QGraphicsOpacityEffect()
        bin_opacity.setOpacity(0)
        bin_button.setGraphicsEffect(bin_opacity)
        bin_button.setVisible(True)
        bin_button.clicked.connect(lambda: self.remove(item))
        layout.addWidget(bin_button, 0)

        # Duplicate Button
        dup_button = QtWidgets.QPushButton()
        dup_button.setObjectName("dupButton")
        dup_button.setStyleSheet(PushButtonIconStyle)
        dup_button.setIcon(QIcon(resource_path('ico/duplicate.png')))
        dup_opacity = QtWidgets.QGraphicsOpacityEffect()
        dup_opacity.setOpacity(0)
        dup_button.setGraphicsEffect(dup_opacity)
        dup_button.setVisible(True)
        dup_button.clicked.connect(lambda: self.duplicate(item))
        layout.addWidget(dup_button, 0)
        
        item = QtWidgets.QListWidgetItem()
        item.setSizeHint(container.sizeHint())
        if row>0 and row < self.count():
            self.insertItem(row, item)
        else:
            self.addItem(item)
        self.setItemWidget(item, container)
        
    def eventFilter(self, source, event) -> bool:
        """Filter events to show/hide buttons on hover."""
        if isinstance(source, QtWidgets.QWidget):
            bin_button = source.findChild(QtWidgets.QPushButton, "binButton")
            if bin_button:
                dup_button = source.findChild(QtWidgets.QPushButton, "dupButton")
                if event.type() == QEvent.Type.Enter:
                    bin_button.graphicsEffect().setOpacity(1)
                    dup_button.graphicsEffect().setOpacity(1)
                elif event.type() == QEvent.Type.Leave:
                    bin_button.graphicsEffect().setOpacity(0)
                    dup_button.graphicsEffect().setOpacity(0)
        return super().eventFilter(source, event)

    def remove(self, item: QtWidgets.QListWidgetItem) -> None:
        row_index = self.row(item)
        self.takeItem(row_index)
        viewport = self.viewport()
        if viewport is None:
            raise RuntimeError("Viewport is not set. Cannot map global position.")
        pos = viewport.mapFromGlobal(QCursor.pos())
        item_under_mouse = self.itemAt(pos)
        if item_under_mouse:
            widget = self.itemWidget(item_under_mouse)
            if widget:
                enter_event = QEvent(QEvent.Type.Enter)
                QtWidgets.QApplication.postEvent(widget, enter_event)
    
    def _get_widget_value(self, widget: QtWidgets.QWidget):
        """Extract value from any supported widget type.
        
        Args:
            widget: The widget to extract value from
            
        Returns:
            The widget's current value in appropriate type
        """
        if isinstance(widget, QtWidgets.QLineEdit):
            return widget.text()
        elif isinstance(widget, SearchableComboBox):
            return widget.currentText()
        elif isinstance(widget, QtWidgets.QComboBox):
            return widget.currentText()
        elif isinstance(widget, (QtWidgets.QSpinBox, QtWidgets.QDoubleSpinBox)):
            return widget.value()
        elif isinstance(widget, QtWidgets.QCheckBox):
            return widget.isChecked()
        elif hasattr(widget, 'text'):
            return widget.text()  # type: ignore
        elif hasattr(widget, 'value'):
            return widget.value()  # type: ignore
        else:
            return str(widget)
    
    def _set_widget_value(self, widget: QtWidgets.QWidget, value) -> None:
        """Set value to any supported widget type.
        
        Args:
            widget: The widget to set value to
            value: The value to set
        """
        if isinstance(widget, QtWidgets.QLineEdit):
            widget.setText(str(value))
        elif isinstance(widget, (SearchableComboBox, QtWidgets.QComboBox)):
            if isinstance(value, int):
                widget.setCurrentIndex(value)
            else:
                index = widget.findText(str(value))
                if index >= 0:
                    widget.setCurrentIndex(index)
                else:
                    widget.setCurrentText(str(value))
        elif isinstance(widget, (QtWidgets.QSpinBox, QtWidgets.QDoubleSpinBox)):
            widget.setValue(float(value))
        elif isinstance(widget, QtWidgets.QCheckBox):
            widget.setChecked(bool(value))
    
    def _get_row_widgets(self, row_index: int) -> List[QtWidgets.QWidget]:
        """Get all widgets from a specific row.
        
        Args:
            row_index: The index of the row
            
        Returns:
            List of widgets in the row's widgets_container
        """
        item = self.item(row_index)
        if not item:
            return []
        
        container = self.itemWidget(item)
        if not container:
            return []
        
        widgets_container = container.findChild(QtWidgets.QWidget, 'widgets_container')
        if not widgets_container:
            return []
        
        return [child for child in widgets_container.children() 
                if not isinstance(child, QtWidgets.QHBoxLayout)]
                
    def duplicate(self, item: QtWidgets.QListWidgetItem) -> None:
        """Duplicate the item and add it below the original, copying all widget values."""
        if not item:
            return
        
        source_row_index = self.row(item)
        widgets = self._get_row_widgets(source_row_index)
        row_values = [self._get_widget_value(widget) for widget in widgets]
        
        self.addRow(source_row_index + 1)
        if row_values:
            self.set_row_values(source_row_index + 1, row_values)

    def to_list(self) -> List[List]:
        """
        Get list of widget values from each row.
        Returns a list of lists, where each inner list contains the values from all widgets in that row.
        
        Supported widget types:
        - QLineEdit: returns text()
        - SearchableComboBox: returns currentText()
        - QComboBox: returns currentText()
        - QSpinBox/QDoubleSpinBox: returns value()
        - QCheckBox: returns isChecked()
        - Other widgets: returns string representation
        
        Returns:
            List of lists containing widget values for each row
        """
        all_rows = []
        for row in range(self.count()):
            widgets = self._get_row_widgets(row)
            row_values = [self._get_widget_value(widget) for widget in widgets]
            if row_values:
                all_rows.append(row_values)
        
        return all_rows

    def set_row_values(self, row_index: int, values: List) -> None:
        """
        Set values for widgets in a specific row.
        
        Args:
            row_index: The index of the row to update
            values: List of values to set, in the same order as widgets from the factory
        """
        if row_index < 0 or row_index >= self.count():
            return
        
        widgets = self._get_row_widgets(row_index)
        for widget, value in zip(widgets, values):
            self._set_widget_value(widget, value)

    def from_list(self, data: List[List]) -> None:
        """
        Populate the list with data from a list of lists.
        Clears existing rows and creates new ones with the provided values.
        
        Args:
            data: List of lists, where each inner list contains values for one row
            
        Example:
            data = [
                ["Text 1", "Option A", 10],
                ["Text 2", "Option B", 20],
                ["Text 3", "Option C", 30]
            ]
            dynamic_list.from_list(data)
        """
        # Clear existing rows
        self.clear()
        
        # Add rows with data
        for row_values in data:
            self.addRow()
            self.set_row_values(self.count() - 1, row_values)
