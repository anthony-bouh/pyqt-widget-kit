from __future__ import annotations

from PyQt6 import QtWidgets
from PyQt6.QtCore import pyqtSignal

from .buttons import DEFAULT_ICON_BUTTON_SIZE, IconButton
from .resources import resource_path

COMPACT_CONTROL_HEIGHT = DEFAULT_ICON_BUTTON_SIZE


class DirectoryLineEdit(QtWidgets.QFrame):
    
    textChanged = pyqtSignal(str)

    def __init__(self, parent: QtWidgets.QWidget | None = None, text: str = "") -> None:
        super().__init__(parent)
        
        self.setFixedHeight(COMPACT_CONTROL_HEIGHT)
        
        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(2, 0, 2, 0)
        layout.setSpacing(3)
        self.setLayout(layout)
        
        self._line_edit = QtWidgets.QLineEdit(text)
        self._line_edit.setFixedHeight(COMPACT_CONTROL_HEIGHT)
        self._line_edit.setReadOnly(True)
        layout.addWidget(self._line_edit)
        
        self._browse_button = IconButton(icon=resource_path('ico/folder.png'), tooltip='Browse for directory')
        self._browse_button.clicked.connect(self._on_browse_clicked)
        layout.addWidget(self._browse_button)
        
        self._clear_button = IconButton(icon=resource_path('ico/cross.png'), tooltip='Clear directory')
        self._clear_button.clicked.connect(lambda: self._line_edit.setText(''))
        layout.addWidget(self._clear_button)
        
        self._line_edit.textChanged.connect(self.textChanged)
    
    def _on_browse_clicked(self) -> None:
        import os
        directory = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Directory", os.getcwd())
        if directory:
            self._line_edit.setText(directory)
    
    def setText(self, text: str) -> None:
        self._line_edit.setText(text)
        
    def text(self) -> str:
        return self._line_edit.text()
