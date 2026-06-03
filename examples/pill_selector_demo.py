"""Run a small PillSelector demo."""

from __future__ import annotations

import sys

from PyQt6 import QtWidgets

from pyqt_widget_kit import PillSelector


def main() -> int:
    app = QtWidgets.QApplication(sys.argv)
    selector = PillSelector()
    selector.setWindowTitle("Pill Selector Demo")
    selector.set_pills(["Python", "Qt", "PyQt6", "Settings", "Widgets"])
    selector.set_selection_mode("multi")
    selector.selectionChanged.connect(print)
    selector.resize(360, 120)
    selector.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
