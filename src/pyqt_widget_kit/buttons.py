from __future__ import annotations

from PyQt6 import QtCore, QtWidgets
from PyQt6.QtCore import QSize
from PyQt6.QtGui import QIcon

from .resources import resource_path

DEFAULT_ICON_BUTTON_SIZE = 22
DEFAULT_ICON_SIZE = 14


class IconButton(QtWidgets.QPushButton):
    
    def __init__(
        self,
        icon: str,
        tooltip: str = "",
        *args,
        button_size: int | None = DEFAULT_ICON_BUTTON_SIZE,
        icon_size: int = DEFAULT_ICON_SIZE,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.setIcon(QIcon(resource_path(icon)))
        self.setIconSize(QSize(icon_size, icon_size))
        if button_size is not None:
            self.setFixedSize(button_size, button_size)
        if tooltip:
            self.setToolTip(tooltip)
     
     
class IconMenuButton(IconButton):
    
    def __init__(self, menu : QtWidgets.QMenu, tooltip:str='', *args, **kwargs) -> None:
        super().__init__(icon='ico/burger.png', tooltip=tooltip, *args, **kwargs)
        self.setMenu(menu)  # Placeholder for menu assignment    


class UpDownButton(IconButton):
    """A toggle button that switches between up and down states with corresponding icons and tooltips."""
    switch = QtCore.pyqtSignal(bool)  # Emitted with True for down, False for up
    
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(icon='ico/up.png', tooltip='Up', *args, **kwargs)
        self.setCheckable(True)
        self.setChecked(False)
        self.toggled.connect(self._on_toggled)
        
    def _on_toggled(self, checked: bool) -> None:
        self.setIcon(QIcon(resource_path('ico/up.png' if checked else 'ico/down.png')))
        self.setToolTip('Down' if checked else 'Up')
        self.switch.emit(checked)


class RightLeftButton(IconButton):
    """A toggle button that switches between right and left states with corresponding icons and tooltips."""
    switch = QtCore.pyqtSignal(bool)  # Emitted with True for left, False for right

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(icon='ico/right.png', tooltip='Right', *args, **kwargs)
        self.setCheckable(True)
        self.setChecked(False)
        self.toggled.connect(self._on_toggled)

    def _on_toggled(self, checked: bool) -> None:
        self.setIcon(QIcon(resource_path('ico/left.png' if checked else 'ico/right.png')))
        self.setToolTip('Left' if checked else 'Right')
        self.switch.emit(checked)
