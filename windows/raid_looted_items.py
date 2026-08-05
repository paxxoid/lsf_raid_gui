import json
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QFile, Qt, QDate
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import (
    QLineEdit,
    QTextEdit,
    QLabel,
    QComboBox,
    QPushButton,
    QTableWidget, 
    QCompleter,
    QTableWidgetItem,
    QDateEdit,
    QCheckBox,
    QSpinBox, QMessageBox
)

from helpers.app_state import AppState


class RadioLootedItemsWindow:
    def __init__(self,  yaml_data, logger, app_state, api_client, parent=None,):
        self.window = self._load_window(parent)
        self.yaml_data = yaml_data
        self.logger = logger
        self.app_state = app_state
        self.api_client = api_client

        self._setup_widget_references()    
        self._connect_signals()    

    def _setup_widget_references(self):    
        pass

    def _connect_signals(self):
        pass

    def _load_window(self, parent=None):
        ui_path = Path(__file__).with_name(
            "raid_looted_items.ui"
        )

        loader = QUiLoader()
        ui_file = QFile(str(ui_path))

        if not ui_file.open(QFile.OpenModeFlag.ReadOnly):
            raise RuntimeError(
                f"Could not open UI file: {ui_path}"
            )

        window = loader.load(ui_file, parent)
        ui_file.close()

        if window is None:
            raise RuntimeError(
                "Failed to load raid looted items UI"
            )

        # Completely destroy the window when closed.
        window.setAttribute(
            Qt.WidgetAttribute.WA_DeleteOnClose,
            True,
        )

        return window        




    def show(self):
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()    



