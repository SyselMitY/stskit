import datetime
import logging
import numpy as np
from typing import Any, Callable, Dict, Generator, Iterable, List, Mapping, NamedTuple, Optional, Set, Tuple, Union
import weakref

import networkx as nx
import trio

from stsobj import ZugDetails, FahrplanZeile, Ereignis
from stsobj import time_to_minutes, time_to_seconds, minutes_to_time, seconds_to_time
from stsplugin import PluginClient, TaskDone
from auswertung import Auswertung


logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


class ZugZielNode(NamedTuple):
    typ: str
    zid: int
    plangleis: str


class VerspaetungsKorrektur:
    """
    basisklasse für die anpassung der verspätungszeit eines fahrplanziels

    eine VerspaetungsKorrektur-klasse besteht im wesentlichen aus der anwenden-methode.
    diese berechnet für das gegebene ziel die abfahrtsverspätung aus der ankunftsverspätung
    und ggf. weiteren ziel- bzw. zugdaten.

    über das _planung-attribut hat die klasse zugriff auf die ganze zugliste.
    sie darf jedoch nur das angegebene ziel sowie allfällige verknüpfte züge direkt ändern.

    wenn ein fahrplanziel abgearbeitet wurde, wird statt `anwenden` die `weiterleiten`-methode aufgerufen,
    um die verspätungskorrektur von folgezügen durchzuführen.
    """
    def __init__(self, planung: 'Planung'):
        super().__init__()
        self._planung = planung

    def anwenden(self, zug: 'ZugDetailsPlanung', ziel: 'ZugZielPlanung'):
        """
        verspätungskorrektur anwenden

        :param zug:
        :param ziel:
        :return:
        """

        ziel.verspaetung_ab = ziel.verspaetung_an

    def weiterleiten(self, zug: 'ZugDetailsPlanung', ziel: 'ZugZielPlanung'):
        """
        verspätungskorrektur von folgezügen aufrufen wenn nötig

        :param zug:
        :param ziel:
        :return:
        """
        pass


class FesteVerspaetung(VerspaetungsKorrektur):
    """
    verspätung auf einen festen wert setzen.

    kann bei vorzeitiger abfahrt auch negativ sein.

    diese klasse ist für manuelle eingriffe des fahrdienstleiters gedacht.
    """

    def __init__(self, planung: 'Planung'):
        super().__init__(planung)
        self.verspaetung: int = 0

    def __str__(self):
        return f"Fix({self.verspaetung})"

    def anwenden(self, zug: 'ZugDetailsPlanung', ziel: 'ZugZielPlanung'):
        ziel.verspaetung_ab = self.verspaetung


class Signalhalt(FesteVerspaetung):
    """
    verspätung durch signalhalt

    diese klasse wird in der verarbeitung des Abfahrt-ereignisses eingesetzt,
    wenn der zug an einem bahnsteig steht, auf ein offenes signal wartet und dadurch verspätet wird.
    die wirkung auf den fahrplan ist dieselbe wie von FesteVerspaetung.
    der andere name und objekt-string dient der unterscheidung.
    """
    def __str__(self):
        return f"Signal({self.verspaetung})"


class Einfahrtszeit(VerspaetungsKorrektur):
    """
    verspätete einfahrt

    die vom simulator gemeldete einfahrtszeit (inkl. verspätung) ist manchmal kleiner als die aktuelle sim-zeit.
    in diesem fall erhöht diese korrektur die verspätung, so dass die einfahrtszeit der aktuellen uhrzeit entspricht.
    """

    def __str__(self):
        return f"Einfahrt"

    def anwenden(self, zug: 'ZugDetailsPlanung', ziel: 'ZugZielPlanung'):
        try:
            plan_an = time_to_minutes(ziel.an)
        except AttributeError:
            logger.debug(f"zug {zug.name} hat keine ankunft in zeile {ziel}")
            ziel.verspaetung_ab = ziel.verspaetung_an
            return

        try:
            plan_ab = time_to_minutes(ziel.ab)
        except AttributeError:
            plan_ab = plan_an

        ankunft = plan_an + ziel.verspaetung_an
        abfahrt = max(ankunft, self._planung.simzeit_minuten)
        ziel.verspaetung_ab = abfahrt - plan_ab


class PlanmaessigeAbfahrt(VerspaetungsKorrektur):
    """
    planmässige abfahrt oder verspätung aufholen wenn möglich

    dies ist die normale abfertigung, soweit kein anderer zug involviert ist.
    die verspätung wird soweit möglich reduziert, ohne die mindestaufenthaltsdauer zu unterschreiten.
    """

    def __str__(self):
        return f"Plan"

    def anwenden(self, zug: 'ZugDetailsPlanung', ziel: 'ZugZielPlanung'):
        try:
            plan_an = time_to_minutes(ziel.an)
        except AttributeError:
            logger.debug(f"zug {zug.name} hat keine ankunft in zeile {ziel}")
            ziel.verspaetung_ab = ziel.verspaetung_an
            return

        try:
            plan_ab = time_to_minutes(ziel.ab)
        except AttributeError:
            plan_ab = plan_an + ziel.mindestaufenthalt

        ankunft = plan_an + ziel.verspaetung_an
        aufenthalt = max(plan_ab - ankunft, ziel.mindestaufenthalt)
        abfahrt = ankunft + aufenthalt
        ziel.verspaetung_ab = abfahrt - plan_ab


class AnkunftAbwarten(VerspaetungsKorrektur):
    """
    wartet auf einen anderen zug.

    die abfahrtsverspätung des von dieser korrektur kontrollierten fahrplanziels
    richtet sich nach der effektiven ankunftszeit des anderen zuges
    oder der eigenen verspätung.

    diese korrektur wird von der auto-korrektur bei ersatzzügen, kupplungen und flügelungen eingesetzt,
    kann aber auch in der fdl_korrektur verwendet werden, um abhängigkeiten zu definieren.

    attribute
    --------

    - ursprung: fahrplanziel des abzuwartenden zuges
    - wartezeit: wartezeit nach ankunft des abzuwartenden zuges
    """

    def __init__(self, planung: 'Planung'):
        super().__init__(planung)
        self.ursprung: Optional[ZugZielPlanung] = None
        self.wartezeit: int = 0

    def __str__(self):
        return f"Ankunft({self.ursprung.zug.name}, {self.wartezeit})"

    def anwenden(self, zug: 'ZugDetailsPlanung', ziel: 'ZugZielPlanung'):
        try:
            plan_an = time_to_minutes(ziel.an)
        except AttributeError:
            plan_an = None

        try:
            plan_ab = time_to_minutes(ziel.ab)
        except AttributeError:
            plan_ab = plan_an + ziel.mindestaufenthalt

        if plan_an is None:
            plan_an = plan_ab

        ankunft = plan_an + ziel.verspaetung_an
        aufenthalt = max(plan_ab - ankunft, ziel.mindestaufenthalt)
        anschluss_an = time_to_minutes(self.ursprung.an) + self.ursprung.verspaetung_an
        anschluss_ab = anschluss_an + self.wartezeit
        abfahrt = max(ankunft + aufenthalt, anschluss_ab)
        ziel.verspaetung_ab = abfahrt - plan_ab


class AbfahrtAbwarten(VerspaetungsKorrektur):
    """
    wartet, bis ein anderer zug abgefahren ist.

    die abfahrtsverspätung des von dieser korrektur kontrollierten fahrplanziels
    richtet sich nach der abfahrtszeit des anderen zuges und der eigenen verspätung.

    diese korrektur wird von der auto-korrektur bei flügelungen eingesetzt,
    kann aber auch in der fdl_korrektur verwendet werden, um abhängigkeiten zu definieren.

    attribute
    --------

    - ursprung: fahrplanziel des abzuwartenden zuges
    - wartezeit: wartezeit nach ankunft des abzuwartenden zuges
    """

    def __init__(self, planung: 'Planung'):
        super().__init__(planung)
        self.ursprung: Optional[ZugZielPlanung] = None
        self.wartezeit: int = 0

    def __str__(self):
        return f"Abfahrt({self.ursprung.zug.name}, {self.wartezeit})"

    def anwenden(self, zug: 'ZugDetailsPlanung', ziel: 'ZugZielPlanung'):
        try:
            plan_an = time_to_minutes(ziel.an)
        except AttributeError:
            plan_an = None

        try:
            plan_ab = time_to_minutes(ziel.ab)
        except AttributeError:
            plan_ab = plan_an + ziel.mindestaufenthalt

        if plan_an is None:
            plan_an = plan_ab

        ankunft = plan_an + ziel.verspaetung_an
        aufenthalt = max(plan_ab - ankunft, ziel.mindestaufenthalt)
        anschluss_ab = time_to_minutes(self.ursprung.ab) + self.ursprung.verspaetung_ab
        anschluss_ab = anschluss_ab + self.wartezeit
        abfahrt = max(ankunft + aufenthalt, anschluss_ab)
        ziel.verspaetung_ab = abfahrt - plan_ab


class Ersatzzug(VerspaetungsKorrektur):
    """
    abfahrt frühestens wenn nummernwechsel abgeschlossen ist

    das erste fahrplanziel des ersatzzuges muss it einer AnschlussAbwarten-korrektur markiert sein.
    """

    def __str__(self):
        return f"Ersatz"

    def anwenden(self, zug: 'ZugDetailsPlanung', ziel: 'ZugZielPlanung'):
        try:
            plan_an = time_to_minutes(ziel.an)
        except AttributeError:
            logger.debug(f"zug {zug.name} hat keine ankunft in zeile {ziel}")
            ziel.verspaetung_ab = ziel.verspaetung_an
            return

        try:
            plan_ab = time_to_minutes(ziel.ersatzzug.fahrplan[0].an)
        except (AttributeError, IndexError):
            try:
                plan_ab = time_to_minutes(ziel.ab)
            except AttributeError:
                plan_ab = plan_an + ziel.mindestaufenthalt

        ankunft = plan_an + ziel.verspaetung_an
        aufenthalt = max(plan_ab - ankunft, ziel.mindestaufenthalt)
        abfahrt = ankunft + aufenthalt
        ziel.verspaetung_ab = abfahrt - plan_ab
        ziel.ab = minutes_to_time(abfahrt - ziel.verspaetung_ab)

        if ziel.ersatzzug:
            ziel.ersatzzug.verspaetung = ziel.verspaetung_ab
            self._planung.zugverspaetung_korrigieren(ziel.ersatzzug)

    def weiterleiten(self, zug: 'ZugDetailsPlanung', ziel: 'ZugZielPlanung'):
        if ziel.ersatzzug:
            self._planung.zugverspaetung_korrigieren(ziel.ersatzzug)


class Kupplung(VerspaetungsKorrektur):
    """
    zwei züge kuppeln

    gekuppelter zug kann erst abfahren, wenn beide züge angekommen sind.

    bemerkung: der zug mit dem kuppel-flag verschwindet. der verlinkte zug fährt weiter.
    """

    def __str__(self):
        return f"Kupplung"

    def anwenden(self, zug: 'ZugDetailsPlanung', ziel: 'ZugZielPlanung'):
        try:
            plan_an = time_to_minutes(ziel.an)
        except AttributeError:
            logger.warning(f"zug {zug} hat keine ankunft in zeile {ziel}")
            ziel.verspaetung_ab = ziel.verspaetung_an
            return

        try:
            plan_ab = time_to_minutes(ziel.ab)
        except (AttributeError, IndexError):
            plan_ab = plan_an + ziel.mindestaufenthalt

        # zuerst die verspaetung des kuppelnden zuges berechnen
        try:
            self._planung.zugverspaetung_korrigieren(ziel.kuppelzug)
            kuppel_index = ziel.kuppelzug.find_fahrplan_index(plan=ziel.plan)
            kuppel_ziel = ziel.kuppelzug.fahrplan[kuppel_index]
            kuppel_verspaetung = kuppel_ziel.verspaetung_an
            kuppel_an = time_to_minutes(kuppel_ziel.an) + kuppel_verspaetung
        except (AttributeError, IndexError):
            kuppel_an = 0

        while abs(kuppel_an - (plan_an + ziel.verspaetung_an)) < 2:
            ziel.verspaetung_an += 1

        ankunft = plan_an + ziel.verspaetung_an
        aufenthalt = max(plan_ab - ankunft, ziel.mindestaufenthalt)
        abfahrt = max(ankunft + aufenthalt, kuppel_an)
        ziel.verspaetung_ab = abfahrt - plan_ab

        if ziel.kuppelzug:
            self._planung.zugverspaetung_korrigieren(ziel.kuppelzug)

    def weiterleiten(self, zug: 'ZugDetailsPlanung', ziel: 'ZugZielPlanung'):
        if ziel.kuppelzug:
            self._planung.zugverspaetung_korrigieren(ziel.kuppelzug)


class Fluegelung(VerspaetungsKorrektur):
    def __str__(self):
        return f"Flügelung"

    def anwenden(self, zug: 'ZugDetailsPlanung', ziel: 'ZugZielPlanung'):
        try:
            plan_an = time_to_minutes(ziel.an)
        except AttributeError:
            logger.warning(f"zug {zug} hat keine ankunft in zeile {ziel}")
            ziel.verspaetung_ab = ziel.verspaetung_an
            return

        try:
            plan_ab = time_to_minutes(ziel.ab)
        except (AttributeError, IndexError):
            plan_ab = plan_an + ziel.mindestaufenthalt

        ankunft = plan_an + ziel.verspaetung_an
        aufenthalt = max(plan_ab - ankunft, ziel.mindestaufenthalt)
        abfahrt = ankunft + aufenthalt
        ziel.verspaetung_ab = abfahrt - plan_ab

        if ziel.fluegelzug:
            ziel.fluegelzug.verspaetung = ziel.verspaetung_an
            ziel.fluegelzug.fahrplan[0].verspaetung_an = ziel.verspaetung_an
            self._planung.zugverspaetung_korrigieren(ziel.fluegelzug)

    def weiterleiten(self, zug: 'ZugDetailsPlanung', ziel: 'ZugZielPlanung'):
        if ziel.fluegelzug:
            self._planung.zugverspaetung_korrigieren(ziel.fluegelzug)


class ZugDetailsPlanung(ZugDetails):
    """
    ZugDetails für das planungsmodul

    dies ist eine unterklasse von ZugDetails, wie sie vom planungsmodul verwendet wird.
    im planungsmodul haben einige attribute eine geänderte bedeutung.
    insbesondere bleibt der fahrplan vollständig (abgefahrene ziele werden nicht gelöscht)
    und enthält auch die ein- und ausfahrten als erste/letzte zeile
    (ausser der zug beginnt oder endet im stellwerk).

    wenn der zug neu angelegt wird, übernimmt die assign_zug_details-methode die daten vom PluginClient.
    die update_zug_details-methode aktualisert die veränderlichen attribute, z.b. gleis, verspätung etc.
    """
    def __init__(self):
        super().__init__()
        self.ausgefahren: bool = False
        self.folgezuege_aufgeloest: bool = False
        self.korrekturen_definiert: bool = False

    @property
    def einfahrtszeit(self) -> datetime.time:
        """
        planmässige einfahrtszeit (ohne verspätung)

        dies entspricht der abfahrtszeit des ersten fahrplaneintrags (einfahrt).

        :return: uhrzeit als datetime.time
        :raise IndexError, wenn der fahrplan keinen eintrag enthält.
        """
        return self.fahrplan[0].ab

    @property
    def ausfahrtszeit(self) -> datetime.time:
        """
        planmässige ausfahrtszeit (ohne verspätung)

        dies enstspricht der ankunftszeit des letzten fahrplaneintrags (ausfahrt).

        :return: uhrzeit als datetime.time
        :raise IndexError, wenn der fahrplan keinen eintrag enthält.
        """
        return self.fahrplan[-1].an

    def route(self, plan: bool = False) -> Iterable[str]:
        """
        route (reihe von stationen) des zuges als generator

        die route ist eine liste von stationen (gleisen, ein- und ausfahrt) in der reihenfolge des fahrplans.
        ein- und ausfahrten können bei ersatzzügen o.ä. fehlen.
        durchfahrtsgleise sind auch enthalten.

        die methode liefert das gleiche ergebnis wie die überschriebene methode.
        aber da in der planung die ein- und ausfahrten im fahrplan enthalten sind,
        ist die implementierung etwas einfacher.

        :param plan: plangleise statt effektive gleise melden
        :return: generator
        """
        for fpz in self.fahrplan:
            if plan:
                yield fpz.plan
            else:
                yield fpz.gleis

    def assign_zug_details(self, zug: ZugDetails):
        """
        objekt mit stammdaten vom PluginClient initialisieren.

        unterschiede zum original-ZugDetails:
        - ein- und ausfahrtsgleise werden als separate fahrplanzeile am anfang bzw. ende der liste eingefügt
          und mit den attributen einfahrt bzw. ausfahrt markiert.
          ankunfts- und abfahrtszeiten werden dem benachbarten fahrplanziel gleichgesetzt.
        - der text 'Gleis', wenn der zug im stellwerk beginnt oder endet, wird aus dem von/nach entfernt.
          das gleis befindet sich bereits im fahrplan, es wird keine zusätzliche ein-/ausfahrt-zeile eingefügt.

        :param zug: original-ZugDetails-objekt vom PluginClient.zugliste.
        :return: None
        """
        self.zid = zug.zid
        self.name = zug.name
        self.von = zug.von.replace("Gleis ", "") if zug.von else ""
        self.nach = zug.nach.replace("Gleis ", "") if zug.nach else ""
        self.hinweistext = zug.hinweistext

        self.fahrplan = []
        if not zug.sichtbar and self.von and not zug.von.startswith("Gleis"):
            ziel = ZugZielPlanung(self)
            ziel.plan = ziel.gleis = self.von
            try:
                ziel.ab = ziel.an = zug.fahrplan[0].an
            except IndexError:
                pass
            ziel.einfahrt = True
            self.fahrplan.append(ziel)
        for zeile in zug.fahrplan:
            ziel = ZugZielPlanung(self)
            ziel.assign_fahrplan_zeile(zeile)
            self.fahrplan.append(ziel)
        if self.nach and not zug.nach.startswith("Gleis"):
            ziel = ZugZielPlanung(self)
            ziel.plan = ziel.gleis = self.nach
            try:
                ziel.ab = ziel.an = zug.fahrplan[-1].ab
            except IndexError:
                pass
            ziel.ausfahrt = True
            self.fahrplan.append(ziel)

        for n, z in enumerate(self.fahrplan):
            z.zielnr = n * 1000

        # zug ist neu in liste und schon im stellwerk -> startaufstellung
        if zug.sichtbar:
            ziel_index = self.find_fahrplan_index(plan=zug.plangleis)
            if ziel_index is None:
                # ziel ist ausfahrt
                ziel_index = -1
            for ziel in self.fahrplan[0:ziel_index]:
                ziel.abgefahren = ziel.angekommen = True
                ziel.verspaetung_ab = ziel.verspaetung_an = zug.verspaetung
            if zug.amgleis:
                ziel = self.fahrplan[ziel_index]
                ziel.angekommen = True
                ziel.verspaetung_an = zug.verspaetung

    def update_zug_details(self, zug: ZugDetails):
        """
        aktualisiert die veränderlichen attribute eines zuges

        die folgenden attribute werden aktualisert, alle anderen bleiben unverändert.
        gleis, plangleis, amgleis, sichtbar, verspaetung, usertext, usertextsender, fahrplanzeile.
        wenn der zug ausfährt, wird das gleis dem nach-attribut gleichgesetzt.

        im fahrplan werden die gleisänderungen aktualisiert.

        anstelle des zuges kann auch ein ereignis übergeben werden.
        Ereignis-objekte entsprechen weitgehend den ZugDetails-objekten,
        enthalten jedoch keinen usertext und keinen fahrplan.

        :param zug: ZugDetails- oder Ereignis-objekt vom PluginClient.
        :return: None
        """

        if zug.gleis:
            self.gleis = zug.gleis
            self.plangleis = zug.plangleis
        else:
            self.gleis = self.plangleis = self.nach

        self.verspaetung = zug.verspaetung
        self.amgleis = zug.amgleis
        self.sichtbar = zug.sichtbar

        if not isinstance(zug, Ereignis):
            self.usertext = zug.usertext
            self.usertextsender = zug.usertextsender

        for zeile in zug.fahrplan:
            ziel = self.find_fahrplanzeile(plan=zeile.plan)
            try:
                ziel.update_fahrplan_zeile(zeile)
            except AttributeError:
                pass

        route = list(self.route(plan=True))
        try:
            self.ziel_index = route.index(zug.plangleis)
        except ValueError:
            # zug faehrt aus
            if not zug.plangleis:
                self.ziel_index = -1

    def find_fahrplan_zielnr(self, zielnr: int) -> 'ZugZielPlanung':
        """
        fahrplaneintrag nach zielnummer suchen

        :param zielnr: gesuchte zielnr
        :return: ZugZielPlanung
        :raise: ValueError, wenn zielnr nicht gefunden wird.
        """

        for ziel in self.fahrplan:
            if ziel.zielnr == zielnr:
                return ziel
        else:
            raise ValueError(f"zielnr {zielnr} nicht gefunden in zug {self.name}")


class ZugZielPlanung(FahrplanZeile):
    """
    fahrplanzeile im planungsmodul

    in ergänzung zum originalen FahrplanZeile objekt, führt diese klasse:
    - nach ziel aufgelöste ankunfts- und abfahrtsverspätung.
    - daten zur verspätungsanpassung.
    - status des fahrplanziels.
      nach ankunft/abfahrt sind die entsprechenden verspätungsangaben effektiv, vorher schätzwerte.

    attribute
    ---------

    - zielnr: definiert die reihenfolge von fahrzielen.
              bei originalen fahrzielen entspricht sie fahrplan-index multipliziert mit 1000.
              bei eingefügten betriebshalten ist sie nicht durch 1000 teilbar.
              die zielnummer wird als schlüssel in der gleisbelegung verwendet.
              sie wird vom ZugDetailsPlanung-objekt gesetzt
              und ändert sich über die lebensdauer des zugobjekts nicht.
    """

    def __init__(self, zug: ZugDetails):
        super().__init__(zug)

        self.zielnr: Optional[int] = None
        self.einfahrt: bool = False
        self.ausfahrt: bool = False
        self.verspaetung_an: int = 0
        self.verspaetung_ab: int = 0
        self.mindestaufenthalt: int = 0
        self.auto_korrektur: Optional[VerspaetungsKorrektur] = None
        self.fdl_korrektur: Optional[VerspaetungsKorrektur] = None
        self.angekommen: Union[bool, datetime.datetime] = False
        self.abgefahren: Union[bool, datetime.datetime] = False

    def __hash__(self) -> int:
        """
        zugziel-hash

        der hash basiert auf den eindeutigen, unveränderlichen attributen zug.zid und plan.

        :return: hash-wert
        """
        return hash((self.zug.zid, self.plan, self.zielnr))

    def __eq__(self, other: 'ZugZielPlanung') -> bool:
        """
        gleichheit von zwei fahrplanzeilen feststellen.

        gleichheit bedeutet: gleicher zug und gleiches plangleis.
        jedes plangleis kommt im sts-fahrplan nur einmal vor.

        :param other: zu vergleichendes FahrplanZeile-objekt
        :return: True, wenn zug und plangleis übereinstimmen, sonst False
        """
        return self.zug.zid == other.zug.zid and self.zielnr == other.zielnr and self.plan == other.plan

    def __str__(self):
        if self.gleis == self.plan:
            return f"Ziel {self.zug.zid}-{self.zielnr}: " \
                   f"Gleis {self.gleis} an {self.an} ab {self.ab} {self.flags}"
        else:
            return f"Ziel {self.zug.zid}-{self.zielnr}: " \
                   f"Gleis {self.gleis} (statt {self.plan}) an {self.an} ab {self.ab} {self.flags}"

    def __repr__(self):
        return f"ZugZielPlanung({self.zug.zid}-{self.zielnr}," \
               f"{self.gleis}, {self.plan}, {self.an}, {self.ab}, {self.flags})"

    def assign_fahrplan_zeile(self, zeile: FahrplanZeile):
        """
        objekt aus fahrplanzeile initialisieren.

        die gemeinsamen attribute werden übernommen.
        folgezüge bleiben leer.

        :param zeile: FahrplanZeile vom PluginClient
        :return: None
        """
        self.gleis = zeile.gleis
        self.plan = zeile.plan
        self.an = zeile.an
        self.ab = zeile.ab
        self.flags = zeile.flags
        self.hinweistext = zeile.hinweistext

        # die nächsten drei attribute werden separat anhand der flags aufgelöst.
        self.ersatzzug = None
        self.fluegelzug = None
        self.kuppelzug = None

    def update_fahrplan_zeile(self, zeile: FahrplanZeile):
        """
        objekt aus fahrplanzeile aktualisieren.

        aktualisiert werden nur:
        - gleis: weil möglicherweise eine gleisänderung vorgenommen wurde.

        alle anderen attribute sind statisch oder werden vom Planung objekt aktualisiert.

        :param zeile: FahrplanZeile vom PluginClient
        :return: None
        """
        self.gleis = zeile.gleis

    @property
    def ankunft_minute(self) -> Optional[int]:
        """
        ankunftszeit inkl. verspätung in minuten

        :return: minuten seit mitternacht oder None, wenn die zeitangabe fehlt.
        """
        try:
            return time_to_minutes(self.an) + self.verspaetung_an
        except AttributeError:
            return None

    @property
    def abfahrt_minute(self) -> Optional[int]:
        """
        abfahrtszeit inkl. verspätung in minuten

        :return: minuten seit mitternacht oder None, wenn die zeitangabe fehlt.
        """
        try:
            return time_to_minutes(self.ab) + self.verspaetung_ab
        except AttributeError:
            return None

    @property
    def verspaetung(self) -> int:
        """
        abfahrtsverspaetung

        dies ist ein alias von verspaetung_ab und sollte in neuem code nicht mehr verwendet werden.

        :return: verspaetung in minuten
        """
        return self.verspaetung_ab

    @property
    def gleistyp(self) -> str:
        if self.einfahrt:
            return 'Einfahrt'
        elif self.ausfahrt:
            return 'Ausfahrt'
        else:
            return 'Gleis'


class Planung:
    """
    zug-planung und disposition

    diese klasse führt einen fahrplan ähnlich wie der PluginClient.
    der fahrplan wird in dieser klasse jedoch vom fahrdienstleiter und vordefinierten algorithmen bearbeitet
    (z.b. für die verspätungsfortpflanzung).

    - die planung erfolgt mittels ZugDetailsPlanung-objekten (entsprechend ZugDetails im PluginClient).
    - züge werden bei ihrem ersten auftreten von den quelldaten übernommen und bleiben in der planung,
      bis sie explizit entfernt werden.
    - bei folgenden quelldatenübernahmen, werden nur noch die zielattribute nachgeführt,
      die fahrplaneingträge bleiben bestehen (im PluginClient werden abgefahrene ziele entfernt).
    - die fahrpläne der züge haben auch einträge zur einfahrt und ausfahrt.

    attribute
    ---------

    zugbaum: der zugbaum ist der primäre speicherort für alle fahrplan-daten.
        der zugbaum ist ein networkx-DiGraph, wobei die nodes zid-nummern sind
        und die edges gerichtete referenzen von stammzügen auf folgezüge.

        das ZugDetailsPlanung-objekt ist, falls vorhanden, im node-attribut obj referenziert.
        das objekt kann fehlen, wenn der fahrplan vom simulator noch nicht übermittelt worden ist.
        edges haben die attribute flag ('E', 'F', 'K') und zielnr (zielnr-attribut im stammzug).

        hinweise:
        - einzelne zugobjekte werden über zugbaum.nodes[zid]['obj'] abgefragt.
          für einen einfachern zugriff steht alternativ das attribut zugliste zur verfügung.
        - dict(zugbaum) liefert einen dict: zid -> {'obj': ZugDetailsPlanung}
        - list(zugbaum) liefert eine liste von zids
        - self.zugbaum.nodes.data(data='obj') liefert einen iterator (zid, ZugDetailsPlanung)

    zugliste: ist ein abgeleitetes objekt und ermöglicht einen kürzeren zugriff auf das zugobjekt.
        der dict ist topologisch sortiert (s. zugsortierung).

    zuege: erstellt einen topologisch sortierten generator von zügen (s. zugsortierung).

    zugbaum_ungerichtet: view auf zugbaum mit ungerichteten kanten.

    zugsortierung: topologisch sortierte liste von zid.
        folgezüge kommen in dieser liste nie vor dem stammzug.

    zugstamm: gibt zu jedem zid den stamm an, d.h. ein set mit allen verknüpften zid.

    auswertung: ...

    simzeit_minuten: ...
    """

    def __init__(self):
        self.zugliste: Dict[int, ZugDetailsPlanung] = dict()
        self.zugbaum = nx.DiGraph()
        self.zugbaum_ungerichtet = nx.Graph()
        self.zugsortierung: List[int] = []
        self.zugstamm: Dict[int, Set[int]] = {}
        self.zielgraph = nx.DiGraph()
        self.zielsortierung: List[Tuple[str, int, str]] = []
        self.zielindex_plan: Dict[Tuple[int, str], Dict[str, ZugZielPlanung]] = {}
        self.auswertung: Optional[Auswertung] = None
        self.simzeit_minuten: int = 0

    def zuege(self) -> Iterable[ZugDetailsPlanung]:
        """
        topologisch sortierter generator von zuegen

        die sortierung garantiert, dass folgezuege hinter ihren stammzuegen gelistet werden.

        :return: iteration von ZugDetailsPlanung-objekten
        """

        for zid in self.zugsortierung:
            try:
                zug = self.zugbaum.nodes[zid]['obj']
                yield zug
            except KeyError:
                pass

    def zuege_uebernehmen(self, zuege: Iterable[ZugDetails]):
        """
        interne zugliste mit sim-daten aktualisieren.

        - neue züge übernehmen
        - bekannte züge aktualisieren
        - ausgefahrene züge markieren
        - links zu folgezügen aktualisieren
        - verspätungsmodell aktualisieren

        :param zuege:
        :return:
        """

        ausgefahrene_zuege = set(self.zugbaum.nodes)

        for zug in zuege:
            try:
                zug_planung = self.zugbaum.nodes[zug.zid]['obj']
            except KeyError:
                # neuer zug
                zug_planung = ZugDetailsPlanung()
                zug_planung.assign_zug_details(zug)
                zug_planung.update_zug_details(zug)
                ausgefahrene_zuege.discard(zug.zid)
            else:
                # bekannter zug
                zug_planung.update_zug_details(zug)
                ausgefahrene_zuege.discard(zug.zid)
            self.zugbaum.add_node(zug.zid, obj=zug_planung)

        for zid in ausgefahrene_zuege:
            try:
                zug = self.zugbaum.nodes[zid]['obj']
            except KeyError:
                pass
            else:
                if zug.sichtbar:
                    zug.sichtbar = zug.amgleis = False
                    zug.gleis = zug.plangleis = ""
                    zug.ausgefahren = True
                    for zeile in zug.fahrplan:
                        zeile.abgefahren = zeile.abgefahren or True

        self._zielgraph_erstellen()
        self._folgezuege_aufloesen()
        self._zugbaum_analysieren()
        self.korrekturen_definieren()

    def _zugbaum_analysieren(self) -> None:
        """
        aktualisiert von zugbaum abgeleitete objekte

        - zugbaum_ungerichtet
        - zugsortierung
        - zugstamm
        - zugliste

        muss jedesmal ausgeführt werden, wenn die zusammensetzung von self.zugbaum verändert wurde.

        für die analyse muss der zugbaum inklusive folgezug-verbindungen komplett sein.
        hierzu sollte die _zielgraph_erstellen-methode verwendet werden.

        :return: None
        """

        self.zugsortierung = list(nx.topological_sort(self.zugbaum))
        self.zugbaum_ungerichtet = self.zugbaum.to_undirected(as_view=True)
        for stamm in nx.connected_components(self.zugbaum_ungerichtet):
            for zid in stamm:
                self.zugstamm[zid] = stamm

        self.zugliste = {zid: data['obj'] for zid in self.zugsortierung
                         if 'obj' in (data := self.zugbaum.nodes[zid])}

    def _folgezuege_aufloesen(self):
        """
        folgezüge aus den zugflags auflösen.

        setzt die ersatzzug/kuppelzug/fluegelzug-attribute gemäss verbindungsangaben im zugbaum.
        die verbindungsangaben werden von _zielgraph_erstellen gesetzt.

        :return: None
        """

        for zid1, zid2, d in self.zugbaum.edges(data=True):
            try:
                zug1: ZugDetailsPlanung = self.zugbaum.nodes[zid1]['obj']
                ziel1: ZugZielPlanung = zug1.find_fahrplan_zielnr(d['zielnr'])
            except KeyError:
                continue
            try:
                zug2: Optional[ZugDetailsPlanung] = self.zugbaum.nodes[zid2]['obj']
            except KeyError:
                zug2 = None

            if d['flag'] == 'E':
                ziel1.ersatzzug = zug2
            elif d['flag'] == 'K':
                ziel1.kuppelzug = zug2
            elif d['flag'] == 'F':
                ziel1.fluegelzug = zug2

    @staticmethod
    def _zugziel_node(ziel: ZugZielPlanung, plangleis: Optional[str] = None, zid: Optional[int] = None,
                      typ: Optional[str] = None) -> ZugZielNode:

        if typ is None:
            if ziel.einfahrt:
                typ = 'E'
            elif ziel.ausfahrt:
                typ = 'A'
            elif ziel.zielnr > int(ziel.zielnr / 1000) * 1000:
                typ = 'B'
            elif ziel.durchfahrt():
                typ = 'D'
            else:
                typ = 'H'

        if plangleis is None:
            plangleis = ziel.plan

        if zid is None:
            zid = ziel.zug.zid

        return ZugZielNode(typ, zid, plangleis)

    def _zielgraph_erstellen(self):
        """
        zielgraph erstellen/aktualisieren

        der zielgraph enthaelt die zielpunkte aller zuege.
        die punkte sind gemaess anordnung im fahrplan sowie planmaessigen und betrieblichen abghaengigkeiten verbunden.
        der zielbaum wird insbesondere verwendet, um eine topologische sortierung der fahrplanziele
        fuer die verspaetungsberechnung zu erstellen.

        der zielbaum muss ein directed acyclic graph sein.
        modifikationen, die zyklen verursachen wuerden, muessen abgewiesen werden.

        node-attribute
        --------------

        obj: ZugZielPlanung-objekt
        zid: zug-id
        nr: zielnr
        plan: plangleis
        typ: zielpunkttyp:
            'H': planmaessiger halt
            'D': durchfahrt
            'E': einfahrt
            'A': ausfahrt
            'B': betriebshalt (vom fdl einfuegter halt)
            'S': signalhalt (ungeplanter halt zwischen zwei zielpunkten)   --- im moment nicht verwendet
        Van: ankunftsverspaetung in minuten
        Vab: abfahrtsverspaetung in minuten

        edge-attribute
        --------------

        typ: verbindungstyp
            'P': planmaessige fahrt
            'E': ersatzzug
            'F': fluegelung
            'K': kupplung
            'R': rangierfahrt (planmaessige fahrt im gleichen bahnhof)   --- von dieser methode nicht erkannt
            'A': ankunft/abfahrt abwarten
            'X': anschluss aufgeben

        :return:
        """

        for zid2, zug in list(self.zugbaum.nodes(data='obj')):
            if zug is None:
                continue

            ziel1 = None
            zzid1 = None

            for ziel2 in zug.fahrplan:
                zzid2 = self._zugziel_node(ziel2)

                try:
                    plan_an = time_to_minutes(ziel2.an)
                except AttributeError:
                    plan_an = None
                try:
                    plan_ab = time_to_minutes(ziel2.ab)
                except AttributeError:
                    plan_ab = plan_an
                if plan_an is None:
                    plan_an = plan_ab

                # t_an, t_ab, v_an, v_ab sind nur defaultwerte!
                self.zielgraph.add_node(zzid2, typ=zzid2[0], obj=ziel2,
                                        zid=ziel2.zug.zid, zielnr=ziel2.zielnr, plan=ziel2.plan,
                                        p_an=plan_an, p_ab=plan_ab,
                                        t_an=plan_an + zug.verspaetung, t_ab=plan_ab + zug.verspaetung,
                                        v_an=zug.verspaetung, v_ab=zug.verspaetung)

                d = weakref.WeakValueDictionary({zzid2[0]: ziel2})
                try:
                    self.zielindex_plan[(zid2, ziel2.plan)].update(d)
                except KeyError:
                    self.zielindex_plan[(zid2, ziel2.plan)] = d

                if ziel1:
                    self.zielgraph.add_edge(zzid1, zzid2, typ='P')
                if zid := ziel2.ersatz_zid():
                    self.zielgraph.add_edge(zzid2, self._zugziel_node(ziel2, zid=zid, typ='H'), typ='E')
                    self.zugbaum.add_edge(zid2, zid, flag='E', zielnr=ziel2.zielnr)
                if zid := ziel2.kuppel_zid():
                    self.zielgraph.add_edge(zzid2, self._zugziel_node(ziel2, zid=zid, typ='H'), typ='K')
                    self.zugbaum.add_edge(zid2, zid, flag='K', zielnr=ziel2.zielnr)
                if zid := ziel2.fluegel_zid():
                    self.zielgraph.add_edge(zzid2, self._zugziel_node(ziel2, zid=zid, typ='H'), typ='F')
                    self.zugbaum.add_edge(zid2, zid, flag='F', zielnr=ziel2.zielnr)
                if ziel2.fdl_korrektur is not None:
                    try:
                        ursprung: ZugZielPlanung = ziel2.fdl_korrektur.ursprung
                        self.zielgraph.add_edge(self._zugziel_node(ursprung), zzid2, typ='A')
                    except AttributeError:
                        pass

                ziel1 = ziel2
                zzid1 = zzid2

        try:
            self.zielsortierung = nx.topological_sort(self.zielgraph)
        except nx.NetworkXUnfeasible:
            logger.error("fehler beim sortieren des zielgraphen")

    def einfahrten_korrigieren(self):
        """
        ein- und ausfahrtszeiten abschätzen.

        die ein- und ausfahrtszeiten werden vom sim nicht vorgegeben.
        wir schätzen sie die einfahrtszeit aus der ankunftszeit des anschliessenden wegpunkts
        und er kürzesten beobachteten fahrzeit zwischen der einfahrt und dem wegpunkt ab.
        die einfahrtszeit wird im ersten fahrplaneintrag eingetragen (an und ab).

        analog wird die ausfahrtszeit im letzten fahrplaneintrag abgeschätzt.

        :return:
        """

        for zug in self.zuege():
            try:
                einfahrt = zug.fahrplan[0]
                ziel1 = zug.fahrplan[1]
            except IndexError:
                pass
            else:
                if einfahrt.einfahrt and einfahrt.gleis and ziel1.gleis:
                    fahrzeit = self.auswertung.fahrzeit_schaetzen(zug.name, einfahrt.gleis, ziel1.gleis)
                    if not np.isnan(fahrzeit):
                        try:
                            einfahrt.an = einfahrt.ab = seconds_to_time(time_to_seconds(ziel1.an) - fahrzeit)
                            logger.debug(f"einfahrt {einfahrt.gleis} - {ziel1.gleis} korrigiert: {einfahrt.ab}")
                        except (AttributeError, ValueError):
                            pass

            try:
                ziel2 = zug.fahrplan[-2]
                ausfahrt = zug.fahrplan[-1]
            except IndexError:
                pass
            else:
                if ausfahrt.ausfahrt:
                    fahrzeit = self.auswertung.fahrzeit_schaetzen(zug.name, ziel2.gleis, ausfahrt.gleis)
                    if not np.isnan(fahrzeit):
                        try:
                            ausfahrt.an = ausfahrt.ab = seconds_to_time(time_to_seconds(ziel2.ab) + fahrzeit)
                            logger.debug(f"ausfahrt {ziel2.gleis} - {ausfahrt.gleis} korrigiert: {ausfahrt.an}")
                        except (AttributeError, ValueError):
                            pass

    def verspaetungen_korrigieren(self):
        """
        verspätungsangaben aller züge nachführen

        :simzeit_minuten: akuelle simulationszeit in minuten seit mitternacht
        :return: None
        """

        for node in self.zielsortierung:
            data = self.zielgraph.nodes[node]
            ziel: ZugZielPlanung = data['obj']
            zug: ZugDetailsPlanung = ziel.zug

            if not ziel.angekommen:
                v = [pred_data['v_ab'] for pred, pred_data in self.zielgraph.pred[node].items()]
                # beim aktuellen ziel verspaetung von zug uebernehmen
                if ziel.einfahrt or zug.plangleis == ziel.plan or len(v) == 0:
                    v.append(zug.verspaetung)
                    ziel.verspaetung_an = zug.verspaetung
                v_an = max(v)
            else:
                v_an = ziel.verspaetung_an
            data['v_an'] = v_an

            # bei noch nicht abgefahrenen zielen verspaetung korrigieren
            if not ziel.abgefahren:
                if ziel.fdl_korrektur is not None:
                    ziel.fdl_korrektur.anwenden(zug, ziel)
                elif ziel.auto_korrektur is not None:
                    ziel.auto_korrektur.anwenden(zug, ziel)
                else:
                    ziel.verspaetung_ab = ziel.verspaetung_an

            data['v_ab'] = ziel.verspaetung_ab

    def zugverspaetung_korrigieren(self, zug: ZugDetailsPlanung):
        """
        verspätungsangaben einer zugfamilie nachführen

        diese methode führt die verspätungsangaben des angegebenen zugs und der verknüpften züge nach.

        aktuell ist die methode nicht implementiert und ruft verspaetungen_korrigieren auf,
        die alle züge nachführt.
        es ist fraglich, ob es effizienter ist, die zugfamilien einzeln zu korrigieren,
        da die bestimmung der familien auch einen aufwand bedeutet.

        :param zug:
        :return:
        """

        self.verspaetungen_korrigieren()

    def korrekturen_definieren(self):
        for zug in self.zuege():
            if not zug.korrekturen_definiert:
                result = self.zug_korrekturen_definieren(zug)
                zug.korrekturen_definiert = zug.folgezuege_aufgeloest and result

    def zug_korrekturen_definieren(self, zug: ZugDetailsPlanung) -> bool:
        result = True
        for ziel in zug.fahrplan:
            ziel_result = self.ziel_korrekturen_definieren(ziel)
            result = result and ziel_result
        return result

    def ziel_korrekturen_definieren(self, ziel: ZugZielPlanung) -> bool:
        result = True

        if ziel.richtungswechsel():
            ziel.mindestaufenthalt = 2
        elif ziel.lokumlauf():
            ziel.mindestaufenthalt = 2
        elif ziel.lokwechsel():
            ziel.mindestaufenthalt = 5

        if ziel.einfahrt:
            ziel.auto_korrektur = Einfahrtszeit(self)
        elif ziel.ausfahrt:
            pass
        elif ziel.durchfahrt():
            pass
        elif ziel.ersatz_zid():
            ziel.auto_korrektur = Ersatzzug(self)
            ziel.mindestaufenthalt = max(ziel.mindestaufenthalt, 1)
            anschluss = AnkunftAbwarten(self)
            anschluss.ursprung = ziel
            try:
                ziel.ersatzzug.fahrplan[0].auto_korrektur = anschluss
            except (AttributeError, IndexError):
                result = False
        elif ziel.kuppel_zid():
            ziel.auto_korrektur = Kupplung(self)
            ziel.mindestaufenthalt = max(ziel.mindestaufenthalt, 1)
            anschluss = AnkunftAbwarten(self)
            anschluss.ursprung = ziel
            try:
                kuppel_ziel = ziel.kuppelzug.find_fahrplanzeile(plan=ziel.plan)
                kuppel_ziel.auto_korrektur = anschluss
            except (AttributeError, IndexError):
                result = False
        elif ziel.fluegel_zid():
            ziel.auto_korrektur = Fluegelung(self)
            ziel.mindestaufenthalt = max(ziel.mindestaufenthalt, 1)
            anschluss = AbfahrtAbwarten(self)
            anschluss.ursprung = ziel
            anschluss.wartezeit = 2
            try:
                ziel.fluegelzug.fahrplan[0].auto_korrektur = anschluss
            except (AttributeError, IndexError):
                result = False
        elif ziel.auto_korrektur is None:
            ziel.auto_korrektur = PlanmaessigeAbfahrt(self)

        return result

    def zug_finden(self, zug: Union[int, str, ZugDetails]) -> Optional[ZugDetailsPlanung]:
        """
        zug nach name oder nummer in zugliste suchen

        :param zug: nummer oder name des zuges oder ein beliebiges objekt mit einem zid attribut,
            z.b. ein ZugDetails vom PluginClient oder ein Ereignis.
        :return: entsprechendes ZugDetailsPlanung aus der zugliste dieser klasse.
            None, wenn kein passendes objekt gefunden wurde.
        """

        zid = None
        try:
            zid = zug.zid
        except AttributeError:
            for z in self.zuege():
                if z.nummer == zug or z.name == zug:
                    zid = z.zid
                    break

        try:
            return self.zugbaum[zid]['obj']
        except KeyError:
            return None

    def fdl_korrektur_setzen(self, korrektur: Optional[VerspaetungsKorrektur], ziel: Union[int, str, ZugZielPlanung]):
        """
        fahrdienstleiter-korrektur setzen

        mit dieser methode kann der fahrdienstleiter eine manuelle verspätungskorrektur auf eine fahrplanzeile anwenden,
        z.b. eine feste abgangsverspätung setzen oder eine abhängigkeit von einem kreuzenden zug festlegen.

        beim setzen einer fdl-korrektur werden alle nachfolgenden gelöscht!
        beim löschen (auf None setzen) bleiben sie erhalten.

        :param korrektur: von VerspaetungsKorrektur abgeleitetes korrekturobjekt.
            in frage kommen normalerweise FesteVerspaetung, AnkunftAbwarten oder AbfahrtAbwarten.
            bei None wird die korrektur gelöscht.
        :param ziel: fahrplanziel auf die die korrektur angewendet wird.
            dies kann ein ZugDetailsPlanung-objekt aus der zugliste dieser klasse sein
            oder ein gleisname oder fahrplan-index.
            in den letzteren beiden fällen, muss auch der zug oder zid angegeben werden.
        :return: None
        """

        zug = ziel.zug
        ziel_index = zug.find_fahrplan_index(plan=ziel.plan)

        ziel.fdl_korrektur = korrektur
        if korrektur:
            for z in zug.fahrplan[ziel_index + 1:]:
                z.fdl_korrektur = None

    def ereignis_uebernehmen(self, ereignis: Ereignis):
        """
        daten von einem ereignis uebernehmen.

        aktualisiert die verspätung und angekommen/abgefahren-flags anhand eines ereignisses.

        :param ereignis: Ereignis-objekt vom PluginClient
        :return:
        """

        logger.debug(f"{ereignis.art} {ereignis.name} ({ereignis.verspaetung})")

        try:
            zug = self.zugbaum.nodes[ereignis.zid]['obj']
        except KeyError:
            logger.warning(f"zug von ereignis {ereignis} nicht in zugliste")
            return None

        try:
            alter_index = zug.ziel_index
            altes_ziel = zug.fahrplan[zug.ziel_index]
        except IndexError:
            logger.warning(f"fehlendes vorheriges ziel bei {ereignis}")
            return

        if ereignis.plangleis:
            neuer_index = zug.find_fahrplan_index(plan=ereignis.plangleis)
        else:
            # ausfahrt
            neuer_index = len(zug.fahrplan) - 1
        if neuer_index is None:
            logger.warning(f"ereignisziel nicht in fahrplan bei {ereignis}")
            return
        elif neuer_index < alter_index:
            logger.warning(f"ignoriere veraltetes ereignis {ereignis}")
            return
        else:
            neues_ziel = zug.fahrplan[neuer_index]

        if ereignis.art == 'einfahrt':
            try:
                einfahrt = zug.fahrplan[0]
            except IndexError:
                pass
            else:
                if einfahrt.einfahrt:
                    einfahrt.verspaetung_ab = time_to_minutes(ereignis.zeit) - time_to_minutes(einfahrt.ab)
                    einfahrt.angekommen = einfahrt.abgefahren = ereignis.zeit

        elif ereignis.art == 'ausfahrt':
            try:
                ausfahrt = zug.fahrplan[-1]
            except IndexError:
                pass
            else:
                if ausfahrt.ausfahrt:
                    ausfahrt.verspaetung_an = ausfahrt.verspaetung_ab = ereignis.verspaetung
                    ausfahrt.angekommen = ausfahrt.abgefahren = ereignis.zeit
                    zug.ausgefahren = True

        elif ereignis.art == 'ankunft':
            altes_ziel.verspaetung_an = time_to_minutes(ereignis.zeit) - time_to_minutes(altes_ziel.an)
            altes_ziel.angekommen = ereignis.zeit
            if altes_ziel.durchfahrt():
                altes_ziel.verspaetung_ab = altes_ziel.verspaetung_an
                altes_ziel.abgefahren = ereignis.zeit
            # falls ein ereignis vergessen gegangen ist:
            for ziel in zug.fahrplan[0:alter_index]:
                ziel.angekommen = ziel.angekommen or True
                ziel.abgefahren = ziel.abgefahren or True

        elif ereignis.art == 'abfahrt':
            if ereignis.amgleis:
                if ereignis.verspaetung > 0:
                    altes_ziel.auto_korrektur = Signalhalt(self)
                    altes_ziel.auto_korrektur.verspaetung = ereignis.verspaetung
            else:
                altes_ziel.verspaetung_ab = ereignis.verspaetung
                altes_ziel.abgefahren = ereignis.zeit

        elif ereignis.art == 'rothalt' or ereignis.art == 'wurdegruen':
            zug.verspaetung = ereignis.verspaetung
            neues_ziel.verspaetung_an = ereignis.verspaetung


async def test() -> Planung:
    """
    testprogramm

    das testprogramm fragt alle daten einmalig vom simulator ab und gibt ein planungsobjekt zurueck.

    :return: Planung-instanz
    """

    client = PluginClient(name='stskit-planung', autor='tester', version='0.0', text='planungsobjekt abfragen')
    await client.connect()

    try:
        async with client._stream:
            async with trio.open_nursery() as nursery:
                await nursery.start(client.receiver)
                await client.register()
                await client.request_simzeit()
                await client.request_zugliste()
                await client.request_zugdetails()
                await client.request_zugfahrplan()
                await client.resolve_zugflags()

                _planung = Planung()
                _planung.zuege_uebernehmen(client.zugliste.values())
                _planung.simzeit_minuten = time_to_minutes(client.calc_simzeit())

                raise TaskDone()

    except TaskDone:
        pass

    return _planung


if __name__ == '__main__':
    planung_obj, simzeit = trio.run(test)
