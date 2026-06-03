from __future__ import annotations

from PyQt6 import QtWidgets
from PyQt6.QtCore import Qt


class HorizontalSlider(QtWidgets.QSlider):

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # Make horizontal by default
        if 'orientation' in kwargs:
            self.setOrientation(kwargs['orientation'])
        else:
            self.setOrientation(Qt.Orientation.Horizontal)
            self.setTickPosition(QtWidgets.QSlider.TickPosition.NoTicks)
        self.setTracking(True) # Show value when sliding
