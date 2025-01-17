"""
datenstrukturen und fenster für anschlussmatrix


"""

import logging
from typing import Any, Dict, Generator, Iterable, List, Mapping, Optional, Set, Tuple, Type, Union

from PyQt5 import QtCore, QtWidgets
from PyQt5.QtCore import pyqtSlot

from stskit.zugschema import Zugschema, ZugschemaBearbeitungModell
from stskit.anlage import Anlage
from stskit.zentrale import DatenZentrale

from stskit.qt.ui_einstellungen import Ui_EinstellungenWindow

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class EinstellungenWindow(QtWidgets.QMainWindow):

    def __init__(self, zentrale: DatenZentrale):
        super().__init__()

        self.zentrale = zentrale

        self.in_update = True
        self.ui = Ui_EinstellungenWindow()
        self.ui.setupUi(self)

        # not implemented yet
        self.ui.tab_widget.removeTab(2)
        self.ui.tab_widget.removeTab(1)
        self.ui.tab_widget.removeTab(0)

        self.setWindowTitle(f"Einstellungen {self.anlage.anlage.name}")

        self.zugschema = Zugschema()
        self.zugschema.load_config(self.anlage.zugschema.name)
        self.zugschema_namen_nach_titel = {titel: name for name, titel in Zugschema.schematitel.items()}
        self.zugschema_modell = ZugschemaBearbeitungModell(None, zugschema=self.zugschema)
        self.ui.zugschema_details_table.setModel(self.zugschema_modell)
        self.ui.zugschema_name_combo.currentIndexChanged.connect(self.zugschema_changed)

        self.update_widgets()
        self.in_update = False

    @property
    def anlage(self) -> Anlage:
        return self.zentrale.anlage

    def update_widgets(self):
        self.in_update = True

        schemas = sorted(self.zugschema_namen_nach_titel.keys())
        self.ui.zugschema_name_combo.clear()
        self.ui.zugschema_name_combo.addItems(schemas)
        self.ui.zugschema_name_combo.setCurrentText(self.zugschema.titel)

        self.in_update = False

        self.ui.zugschema_details_table.resizeColumnsToContents()
        self.ui.zugschema_details_table.resizeRowsToContents()

    @pyqtSlot()
    def zugschema_changed(self):
        if self.in_update:
            return

        titel = self.ui.zugschema_name_combo.currentText()
        try:
            name = self.zugschema_namen_nach_titel[titel]
        except KeyError:
            return

        changed = name != self.zugschema.name

        if changed:
            self.zugschema.load_config(name)
            self.zugschema_modell.update()
            self.ui.zugschema_details_table.resizeColumnsToContents()
            self.ui.zugschema_details_table.resizeRowsToContents()

    @pyqtSlot()
    def accept(self):
        self.anlage.zugschema.load_config(self.zugschema.name)
        self.close()

    @pyqtSlot()
    def reject(self):
        self.zugschema.load_config(self.anlage.zugschema.name)
        self.zugschema_modell.update()
        self.close()
