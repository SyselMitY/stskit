import matplotlib as mpl
import numpy as np
import sys
import trio
import qtrio
from typing import Any, Dict, List, Optional, Set, Union

from PyQt5 import QtCore, QtWidgets, uic, QtGui

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure

from stsplugin import PluginClient, TaskDone
from database import StsConfig
from auswertung import StsAuswertung
from stsobj import time_to_minutes, Ereignis

mpl.use('Qt5Agg')


def hour_minutes_formatter(x: Union[int, float], pos: Any) -> str:
    # return "{0:02}:{1:02}".format(int(x) // 60, int(x) % 60)
    return f"{int(x) // 60:02}:{int(x) % 60:02}"


class MainWindow(QtWidgets.QMainWindow):

    def __init__(self):
        super().__init__()
        self.debug: bool = True
        self.closed = trio.Event()
        self.client: Optional[PluginClient] = None
        self.config: Optional[StsConfig] = None
        self.config_path = "zugtabelle.json"
        self.auswertung: Optional[StsAuswertung] = None

        self._main = QtWidgets.QWidget()
        self.setCentralWidget(self._main)
        layout = QtWidgets.QVBoxLayout(self._main)

        einfahrten_canvas = FigureCanvas(Figure(figsize=(5, 3)))
        layout.addWidget(einfahrten_canvas)
        self._einfahrten_ax = einfahrten_canvas.figure.subplots()
        self._bars_ein = None
        self._labels_ein = []

        self.enable_update = True

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """Detect close events and emit the ``closed`` signal."""

        super().closeEvent(event)

        if event.isAccepted():
            try:
                self.config.save(self.config_path)
            except (AttributeError, OSError):
                pass

            self.auswertung.fahrzeiten.report()

            self.enable_update = False
            self.closed.set()

    async def update_loop(self):
        await self.client.registered.wait()
        while self.enable_update:
            await self.update()
            await trio.sleep(60)

    async def ereignis_loop(self):
        await self.client.registered.wait()
        async for ereignis in self.client._ereignis_channel_out:
            if self.debug:
                print(ereignis)
            if self.auswertung:
                self.auswertung.ereignis_uebernehmen(ereignis)

    @staticmethod
    def zugtitel(zug) -> str:
        """
        "zugname (verspätung)"

        :return: (str)
        """

        if zug.verspaetung:
            return f"{zug.nummer} ({zug.verspaetung:+})"
        else:
            return f"{zug.nummer}"

    async def update(self):
        await self.get_sts_data()
        for art in Ereignis.arten:
            await self.client.request_ereignis(art, self.client.zugliste.keys())

        if not self.config:
            self.config = StsConfig(self.client.anlageninfo)
            try:
                self.config.load(self.config_path)
            except (OSError, ValueError):
                pass
            if self.config.auto:
                self.config.auto_config(self.client)

        if self.auswertung:
            self.auswertung.zuege_uebernehmen(self.client.zugliste.values())
        else:
            self.auswertung = StsAuswertung(self.config)

        if self._bars_ein is not None:
            self._bars_ein.remove()
        for label in self._labels_ein:
            label.remove()

        kwargs = dict()
        kwargs['align'] = 'center'
        kwargs['alpha'] = 0.5
        # kwargs['color'] = 'red'
        kwargs['edgecolor'] = 'black'
        kwargs['linewidth'] = 1
        kwargs['width'] = 1.0

        try:
            x_labels_pos, x_labels, x_pos, y_bot, y_hgt, bar_labels, colors = self.build_bars(
                self.client.wege_nach_typ[6])
        except KeyError:
            return None

        self._einfahrten_ax.set_title('einfahrten')
        self._einfahrten_ax.set_xticks(x_labels_pos, x_labels, rotation=45, horizontalalignment='right')

        self._einfahrten_ax.yaxis.set_major_formatter(hour_minutes_formatter)
        self._einfahrten_ax.yaxis.set_minor_locator(mpl.ticker.MultipleLocator(1))
        self._einfahrten_ax.yaxis.set_major_locator(mpl.ticker.MultipleLocator(10))
        self._einfahrten_ax.yaxis.grid(True, which='major')
        # ymin = min(y_bot)
        ymin = time_to_minutes(self.client.calc_simzeit())
        self._einfahrten_ax.set_ylim(bottom=ymin + 30, top=ymin, auto=False)

        self._bars_ein = self._einfahrten_ax.bar(x_pos, y_hgt, bottom=y_bot, data=None, color=colors, **kwargs)
        # fontsize: float or {'xx-small', 'x-small', 'small', 'medium', 'large', 'x-large', 'xx-large'}
        # fontstretch: {'ultra-condensed', 'extra-condensed', 'condensed', 'semi-condensed', 'normal'}
        # fontstyle: {'normal', 'italic', 'oblique'}
        # fontweight: {'normal', 'semibold', 'bold', 'heavy', 'extra bold', 'black'}
        self._labels_ein = self._einfahrten_ax.bar_label(self._bars_ein, labels=bar_labels, label_type='center',
                                                         fontstretch='condensed')

        # Trigger the canvas to update and redraw.
        self._einfahrten_ax.figure.canvas.draw()

    def build_bars(self, knoten_liste):
        x_labels = set()
        slots = list()

        for knoten in knoten_liste:

            gruppenname = self.config.suche_gleisgruppe(knoten.name, self.config.einfahrtsgruppen)
            if not gruppenname:
                continue

            for zug in knoten.zuege:
                if not zug.sichtbar:
                    try:
                        zeile = zug.fahrplan[0]
                        ankunft = time_to_minutes(zeile.an) + zug.verspaetung
                        korrektur = self.auswertung.fahrzeiten.get_fahrzeit(zug.von, zeile.gleis) / 60
                        if not np.isnan(korrektur):
                            ankunft -= round(korrektur)
                        aufenthalt = 1
                        slot = {'zug': zug, 'gruppe': gruppenname, 'zeit': ankunft, 'dauer': aufenthalt}
                    except (AttributeError, IndexError):
                        pass
                    else:
                        x_labels.add(gruppenname)
                        slots.append(slot)

        x_labels = sorted(x_labels)
        x_labels_pos = list(range(len(x_labels)))

        # konfliktbehandlung
        slots.sort(key=lambda s: s['zeit'])
        frei = {gruppe: 0 for gruppe in x_labels}
        letzter_slot = {gruppe: None for gruppe in x_labels}
        for slot in slots:
            slot['konflikt'] = frei[slot['gruppe']] > slot['zeit']
            if slot['konflikt'] and letzter_slot[slot['gruppe']] is not None:
                letzter_slot[slot['gruppe']]['konflikt'] = True
            slot['zeit'] = max(frei[slot['gruppe']], slot['zeit'])
            frei[slot['gruppe']] = slot['zeit'] + slot['dauer']
            letzter_slot[slot['gruppe']] = slot

        x_pos = np.asarray([x_labels.index(slot['gruppe']) for slot in slots])
        y_bot = np.asarray([slot['zeit'] for slot in slots])
        y_hgt = np.asarray([slot['dauer'] for slot in slots])
        labels = [f"{self.zugtitel(slot['zug'])}" for slot in slots]

        # farben = {g: mpl.colors.TABLEAU_COLORS[i % len(mpl.colors.TABLEAU_COLORS)]
        #           for i, g in enumerate(self.client.zuggattungen)}
        # colors = [farben[b[5]] for b in bars]
        farben = [k for k in mpl.colors.TABLEAU_COLORS]
        # colors = [farben[i % len(farben)] for i in range(len(bars))]

        # colors = [farben[slot['zug'].nummer // 10000] for slot in slots]
        def farbe(sl):
            if sl['konflikt']:
                return 'r'
            else:
                return farben[sl['zug'].nummer // 10000]
        colors = [farbe(slot) for slot in slots]

        return x_labels_pos, x_labels, x_pos, y_bot, y_hgt, labels, colors

    async def get_sts_data(self, alles=False):
        if alles or not self.client.anlageninfo:
            await self.client.request_anlageninfo()
        if alles or not self.client.bahnsteigliste:
            await self.client.request_bahnsteigliste()
        if alles or not self.client.wege:
            await self.client.request_wege()

        await self.client.request_zugliste()
        await self.client.request_zugdetails()
        await self.client.request_zugfahrplan()

        self.client.update_bahnsteig_zuege()
        self.client.update_wege_zuege()


async def main():
    window = MainWindow()

    client = PluginClient(name='zugtabelle', autor='bummler', version='0.1', text='zugtabellen')
    await client.connect()
    window.client = client

    try:
        async with client._stream:
            async with trio.open_nursery() as nursery:
                await nursery.start(client._receiver)
                await client.register()
                await client.request_simzeit()
                await client.request_anlageninfo()
                nursery.start_soon(window.update_loop)
                nursery.start_soon(window.ereignis_loop)
                window.show()
                await window.closed.wait()
                raise TaskDone()

    except KeyboardInterrupt:
        pass
    except TaskDone:
        pass


if __name__ == "__main__":
    qtrio.run(main)
