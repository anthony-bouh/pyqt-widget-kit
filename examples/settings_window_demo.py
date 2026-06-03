"""Run a small SettingsWindow demo."""

from __future__ import annotations

import sys

from PyQt6 import QtWidgets

from pyqt_widget_kit.settings import SettingsWindow


class DemoSettingsWindow(SettingsWindow):
    title = "Settings Demo"
    show_tree = True

    def __init__(self) -> None:
        super().__init__()
        self.add_text(key="general.name", title="Name", value="Example", section="General")
        self.add_bool(key="general.enabled", title="Enabled", value=True, section="General")
        self.add_int(key="export.count", title="Count", value=10, minimum=1, section="Export")


def main() -> int:
    app = QtWidgets.QApplication(sys.argv)
    window = DemoSettingsWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
