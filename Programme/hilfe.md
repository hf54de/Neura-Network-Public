# NeuronNetz – Hilfe und Bedienungsanleitung

> **Hinweis zur Hilfedatei**  
>  
> Diese Datei ist die bearbeitbare Hilfedatei des Programms **NeuronNetz**.  
> Sie kann mit Visual Studio Code, Notepad++, Windows Editor oder jedem anderen Texteditor geändert werden.

---

# 1. Überblick

**NeuronNetz** ist ein grafischer Editor zum Erstellen, Trainieren und Testen kleiner neuronaler Netzwerke.

Mit dem Programm können Sie:

- Neuronen frei auf der Zeichenfläche anordnen
- Input-, Hidden- und Output-Neuronen verwenden
- Verbindungen mit Gewichten erstellen
- Aktivierungsfunktionen festlegen
- Trainingsdaten anlegen oder importieren
- Trainingsdatenspalten einzelnen Neuronen zuordnen
- Netzwerke trainieren
- Gewichte während des Trainings beobachten
- Testergebnisse auswerten
- Netzwerke automatisch erzeugen
- Projekte speichern und später wieder öffnen

Das Programm ist besonders dafür geeignet, den Aufbau und das Lernverhalten neuronaler Netze sichtbar und nachvollziehbar zu machen.

---

# 2. Programmoberfläche

Die Oberfläche besteht aus mehreren Bereichen.

## Zeichenfläche

Auf der großen Zeichenfläche werden Neuronen, Verbindungen und Kommentare dargestellt.

## Eigenschaftenfenster

Rechts befindet sich das Eigenschaftenfenster.

Dort werden die Daten des aktuell ausgewählten Objekts angezeigt und bearbeitet.

Die Bereiche **Eigenschaften**, **Mathematik** und **Projektablauf** sind
untereinander angeordnet und lassen sich einzeln aufklappen. Dadurch kann das
Fenster deutlich schmaler eingestellt werden, ohne dass Registerkarten
abgeschnitten werden.

Je nach Auswahl erscheinen:

- Neuroneneigenschaften
- Verbindungseigenschaften
- Kommentareigenschaften

## Menüleiste

Die wichtigsten Menüs sind:

- **Datei**
- **Bearbeiten**
- **Ansicht**
- **Netzwerk**
- **Trainingsdaten**
- **Einstellungen**
- **Hilfe**

**Hilfe → Tutorials** öffnet den normalen Windows-Dateidialog. Ohne einen
persönlich gespeicherten Pfad verwendet NeuronNetz automatisch den sichtbaren
Ordner `Tutorials` neben der EXE. Im Quellbetrieb wird entsprechend eine Ebene
oberhalb des Programmordners gesucht. Fehlt der Ordner, wird er angelegt. Ist
der Programmort nicht beschreibbar, verwendet NeuronNetz als sicheren Ersatz
`Dokumente\NeuronNetz\Tutorials`.

Dort kann ein PDF-, Word-, HTML-, Markdown- oder Text-Tutorial ausgewählt und
mit dem zugehörigen Windows-Programm geöffnet werden. Wird in einen anderen
Ordner gewechselt und dort eine Datei geöffnet, merkt sich NeuronNetz diesen
persönlich gewählten Ordner für den nächsten Aufruf. Eigene oder bereits
bearbeitete Dateien bleiben unverändert.

## Statusleiste

Am unteren Rand werden unter anderem angezeigt:

- Anzahl der Neuronen und Verbindungen
- Status der Trainingsdaten
- gespeicherter oder geänderter Projektzustand
- aktueller Zoom
- Meldungen zu Projekten
- Meldungen zu Trainingsdaten
- Trainingsergebnisse

Kurzzeitige Meldungen ersetzen die dauerhafte Projektübersicht vorübergehend.
Danach erscheint sie automatisch wieder.

---

# 3. Neues Projekt

Ein neues Projekt wird über folgenden Menüpunkt angelegt:

**Datei → Neu**

Danach wählt der Benutzer einen von vier Einstiegen:

- **Leeres Projekt anlegen**
- **Netzwerk automatisch erstellen**
- **Netzwerk aus Trainingsdaten erstellen**
- **Eigene Projektidee entwickeln**

Jeder Einstieg legt zunächst ein neues, leeres Projekt an und öffnet danach
gegebenenfalls den passenden Assistenten. Falls das aktuelle Projekt geändert
wurde, fragt das Programm genau einmal, ob die Änderungen gespeichert werden
sollen.

Ein neues Projekt enthält:

- keine Neuronen
- keine Verbindungen
- keine Kommentare
- keine Trainingsdaten
- Standardwerte für Training und Darstellung

---

# 4. Neuron erstellen

Ein einzelnes Neuron wird über das Kontextmenü der Zeichenfläche angelegt.

1. Mit der rechten Maustaste auf eine freie Stelle klicken.
2. **Neuron einfügen** wählen.
3. Das neue Neuron wird an der angeklickten Position erzeugt.
4. Das Neuron wird automatisch ausgewählt.
5. Seine Eigenschaften erscheinen rechts im Eigenschaftenfenster.

Neue Neuronen erhalten fortlaufende IDs und zunächst einen Namen wie:

```text
N1
N2
N3
```

---

# 5. Neuronentypen

Jedes Neuron besitzt einen Typ.

## Input

Ein Input-Neuron übernimmt einen Eingangswert aus den Trainingsdaten oder aus dem Eigenschaftenfenster.

Typische Merkmale:

- besitzt einen Eingabewert X
- besitzt keinen trainierbaren Bias
- besitzt keine Aktivierungsfunktion im eigentlichen Sinn
- gibt seinen Eingabewert als Ausgang Y weiter

## Hidden

Ein Hidden-Neuron verarbeitet Werte innerhalb des Netzwerks.

Es besitzt:

- eingehende Verbindungen
- Gewichte
- Bias
- Aktivierungsfunktion
- Summenwert Σ
- Ausgangswert Y

## Output

Ein Output-Neuron liefert das Ergebnis des Netzwerks.

Zusätzlich zu den normalen Neuroneneigenschaften besitzt es:

- Sollwert
- Fehler
- Delta

---

# 6. Eigenschaften eines Neurons

Nach dem Anklicken eines Neurons erscheinen seine Daten im Eigenschaftenfenster.

Das Fenster besitzt für Neuronen die Registerkarten **Eigenschaften**
und **Mathematik**. Die erste Seite enthält die bearbeitbaren Daten und
Laufzeitwerte. Die zweite Seite erklärt, wie die aktuell sichtbaren
Rechenwerte entstanden sind.

## Allgemeine Eigenschaften

### ID

Eindeutige Nummer des Neurons.

Die ID wird automatisch vergeben und kann nicht geändert werden.

### Name

Frei wählbarer Name des Neurons.

Beispiele:

```text
Temperatur
Druck
Freigabe
N1
```

### Typ

Mögliche Typen:

- Input
- Hidden
- Output

## Parameter

### Aktivierung

Mögliche Aktivierungsfunktionen:

- Linear
- ReLU
- Sigmoid
- Tanh

### Bias

Zusätzlicher trainierbarer Wert eines Hidden- oder Output-Neurons.

### Eingabewert

Nur bei Input-Neuronen sichtbar.

Der Wert wird bei einer Vorwärtsberechnung als Eingang X verwendet.

## Position

Die aktuelle Position wird angezeigt als:

- Position X
- Position Y

Diese Werte werden automatisch beim Verschieben aktualisiert.

## Laufzeitwerte

Je nach Neuronentyp werden angezeigt:

- X
- Σ
- Y
- Sollwert
- Fehler
- Delta

## Registerkarte Mathematik

Bei Input-Neuronen zeigt die Registerkarte die direkte Übernahme von
`X` nach `Y`. Bei Hidden- und Output-Neuronen werden dargestellt:

- jeder einzelne Beitrag `YQuelle × Gewicht`
- Bias und gewichtete Summe `Σ`
- Formel und Ergebnis der Aktivierungsfunktion
- Ableitung der Aktivierungsfunktion
- bei Output-Neuronen Sollwert, Fehler und Delta
- bei Hidden-Neuronen Rückwärtssumme und Delta

Die Vorwärtsrechnung verwendet den aktuellen Netzwerkzustand. Für die
Rückwärtsrechnung merkt sich das Programm im Arbeitsspeicher die Werte
des letzten Lernschritts. Dadurch werden alte Deltas nicht mit bereits
geänderten Gewichten vermischt. Dieser Rechenschnappschuss ist nur für
die Anzeige bestimmt und wird nicht in der Projektdatei gespeichert.

Beispiel:

```text
Σ = N1.Y × W1 + N2.Y × W2 + B
Σ = 0.75 × 2.0 + 0.20 × 1.5 + 0.50
Σ = 2.30
Y = Sigmoid(Σ)
Y = 0.908877
```

---

# 7. Verbindungen erstellen

Eine Verbindung wird mit der Maus vom Ausgangsport eines Neurons zum Eingangsport eines anderen Neurons gezogen.

1. Ausgangsport des Startneurons anklicken.
2. Maustaste gedrückt halten.
3. Zum Eingangsport des Zielneurons ziehen.
4. Maustaste loslassen.

Die Verbindung besitzt:

- eine eindeutige ID
- ein Startneuron
- ein Zielneuron
- ein Gewicht W
- eine Pfeilspitze zur Anzeige der Richtung

Eine Verbindung kann nicht auf dasselbe Neuron zurückgeführt werden.

Doppelte Verbindungen zwischen denselben beiden Neuronen werden verhindert.

---

# 8. Eigenschaften einer Verbindung

Nach dem Anklicken einer Verbindung werden rechts angezeigt:

- ID
- Startneuron
- Zielneuron
- Gewicht

Das Gewicht kann direkt geändert werden.

Auch Verbindungen besitzen die Registerkarten **Eigenschaften** und
**Mathematik**. Die Mathematikseite zeigt den Vorwärtsbeitrag der
Verbindung zur gewichteten Summe des Zielneurons. Zusätzlich wird die
Lernregel

```text
ΔW = Lernrate × Delta des Zielneurons × Ausgang des Startneurons
```

mit den gespeicherten Rechenwerten des letzten Lernschritts eingesetzt.
Damit lässt sich exakt nachvollziehen, wie diese Verbindung dabei
verändert wurde. Oberhalb davon bleibt der Vorwärtsbeitrag des aktuellen
Netzwerkzustands sichtbar.

Beispiel:

```text
Gewicht: -0.85
```

Die sichtbare Gewichtsanzeige auf der Zeichenfläche wird automatisch aktualisiert.

Bei mehreren nah beieinanderliegenden Gewichtsanzeigen versucht das Programm, Überlappungen automatisch zu vermeiden.

---

# 9. Kommentare

Kommentare dienen zur Dokumentation des Netzwerks.

## Kommentar einfügen

1. Mit der rechten Maustaste auf eine freie Stelle klicken.
2. **Kommentar einfügen** wählen.

## Eigenschaften eines Kommentars

Im Eigenschaftenfenster können geändert werden:

Ein Rechtsklick auf einen Kommentar bietet zusätzlich **Bearbeiten** und
**Löschen**. **Bearbeiten** öffnet ein eigenes Fenster für den mehrzeiligen
Text und die Schriftgröße. Enter erzeugt eine neue Zeile, `Strg+Enter`
übernimmt und Esc bricht ab. Die Bearbeitung im Eigenschaftenfenster bleibt
weiterhin verfügbar.

- Text
- Breite
- Höhe
- Schriftgröße
- Schriftart

Kommentare können frei verschoben und in ihrer Größe verändert werden.
Einzeilige Kommentare lassen sich bis auf eine kompakte Höhe von 36 Pixeln
verkleinern.

Kommentare werden zusammen mit dem Projekt gespeichert.

---

# 10. Objekte auswählen und verschieben

## Einzelnes Objekt auswählen

Ein Neuron, eine Verbindung oder ein Kommentar wird durch Anklicken ausgewählt.

Mit der rechten Maustaste auf einem Neuron stehen **Bearbeiten** und
**Löschen** zur Verfügung. **Bearbeiten** öffnet ein kompaktes Fenster für
Name, Typ und Aktivierungsfunktion. Für Hidden- und Output-Neuronen stehen
**Linear**, **ReLU**, **Sigmoid** und **Tanh** zur Auswahl. Input-Neuronen
besitzen keine Aktivierungsfunktion; dort ist die Auswahl deaktiviert.
**Übernehmen** oder Enter speichert die Änderungen, **Abbrechen** verwirft sie.
Vor dem Löschen wird immer noch einmal nachgefragt. Auf einer freien Stelle
enthält das Kontextmenü keinen Eintrag zum Löschen.

## Mehrere Objekte auswählen

Mit gedrückter `Strg`-Taste können mehrere Objekte ausgewählt werden.

## Rechteckauswahl

Auf einer freien Stelle klicken und mit gedrückter Maustaste ein Rechteck aufziehen.

Alle Objekte innerhalb des Rechtecks werden ausgewählt.

## Verschieben

Ausgewählte Neuronen oder Kommentare können mit der Maus verschoben werden.

Bei mehreren ausgewählten Objekten werden diese gemeinsam verschoben.

Verbindungen passen ihre Position automatisch an.

---

# 11. Kopieren, Ausschneiden und Einfügen

Die Funktionen befinden sich im Menü:

**Bearbeiten**

## Kopieren

**Bearbeiten → Kopieren**

Tastenkürzel:

```text
Strg+C
```

Kopiert werden:

- ausgewählte Neuronen
- ausgewählte Kommentare
- Verbindungen zwischen gemeinsam kopierten Neuronen
- Neuroneneigenschaften
- Verbindungsgewichte
- Kommentartexte und Kommentargrößen

## Ausschneiden

**Bearbeiten → Ausschneiden**

Tastenkürzel:

```text
Strg+X
```

Die Auswahl wird in die interne Zwischenablage übernommen und anschließend aus dem Projekt entfernt.

## Einfügen

**Bearbeiten → Einfügen**

Tastenkürzel:

```text
Strg+V
```

Kopierte Objekte werden leicht versetzt eingefügt.

Ausgeschnittene Objekte werden beim ersten Einfügen an ihrer ursprünglichen Position wiederhergestellt.

---

# 12. Rückgängig und Wiederholen

## Rückgängig

**Bearbeiten → Rückgängig**

Tastenkürzel:

```text
Strg+Z
```

## Wiederholen

**Bearbeiten → Wiederholen**

Tastenkürzel:

```text
Strg+Y
```

Das Programm speichert bis zu **100 Arbeitsschritte**.

Rückgängig und Wiederholen berücksichtigen unter anderem:

- Erstellen von Neuronen
- Erstellen von Verbindungen
- Löschen
- Verschieben
- Kopieren und Einfügen
- Änderungen im Eigenschaftenfenster
- Änderungen von Gewichten
- Änderungen von Bias-Werten
- Kommentare
- automatische Netzwerkerzeugung
- Darstellungsoptionen

Beim Bearbeiten eines Textfelds wirkt `Strg+Z` zunächst innerhalb des Textfelds.

---

# 13. Ansicht und Zoom

Das Menü **Ansicht** enthält die Zoomfunktionen.

## Zeichenfläche mit der Hand verschieben

Auf einer freien Stelle der Zeichenfläche wird der Mauszeiger zu einer
geöffneten Hand. Ziehen mit gedrückter linker Maustaste verschiebt dort den
sichtbaren Ausschnitt. Ein Ziehen auf einem Objekt bedient weiterhin dieses
Objekt. Die Alt-Taste kann zusätzlich wie bisher verwendet werden.

Beim Ziehen wird die Hand geschlossen dargestellt. Nach dem Loslassen der
Maustaste erscheint sie auf der freien Fläche wieder geöffnet.

Dabei werden keine Neuronen, Kommentare oder Verbindungen markiert oder an eine
neue Position gesetzt. Es wird ausschließlich der sichtbare Ausschnitt bewegt.
Objekte lassen sich deshalb weiterhin normal markieren und verschieben.

Der Handmodus funktioniert auch, während das nicht-modale Trainingsfenster
geöffnet ist.

Auch bei ausgeschaltetem Netzwerkmonitor bleibt die manuelle Verschiebung
sichtbar. Der ausgeschaltete Monitor unterdrückt weiterhin die automatischen
Trainingsaktualisierungen; eine bewusst mit der Hand ausgeführte
Navigation wird dagegen sofort gezeichnet.

## Werkzeugleiste

Der Werkzeugleistenbereich stellt die Menübefehle direkt unterhalb der
Menüleiste in klar getrennten Gruppen bereit:

- **Datei:** Neu, Öffnen, Speichern und Speichern unter
- **Bearbeiten:** Rückgängig, Wiederholen, Ausschneiden, Kopieren,
  Einfügen, Alles markieren und Löschen
- **Ansicht:** Einstellungen, Vergrößern, Verkleinern, 100 Prozent und
  Alles anzeigen
- **Netzwerk:** Erzeugen, Anordnen, Prüfen, Vorwärtsberechnung und Training
- **Daten:** Trainingsdaten, Testdaten und Test mit Testdaten
- **Hilfe:** Dokumentation und Tutorials

Seltene oder potentiell unerwünschte Befehle wie **Beenden**, **Über**
und **Testdatenzuordnung entfernen** bleiben ausschließlich im Menü.

Alle Symbole stammen aus einem einheitlichen programmeigenen SVG-Satz.
Kurze Beschriftungen unter den Symbolen machen auch die speziellen
Netzwerkfunktionen eindeutig erkennbar.

Jede Schaltfläche zeigt beim Verweilen mit der Maus eine kurze Erklärung.
Deaktivierte Befehle, beispielsweise **Rückgängig** ohne vorhandenen
Arbeitsschritt oder **Testen** ohne zugeordnete Testdaten, sind auch in der
Werkzeugleiste deaktiviert.

Unter **Ansicht → Werkzeugleisten anzeigen** können alle Gruppen gemeinsam
ein- und ausgeblendet werden. Die Gruppen können verschoben und an einer
anderen Seite des Hauptfensters angedockt werden. Position und Sichtbarkeit werden als
persönliche Programmeinstellung gespeichert und gehören nicht zur
Projektdatei.

Symbolgröße und Beschriftungen werden unter
**Einstellungen → Programmeinstellungen... → Werkzeugleisten** angepasst.

## Vergrößern

```text
Strg++
```

## Verkleinern

```text
Strg+-
```

## 100 %

```text
Strg+0
```

Setzt den Zoom auf 100 Prozent zurück.

## Alles anzeigen

```text
Strg+F
```

Verwirft einen mit dem Handmodus verschobenen Ausschnitt, begrenzt die
Arbeitsfläche wieder auf die Projektobjekte und stellt das gesamte Netzwerk
mittig im Fenster dar.

Der Zoomstatus und der sichtbare Mittelpunkt werden mit dem Projekt gespeichert.

---

# 14. Programmeinstellungen

Das zentrale Einstellungsfenster befindet sich unter:

**Einstellungen → Programmeinstellungen...**

Es enthält links die Kategorien:

- Darstellung
- Farben
- Werkzeugleisten
- Editor
- Sprache

Ein Hinweis auf jeder Seite zeigt, ob die Werte mit dem aktuellen
Projekt oder als persönliche Programmeinstellung gespeichert werden.

Änderungen werden bereits bei geöffnetem Einstellungsfenster als
Vorschau auf der Zeichenfläche angezeigt. **Abbrechen** stellt die
vorherigen Werte wieder her. Mit **Standardwerte dieser Seite** wird nur
die gerade angezeigte Kategorie zurückgesetzt.

Das Einstellungssymbol in der Werkzeugleiste öffnet dasselbe Fenster
direkt auf der Seite **Darstellung**.

## Projekteinstellungen

Die sichtbaren Netzbestandteile auf der Seite **Darstellung** sowie die
Seite **Farben** werden mit der Projektdatei gespeichert. Dadurch kann
jedes Netzwerk seine eigene Darstellung und Farbpalette besitzen.

## Programmeinstellungen

Die Optionen für die **Programmoberfläche** auf der Seite
**Darstellung** sowie die Seiten **Werkzeugleisten** und **Editor**
werden benutzerbezogen unter
`AppData\Roaming\NeuronNetz\settings.json` gespeichert und gelten für alle
Projekte. Der Ordner wird beim ersten Speichern automatisch angelegt und muss
bei einer weitergegebenen EXE nicht vorbereitet werden.

Auf der Seite **Sprache** wird die Programmsprache ausgewählt. Verfügbare
Sprachen werden aus `languages.json` gelesen. Die Auswahl wird ebenfalls in
`settings.json` gespeichert. Nach einer Änderung fragt NeuronNetz, ob das
Programm sofort neu gestartet werden soll. **Ja** speichert und startet nach
der normalen Prüfung auf ungesicherte Projektänderungen neu. **Nein** speichert
die Sprache für den nächsten Programmstart. **Abbrechen** verwirft nur die
Sprachänderung; andere geänderte Einstellungen bleiben erhalten.

`languages.json` enthält sowohl den englischen als auch den deutschen
Sprachblock. Sichtbare Abschnittseinträge gliedern die Datei nach Menüs,
Einstellungen, Projektfunktionen, Dateneditor, Training und weiteren
Funktionsbereichen. Dadurch können Texte auch ohne Änderung des Programmcodes
angepasst werden. Fehlt die Sprachdatei oder eine einzelne Übersetzung,
verwendet das Programm den fest eingebauten englischen Notfalltext. Die
Dokumentation wird passend zur Sprache aus `hilfe_en.md`, `hilfe_de.md` oder
einer später ergänzten Hilfedatei geladen.

Die projektbezogene Option **Kennlinien der Aktivierungsfunktionen in
Neuronen anzeigen** befindet sich auf der Seite **Darstellung**. Hidden- und
Output-Neuronen zeigen damit unten rechts eine transparente Miniatur der
gewählten Funktion. Achsen, wenige lesbare Skalenwerte und die blaue Kurve
unterscheiden Linear, ReLU, Sigmoid und Tanh unmittelbar. Input-Neuronen
besitzen keine Aktivierungsfunktion und zeigen deshalb keine Kennlinie.

Die Umstellung erfolgt bewusst in überprüfbaren Funktionsgruppen. Bereits
vollständig sprachabhängig sind die Hauptmenüs, Werkzeugleisten, das zentrale
Einstellungsfenster, die Beschriftungen des Eigenschaftenfensters sowie die
wichtigsten Projekt- und Speicherabfragen. Weitere Fachdialoge werden in den
folgenden Ausbauschritten ergänzt.

## Eigenschaftenfenster anzeigen

Mit der Option **Eigenschaftenfenster anzeigen** kann das rechts
angedockte Eigenschaftenfenster unmittelbar ein- oder ausgeblendet
werden. Beim Ausblenden steht der Zeichenfläche entsprechend mehr Platz
zur Verfügung. Beim Einschalten wird das Eigenschaftenfenster immer
wieder am rechten Rand des Hauptfensters angedockt. Dadurch wird auch
eine versehentlich verschobene oder außerhalb des sichtbaren Bereiches
liegende Fensterposition korrigiert.

Das Eigenschaftenfenster ist fest für den rechten Rand vorgesehen und
kann nicht als selbständiges schwebendes Fenster abgetrennt werden. Ein
Doppelklick auf seine Kopfzeile verändert deshalb die Position nicht.
Die Breite lässt sich an der linken Trennlinie bis zu einer lesbaren
Mindestbreite verändern und wird für den nächsten Programmstart gespeichert.

Wird das Eigenschaftenfenster über sein eigenes Schließsymbol
geschlossen, wird die Option automatisch mitgeführt. Die Sichtbarkeit
ist eine persönliche Programmeinstellung: Sie gilt projektunabhängig,
verändert die Projektdatei nicht und markiert das Projekt nicht als
geändert.

## Kompakte Zahlendarstellung

Zahlen in Neuronen, Ergebnisfeldern, Trainings- und Testtabellen,
Kalibrierungsanzeigen und der Trainingshistorie werden übersichtlich
und ohne unnötige Nachkommastellen dargestellt. Sehr kleine oder sehr
große Werte erscheinen automatisch in wissenschaftlicher Schreibweise,
damit ein von null verschiedener Fehler nicht fälschlich wie `0`
aussieht.

Diese Kürzung betrifft ausschließlich die Anzeige. Berechnungen sowie
die Speicherung in Projekt-, Trainings- und Testdateien verwenden
weiterhin die vollständige interne Genauigkeit. Auch Eingabefelder für
Lernrate, Fehlergrenze, Gewichte und Bias bleiben präzise bearbeitbar.

## Gewichtswerte anzeigen

Mit der Option

**Gewichtswerte anzeigen**

können die W-Kästchen auf der Zeichenfläche ein- oder ausgeblendet werden.

### Aktiviert

- alle sichtbaren Gewichte werden angezeigt
- Gewichtsänderungen können während des Trainings beobachtet werden

### Deaktiviert

- Verbindungslinien und Pfeile bleiben sichtbar
- W-Kästchen werden ausgeblendet
- Gewichte bleiben vollständig erhalten
- Gewichte können weiterhin im Eigenschaftenfenster bearbeitet werden

Die Einstellung wird mit dem Projekt gespeichert.

## Berechnungswerte anzeigen

Blendet die Zahlenwerte innerhalb der Neuronen ein oder aus. Dazu
gehören Bias sowie die Laufzeitwerte `X`, `Σ` und `Y`.
Die Werte bleiben intern erhalten und werden weiterhin berechnet.

## Äußere Ein- und Ausgabewerte anzeigen

Blendet die kleinen Wertefelder vor Input- und hinter Output-Neuronen
ein oder aus. Die Felder machen den vollständigen Datenfluss sichtbar:

- Vor einem Input-Neuron steht der eingegebene Rohwert. Im Neuron wird
  unter `X` der tatsächlich vom Netzwerk verwendete, gegebenenfalls
  skalierte Wert angezeigt.
- Hinter einem Output-Neuron steht der in die ursprüngliche Einheit
  zurückskalierte Ausgabewert.
- Beim Training, im Mathematikmodus und beim Testen zeigt das
  Outputfeld zusätzlich `Ist` und `Soll` untereinander an.
- Ohne Skalierung stimmen äußerer und innerer Wert überein.

Die äußeren Felder sind fest mit den Neuronen verbunden und bewegen sich
beim Verschieben automatisch mit. Sie sind reine Anzeigen und verändern
weder Trainingsdaten noch Netzwerkberechnung.

## Anschlussports anzeigen

Blendet die farbigen Ein- und Ausgangsports der Neuronen ein oder aus.
Ausgeblendete Ports bleiben bedienbar und erscheinen wieder, sobald der
Mauszeiger ihre Position berührt. Neue Verbindungen können deshalb auch
bei ausgeblendeten Ports angelegt werden.

## Neuronennamen anzeigen

Blendet die Namen in den farbigen Kopfbereichen der Neuronen ein oder
aus. Die Namen selbst und alle Zuordnungen bleiben unverändert.

## Kommentare anzeigen

Blendet alle Kommentarfelder vorübergehend aus. Die Kommentare werden
nicht gelöscht und erscheinen nach dem erneuten Einschalten wieder an
ihren bisherigen Positionen.

## Gewichte durch Farbe und Linienstärke darstellen

Mit der Option

**Gewichte durch Farbe und Linienstärke darstellen**

werden Vorzeichen und Betrag eines Gewichts direkt an der
Verbindungslinie sichtbar gemacht.

### Aktiviert

- positive Gewichte werden blau dargestellt
- negative Gewichte werden rot dargestellt
- Gewichte nahe null werden grau dargestellt
- mit zunehmendem Betrag wird die Verbindungslinie stärker
- die Pfeilspitze erhält dieselbe Farbe wie die Verbindung
- die W-Kästchen bleiben zusätzlich sichtbar, wenn
  **Gewichtswerte anzeigen** aktiviert ist

Die Linienstärke ist nach oben begrenzt. Dadurch bleiben auch
Verbindungen mit sehr großen Gewichten übersichtlich.

Eine ausgewählte Verbindung erhält eine kräftig rote Kontur. Ihre
eigentliche Gewichtsfarbe bleibt dabei weiterhin erkennbar.

### Deaktiviert

- alle Verbindungslinien werden wie bisher schwarz dargestellt
- alle Gewichte und W-Kästchen bleiben unverändert erhalten

Alle Einstellungen im Bereich **Sichtbare Elemente und Verbindungen**
werden mit dem Projekt gespeichert. Die Sichtbarkeit des
Eigenschaftenfensters ist dagegen eine persönliche Programmeinstellung.
Bei älteren Projekten sind die neu hinzugekommenen Elemente zunächst
sichtbar.

## Farben

Auf der Seite **Farben** lassen sich einstellen:

- Kopfbereiche von Input-, Hidden- und Output-Neuronen
- Neuronenhintergrund
- Input- und Output-Ports
- positive, negative und neutrale Gewichte
- Auswahlmarkierung
- Kommentarhintergrund
- Hintergrund der Zeichenfläche

Ein Klick auf ein Farbfeld öffnet die Farbauswahl. Das Ergebnis wird
unmittelbar im geöffneten Projekt angezeigt.

## Werkzeugleisten

Diese Seite enthält:

- Symbolgröße von 12 bis 36 Pixeln
- automatische Anpassung der Abmessungen an kleinere und größere Bildschirme
- alternativ eine eigene Breite für vertikale und eine eigene Höhe für
  horizontale Werkzeugleisten
- Beschriftungen unter den Symbolen ein- oder ausblenden
- alle Werkzeugleistengruppen ein- oder ausblenden

Solange die automatische Anpassung eingeschaltet ist, sind die beiden
manuellen Maße gesperrt. Ein Hinweis direkt unter der Option erklärt, dass die
Automatik für eigene Werte zuerst ausgeschaltet werden muss.

## Editor

Hier werden der freie Rand der Zeichenfläche um die Projektobjekte und
die Schrittweite des Mausrad-Zooms eingestellt.

Zusätzlich kann die vereinfachte Verschiebung großer Netzbereiche ein- oder
ausgeschaltet werden. Bei sehr vielen betroffenen Verbindungen blendet das
Programm die Linien während des Ziehens kurz aus und berechnet sie beim
Loslassen einmal vollständig neu.

---

# 15. Netzwerk automatisch erzeugen

Der Erzeugungsdialog, die automatische Anordnung und die Netzwerkprüfung
folgen vollständig der unter **Programmeinstellungen → Sprache** gewählten
Programmsprache. Dazu gehören auch Strukturvorschauen, Warnungen,
Prüfergebnisse und Statusmeldungen. Bezeichnungen mathematischer
Aktivierungsfunktionen wie Sigmoid, Tanh, ReLU und Linear bleiben eindeutig
und sprachunabhängig.

Der Menüpunkt befindet sich unter:

**Netzwerk → Netzwerk automatisch erzeugen...**

Damit lässt sich ein vollständiges Netzwerk mit wenigen Eingaben erstellen.

## Einstellbare Werte

- Anzahl Input-Neuronen
- Anzahl Hidden-Schichten
- individuelle Anzahl Neuronen für jede Hidden-Schicht
- Anzahl Output-Neuronen
- Aktivierung der Hidden-Neuronen
- Aktivierung der Output-Neuronen
- vollständig zwischen den Schichten verbinden
- vorhandenes Netzwerk ersetzen
- leere Trainingsdatenstruktur anlegen

Für jede gewählte Hidden-Schicht erscheint eine eigene Eingabezeile.
Bei zwei Hidden-Schichten können beispielsweise `8` und `4` Neuronen
eingestellt werden. Die Zusammenfassung zeigt dann unmittelbar die
Struktur `3 → 8 → 4 → 1` und berechnet die entstehende Anzahl von
Neuronen und Verbindungen mit diesen individuellen Schichtgrößen.

## Automatische Anordnung

Die erzeugten Neuronen werden automatisch in Spalten angeordnet:

```text
Input-Schicht → Hidden-Schicht(en) → Output-Schicht
```

Die Schichten und Neuronen werden mit großzügigem Abstand platziert.

## Vollständige Verbindung

Bei aktivierter vollständiger Verbindung wird jedes Neuron einer Schicht mit jedem Neuron der folgenden Schicht verbunden.

## Vorhandenes Netzwerk ersetzen

Bei aktivierter Option werden vorhandene Neuronen und Verbindungen entfernt.

Kommentare bleiben erhalten.

## Leere Trainingsdatenstruktur anlegen

Für jedes Input- und Output-Neuron wird automatisch eine passende Trainingsdatenspalte erzeugt.

Die Spalten werden direkt den erzeugten Neuronen zugeordnet.

## Netzwerk getrennt aus Trainingsdaten erzeugen

Der zusätzliche Menüpunkt **Netzwerk → Netzwerk aus Trainingsdaten
erzeugen...** beginnt bewusst nicht mit einer Netzstruktur, sondern mit den
Daten. Der bisherige Generator bleibt davon vollständig getrennt.

Der Assistent führt in dieser Reihenfolge durch den Ablauf:

1. Anzahl der Ein- und Ausgänge festlegen.
2. Die passende Trainingsdatentabelle erzeugen und öffnen.
3. Spalten benennen, Einheiten eintragen und Werte mit `Strg+V` oder über
   **CSV importieren...** übernehmen.
4. Nach dem Schließen der Tabelle alle geeigneten **analogen** Spalten
   automatisch aus ihren Minimal- und Maximalwerten auf `0 … 1` skalieren.
   Binärspalten bleiben immer unskaliert.
5. Den aus Anzahl und Art der Daten abgeleiteten Netzwerkvorschlag prüfen.
6. Hidden-Schichten, Neuronenzahlen und Aktivierungsfunktionen bei Bedarf
   ändern und das Netzwerk erzeugen.

Ausgangsspalten, die ausschließlich die Werte `0` und `1` enthalten, werden
als Klassifikation erkannt und erhalten im Vorschlag **Sigmoid**. Andere
Ausgänge erhalten **Linear**. Bei vier Eingängen und mehreren Ausgängen wird
beispielsweise zunächst `4 → 8 → 4 → 2` vorgeschlagen. Der Vorschlag ist eine
editierbare Ausgangsbasis, keine starre Vorgabe.

Spalten mit nur einem konstanten Wert können nicht per Min-Max skaliert werden
und bleiben unskaliert; der Assistent weist in seiner Zusammenfassung darauf
hin. Beim Erzeugen werden die Spaltennamen als Namen der Input- und
Output-Neuronen übernommen. Erst nachdem diese echten Neuronen angelegt sind,
werden die Trainingsspalten dauerhaft zugeordnet.

Markierte Tabellenzellen lassen sich mit `Strg+C` tabulatorgetrennt in die
Zwischenablage kopieren. Die rein sichtbare Spalte **Nr.** ist nicht auswählbar
und wird auch beim Ziehen über die gesamte Tabelle ausgelassen. Zeilen und
Datenspalten bleiben erhalten, sodass der Bereich
unmittelbar wieder in einen Trainingsdateneditor, in Excel, Calc oder einen
Texteditor eingefügt werden kann. Ein Rechtsklick in die Tabelle öffnet außerdem
ein Kontextmenü mit Rückgängig, Wiederholen, Ausschneiden, Kopieren, Einfügen,
Alles markieren und Löschen. **Löschen** entfernt immer die vollständigen
ausgewählten Datensätze und verhält sich damit genauso wie die Schaltfläche
**Ausgewählte Datensätze löschen**. `Strg+Z` und `Strg+Y` machen Änderungen im
Dateneditor rückgängig beziehungsweise stellen sie wieder her. Dazu gehören
das Einfügen, Ausschneiden, Löschen, Hinzufügen und Entfernen von Datensätzen.

Längere Beschriftungen in den seitlich angedockten Werkzeugleisten werden bei
Bedarf zweizeilig dargestellt. Kurze Beschriftungen bleiben einzeilig, damit
die Werkzeugleiste schmal und gut lesbar bleibt.

## Hidden-Struktur ändern

Mit **Netzwerk → Struktur ändern...** lässt sich die vorhandene Hidden-Struktur
kompakt umbauen. Der Dialog zeigt die erkannte Anzahl der Hidden-Schichten und
für jede Schicht eine eigene Eingabe für die Neuronenzahl. Wird die Anzahl der
Schichten erhöht, erscheinen die zusätzlichen Eingabezeilen automatisch.

Eingangs- und Ausgangsneuronen bleiben mit ihren IDs, Namen und
Trainingsdatenzuordnungen erhalten. Nur Hidden-Neuronen und Verbindungen werden
neu aufgebaut; aufeinanderfolgende Schichten werden vollständig verbunden und
anschließend automatisch angeordnet. Da die bisher trainierten Parameter nicht
zur neuen Struktur passen, muss das Netzwerk danach neu trainiert werden. Vor
der Änderung erscheint deshalb eine Sicherheitsabfrage. Nach der Bestätigung
werden die nicht mehr passenden Trainingsläufe, gespeicherten Netzzustände und
Analysebezüge entfernt; passende Trainings- und Testdaten bleiben erhalten.
Die gesamte Änderung ist ein gemeinsamer Rückgängig-Schritt. **Abbrechen** oder
**Übernehmen** ohne geänderte Werte verändert das Projekt nicht.

Beim manuellen Löschen oder Ändern des Typs eines Eingangs- oder
Ausgangsneurons warnt NeuronNetz, dass vorhandene Trainings- und Testdaten
möglicherweise nicht mehr passen. Reines Verschieben oder optische Änderungen
lösen keine Warnung aus.

## Vorhandenes Netzwerk automatisch anordnen

Der Menüpunkt

**Netzwerk → Vorhandenes Netzwerk automatisch anordnen...**

ordnet die bereits vorhandenen Neuronen und Verbindungen neu, ohne die
Netzwerkstruktur oder trainierte Werte zu verändern.

Dabei gilt:

- Input-Neuronen stehen links
- Output-Neuronen stehen rechts
- Hidden-Neuronen werden anhand ihrer Verbindungstiefe in Schichten eingeordnet
- die Reihenfolge innerhalb einer Schicht wird zur Verringerung von Kreuzungen optimiert
- nicht von einem Input erreichbare Hidden-Neuronen bilden eine getrennte Gruppe
- Kommentare bleiben unverändert

Im Dialog lassen sich der horizontale Abstand zwischen den Schichten und
der vertikale Abstand zwischen den Neuronen einstellen. Als Vorgabe werden
die Abstände der aktuellen Zeichnung verwendet. Erst eine Änderung im Dialog
oder **Standardwerte** erzeugt eine Vorschau. **Abbrechen** stellt alle
ursprünglichen Positionen wieder her.

Die vollständige Anordnung wird als ein gemeinsamer Arbeitsschritt
gespeichert und kann daher mit einmal `Strg+Z` zurückgenommen werden.

Enthält das Netzwerk eine Rückkopplung oder einen gerichteten Zyklus,
können keine eindeutigen Schichten bestimmt werden. Das Programm nennt
in diesem Fall die betroffenen Neuronen und verändert keine Positionen.

---

# Assistent für eigene Projekte

Über **Trainingsdaten → Assistent für eigene Projekte...** oder das Symbol
**Projektassistent** lässt sich ein bearbeitbarer Prompt für eine externe KI
vorbereiten. NeuronNetz stellt dabei selbst keine Verbindung zu einer KI her
und überträgt keine Daten.

Sieben projektunabhängige Auswahlfelder grenzen Ausgangslage, Interesse,
Projektart, Art des Zusammenhangs, Entstehung der Trainingsdaten,
Schwierigkeit und Ausschlüsse ein. Jedes Feld darf auf **Noch nichts
ausgewählt** stehen bleiben. Bei einer vorhandenen Idee, einem eigenen Thema
oder eigenen Ausschlüssen erscheint zusätzlich ein freies Textfeld.

**Prompt erzeugen** erstellt einen weiterhin frei bearbeitbaren Text. Dieser
fordert eine kurze Projektbeschreibung, sinnvolle Inputs und Outputs, einen
begründeten Netzwerkvorschlag sowie passende Trainingsdaten oder einen
Erfassungsplan an. Direkt lieferbare Trainingsdaten sollen ohne Überschriften
und Nummerierung mit echten Tabulatoren zwischen den Spalten ausgegeben
werden. Analoge Werte werden dabei ausdrücklich als unskalierte Rohwerte in
ihren natürlichen Einheiten angefordert; die Skalierung erfolgt später in
NeuronNetz. **Prompt kopieren** übernimmt den fertigen Text in die
Zwischenablage.

Die zuletzt verwendeten sieben Auswahlen werden als Programmeinstellung,
nicht im Projekt, gespeichert. Freie Eingaben und der erzeugte Prompt werden
nicht dauerhaft gespeichert. **Auswahl zurücksetzen** stellt alle Felder
wieder auf **Noch nichts ausgewählt**. Unter **Programmeinstellungen →
Darstellung** kann der Assistent einschließlich Menüeintrag und Symbol
ausgeblendet werden.

KI-Vorschläge und erzeugte Daten müssen fachlich geprüft werden. Simulierte
Daten ersetzen keine realen Messwerte, und NeuronNetz ist nicht für
sicherheitskritische reale Steuerungen vorgesehen.

---

# 16. Trainingsdaten

Der Trainingsdaten- und Testdateneditor einschließlich Spalteneigenschaften,
Skalierung, CSV-Import, Testdatenauswahl und aller Sicherheitsabfragen wird in
der unter **Programmeinstellungen → Sprache** gewählten Programmsprache
angezeigt. Die gespeicherten `.nndata`- und `.nntest`-Dateien selbst bleiben
sprachunabhängig und können deshalb in jeder Oberflächensprache verwendet
werden.

Der Trainingsdateneditor wird geöffnet über:

**Trainingsdaten → Trainingsdaten bearbeiten...**

Trainingsdaten werden unabhängig vom Projekt in einer eigenen Datei gespeichert.

Dateiendung:

```text
.nndata
```

## Aufbau einer Trainingsdatendatei

Eine Trainingsdatendatei enthält:

- Name
- Spalten
- Rollen der Spalten
- Zuordnung der Spalten zu Neuronen
- optionale Kalibrierung der Spalten
- Datensätze

## Spaltentypen

Jede Spalte besitzt eine Rolle:

- Input
- Output

## Datensätze

Jede Tabellenzeile entspricht einem vollständigen Trainingsdatensatz.

Beispiel:

| Input 1 | Input 2 | Output 1 |
|---:|---:|---:|
| 0 | 0 | 0 |
| 0 | 1 | 1 |
| 1 | 0 | 1 |
| 1 | 1 | 0 |

## Tabellendaten aus der Zwischenablage einfügen

Tabellarische Daten können aus der Zwischenablage in den
Trainingsdateneditor übernommen werden. Als Quelle eignen sich zum
Beispiel Tabellenkalkulationen, Webseiten oder andere Programme, die
Zeilen und Spalten als Tabellentext in die Zwischenablage kopieren.

Zum Einfügen dienen das Tastenkürzel `Strg+V` oder der Befehl **Einfügen** im
Kontextmenü der Tabelle. Eine zusätzliche Schaltfläche ist nicht erforderlich.

Vor dem Einfügen prüft der Editor den vollständigen Datenblock. Enthält er mehr
Spalten als ab der markierten Zelle verfügbar sind oder ungültige Zahlenwerte,
wird nichts in die Tabelle übernommen und es bleibt keine zusätzliche oder
teilweise gefüllte Zeile zurück.

Das Einfügen ist nicht an Microsoft Excel gebunden.

## Getrennte Testdaten

Neben den Trainingsdaten kann einem Projekt eine `.nntest`-Datei
als Testdatendatei zugeordnet werden. Sie verwendet dasselbe Spalten-,
Zuordnungs- und Dateiformat wie die Trainingsdaten.

Die Befehle befinden sich im Menü **Trainingsdaten**:

- **Testdaten bearbeiten...**
- **Testdatenzuordnung entfernen**
- **Mit Testdaten testen...**

Die Testdatendatei sollte Datensätze enthalten, die beim Training nicht
verwendet wurden. So lässt sich beurteilen, wie gut das trainierte Netz
auf bisher unbekannte Eingaben reagiert.

Beim erstmaligen Anlegen neuer Testdaten fragt das Programm, was aus den
aktuellen Trainingsdaten übernommen werden soll:

- **Struktur und Skalierung übernehmen** übernimmt Spaltennamen, Rollen,
  Neuronenzuordnungen und alle Kalibrierungswerte. Dies ist die empfohlene
  Einstellung.
- **Nur Struktur übernehmen** übernimmt Spalten und Zuordnungen, setzt die
  Skalierung jedoch zurück.
- **Ohne Übernahme** legt eine unabhängige leere Testdatenstruktur an.

Beim erstmaligen Anlegen der leeren Testdatenstruktur werden noch keine
Trainingsdatensätze kopiert. Die neue Testtabelle bleibt zunächst leer und
kann anschließend manuell gefüllt oder über **Neue Testdaten erzeugen...**
mit ausgewählten Trainingszeilen befüllt werden.

Übernommene Skalierungen sind in der Spaltenüberschrift durch den Zusatz
**(Training)** sowie durch einen Hinweis oberhalb der Tabelle erkennbar.
Liegen Testwerte außerhalb des bei der Min–Max-Skalierung gespeicherten
Trainingsbereichs, wird die Spalte gelb mit **⚠ Außerhalb Trainingsbereich**
gekennzeichnet. Die Werte bleiben zulässig und werden nach derselben Formel
weitergerechnet; sie werden nicht begrenzt.

Weicht die Skalierung einer Testspalte später von der gleich zugeordneten
Trainingsspalte ab, zeigt das Programm vor dem Test eine Warnung. Der Test
kann dann abgebrochen oder bewusst trotzdem ausgeführt werden.

## Testdaten aus Trainingsdaten übernehmen

Im Testdateneditor steht die Schaltfläche
**Neue Testdaten erzeugen...** zur Verfügung. Sie erzeugt
keine erfundenen Zahlen, sondern kopiert ausgewählte vollständige Zeilen in
die Testtabelle. Die aktive Trainingsdatei bleibt vollständig, unverändert
und weiterhin mit dem Projekt verbunden.

Einstellbar sind:

- der Testanteil in Prozent
- eine gleichmäßig über die Tabelle verteilte Auswahl
- eine zufällige Auswahl ohne Zurücklegen
- ein Zufallsstartwert für eine reproduzierbare Auswahl
- **Auswahl neu mischen** für eine andere Zufallsauswahl

Eine Vorschau zeigt vor dem Übernehmen die ursprünglichen Zeilennummern und
Werte. Die Funktion legt stets eine neue, zunächst noch nicht gespeicherte
Testdatenreihe an. Eine zuvor geöffnete und gespeicherte `.nntest`-Datei wird
nicht überschrieben und bleibt erhalten. Ungespeicherte Änderungen werden
vorher wie gewohnt zum Speichern angeboten. Die neue Reihe wird anschließend
unter einem eigenen Namen gespeichert. Eine zusätzliche Trainingskopie wird
nicht erzeugt.

Wurde das Netzwerk mit allen Trainingszeilen trainiert, sind die kopierten
Testfälle dem Netzwerk bereits bekannt. Eine solche Auswertung zeigt, wie gut
das Netzwerk bekannte Trainingsfälle wiedergibt. Sie ist kein unabhängiger
Nachweis der Verallgemeinerung auf neue Daten. Für einen unabhängigen Test
sollten zusätzliche Messwerte verwendet werden, die nicht im Training
enthalten waren.

---

# 17. Trainingsdaten zuordnen

Jede Input- und Output-Spalte muss genau einem passenden Neuron zugeordnet sein.

## Spalteneigenschaften öffnen

Mit der rechten Maustaste auf eine Spaltenüberschrift klicken.

Danach:

**Spalteneigenschaften...**

## Einstellbare Spalteneigenschaften

- Spaltenname
- optionale Einheit der Rohwerte, zum Beispiel `km/h`, `s`, `m` oder `°C`
- Typ
- Datenart **Analog** oder **Binär**
- zugeordnetes Neuron
- Kalibrierung beziehungsweise Skalierung

Wird der Spaltenname mit **OK** übernommen, erhält das zugeordnete Input- oder
Output-Neuron denselben Namen. Eine Umbenennung des Neurons im Eigenschaftsbereich
wird umgekehrt in zugeordnete Trainings- und Testdatenspalten übernommen.
Neuronennamen müssen eindeutig sein.

Die Einheit ist nur eine verständliche Beschriftung. Sie verändert die
Berechnung nicht. Das Programm zeigt sie unter anderem in den
Tabellenüberschriften, bei der Vorwärtsberechnung sowie an den äußeren Ein- und
Ausgabefeldern der Neuronen an.

Bei automatisch angelegten Namen wie **Input 1** oder **Output 1** übernimmt das
Programm nach der Zuordnung den Namen des gewählten Neurons. Ein selbst
eingetragener Spaltenname bleibt erhalten und wird nicht automatisch
überschrieben.

Binäre Spalten erlauben ausschließlich `0` und `1` und benötigen keine
Skalierung. Beim Umschalten einer vorhandenen Spalte auf **Binär** weist das
Programm auf abweichende Tabellenwerte hin, ohne sie automatisch zu verändern.
Analoge Spalten verwenden die bisherigen Zahlen- und Skalierungsfunktionen.
Die Tabellenüberschrift kennzeichnet die Datenart mit `● Binär` oder
`∿ Analog`. Ältere Datendateien werden weiterhin als analog behandelt.

## Binäre Eingänge als zweidimensionales Array

Sind alle Eingangsspalten binär, bietet die manuelle Vorwärtsberechnung
**Eingabe-Array definieren...** an. Der Button öffnet einen eigenen
Zuordnungsdialog. Zeilen und Spalten werden vorgegeben; anschließend
wird jeder binäre Eingang genau einem Rasterfeld zugeordnet. Die automatisch
erzeugte Standardsortierung kann in jedem Feld geändert werden. Eine
Muster-Visualisierung zeigt den aktuell gewählten Trainingsdatensatz, mit
**Zurück** und **Weiter** kann durch alle Datensätze geblättert werden. Unter
dem Raster stehen die zugehörigen Sollausgänge; bei einer binären
Klassifikation werden die aktiven Sollausgänge besonders eindeutig genannt.

Die Array-Definition wird optional in der Trainingsdatendatei gespeichert.
Ältere Dateien und Projekte ohne Array bleiben vollständig kompatibel. In der
Vorwärtsberechnung erscheint bei vorhandener Definition zusätzlich
**Rasteransicht anzeigen** und **Array bearbeiten...**. Dort schaltet ein Klick auf ein Feld den
zugeordneten Binäreingang und berechnet das Ergebnis sofort neu. Mit
**Listenansicht anzeigen** geht es zur gewohnten Eingabetabelle zurück.

## Kalibrierung einer Datenspalte

In den **Spalteneigenschaften** kann für jede Input- und Output-Spalte
einzeln festgelegt werden:

- keine Skalierung
- Min–Max-Skalierung auf 0 bis 1
- Min–Max-Skalierung auf −1 bis +1
- Standardisierung über Mittelwert und Standardabweichung

Beim Verweilen über einem Eintrag der Verfahrensliste erklärt ein Tooltip kurz
den Zweck: Rohdaten unverändert übernehmen, auf `0 … 1` für Sigmoid oder auf
`−1 … +1` für Tanh abbilden beziehungsweise per Z-Score um Mittelwert null
standardisieren.

Minimum, Maximum, Mittelwert und Standardabweichung können manuell
eingetragen oder mit **Aus Tabellendaten ermitteln** aus der betreffenden
Spalte übernommen werden. Eine Vorschau zeigt die Umrechnung eines
eingegebenen Rohwertes in den späteren Netzwert.

## Alle Trainingsspalten automatisch skalieren

Mit **Automatisch skalieren nach Tabellendaten** wertet das Programm alle
Trainingsspalten gemeinsam aus. Für jede geeignete Spalte werden der kleinste
und größte endliche Tabellenwert als Rohwertbereich übernommen. Inputspalten
und gewöhnliche Outputspalten erhalten eine Min–Max-Skalierung auf 0 bis 1.
Ist eine Outputspalte einem Tanh-Neuron zugeordnet, wird stattdessen automatisch
auf −1 bis +1 skaliert.

Spalten ohne gültige Zahlenwerte und konstante Spalten, bei denen Minimum und
Maximum gleich sind, werden übersprungen. Eine grüne Statuszeile nennt danach
die Anzahl der skalierten und übersprungenen Spalten; die Namen übersprungener
Spalten stehen im Tooltip. Es erscheint keine Bestätigungsabfrage.

Der Button ist nur im Trainingsdateneditor sichtbar. Testdaten müssen dieselbe
Skalierung wie die Trainingsdaten verwenden und werden deshalb weiterhin aus
den Trainingsdaten übernommen. Die Rohwerte der Tabelle, Spaltennamen,
Einheiten und Neuronzuordnungen bleiben unverändert.


Der Skalierungszustand wird direkt in jeder Spaltenüberschrift angezeigt.
Beispiele sind **↔ Skaliert: −1 … +1**, **↔ Standardisiert** und
**Unskaliert: 0 … 1**. Unskalierte Spalten, deren Rohwerte außerhalb von
−1 bis +1 liegen, erhalten einen gelben Warnhinweis mit Wertebereich, zum
Beispiel **⚠ Unskaliert: 11.723 … 161.743**. Der Tooltip enthält weitere
Einzelheiten.

Die Tabelle und die Datendatei behalten weiterhin die ursprünglichen
Rohwerte. Beim Training und bei der Vorwärtsberechnung mit Datensätzen werden
Inputwerte und Output-Sollwerte automatisch in den eingestellten Netzbereich
umgerechnet. Angezeigte Istwerte und Fehler im Netztest werden anschließend
wieder in die ursprünglichen Rohwerte zurückgerechnet.

Trainings- und Testdaten müssen für gleich zugeordnete Spalten dieselben
Kalibrierungswerte verwenden. Werte außerhalb des gespeicherten Rohbereichs
werden entsprechend der festgelegten Formel weitergerechnet und nicht
automatisch begrenzt.

Der im Trainingsfenster angezeigte mittlere Epochenfehler bezieht sich bei
kalibrierten Output-Spalten auf die internen skalierten Netzwerte. Der
Netztest zeigt Sollwert, Istwert und Fehler dagegen in den ursprünglichen
Rohwerten an.

## Statusfarben

Die Spaltenüberschrift zeigt den Zuordnungsstatus.

### Grün

Zuordnung ist gültig.

### Rot

Spalte ist nicht zugeordnet oder doppelt zugeordnet.

### Orange

Die gespeicherte Zuordnung ist ungültig oder das Neuron wurde nicht gefunden.

Beim Öffnen versucht der Editor veraltete Zuordnungen automatisch zu
reparieren. Stimmen die Anzahlen der Input- beziehungsweise Output-Spalten mit
dem Netzwerk überein, werden zuerst ID und Name und anschließend die eindeutige
Reihenfolge verwendet. Eine reparierte Datendatei wird als geändert markiert.

### Grau

Die Zuordnung ist gültig und die unskalierte Spalte besitzt bereits einen
kleinen Wertebereich innerhalb von −1 bis +1.

### Gelb

Die Zuordnung ist gültig, aber die Spalte ist bei einem auffälligen
Rohwertbereich nicht skaliert. Die Skalierung sollte vor dem Training geprüft
werden.

## Voraussetzungen für Training

- jede Input-Spalte ist genau einem Input-Neuron zugeordnet
- jede Output-Spalte ist genau einem Output-Neuron zugeordnet
- alle Input-Neuronen sind zugeordnet
- alle Output-Neuronen sind zugeordnet

---

# 18. Training starten

Das Training wird geöffnet über:

**Netzwerk → Mit Trainingsdaten trainieren...**

Vor dem Öffnen des Trainingsdialogs prüft das Programm:

- Netzwerkstruktur
- vorhandene Trainingsdaten
- Spaltenzuordnungen
- Neuronentypen
- vorhandene Datensätze

Das Training kann nur gestartet werden, wenn das Netzwerk gültig ist.

Im Bereich **Trainingsdaten** zeigt der Dialog vor dem Start außerdem kompakt
die Netzstruktur, die Anzahl der Gewichte und Bias-Werte, alle trainierbaren
Parameter sowie eine Schätzung der Verbindungsoperationen je Epoche. Die
Vorwärtsrechnung zählt eine Operation je Gewicht und Datensatz. Für das gesamte
Training werden Vorwärtsrechnung, Rückwärtsrechnung und Parameteränderung mit
ungefähr dem Dreifachen abgeschätzt. Die Anzeige wird nur einmal beim Öffnen
berechnet und verlangsamt das Training nicht.

Nach einem abgeschlossenen oder gestoppten Trainingslauf erscheint direkt
darunter die geschätzte Gesamtzahl der Trainingsoperationen. Bei einem Stopp
werden nur die bis dahin tatsächlich bearbeiteten Datensätze berücksichtigt.

Unskalierte Trainingsspalten mit Rohwerten außerhalb von −1 bis +1 verhindern
das Training nicht. Beim Öffnen des Trainingsfensters erscheint jedoch ein
gelber Hinweis mit Spaltenname, zugeordnetem Neuron und festgestelltem
Wertebereich. Binäre Spalten mit Werten von 0 bis 1 erzeugen keinen Hinweis.

Sind die Sollwerte eines binären Outputs stark unausgeglichen, beispielsweise
31-mal **Aus** und nur einmal **Ein**, erscheint ebenfalls ein gelber Hinweis.
Das Training wird dadurch nicht blockiert. Der Hinweis macht darauf aufmerksam,
dass ein kleiner mittlerer Fehler die seltene Klasse verdecken kann und deshalb
auch der maximale Einzelfehler sowie der Netztest geprüft werden sollten.

Bei mehreren betroffenen Outputs kann dieser ausführliche Hinweis ein- und
ausgeklappt werden, damit er nicht den übrigen Inhalt des Trainingsfensters
verdrängt.

Wenn sich während eines längeren Abschnitts sowohl der mittlere Epochenfehler
als auch der maximale Einzelfehler kaum noch verbessern, weist das Fenster auf
ein mögliches Plateau hin. Das Programm ändert dabei weder Lernrate noch
Gewichte automatisch und bricht das Training nicht ab. Der Hinweis bleibt
lesbar, bis er mit **×** geschlossen oder ein neuer Trainingslauf begonnen
wird. Beim Fortsetzen desselben Laufes bleibt ein geschlossener Hinweis aus.

---

# 19. Trainingsparameter

## Netzwerk vor Trainingsbeginn neu initialisieren

Ist diese Option aktiviert, werden Gewichte und Bias vor dem Trainingsstart neu gesetzt.

Ohne Haken wird auf dem vorhandenen Lernstand weitertrainiert.

## Gewichtsinitialisierung

### Xavier/Glorot

Empfohlene Initialisierung mit zufälligen Startwerten.

### Alle Gewichte = 0

Nur für besondere Tests geeignet.

Bei mehrschichtigen Netzen können ausschließlich nullwertige Gewichte das Lernen blockieren.

## Bias-Initialisierung

### Bias = 0

Empfohlene Grundeinstellung.

### Bias zufällig nach Xavier/Glorot

Kann bei bestimmten Aufgaben helfen, symmetrische Zustände zu vermeiden.

## Lernrate

Bestimmt die Größe der Gewichtsänderungen.

Typische Startwerte:

```text
0.001
0.01
0.05
0.1
```

Eine zu große Lernrate kann zu instabilem Lernen führen.

Eine zu kleine Lernrate kann das Training stark verlangsamen.

## Momentum

Momentum übernimmt einen Anteil der vorherigen Gewichts- oder Bias-Änderung in
den nächsten Lernschritt. Dadurch kann das Training gleichmäßiger und schneller
in eine günstige Richtung laufen.

- **0** schaltet Momentum vollständig aus und erhält das bisherige Trainingsverhalten.
- Werte zwischen **0,5** und **0,9** eignen sich zum vorsichtigen Ausprobieren.
- Sehr hohe Werte können zu Überschwingen oder schwankendem Fehler führen.

Ein neuer Trainingslauf beginnt immer mit Momentumzuständen von null. Beim
Fortsetzen eines Laufes werden die zu jeder Verbindung und jedem Bias
gespeicherten Zustände übernommen. Lernrate und Momentum gehören deshalb fest
zum begonnenen Lauf.

## Fehlergrenze

Bei **Bis Fehlergrenze** wird das Training beendet, sobald der mittlere Epochenfehler kleiner oder gleich der eingestellten Grenze ist.

Beispiel:

```text
0.01
```

## Maximale Epochen

Begrenzt die maximale Trainingsdauer.

Beispiel:

```text
20000
```

## Ausführung mit und ohne Live-Monitoring

Die mathematische Trainingsrechnung ist in beiden Fällen identisch. Der
wesentliche Geschwindigkeitsunterschied entsteht durch die grafische
Darstellung:

- Mit **Daten monitoren** werden Netzwerkwerte, Gewichte und die sichtbare
  Netzwerkansicht während des Trainings regelmäßig aktualisiert.
- Ohne **Daten monitoren** bleibt das Netzwerk eingefroren. Ergebnisfelder,
  Epochenzähler, Zeit und Fehlerkurve im Trainingsfenster laufen dennoch weiter.

Ohne Live-Monitoring müssen Neuronen, Verbindungen, Eigenschaftenfenster und
Zeichenfläche nicht fortlaufend neu gezeichnet werden. Besonders bei großen
Netzen kann das Training dadurch deutlich schneller werden. Die Gewichte und
Bias-Werte werden selbstverständlich trotzdem trainiert.

Mit **Trainingshistorie...** wird dieselbe Trainingshistorie wie über
das Netzwerkmenü geöffnet. Ein kompatibler gespeicherter Zustand stellt
Gewichte und Bias-Werte wieder her. Die damalige Datendatei ist dafür nicht
erforderlich; zum Weitertrainieren werden aktuelle Trainingsdaten benötigt.

Beim Öffnen zeigt das Trainingsfenster automatisch den aktiven Trainingslauf
der aktuell zugeordneten Trainingsdatendatei mit Ergebniswerten und
Fehlerkurve. Nach dem Wiederherstellen eines Laufs in der Trainingshistorie
gilt dieser als aktiv. Ist kein passender Lauf vorhanden, bleibt die
Ergebnisanzeige leer. Läufe anderer Trainingsdatendateien werden nicht
angezeigt.

## Daten monitoren

Mit der Option **Daten monitoren** wird gesteuert, ob die grafische Netzwerkdarstellung während des Trainings aktualisiert wird.

### Aktiviert

- Gewichte ändern sich sichtbar
- Neuronenwerte werden aktualisiert
- Training läuft langsamer

### Deaktiviert

- Netzwerkdarstellung bleibt während des Trainings eingefroren
- Training läuft schneller
- Ergebnisfelder werden weiterhin aktualisiert
- Stop-Schaltfläche bleibt funktionsfähig
- auch nach einem einzelnen Trainingsabschnitt bleibt die Darstellung
  eingefroren
- beim erneuten Einschalten von **Daten monitoren** erscheint sofort der
  aktuelle Netzstand
- spätestens beim Schließen des Trainingsfensters wird die Darstellung
  abschließend aktualisiert

## Fehlerkurve anzeigen

Mit **Fehlerkurve während des Trainings anzeigen** wird gesteuert,
ob der mittlere Epochenfehler als Diagramm dargestellt wird.

### Aktiviert

- die Fehlerkurve wächst während des Trainings von links nach rechts
- die X-Achse zeigt die Epoche
- die Y-Achse zeigt den mittleren Epochenfehler (MSE)
- die eingestellte Fehlergrenze erscheint als gestrichelte Linie
- die Kurve bleibt nach dem Trainingsende sichtbar

Über der Grafik kann die Y-Achse umgeschaltet werden:

- **Linear** ist die normale und leicht verständliche Darstellung.
- **Logarithmisch** macht Unterschiede über viele Größenordnungen
  sichtbar und kann bei sehr kleinen Fehlerwerten hilfreich sein.

Standardmäßig wird die lineare Darstellung verwendet. Die gewählte
Darstellung wird mit dem Projekt gespeichert. Unter der Grafik stehen
der Fehler zu Beginn des Trainingslaufes und der aktuelle Fehler. Das Training und die Fehlerberechnung
selbst werden durch die gewählte Darstellung nicht verändert.

Der Fehlerwert jeder Epoche wird für die Kurvenform erfasst. Die sichtbare
Anzeige wird jedoch auf höchstens zehn Neuzeichnungen pro Sekunde begrenzt.
Dadurch bleiben auch kurze und stark gekrümmte Lernverläufe erhalten, ohne das
Training bei jeder einzelnen Epoche durch ein Neuzeichnen zu unterbrechen.

### Deaktiviert

- das Diagramm bleibt ausgeblendet
- die Fehlerwerte jeder Epoche werden unsichtbar weiter erfasst
- beim erneuten Einschalten erscheint sofort der vollständige bisherige Verlauf
- kompakte Messpunkte für die Trainingshistorie werden weiterhin gespeichert
- das Training erhält keinen Aufwand durch sichtbare Neuzeichnungen

Der Haken kann auch während eines laufenden oder angehaltenen Trainings geändert
werden. Das Ein- und Ausblenden unterbricht den Trainingslauf nicht.

---

# 20. Training beobachten

Im Ergebnisbereich werden angezeigt:

- mittlerer Epochenfehler mit festem Startwert und laufend aktualisiertem Wert
- ausgeführte Epochen
- maximaler Einzelfehler
- Zeit seit Start
- Status

Wenn die Option **Fehlerkurve während des Trainings anzeigen**
aktiviert ist, erscheint unter dem Ergebnisbereich zusätzlich der
Fehlerverlauf des aktuellen Trainingslaufes.

## Zeit seit Start

Die Trainingszeit wird in Sekunden angezeigt.

Beispiel:

```text
18.2 s
```

## Trainingsschaltflächen

Die eingerahmte Gruppe **Trainingsziel** zeigt mit klassischen Optionsfeldern,
dass genau eine von drei Alternativen gewählt wird:

- **1 Epoche** trainiert genau eine weitere Epoche.
- **Anzahl** verwendet die im zugehörigen Zahlenfeld eingestellte Epochenzahl
  (Vorgabe 1000). Das Feld ist nur bei dieser Auswahl aktiv.
- **Bis Fehlergrenze** trainiert bis zur Fehlergrenze oder bis zur maximalen
  Gesamtepochenzahl – je nachdem, was zuerst erreicht wird.

Das zuletzt gewählte Trainingsziel wird mit dem Projekt gespeichert.

Die danebenliegende, gleich hohe Gruppe **Training steuern** enthält die
eigentlichen Befehle. Beide Gruppen sind links und rechts bündig mit den
Bereichen darüber. **Neues Training starten** beginnt einen neuen Lauf,
**Fortsetzen** führt den bisherigen Lauf mit fortlaufender Kurve und
Epochenzählung weiter. **Stoppen** hält den laufenden Abschnitt
kontrolliert an. Der Info-Button steht mit diesen drei Befehlen in einer Zeile.

Die linke Seite ist in drei Bereiche gegliedert:

- **Nur für einen neuen Trainingslauf** enthält die Initialisierung von
  Gewichten und Bias. Diese Einstellungen werden beim Fortsetzen immer ignoriert.
- **Trainingsparameter** enthält Lernrate, Momentum, Fehlergrenze und maximale Epochen.
- **Ausführung und Anzeige** enthält die Live-Aktualisierung des Netzwerks und
  die Anzeige der Fehlerkurve. Ist **Daten monitoren** ausgeschaltet, bleibt die
  Netzwerkansicht eingefroren und das Training läuft ohne diese zusätzliche
  grafische Aktualisierung schneller weiter.

Kleine **i**-Schaltflächen öffnen kurze Erklärungen zu den jeweils
zusammengehörenden Funktionen. Ein gemeinsamer Hinweis erläutert die
Neuinitialisierung einschließlich Xavier/Glorot und Bias, ein weiterer die
Ausführungs- und Anzeigeoptionen. Zusätzliche Hinweise erklären den
Fehlerverlauf, die Trainingsziele, die Trainingssteuerung sowie die gemeinsame
Zeile für Auswertung und weitere Funktionen. Die Fenster
verändern weder Einstellungen noch den Trainingszustand. Alle Hinweise öffnen
sich ohne Windows-Meldeton als schlanke Dialoge mit hellgelbem Textbereich und
einer eindeutigen Schaltfläche **Schließen**. Dasselbe Erscheinungsbild wird
auch für die Detailanzeige des maximalen Einzelfehlers verwendet.

Lernrate und Momentum gehören fest zum aktuellen Lauf. Wurde einer dieser Werte
nachträglich geändert, bietet **Fortsetzen** an, beide ursprünglichen Werte
wiederherzustellen, oder den Vorgang abzubrechen. Für andere Werte muss ein
neuer Lauf gestartet werden. Fehlergrenze und maximale Epochen dürfen vor dem
Fortsetzen angepasst werden.

## Stopp

Mit **Stoppen** wird der aktuelle Trainingsabschnitt nach dem laufenden
Verarbeitungsschritt kontrolliert beendet. Danach sind **Fortsetzen**,
**Erproben...**, **Test und Analyse...**, **Training debuggen...**,
**Trainingshistorie...** und **Schließen** wieder verfügbar. Diese vier
weiterführenden Funktionen stehen in einer gemeinsamen einzeiligen Leiste;
der anschließende Info-Button erklärt sie zusammen. Nach einer Trennlinie
schließt **Schließen** ganz rechts das Trainingsfenster.

**Erproben...** öffnet nach einem gestoppten oder regulär beendeten
Trainingslauf dasselbe Erprobungsfenster wie **Netzwerk → Netzwerk
erproben...**. Es verwendet den aktuellen trainierten Netzstand und ist
während des Trainings sowie vor dem ersten Trainingslauf deaktiviert.

**Fortsetzen** führt denselben Trainingslauf mit den vorhandenen Gewichten,
Bias-Werten, Momentumzuständen sowie der ursprünglichen Lernrate und dem
ursprünglichen Momentum weiter. Die Epochenzählung und die vorhandene Fehlerkurve werden
fortgeführt; es entsteht kein zusätzlicher Eintrag in der Trainingshistorie.
Bei **1 Epoche** oder einer festen Epochenzahl gilt die Fehlergrenze nicht als
vorzeitiges Ende. Bei **Bis Fehlergrenze** bestimmen Fehlergrenze und maximale
Gesamtepochenzahl das Ende.
Die Zeit zwischen zwei Abschnitten zählt nicht zur Trainingsdauer.

## Kompaktansicht

Alle Beschriftungen, Statusmeldungen und Diagrammtexte des Trainingsfensters
folgen der unter **Programmeinstellungen → Sprache** gewählten Sprache. Das
gilt für Vollansicht, Kompaktansicht und minimierte Ansicht. Mathematische
Fachbegriffe wie MSE, Xavier/Glorot, Bias, Sigmoid und Tanh bleiben als
eindeutige Bezeichnungen unverändert.

Mit **Kompaktansicht** lässt sich das Trainingsfenster jederzeit auf
einen kleinen Trainingsmonitor reduzieren. Das ist auch während eines
laufenden oder angehaltenen Trainings möglich.

In der Kompaktansicht bleiben sichtbar:

- **Netzwerkmonitor: Ein/Aus** zum sofortigen Umschalten der sichtbaren
  Netzwerkaktualisierung
- Fehlerkurve und Umschaltung der Y-Achse
- ein zweizeiliges hellblaues Statusfeld mit Epoche, Trainingszeit,
  Status, Startfehler und aktuellem Fehler
- Schaltflächen für einen neuen Lauf
- **Stoppen** und **Fortsetzen** für den aktuellen Lauf

Trainingsdaten, Initialisierung, Parameter, ausführliche Ergebnisfelder
sowie Test- und Debugfunktionen werden nur vorübergehend ausgeblendet.
Das Netzwerk hinter dem Dialog bleibt dadurch weitgehend sichtbar und
kann bei eingeschalteter Live-Aktualisierung weiter beobachtet werden.

Mit **Vollansicht** kehrt das Fenster zu seiner vorherigen Größe und
Position zurück. Der Trainingslauf und die Fehlerkurve werden durch den
Ansichtswechsel nicht verändert.

Mit **Minimieren** wird das Trainingsfenster zu einer schmalen, einzeiligen
Steuerung über der Netzwerkansicht. Sichtbar bleiben:

- Nummer des aktuellen Trainingslaufs
- tatsächlich ausgeführte Epoche
- laufende beziehungsweise gesamte Trainingszeit
- gewähltes Trainingsziel: eine Epoche, feste Epochenzahl oder Fehlergrenze
- **Live** als direkter Schalter für **Daten monitoren**
- **Neu**, **Fortsetzen** und **Stoppen**
- **Voll** und **Kompakt** zum Wechsel in die größeren Ansichten

Die drei Trainingsschaltflächen sind keine getrennten Funktionen. Sie lösen
exakt dieselben Befehle wie die gleichnamigen Schaltflächen der Vollansicht
aus. Vor dem ersten Lauf ist nur **Neu** verfügbar. Nach einem abgeschlossenen
Abschnitt wird **Fortsetzen** aktiv. Ist als Ziel **1 Epoche** gewählt, führt
jeder Klick auf **Fortsetzen** genau eine weitere Epoche desselben Laufs aus.
Während das Training rechnet, ist **Stoppen** aktiv.

Die Minimalansicht ist besonders geeignet, wenn das Netzwerk hinter dem
Fenster beobachtet werden soll. Ist **Live** deaktiviert, bleibt die sichtbare
Netzwerkdarstellung eingefroren und das Training benötigt weniger Zeit für
grafische Aktualisierungen. Epoche, Zeit und Fehlerkurve werden davon nicht
verfälscht.

Die Kompaktansicht kann in der Höhe nur so weit verkleinert werden, dass
Fehlerkurve, Achsenskalierung und Trainingsschaltflächen vollständig sichtbar
bleiben.

Der Schalter **Netzwerkmonitor** der Kompaktansicht und **Live** in der
Minimalansicht entsprechen dem Haken **Daten monitoren** der Vollansicht. Alle
drei bleiben synchron. Bei ausgeschaltetem Monitor läuft das Training
unverändert weiter. Die dahinterliegende Netzwerkdarstellung bleibt bis zum
erneuten Einschalten oder bis zum Schließen des Trainingsfensters eingefroren.

Der Haken und der Schalter bleiben auch während eines laufenden oder
angehaltenen Trainings bedienbar. Beim erneuten Einschalten wird die
Netzwerkdarstellung sofort auf den aktuellen Trainingsstand gebracht und
anschließend wieder live aktualisiert.

## Editor während des Trainings bedienen

Das Trainingsfenster ist ein nicht-modales Werkzeugfenster. Es bleibt über
dem Hauptfenster sichtbar, während der grafische Editor mit der Maus bedient
werden kann. Das gilt sowohl während eines laufenden als auch während eines
angehaltenen Trainings.

Der Tastaturfokus wird nicht automatisch zwischen Trainingsfenster und Editor
verschoben. Für den Handmodus ist trotzdem kein vorheriger Fokus-Klick nötig:
**Alt gedrückt halten und unmittelbar mit der linken Maustaste auf der
Zeichenfläche ziehen**. Der Handmodus wird direkt aus diesem Mausereignis
erkannt und funktioniert bei geöffneter Vollansicht und Kompaktansicht.

Im Editor sind dabei möglich:

- Zeichenfläche vergrößern und verkleinern
- sichtbaren Ausschnitt verschieben
- Neuronen, Verbindungen und Kommentare auswählen
- Neuronen und Kommentare räumlich verschieben
- Werte im Eigenschaftenfenster beobachten

Damit das laufende Training nicht versehentlich verändert oder einem anderen
Projekt zugeordnet wird, sind währenddessen strukturelle und mathematische
Änderungen gesperrt. Dazu gehören insbesondere das Erzeugen oder Löschen von
Objekten und Verbindungen, Datei- und Projektwechsel, Rückgängig/Wiederholen,
Eigenschaftsänderungen sowie weitere Trainings-, Test- und Mathematikbefehle.

Nach dem Schließen des Trainingsfensters stehen alle Befehle wieder normal zur
Verfügung. Verschobene Neuronen und Kommentare behalten ihre neue Position und
können anschließend mit dem Projekt gespeichert werden.

---

# 21. Test und Analyse

Das vollständige Analysefenster kann auf zwei Wegen geöffnet werden:

- im Trainingsdialog über **Test und Analyse...**
- direkt über **Netzwerk → Netzwerk testen...** oder das Symbol **Testen**
  in der Werkzeugleiste

Beide Wege öffnen dasselbe Fenster mit **Datensatzvergleich**, **Fehlerauswertung**,
**Soll-Ist-Diagramm**, **Toleranzprüfung** und **Einflussanalyse**. Dabei werden
die zugeordneten Daten mit dem aktuellen Netzwerk ausgewertet, ohne Gewichte
oder Bias-Werte zu verändern.

Das Ergebnisfenster verwendet kompakte, am Inhalt ausgerichtete Spalten. Die
Fehlerspalte wird nicht über die restliche Fensterbreite gestreckt, sodass das
Fenster insbesondere bei Netzen mit einem Ausgang deutlich schmaler bleibt.

Angezeigt werden unter anderem:

- Eingangswerte
- Sollwert
- Istwert
- Fehler

Damit lässt sich prüfen, ob das Netz die Trainingsaufgabe tatsächlich korrekt löst.

## Mit getrennten Testdaten testen

Über **Trainingsdaten → Mit Testdaten testen...** wird die dem Projekt
zugeordnete Testdatendatei ausgewertet. Auch hierbei findet ausschließlich
eine Vorwärtsberechnung statt. Gewichte und Bias-Werte werden nicht verändert.

Zusätzlich zu Sollwert, Istwert und Fehler zeigt die Gesamtauswertung:

- Anzahl der Testdatensätze
- mittleren quadratischen Fehler (MSE)
- mittleren absoluten Fehler
- maximalen absoluten Einzelfehler
- bei binären Sollwerten die Anzahl korrekt klassifizierter Ausgaben

Im **Soll-Ist-Diagramm** eines binären Outputs teilen Linien bei Sollwert 0,5
und Istwert 0,5 die Darstellung in vier Quadranten (Entscheidungsbereiche): **richtig
Aus**, **fälschlich Ein**, **fälschlich Aus** und **richtig Ein**. Blaue Punkte
kennzeichnen richtige, rote Punkte falsche Zuordnungen. Beim Zeigen auf einen
Punkt erscheinen Datensatznummer, Sollwert und Istwert; ein Klick wechselt bei
binären Outputs nicht in den Datensatzvergleich.

---

# 22. Training debuggen

Fensterbeschriftungen, Schaltflächen und der vollständige Rechenbericht des
Trainingsdebuggers folgen der gewählten Programmsprache. Mathematische
Variablen und Symbole wie Σ, Y, δ, ΔW und MSE bleiben unverändert.

Im Trainingsdialog befindet sich die Schaltfläche:

**Training debuggen...**

Der Trainings-Debugger untersucht einzelne Trainingsschritte sehr detailliert.

Angezeigt werden:

- Eingabewerte
- Vorwärtsberechnung
- Summenwerte
- Ausgangswerte
- Fehler
- Deltas
- Rückwärts-Summen
- Aktivierungsableitungen
- Gewichtsänderungen
- Bias-Änderungen
- Ergebnis vor und nach der Änderung

Zusätzlich kann der Zustand beim Öffnen des Debuggers wiederhergestellt werden.

Der Debugger eignet sich besonders zur Fehlersuche bei Netzen, die nicht lernen.

---

# 23. Netzwerk erproben

Der Menüpunkt befindet sich unter:

**Netzwerk → Netzwerk erproben...**

Dabei wird das aktuelle Netzwerk einmal vollständig berechnet.

Sind vollständig zugeordnete Trainingsdaten geladen, öffnet sich das Fenster
**Netzwerk erproben**. Das gilt auch, wenn keine Spalte
skaliert ist. Dort werden die Inputs als verständliche Rohwerte eingegeben. Daneben
zeigt das Programm unmittelbar die daraus berechneten internen X-Werte. Ohne
Skalierung sind Rohwert und interner Wert identisch. Die Eingabe- und
Ausgabezeilen tragen die Namen der
zugeordneten Neuronen. Zahlenfelder blenden überflüssige Endnullen aus, ohne
die Rechengenauigkeit zu verringern. Ist in den Spalteneigenschaften eine
Einheit eingetragen, wird sie bei den Rohwerten ebenfalls angezeigt.

Jede abgeschlossene Änderung eines analogen Eingabefeldes wird sofort
berechnet. Binäre Eingänge besitzen einen anklickbaren Ein-/Aus-Schalter und
reagieren unmittelbar auf jeden Mausklick; eine zusätzliche Berechnungstaste
ist deshalb nicht nötig. Enter übernimmt einen manuell eingegebenen Wert und
lässt das Fenster geöffnet. Die Schrittweite der Pfeiltasten wird aus den
Abständen der vorhandenen Trainingswerte dieser Spalte abgeleitet; bei
positiven ganzen Trainingswerten beträgt sie eins. Analoge Eingänge besitzen
zusätzlich einen synchronen Schieberegler. Der
zulässige Rohwertbereich reicht exakt vom kleinsten bis zum größten
Trainingswert und wird im Fenster angezeigt. Kleinere und größere Eingaben
sind unabhängig von der Skalierung nicht möglich. Für jeden Output zeigt das
Fenster:

- den in die ursprüngliche Einheit zurückgerechneten Rohwert
- den internen Y-Wert des Netzes
- die verwendete Skalierung
- bei binären Ausgängen zusätzlich `● Ein` oder `○ Aus`; dabei gilt
  `Y > 0,5` als Ein, sonst Aus

Auf den Neuronen im Editor bleiben weiterhin die internen X-, Summen- und
Y-Werte sichtbar. Bei binären Ein- und Ausgängen erscheint dort neben dem
kontinuierlichen Zahlenwert ebenfalls das gut erkennbare Zustandssymbol.
Gewichte und Bias-Werte werden durch die Berechnung nicht verändert.

**Beschreibung...** zeigt die Projektbeschreibung. **Testauswertung...**
öffnet zur Information das Fenster **Netzwerk mit Trainingsdaten testen**.
Nach dem Schließen werden die zuletzt eingestellten Eingaben und Ergebnisse
der manuellen Vorwärtsberechnung wieder angezeigt.

Bei binären Ausgängen werden nur die zusammengehörenden Soll- und Ist-Zellen
einer Fehlklassifikation rot hinterlegt. Korrekte Ergebnisse und die übrigen
Zellen der Zeile bleiben neutral. Die Zusammenfassung nennt zusätzlich die
korrekten und fehlerhaften Datensätze. Mit **Nur fehlerhafte Datensätze
anzeigen** lassen sich die korrekten Zeilen vorübergehend ausblenden. Analoge
Ergebnisse und die vollständigen Zahlenwerte bleiben unverändert verfügbar.

Analoge Ausgänge sind wie die Eingänge gegliedert. Neben Roh- und Y-Wert stehen
Skalierung, Trainingsdatenbereich und ein nicht bedienbarer Ergebnisbalken.
Eine farbige LED zeigt, wie gut die aktuelle Kombination der Eingaben durch
ähnliche Trainingsfälle gestützt wird. Sie ist keine Sollwertanzeige und kein
Beweis für die Richtigkeit des Ergebnisses. Der Info-Button neben **Anzeige**
erläutert die Farben. Binäre Ausgänge zeigen an derselben Stelle weiterhin
`● Ein` oder `○ Aus`. Intern wird stets mit voller Genauigkeit gerechnet.

Welche Darstellung verwendet wird, richtet sich ausschließlich nach der in
den Trainingsdaten gespeicherten **Datenart**. Einheit, Spaltenname und die
zufällige Wertemenge entscheiden nicht darüber. Sobald mindestens eine
binäre Spalte vorhanden ist, kann unten mit **Zwischenwerte anzeigen** in eine
experimentelle Ansicht gewechselt werden. Dort erhalten binäre Eingänge und
Ausgänge Regler von 0 bis 1. **Binäransicht anzeigen** kehrt zu den
Ein-/Aus-Schaltern und Entscheidungen zurück. Analoge Spalten bleiben beim
Umschalten unverändert. Ein Hinweis kennzeichnet die Zwischenwerte deutlich
als Experiment außerhalb der regulären binären Trainingsfälle.

Das Fenster kann in der Breite verändert werden. Lange Dateipfade werden
gekürzt angezeigt und erscheinen vollständig als Tooltip. Die zuletzt
verwendete Fensterbreite wird beim nächsten Öffnen wiederhergestellt.

Alle Beschriftungen, Skalierungsangaben, Status- und Fehlermeldungen dieses
Fensters folgen der gewählten Programmsprache.

Sind keine Trainingsdaten geladen oder sind deren Spalten nicht vollständig
dem Netzwerk zugeordnet, bleibt die direkte Vorwärtsberechnung erhalten. Dann
stammen die Input-Werte aus den Eigenschaften der Input-Neuronen.

Die Ergebnisse der Output-Neuronen werden anschließend angezeigt.

## Anwendungsansicht

Die **Anwendungsansicht** ist eine eigenständige, projektbezogene
Bedienoberfläche für das trainierte Netzwerk. Sie übersetzt Zahlenwerte in
eine anschauliche praktische Anwendung: Eingabewerte werden direkt verändert,
während Anzeigen, Schalter und Zeiger die Reaktion des Netzwerks unmittelbar
sichtbar machen. Hintergrundgrafiken und Beschriftungen stellen den Bezug zur
jeweiligen Anwendung her. Die Ansicht kann über **Netzwerk →
Anwendungsansicht...**, die Werkzeugleiste oder aus dem normalen
Erprobungsfenster geöffnet werden. Voraussetzung sind ein gültiges
Netzwerk, zugeordnete Trainingsdaten sowie vollständig zugeordnete Ein- und
Ausgänge.

Der **(i)-Button** links neben **Alles zeigen** blendet eine kurze Erklärung
zum Zweck der Anwendungsansicht ein. **Beschreibung…** und
**Testauswertung…** öffnen dieselben projektbezogenen Informationen und
Auswertungen wie im normalen Erprobungsfenster.

Im Gegensatz zur tabellarischen Erprobungsansicht lassen sich Ein- und
Ausgänge frei auf einer Zeichenfläche platzieren. Eine Hintergrundgrafik,
Kommentare und einfache Formen können daraus eine anschauliche Bedien- oder
Prozessdarstellung machen. Gewichte und Bias-Werte werden dabei nicht verändert.

### Bearbeiten und Erproben

Das Auswahlfeld **Modus** trennt Gestaltung und Bedienung klar voneinander:

- **Bearbeiten** erlaubt Auswählen, Verschieben, Vergrößern, Verkleinern,
  Einfügen, Löschen, Färben und Anordnen der Gestaltungselemente.
- **Erproben** bedient die Eingänge und berechnet die Ausgänge sofort.
  Gestaltungselemente lassen sich in diesem Modus nicht versehentlich bewegen.

Das Fenster startet im Modus **Erproben**. Zum Aufbau oder Ändern der
Oberfläche wird bewusst auf **Bearbeiten** umgeschaltet.

Im Menü **Gestaltung** blendet **Raster anzeigen** ein projektbezogenes
Hilfsraster ein. **Rasterabstand…** legt den Abstand zwischen 5 und 200 Pixeln
fest. Beim Wechsel zu **Erproben** wird das Raster automatisch ausgeblendet.

### Ein- und Ausgänge auswählen

Beim ersten Öffnen muss nicht zwangsläufig jede vorhandene Ein- und Ausgabe
auf der Fläche stehen. Über einen Rechtsklick in einen freien Bereich und
**Element hinzufügen** lassen sich gezielt hinzufügen:

- einzelne Eingänge
- einzelne Ausgänge
- das definierte binäre Eingabe-Array
- Kommentare
- grafische Formen
- eine Hintergrundgrafik

**Alle Ein- und Ausgänge hinzufügen** ergänzt in einem gemeinsamen Schritt
sämtliche noch nicht sichtbaren Neuronenkacheln. Bereits vorhandene Kacheln
werden dabei nicht verdoppelt.

Bereits enthaltene Ein- oder Ausgänge sind im Auswahlmenü deaktiviert. Über
**Entf** oder das Kontextmenü können markierte Elemente nach einer Rückfrage
aus der Gestaltung entfernt werden. Das zugehörige Neuron und seine
Trainingsdaten bleiben dabei selbstverständlich erhalten.

### Eingabekarten

Analoge Eingänge besitzen ein Zahlenfeld und einen synchronen Regler. Werte
werden in der gespeicherten Einheit und innerhalb des aus den Trainingsdaten
bekannten Bereichs eingegeben. Binäre Eingänge erscheinen als eindeutige
Ein-/Aus-Schalter.

Jede Karte kann im Bearbeitungsmodus verschoben und am Griff unten rechts in
der Größe verändert werden. Eine Mindestgröße verhindert, dass Beschriftung,
Zahlenfeld oder Regler unlesbar werden. Über das Kontextmenü kann die
Kachelfarbe geändert oder eine Größe auf weitere gemeinsam markierte Karten
übertragen werden.

### Ausgangskarten

Analoge Ausgänge können wahlweise als Balken oder als halbkreisförmiger Zeiger
dargestellt werden. Unter der Skala stehen Minimum und Maximum aus der
Ausgabeskalierung; die aktuelle Ausgabe erscheint als Rohwert mit Einheit.
Größe und Kachelfarbe sind wie bei Eingängen einstellbar.

Binäre Ausgänge zeigen kompakt **Ein** oder **Aus**. Mit **Zwischenwerte
binärer Ausgänge anzeigen** wird stattdessen der kontinuierliche Y-Wert als
Balken dargestellt. Eine zusätzliche rote oder grüne Kennzeichnung zeigt dann,
ob dieser Wert als 0 oder 1 interpretiert wird. Sie ist keine Qualitätsanzeige.

### Binäres Eingabe-Array

Wurde in den Trainingsdaten ein zweidimensionales binäres Eingabe-Array
definiert, kann es als eigenes Element eingefügt werden. Im Modus
**Erproben** lassen sich die einzelnen Felder direkt anklicken. Die
zugeordneten Eingangskarten und die Netzberechnung folgen sofort.

Über das Kontextmenü sind Kachelfarbe sowie die Farben für Bit **Ein** und Bit
**Aus** einstellbar. Tooltips nennen die jeweilige Eingabe beziehungsweise das
zugeordnete Neuron.

### Hintergrundgrafik

Eine Grafik kann über **Element hinzufügen → Grafik laden...** eingefügt
werden. Zusätzlich sind Drag-and-drop sowie das Einfügen eines Bildes aus der
Zwischenablage mit **Strg+V** möglich. Die Grafik kann verschoben und am Griff
unten rechts proportional angepasst werden. Sie liegt hinter den Bedienkarten
und grafischen Formen.

Beim Speichern wird das Bild in den Projektordner
`grafisches_experiment` übernommen und unter einem festen Namen verwaltet. Der
ursprüngliche Ablageort wird dadurch nicht benötigt. **Entf** entfernt eine
markierte Grafik nach einer Sicherheitsabfrage auch aus der Gestaltung.

### Kommentare und grafische Formen

Kommentare können frei platziert und formatiert werden. Einstellbar sind Text,
Schriftgröße, Fettdruck, Ausrichtung, Schriftfarbe, Hintergrundfarbe und
Rahmen.

Als grafische Formen stehen Linie, Rechteck und Kreis beziehungsweise Ellipse
zur Verfügung. Linienfarbe, Linienstärke und bei Flächen zusätzlich Füllfarbe
oder transparente Füllung sind einstellbar. Formen liegen hinter den Ein- und
Ausgabekarten. Linien werden über ihre beiden Endpunkte verändert; Rechtecke
und Ellipsen über Größe und Position. Linien können am Ende eine Pfeilspitze
tragen. **Pfeilrichtung umkehren** setzt die Spitze auf das andere Linienende.

Markierte Kommentare und Formen können mit **Strg+C** und **Strg+V** kopiert
werden. Ein Bild in der Windows-Zwischenablage hat beim Einfügen Vorrang; wird
danach wieder eine Form kopiert, verwendet **Strg+V** erneut die interne
Elementkopie.

### Auswählen, Verschieben und Anordnen

Ein Klick markiert ein Element. Mehrere Elemente können gemeinsam ausgewählt
werden. Beim Aufziehen eines Auswahlrahmens werden nur Elemente markiert, die
vollständig innerhalb des Rahmens liegen. Markierte Elemente besitzen einen
roten Rahmen und können gemeinsam verschoben werden.

Die Pfeiltasten verschieben die Auswahl pixelweise. Über **Anordnen** können
mehrere markierte Elemente an Kanten ausgerichtet oder gleichmäßig horizontal
beziehungsweise vertikal verteilt werden. Das funktioniert auch bei einem
Raster aus mehreren Zeilen und Spalten.

**Rückgängig** und **Wiederholen** erfassen die Gestaltungsschritte. Mit
**Standardlayout** werden Karten nach einer Rückfrage wieder übersichtlich
angeordnet; die geladene Hintergrundgrafik bleibt erhalten.

### Zoom und Bildausschnitt

Das Mausrad zoomt um die Position des Mauszeigers. Nach dem Vergrößern kann die
Fläche mit **Alt+linker Maustaste** beziehungsweise mit der geschlossenen Hand
verschoben werden. Die aktuelle Zoomstufe erscheint in der Statuszeile.
**Alles zeigen** passt alle vorhandenen Gestaltungselemente in die sichtbare
Fläche ein. Der Zoom kann nicht weiter verkleinert werden als für die
vollständige Darstellung sinnvoll ist.

Fenstergröße, Zoom, Bildausschnitt, Positionen, Kartengrößen, Farben,
Darstellungsarten und alle zusätzlichen Elemente werden projektbezogen
gespeichert.

### Speichern und Schließen

**Strg+S** und **Speichern** sichern die Gestaltung. Solange keine Änderung
vorliegt, bleibt **Speichern** deaktiviert. Beim Schließen oder bei **Esc**
fragt das Programm nach, wenn noch ungesicherte Änderungen vorhanden sind.

Die Gestaltung liegt als lesbare `layout.json` im Projektordner
`grafisches_experiment`. Sie ergänzt die `.nnproj`-Datei und verändert weder
Netzwerkstruktur noch Trainingsdaten.

---

# 24. Netzwerk prüfen

Der Menüpunkt befindet sich unter:

**Netzwerk → Netzwerk prüfen...**

Geprüft werden unter anderem:

- Anzahl Input-Neuronen
- Anzahl Hidden-Neuronen
- Anzahl Output-Neuronen
- Anzahl Verbindungen
- fehlende Eingänge
- fehlende Ausgänge
- nicht erreichbare Neuronen
- vorhandener Pfad von Input zu Output

Fehler werden in einem Meldungsfenster angezeigt.

---

# 25. Projekt speichern und öffnen

## Projekt speichern

**Datei → Speichern**

Beim Speichern des Projekts werden geänderte zugehörige Trainings- und
Testdaten automatisch in ihren eigenen Dateien mitgespeichert. Besitzt ein
geändertes Dokument noch keinen Dateipfad, legt das Programm die Datei im
passenden Projektunterordner `trainingsdaten` beziehungsweise `testdaten` an.

## Projekt speichern unter

**Datei → Speichern unter...**

Beim ersten Speichern und bei **Speichern unter...** erscheint ein
Projektfenster mit folgenden Angaben:

- Projektname
- Speicherort
- **Eigenen Projektordner anlegen (empfohlen)**
- **Zugehörige Trainings- und Testdaten übernehmen**

Ohne einen bereits gespeicherten Projektpfad startet dieses Fenster
automatisch im Ordner `Projekte` neben der EXE. Dadurch kann ein vollständig
entpacktes NeuronNetz-Paket seine Beispielprojekte, neue Projekte und
Tutorials ohne vorherige Pfadauswahl verwenden. Fehlt `Projekte`, wird der
Ordner angelegt. Ist der Programmort nicht beschreibbar, wird auf
`Dokumente\NeuronNetz\Projekte` ausgewichen.
Beim ersten Speichern eines neu angelegten Projekts wird immer dieser
übergeordnete Ordner `Projekte` vorgeschlagen und nicht der Ordner des zuletzt
verwendeten Einzelprojekts.
Bei **Speichern unter** aus einem bestehenden Projekt wird für einen neuen
eigenen Projektordner stets der übergeordnete Ordner `Projekte` vorgeschlagen.

Bei aktiviertem Projektordner entsteht sofort eine vollständige
Grundstruktur:

```text
Projektname/
├── Projektname.nnproj
├── trainingsdaten/
├── testdaten/
└── exporte/
```

Die Unterordner werden auch dann sofort angelegt, wenn sie zunächst noch
leer sind. Bereits vorhandene Datendateien können dadurch anschließend
direkt mit dem Explorer einsortiert werden.

Ist **Zugehörige Trainings- und Testdaten übernehmen** aktiviert, werden
die aktuell im Programm zugeordneten Daten in die passenden Unterordner
geschrieben. Die neue Projektdatei verweist danach auf diese Kopien.
Gleichnamige vorhandene Datendateien werden nicht überschrieben, sondern
erhalten automatisch einen freien Dateinamen.

Wird kein eigener Projektordner angelegt, entsteht nur die Projektdatei
am ausgewählten Speicherort. Bestehende Projekte und diese bisherige
Arbeitsweise bleiben damit weiterhin möglich.

## Projekt umbenennen

**Datei → Projekt umbenennen...** ändert bei einem strukturierten Projekt den
Namen des eigenen Projektordners und der darin enthaltenen `.nnproj`-Datei
gemeinsam. Voraussetzung ist, dass Ordner und Projektdatei vor dem Umbenennen
denselben Namen tragen. Ungültige Windows-Dateinamen und bereits vorhandene
Zielordner werden abgewiesen.

Interne Datenverweise, der zuletzt verwendete Projektpfad und die Liste der
zuletzt geöffneten Projekte werden dabei angepasst. Ein mitgeliefertes
Beispielprojekt wird nicht direkt umbenannt; davon muss zuerst mit
**Speichern unter...** eine eigene Kopie angelegt werden.

Projektdateien verwenden die Endung:

```text
.nnproj
```

## Projekt öffnen

**Datei → Öffnen...**

Unter **Datei → Zuletzt geöffnete Projekte** stehen außerdem die letzten
fünf erfolgreich geöffneten oder neu gespeicherten Projekte zur direkten
Auswahl. Das zuletzt verwendete Projekt steht an erster Stelle. Der
vollständige Dateipfad wird als Hinweis angezeigt.

Unter **Einstellungen → Programmeinstellungen... → Editor** kann
**Startbild anzeigen, während das Programm geladen wird** ein- oder
ausgeschaltet werden. Das Startbild zeigt Programmname, Leitsatz, Version und
den aktuellen Ladeschritt. Nach dem abgeschlossenen Laden bleibt es noch
2,5 Sekunden sichtbar. Seine Mitte richtet sich nach der gespeicherten
Position des späteren Hauptfensters. Erst danach verschwindet es und das
vorbereitete Hauptfenster wird sichtbar. Bei einem automatisch geöffneten
Projekt bleibt dessen zuletzt gespeicherte Netzwerkansicht erhalten.

An derselben Stelle kann
**Zuletzt bearbeitetes Projekt beim Programmstart automatisch öffnen** ein-
oder ausgeschaltet werden. Die Option ist standardmäßig aktiv. Eine beim
Programmstart ausdrücklich übergebene `.nnproj`-Datei hat immer Vorrang. Ist
der automatisch gemerkte Pfad nicht mehr vorhanden oder die Projektdatei
beschädigt, startet NeuronNetz ohne Projekt und verwirft den ungültigen
automatischen Startpfad.

Wurde eine dort aufgeführte Projektdatei verschoben oder gelöscht, meldet
das Programm den fehlenden Pfad und entfernt den ungültigen Eintrag aus der
Liste. Die Verlaufsliste ist eine programmeigene Einstellung und wird nicht
in den einzelnen Projektdateien gespeichert.

## Im Projekt gespeicherte Daten

Gespeichert werden unter anderem:

- Neuronen
- Neuronentypen
- Namen
- Aktivierungsfunktionen
- Bias-Werte
- Input-Werte
- Sollwerte
- Positionen
- Verbindungen
- Gewichte
- Kommentare
- Kommentargrößen
- Kommentarschriftgrößen
- Zoom
- sichtbarer Mittelpunkt
- Verweis auf Trainingsdatendatei
- Verweis auf Testdatendatei
- Trainingsparameter
- Trainingshistorie mit kompakten Fehlerkurven
- Monitoring-Einstellung
- Darstellungsoptionen

---

# 26. Trainingsdatendateien speichern

Trainingsdaten sind eigenständige Dateien.

Im Trainingsdateneditor stehen zur Verfügung:

- Neu
- Öffnen
- Speichern
- Speichern unter

Die Trainingsdatendatei wird mit dem Projekt verknüpft.

Bei Projekten mit eigener Ordnerstruktur startet der Trainingsdateneditor
automatisch im Unterordner `trainingsdaten`. Der Testdateneditor verwendet
entsprechend den Unterordner `testdaten`.

Liegt eine Datendatei innerhalb des Projektordners oder auf demselben
Laufwerk, kann der Projektverweis relativ gespeichert werden. Dadurch
bleiben die Verknüpfungen erhalten, wenn der vollständige Projektordner
verschoben oder kopiert wird.

Wird eine verknüpfte Datei nicht gefunden, fragt das Programm nach einer anderen Trainingsdatendatei.

Testdaten sind eigenständige `.nntest`-Dateien. Ihre Zuordnung
wird getrennt im Projekt gespeichert. Der Befehl
**Testdatenzuordnung entfernen** entfernt nur diesen Projektverweis; die
Datei selbst wird nicht gelöscht.

---

# 27. Beispiel: XOR

## Aufgabe

Der Ausgang ist 1, wenn genau einer der beiden Eingänge 1 ist.

## Trainingsdaten

| X1 | X2 | Sollwert |
|---:|---:|---:|
| 0 | 0 | 0 |
| 0 | 1 | 1 |
| 1 | 0 | 1 |
| 1 | 1 | 0 |

## Möglicher Netzwerkaufbau

- 2 Input-Neuronen
- 1 Hidden-Schicht
- 2 Hidden-Neuronen
- 1 Output-Neuron
- Hidden: Sigmoid oder Tanh
- Output: Sigmoid
- vollständige Verbindung

## Empfohlene Startwerte

```text
Gewichte: Xavier/Glorot
Bias: 0 oder zufällig
Lernrate: 0.05 bis 0.1
Fehlergrenze: 0.01
Maximale Epochen: 10000
```

---

# 28. Beispiel: 3-Bit-XOR

## Aufgabe

Der Ausgang ist 1, wenn eine ungerade Anzahl der drei Eingänge den Wert 1 besitzt.

## Trainingsdaten

| X1 | X2 | X3 | Sollwert |
|---:|---:|---:|---:|
| 0 | 0 | 0 | 0 |
| 0 | 0 | 1 | 1 |
| 0 | 1 | 0 | 1 |
| 0 | 1 | 1 | 0 |
| 1 | 0 | 0 | 1 |
| 1 | 0 | 1 | 0 |
| 1 | 1 | 0 | 0 |
| 1 | 1 | 1 | 1 |

## Möglicher Netzwerkaufbau

- 3 Input-Neuronen
- 1 Hidden-Schicht
- 4 bis 6 Hidden-Neuronen
- 1 Output-Neuron
- Hidden: Sigmoid oder Tanh
- Output: Sigmoid
- vollständige Verbindung

## Empfohlene Startwerte

```text
Gewichte: Xavier/Glorot
Bias: 0 oder zufällig
Lernrate: 0.05 bis 0.1
Fehlergrenze: 0.01
Maximale Epochen: 20000 bis 50000
```

Mehrere zufällige Initialisierungen können unterschiedlich schnell lernen.

---

# 29. Typische Probleme und Lösungen

## Das Netzwerk lernt nicht

Prüfen:

- sind alle Trainingsspalten korrekt zugeordnet?
- ist jedes Output-Neuron mit einem Sollwert verbunden?
- existiert ein vollständiger Pfad von Input zu Output?
- wurden alle Gewichte mit 0 initialisiert?
- ist die Lernrate zu groß oder zu klein?
- passt die Aktivierungsfunktion zum Wertebereich der Sollwerte?

## Der Fehler bleibt nahezu konstant

Mögliche Ursachen:

- Lernrate zu klein
- ungünstige Initialisierung
- zu wenige Hidden-Neuronen
- falsche Spaltenzuordnung
- ungeeignete Aktivierungsfunktion
- ausschließlich nullwertige Gewichte

Mögliche Maßnahmen:

- Xavier/Glorot verwenden
- Bias zufällig initialisieren
- Lernrate verändern
- Hidden-Schicht vergrößern
- Training erneut starten

## Der Fehler schwankt stark

Mögliche Ursache:

- Lernrate zu groß

Lösung:

```text
Lernrate verkleinern
```

## Sollwerte können nicht erreicht werden

Prüfen Sie den Wertebereich der Output-Aktivierung.

### Sigmoid

Ausgangsbereich:

```text
0 bis 1
```

### Tanh

Ausgangsbereich:

```text
-1 bis 1
```

### ReLU

Ausgangsbereich:

```text
0 bis unendlich
```

### Linear

Nicht begrenzt.

## W-Kästchen wirken unübersichtlich

Unter

**Einstellungen → Programmeinstellungen... → Darstellung → Gewichtswerte anzeigen**

können die Gewichtsanzeigen ausgeblendet werden.

## Training ist langsam

Mögliche Maßnahmen:

- Datenmonitoring deaktivieren
- weniger Epochen verwenden
- Fehlergrenze anpassen
- Netzwerkgröße prüfen

## Trainingsdaten werden nicht gefunden

Beim Öffnen des Projekts kann eine andere `.nndata`-Datei ausgewählt werden.

---

# 30. Tastenkürzel

| Funktion | Tastenkürzel |
|---|---|
| Neues Projekt | `Strg+N` |
| Projekt öffnen | `Strg+O` |
| Projekt speichern | `Strg+S` |
| Projekt speichern unter | `Strg+Umschalt+S` |
| Programm beenden | `Alt+F4` |
| Rückgängig | `Strg+Z` |
| Wiederholen | `Strg+Y` |
| Ausschneiden | `Strg+X` |
| Kopieren | `Strg+C` |
| Einfügen | `Strg+V` |
| Alles markieren | `Strg+A` |
| Löschen | `Entf` |
| Vergrößern | `Strg++` |
| Verkleinern | `Strg+-` |
| Zoom 100 % | `Strg+0` |
| Alles anzeigen | `Strg+F` |
| Zeichenfläche mit der Hand verschieben | `Alt` halten und mit linker Maustaste ziehen |

---

# 31. Mathematische Grundlagen

Dieses Kapitel erklärt die Mathematik, die NeuronNetz bei der
Vorwärtsberechnung und beim Training verwendet. Die Formeln sind so
geschrieben, wie sie im Programm umgesetzt sind.

## Verwendete Formelzeichen

| Zeichen | Bedeutung |
|---|---|
| `x` | Eingabewert eines Input-Neurons |
| `y` | Ausgabewert eines Neurons |
| `t` | Sollwert eines Output-Neurons |
| `w` | Gewicht einer Verbindung |
| `b` | Bias eines Neurons |
| `Σ` | gewichtete Summe vor der Aktivierung |
| `f(Σ)` | Aktivierungsfunktion |
| `f'(Σ)` | Ableitung der Aktivierungsfunktion |
| `e` | Fehler eines Output-Neurons |
| `δ` | Delta eines Neurons |
| `η` | Lernrate |

## Gewichtete Summe

Ein Hidden- oder Output-Neuron erhält die Ausgaben der mit ihm
verbundenen Vorgängerneuronen. Jede dieser Ausgaben wird mit dem
Gewicht der jeweiligen Verbindung multipliziert. Anschließend wird
der Bias addiert:

```text
Σ = y₁ · w₁ + y₂ · w₂ + ... + yₙ · wₙ + b
```

Der Bias wirkt wie ein zusätzlicher, ständig verfügbarer Eingang.
Durch ihn kann die Aktivierung eines Neurons nach links oder rechts
verschoben werden.

## Vorwärtsberechnung

Bei der Vorwärtsberechnung, auch **Forward Pass** genannt, werden die
Neuronen vom Eingang zum Ausgang berechnet.

Für Input-Neuronen gilt:

```text
y = x
```

Für Hidden- und Output-Neuronen gilt:

```text
y = f(Σ)
```

Die Aktivierungsfunktion bestimmt, wie die gewichtete Summe in den
Ausgabewert des Neurons umgewandelt wird.

## Aktivierungsfunktionen

NeuronNetz unterstützt **Linear**, **ReLU**, **Sigmoid** und **Tanh**.
Für die Backpropagation wird jeweils auch die Ableitung benötigt.

### Linear

```text
f(Σ)  = Σ
f'(Σ) = 1
```

Die lineare Funktion verändert den Wert nicht. Ihr Wertebereich ist
unbegrenzt. Sie eignet sich besonders für Output-Neuronen, wenn ein
beliebiger Zahlenwert vorhergesagt werden soll.

Mehrere ausschließlich lineare Schichten können gemeinsam keine
nichtlinearen Zusammenhänge abbilden.

### ReLU

ReLU bedeutet **Rectified Linear Unit**.

```text
f(Σ) = max(0, Σ)

          1, wenn Σ > 0
f'(Σ) =
          0, wenn Σ ≤ 0
```

Negative und null betragende Summen werden auf `0` gesetzt. Positive
Werte werden unverändert weitergegeben. ReLU wird häufig für
Hidden-Neuronen verwendet und kann bei positiven Summen ein schnelles
Lernen ermöglichen.

Bleibt die Summe eines ReLU-Neurons dauerhaft kleiner oder gleich
null, ist auch seine Ableitung null. Das Neuron erhält dann über die
Backpropagation kein Lernsignal. Dieser Zustand wird gelegentlich als
**totes ReLU-Neuron** bezeichnet.

### Sigmoid

```text
              1
f(Σ) = -----------------
        1 + exp(-Σ)

f'(Σ) = f(Σ) · (1 - f(Σ))
```

Sigmoid bildet jeden Eingabewert auf einen Wert zwischen `0` und `1`
ab. Die Funktion eignet sich deshalb für Ausgaben, die als Anteil,
Wahrscheinlichkeit oder Wahr/Falsch-Wert interpretiert werden.

Bei sehr großen positiven oder negativen Summen nähert sich die
Ausgabe `1` beziehungsweise `0`. Gleichzeitig wird die Ableitung sehr
klein. Das Lernen kann dadurch langsamer werden.

### Tanh

```text
f(Σ)  = tanh(Σ)
f'(Σ) = 1 - tanh²(Σ)
```

Tanh bedeutet **hyperbolischer Tangens** und bildet Eingabewerte auf
den Bereich zwischen `-1` und `1` ab. Im Gegensatz zu Sigmoid ist die
Funktion um null zentriert.

Auch bei Tanh wird die Ableitung für sehr große positive oder negative
Summen klein. In tiefen Netzen kann sich das Lernsignal deshalb über
mehrere Schichten stark abschwächen.

## Fehlerberechnung

Für jedes Output-Neuron wird zunächst die Abweichung zwischen Sollwert
und berechnetem Ausgabewert bestimmt:

```text
e = t - y
```

Als zusammengefassten Fehler eines Trainingsschritts verwendet das
Programm den **mittleren quadratischen Fehler**, kurz MSE:

```text
          1   m
MSE =    ---  Σ  (tᵢ - yᵢ)²
          m  i=1
```

`m` ist dabei die Anzahl der Output-Neuronen. Durch das Quadrieren
werden positive und negative Abweichungen gleich behandelt. Größere
Abweichungen wirken sich stärker aus als kleine.

## Backpropagation

Backpropagation verteilt den Fehler von den Output-Neuronen rückwärts
durch das Netzwerk. Dabei erhält jedes trainierbare Neuron ein Delta.
Das Delta beschreibt, wie stark dieses Neuron zur notwendigen
Korrektur beiträgt.

### Delta eines Output-Neurons

Für ein Output-Neuron berechnet das Programm:

```text
δ = (t - y) · f'(Σ)
```

Der Ausgabefehler wird also mit der lokalen Steigung der
Aktivierungsfunktion multipliziert.

### Delta eines Hidden-Neurons

Ein Hidden-Neuron besitzt keinen eigenen Sollwert. Sein Delta ergibt
sich aus den Deltas der nachfolgenden Neuronen und den Gewichten der
Verbindungen zu diesen Neuronen:

```text
δ = f'(Σ) · (w₁ · δ₁ + w₂ · δ₂ + ... + wₙ · δₙ)
```

So wird der Fehler Schicht für Schicht vom Ausgang in Richtung Eingang
weitergegeben.

## Gewichte und Bias aktualisieren

Nach der Berechnung aller Deltas werden die Verbindungsgewichte
angepasst:

```text
Δw = η · δ · y_vorher
w_neu = w_alt + Δw
```

`y_vorher` ist der Ausgabewert des Neurons am Anfang der Verbindung.
Der Bias eines Hidden- oder Output-Neurons wird entsprechend geändert:

```text
Δb = η · δ
b_neu = b_alt + Δb
```

Das Pluszeichen in diesen Formeln ergibt sich daraus, dass NeuronNetz
den Fehler als `t - y` definiert. Die Aktualisierung bewegt Gewicht und
Bias dadurch in Richtung eines kleineren Fehlers.

Die neuen Gewichte und Bias-Werte beeinflussen erst den nächsten
Forward Pass.

## Bedeutung der Lernrate

Die Lernrate `η` bestimmt die Größe jedes Lernschritts:

- Eine kleine Lernrate führt zu vorsichtigen Änderungen. Das Training
  kann stabiler sein, benötigt aber meist mehr Epochen.
- Eine große Lernrate führt zu stärkeren Änderungen. Das Training kann
  schneller vorankommen, aber auch schwanken oder am Ziel vorbeilaufen.

Es gibt keine Lernrate, die für jedes Netzwerk optimal ist. Wenn der
Fehler stark schwankt, sollte meist eine kleinere Lernrate ausprobiert
werden. Sinkt der Fehler nur sehr langsam, kann eine etwas größere
Lernrate sinnvoll sein.

## Beispiel eines Rechenschritts

Ein Sigmoid-Neuron erhält zwei Werte:

```text
y₁ = 0,5     w₁ = 0,8
y₂ = 0,2     w₂ = -0,4
b  = 0,1
```

Die gewichtete Summe lautet:

```text
Σ = 0,5 · 0,8 + 0,2 · (-0,4) + 0,1
Σ = 0,42
```

Die Sigmoid-Aktivierung ergibt ungefähr:

```text
y = Sigmoid(0,42) ≈ 0,6035
```

Bei einem Sollwert von `t = 1` beträgt der Fehler:

```text
e = 1 - 0,6035 = 0,3965
```

Die Ableitung der Sigmoid-Funktion ist an dieser Stelle ungefähr
`0,2393`. Daraus folgt:

```text
δ = 0,3965 · 0,2393 ≈ 0,0949
```

Bei einer Lernrate von `η = 0,1` wird das erste Gewicht geändert um:

```text
Δw₁ = 0,1 · 0,0949 · 0,5 ≈ 0,0047
w₁_neu = 0,8 + 0,0047 = 0,8047
```

Der Bias wird ebenfalls angepasst:

```text
Δb = 0,1 · 0,0949 ≈ 0,0095
b_neu = 0,1 + 0,0095 = 0,1095
```

Beim nächsten Forward Pass liegt die Ausgabe dadurch etwas näher am
Sollwert `1`.

## Praktische Hinweise

- Sigmoid passt gut zu Output-Werten zwischen `0` und `1`.
- Tanh passt gut zu Output-Werten zwischen `-1` und `1`.
- Linear eignet sich für nicht begrenzte numerische Output-Werte.
- ReLU wird häufig in Hidden-Neuronen eingesetzt.
- Aktivierungsfunktion und Sollwertbereich müssen zusammenpassen.
- Sehr kleine Ableitungen schwächen das rückwärts übertragene
  Lernsignal ab. Dies wird als **verschwindender Gradient** bezeichnet.
- Eine geeignete Initialisierung verhindert, dass viele Neuronen schon
  zu Beginn in ungünstigen Wertebereichen liegen.
- Backpropagation benötigt ein gerichtetes Netz ohne Zyklen und einen
  vollständigen Pfad von den Input- zu den Output-Neuronen.

---

# 32. Trainingshistorie

Die projektbezogene Trainingshistorie wird geöffnet über:

**Netzwerk → Trainingshistorie...**

Die Spalte **Modus** zeigt für neue Läufe **Normal** oder **Schnell**. Bei
älteren Historieneinträgen, die diese Information noch nicht gespeichert
haben, steht **Unbekannt**. Der Modus wird auch in den CSV-Export aufgenommen.

Nach jedem erfolgreich abgeschlossenen Trainingslauf wird automatisch
ein neuer Eintrag angelegt. Gespeichert werden:

- Datum und Uhrzeit
- verwendete Trainingsdatendatei
- neuer Lernlauf oder fortgesetztes Training
- Initialisierung von Gewichten und Bias
- Lernrate und Fehlergrenze
- angeforderte und ausgeführte Epochen
- Startfehler, Endfehler und maximaler Einzelfehler
- Trainingsdauer und Abschlussstatus
- eine kompakte Fehlerkurve mit bis zu 10.000 echten Messpunkten
- den Endzustand aller Gewichte und Bias-Werte

Die Messdichte nimmt stufenweise ab: Bis Epoche 500 wird jede Epoche
gespeichert, bis 10.000 jede zehnte, bis 100.000 jede hundertste und danach
jede tausendste Epoche. Der tatsächliche Endpunkt eines Trainingsabschnitts
wird immer aufgenommen. Es werden keine Werte gemittelt oder künstlich
geglättet; das Diagramm verbindet ausschließlich tatsächlich gemessene
Fehlerwerte. So bleibt der besonders wichtige Trainingsbeginn detailreich,
ohne die Projektdatei bei sehr langen Läufen unnötig zu vergrößern.

Ältere Trainingshistorien bleiben lesbar. Details, die eine ältere
Programmversion bereits verworfen hat, können beim erneuten Öffnen jedoch
nicht nachträglich rekonstruiert werden.

Gespeichert wird ausschließlich der Endzustand eines Laufes. Die Werte
der einzelnen Epochen werden nicht als vollständige Netzwerkzustände
aufbewahrt.

## Trainingsläufe vergleichen

Ein oder mehrere Tabellenzeilen können ausgewählt werden. Die
zugehörigen Fehlerkurven erscheinen gemeinsam im unteren Diagramm.
Die **Y-Skalierung** kann zwischen **Linear** und **Logarithmisch** umgeschaltet
werden. Die lineare Fehlerachse beginnt immer bei null. Eine logarithmische
Achse beginnt mathematisch bedingt beim kleinsten sinnvollen positiven Wert.

Das Mausrad vergrößert oder verkleinert ausschließlich den sichtbaren
Epochenbereich der X-Achse um die Position des Mauszeigers. Über dem Diagramm
erscheint eine offene Hand. Mit gedrückter linker Maustaste schließt sie sich;
durch Ziehen wird der Ausschnitt ausschließlich horizontal verschoben. Die
Y-Skalierung bleibt dabei unverändert. **Gesamt** zeigt wieder den vollständigen
Epochenbereich. Kurvenpunkte außerhalb des sichtbaren Ausschnitts werden weder
gelöscht noch verändert.

## Ausgewählten Lauf laden

Wählen Sie genau einen Trainingslauf aus und klicken Sie auf
**Ausgewählten Lauf laden**. Der Lauf wird als **aktiv** gekennzeichnet.
Das Programm übernimmt alle am Ende dieses Laufes gespeicherten Gewichte und Bias-Werte. Die
damalige Lernrate, Fehlergrenze und angeforderte Epochenzahl werden
ebenfalls in die Trainingseinstellungen übernommen. **Netzwerk vor
Trainingsbeginn neu initialisieren** wird ausgeschaltet, damit eine
Fortsetzung den wiederhergestellten Zustand nicht überschreibt. Die
Wiederherstellung kann mit **Rückgängig** in einem Schritt aufgehoben
werden.

Die Schaltfläche ist nur aktiv, wenn der ausgewählte Lauf einen
gespeicherten Endzustand besitzt und die Neuronen sowie Verbindungen
noch zur aktuellen Netzwerkstruktur passen. Bei älteren
Historieneinträgen oder nach einer Strukturänderung bleibt sie
deaktiviert.

## Einträge löschen

Mit **Ausgewählte Läufe löschen** werden die markierten Einträge nach
einer Sicherheitsabfrage aus dem Projekt entfernt. Wird dabei der aktive
Lauf gelöscht, lädt das Programm den jüngsten verbleibenden Lauf vollständig
und kennzeichnet ihn als aktiv. Werden alle Läufe gelöscht, bleibt der aktuelle
Netzwerkzustand erhalten; es gibt jedoch keinen aktiven Lauf mehr und
**Fortsetzen** ist nicht verfügbar.

## CSV-Export

**Als CSV exportieren...** schreibt die tabellarischen Kennzahlen aller
Historieneinträge in eine semikolongetrennte CSV-Datei. Die kompakten
Kurvenpunkte verbleiben in der Projektdatei.

## Speicherung

Die Trainingshistorie gehört zur `.nnproj`-Datei. Bestehende Projekte
ohne Historie werden weiterhin geöffnet und beginnen mit einer leeren
Historie. Das aktuelle Projektformat besitzt Version 14.

---

# 33. Mathematikmodus

Die Oberfläche, Statusmeldungen und sämtliche erklärenden Texte des
datensatzweisen Rechenberichts folgen der gewählten Programmsprache. Dasselbe
gilt für die Rechenwege von Neuronen und Verbindungen auf der Registerkarte
**Mathematik** im Eigenschaftenfenster. Formeln und Zahlenwerte werden durch
den Sprachwechsel nicht verändert.

Der Mathematikmodus ergänzt das normale schnelle Training um eine
langsame, nachvollziehbare Untersuchung einzelner Lernschritte. Das
normale Trainingsfenster bleibt davon unverändert.

## Mathematikmodus öffnen

**Netzwerk → Mathematikmodus...** wählen oder das Symbol **Mathematik** in
der Werkzeugleiste anklicken. Ist bereits ein Neuron markiert, wird es
übernommen. Ohne Markierung zeigt die Auswahlliste **Kein Neuron gewählt**;
das Experiment bleibt gesperrt, bis dort bewusst ein Neuron ausgewählt wurde.
Das betrachtete Neuron kann vor dem Experimentstart im Fenster gewechselt
werden. Gültig zugeordnete Trainingsdaten bleiben Voraussetzung.

## Experiment vorbereiten

Die linke Seite enthält kompakt:

- eine Auswahlliste aller Neuronen; das betrachtete Neuron kann ohne
  Schließen des Fensters gewechselt werden
- Lernrate, Momentum und Anzeigegenauigkeit
- die beiden Startarten **Aktuellen Netzwerkzustand fortsetzen** und
  **Neues Experiment initialisieren**
- die Datensatztabelle mit ihrer Datensatzanzahl
- Erklärung und Formeln
- einstellbare Anzeigegenauigkeit von zwei bis zehn Nachkommastellen
Beim Fortsetzen werden die beim Start vorhandenen Gewichte, Bias-Werte und
Momentumzustände übernommen. Bei einem neuen Experiment stehen Xavier/Glorot oder Nullwerte
für die Gewichte sowie Null- oder Xavier/Glorot-Werte für den Bias zur
Verfügung. Neue Zufallswerte entstehen beim Klick auf **Experiment starten**.
Die gewählten Startbedingungen gelten ausschließlich im Mathematikmodus.

Vor dem Start sind die Rechenschritte gesperrt. Nach **Experiment starten**
werden die Startangaben gesperrt und der geführte Rechenweg freigegeben.
Der Bereich **Ausgangsdaten** klappt dabei automatisch zu einer kompakten
Zusammenfassung zusammen und kann über **Details anzeigen** wieder geöffnet
werden. Die Erklärungen verwenden eine gemeinsame kompakte Tabellenform mit
einheitlichen Zeilenabständen.
**Experiment neu vorbereiten** stellt den Zustand vom Öffnen des Fensters
wieder her und gibt die Startauswahl erneut frei.

Skalierungen aus den Trainingsdaten werden automatisch angewendet. Im
Rechenbericht stehen deshalb sowohl Rohwerte als auch die tatsächlich
im Netzwerk verwendeten skalierten Werte.

## Datensatzweise rechnen

**Nächster Datensatz** führt genau einen vollständigen Lernschritt aus:

1. Eingangswerte des markierten Datensatzes setzen
2. Netzwerk vorwärts berechnen
3. Fehler und Deltas zurückrechnen
4. Gewichte und Bias-Werte aktualisieren

Die Datensätze werden absichtlich in der sichtbaren Tabellenreihenfolge
verarbeitet und nicht wie beim normalen Training gemischt. Nach dem
letzten Datensatz ist die Epoche abgeschlossen. **Nächste Epoche
beginnen** startet anschließend wieder bei der ersten Tabellenzeile.

**Restliche Epoche ausführen** verarbeitet alle noch offenen Zeilen der
aktuellen Epoche automatisch.

## Geführter Rechenweg und Neuron-Lupe

Die Standardansicht teilt einen Lernschritt in sieben überschaubare Phasen:

1. Startwerte
2. Eingangs- und Sollwerte
3. gewichtete Summe
4. Aktivierung
5. Fehler und Delta
6. neue Parameter
7. Ergebnis und weiter

Die gemeinsame Navigationsleiste führt mit einer hervorgehobenen Hauptaktion
durch die Erklärung. Am Ende wird daraus **Nächsten Datensatz berechnen** oder
**Nächste Epoche beginnen**. Die Abschlussseite bestätigt den beendeten
Lernschritt und weist auf die nächsten Möglichkeiten hin.

Eine vergrößerte, schreibgeschützte Neuron-Lupe verwendet
dieselbe grafische Darstellung wie die Zeichenfläche. Sie zeigt das
ausgewählte Neuron, seine direkten Verbindungen und die Werte des gewählten
Lernschritts. Der Erklärungstext steht links unter der Datensatztabelle, sodass
die rechte Seite weitgehend für die Grafik verfügbar ist. Mit dem Mausrad und
den Schaltflächen `−`, `100 %`, **Alles zeigen** und `+` kann gezoomt werden.
Ziehen auf einer freien Stelle verschiebt nur die Ansicht; Neuronen und
Verbindungen bleiben schreibgeschützt. Beim Wechsel zum nächsten Rechenschritt
bleiben Zoomstufe und Bildausschnitt erhalten. Ein Wechsel des betrachteten
Neurons oder **Alles zeigen** passt die Grafik wieder vollständig ein.

Gewichte tragen überall eine eindeutige Verbindungsnummer. Beispielsweise
bezeichnet `W3: N4 → Ausgabe` das Eingangsgewicht der Verbindung von `N4`
zum nachfolgenden Zielneuron `Ausgabe`. Auf der Zeichenfläche steht dazu
kompakt `W3 = ...`.

Die Tabellen der geführten Ansicht stellen alte Werte, den unmittelbaren
Gradientenanteil, die vorherige Bewegung, den Momentumanteil, die neue Bewegung
und den neuen Parameterwert direkt gegenüber. Bei Momentum `0` sind vorherige
Bewegung und Momentumanteil null; die Rechnung entspricht dann exakt dem
bisherigen Lernverfahren. Die gewählte Zahl von Nachkommastellen verändert nur
die Anzeige; intern wird weiterhin mit voller Genauigkeit gerechnet.
Parameteränderungen `Δ` erscheinen unabhängig davon mit mindestens acht
Nachkommastellen, damit auch sehr kleine Lernschritte sichtbar bleiben.
Gerundete Nullwerte werden ohne irreführendes negatives Vorzeichen dargestellt.

Die geführte Ansicht unterscheidet die Neuronentypen fachlich:

- Bei Input-Neuronen zeigt sie die ausgehenden Startgewichte, `Y = X` und den
  Hinweis, dass kein Sollwert, eigener Fehler, Delta oder Bias existiert.
- Bei Hidden-Neuronen zeigt sie die gewichteten Deltas der nachfolgenden
  Neuronen, deren Summe, die Ableitung und das daraus berechnete Hidden-Delta.
- Bei Output-Neuronen zeigt sie Sollwert, Istwert, Fehler, Ableitung und
  Output-Delta.

Analoge Eingangs- und Sollwerte werden gemeinsam als Rohwert mit Einheit und
als intern verwendeter skalierter Netzwert angezeigt. Die Aktivierungsphase
zeigt Formel, eingesetzten Summenwert und Ergebnis für Linear, ReLU, Sigmoid
oder Tanh. Am Ende eines Datensatzes erscheint dessen mittlerer quadratischer
Fehler; am Epochenende der Mittelwert über alle Datensätze der Epoche.
Bei einem binären Output bleibt der kontinuierliche Y-Wert sichtbar. Ergänzend
zeigt der Rechenweg `● Ein` oder `○ Aus`; die Entscheidung verwendet
`Y > 0,5`.

## Vollständiges Protokoll

Für jeden bereits verarbeiteten Datensatz kann die entsprechende Zeile
angeklickt werden. Die Registerkarte **Vollständiges Protokoll** enthält für
das ausgewählte Neuron weiterhin:

- Rohwerte und skalierte Netzwerte
- gewichtete Summe mit allen einzelnen Summanden
- Aktivierungsfunktion und Ableitung
- Sollwert, Fehler und Delta bei Output-Neuronen
- Rückwärtssumme und Delta bei Hidden-Neuronen
- Gewichtsänderungen der zugehörigen Verbindungen
- Bias-Änderung
- vorherige und neue Momentumzustände von Gewichten und Bias
- mittlerer quadratischer Fehler des Lernschritts

Bei einem Input-Neuron werden die direkte Übernahme von `X` nach `Y`
und die Änderungen seiner ausgehenden Gewichte gezeigt.

## Zurück und neu vorbereiten

**Letzten Datensatz zurücknehmen** nimmt genau den zuletzt ausgeführten
Datensatz zurück. Dabei
werden Gewichte, Bias-Werte, Momentumzustände, Laufzeitwerte, Lernrate, Epoche und
Tabellenfortschritt gemeinsam wiederhergestellt.

**Epoche zurücknehmen** verwirft nach Bestätigung die späteren Lernschritte
und stellt den Beginn der aktuellen Epoche wieder her. Wird die Funktion am
Epochenanfang erneut verwendet, kann zum Beginn der vorherigen Epoche
zurückgekehrt werden.

**Experiment neu vorbereiten** verwirft alle bislang im Mathematikmodus
ausgeführten Lernschritte und stellt den Zustand beim Öffnen des Fensters
wieder her. Danach kann eine der beiden Startarten neu gewählt werden.

## Mathematikmodus schließen

Der Mathematikmodus ist ein reiner Experimentierbereich. Beim Schließen
werden grundsätzlich die Gewichte, Bias-Werte, die Lernrate und die
angezeigten Rechenwerte vom Öffnen des Mathematikmodus wiederhergestellt.
Das zuletzt trainierte Netzwerk bleibt dadurch unverändert erhalten.

Der Rechenverlauf selbst wird nicht in der Projektdatei gespeichert.

---

# 34. Projektbeschreibung

Über **Datei → Projektbeschreibung...** oder das Symbol **Beschreibung** in
der Datei-Werkzeugleiste öffnet sich ein freier Texteditor für Informationen,
Beobachtungen, Ideen und Notizen zum aktuellen Projekt. Das Programm gibt
keine Gliederung und keine Pflichtfelder vor.

## Text bearbeiten und formatieren

Die kleine Formatierungsleiste bietet:

- Schriftart
- Schriftgröße
- Fett
- Kursiv
- Unterstrichen

Zusätzlich stehen die üblichen Funktionen eines Texteditors zur Verfügung:

- **Strg+C** – kopieren
- **Strg+X** – ausschneiden
- **Strg+V** – einfügen
- **Strg+A** – alles markieren
- **Strg+Z** – rückgängig
- **Strg+Y** – wiederholen
- Kontextmenü über die rechte Maustaste

Die Liste **Schriftart** zeigt die aktuell verwendete Schrift als Namen, ohne
unruhige Schriftvorschau in der Auswahlliste. Eine gewählte Schrift wird auf
markierten Text angewendet oder gilt ab der aktuellen Schreibposition.

Mit **Übernehmen** wird der bearbeitete Inhalt in das aktuelle Projekt
übernommen. **Abbrechen** verwirft die Änderungen aus dem gerade geöffneten
Fenster.

## Speicherung

Die Beschreibung wird einschließlich ihrer grundlegenden Formatierungen
direkt in der `.nnproj`-Datei gespeichert. Eine zusätzliche Textdatei ist
nicht erforderlich. Änderungen an der Beschreibung kennzeichnen das Projekt
als geändert und werden erst mit dem normalen Speichern des Projekts dauerhaft
geschrieben.

## Beispielprojekte

Im unteren Bereich kann ein Projekt für das Menü **Datei → Beispielprojekte**
gekennzeichnet und mit einem Schwierigkeitsgrad von `★` bis `★★★★` versehen
werden. Nur Projekte mit gesetztem Haken und gültigem Schwierigkeitsgrad
erscheinen dort. Das Programm durchsucht dafür den gesamten Projektordner.
Ältere und nicht gekennzeichnete Projekte bleiben normale Projekte. Wird ein
Beispiel über dieses Menü geöffnet, erzeugt **Speichern** eine eigene Kopie und
überschreibt nicht das bereitgestellte Original.

In den Menüs **Beispielprojekte** und **Zuletzt geöffnete Projekte** erscheint
nach etwa einer halben Sekunde eine schreibgeschützte Vorschau der vorhandenen
Projektbeschreibung. Das Vorschaufenster besitzt eine feste Größe von ungefähr
420 × 300 Pixeln. Dadurch bleibt das Menü beim Wechsel zwischen Projekten ruhig.
Grundlegende Textformatierungen werden dargestellt; sehr lange Beschreibungen
werden für diese Kurzvorschau gekürzt und nicht scrollbar angezeigt. Projekte
ohne Beschreibung zeigen keine Vorschau. Die Funktion kann unter
**Einstellungen → Darstellung** abgeschaltet werden; ein Klick auf den
Menüeintrag öffnet das Projekt weiterhin unverändert.

Ältere Projektdateien ohne Beschreibung lassen sich weiterhin öffnen und
beginnen mit einem leeren Text. Das aktuelle Projektformat besitzt Version 14.

---

# 35. Projektübersicht

Über **Datei → Projektübersicht...** öffnet sich eine kompakte, rein
informative Zusammenfassung. Sie zeigt Netzwerkstruktur, Anzahl der Neuronen
und Verbindungen, Anzahl der Trainings- und Testdatensätze sowie Datum,
Epochenzahl und mittleren Fehler des letzten aktiven Trainingslaufs. Existiert
noch kein Lauf, wird dies ausdrücklich angezeigt. Projektbild und frei
formatierte Projektbeschreibung gehören bewusst nicht in dieses Fenster.

# 36. Projektablauf

Der Reiter **Projektablauf** befindet sich im rechten
Eigenschaftenfenster. Er zeigt automatisch, ob Netzwerk, Trainingsdaten,
Kalibrierung, Training und Ergebnisanalyse bereits verfügbar sind. Ein Klick
auf einen Schritt öffnet die zugehörige vorhandene Programmfunktion. Der Reiter
ist dauerhaft verfügbar und benötigt deshalb keinen Schalter im Menü
**Ansicht**.

# 37. Projektbericht exportieren

Über **Datei → Projektbericht exportieren...** wird ein bearbeitbarer
Projektbericht im DOCX-Format erzeugt. Der Befehl besitzt auch ein Symbol in
der Datei-Werkzeugleiste. Als Speicherort wird der Unterordner **exporte** des
aktuellen Projekts vorgeschlagen. Der Bericht enthält die formatierte
Projektbeschreibung, die eingerahmte und zentrierte Netzwerkdarstellung,
Trainingsdatei und -einstellungen, die Trainingskurve des aktiven Laufs,
Soll-Ist- beziehungsweise Entscheidungsdiagramme für alle Outputs, die je
Output eingestellten Toleranzen sowie die größten Abweichungen mit Einheiten.
Die Trainingsdaten werden ausgewertet. Gewichte und
Bias-Werte werden durch den Export nicht verändert.

Der Dokumentkopf nennt Projekt, Erstellungsdatum und aktiven Lauf. Die
Trainingstabelle und ihre Kurve bleiben zusammen; die Kurve wird bei einem
großen positiven Wertebereich automatisch logarithmisch dargestellt. Je drei
gleich große Output-Diagramme werden auf einer Seite angeordnet. Tabellenzeilen
werden nicht geteilt und Tabellenköpfe auf Folgeseiten wiederholt. Bei
prozentualen Outputs ist die Abweichung in Prozentpunkten angegeben. Bei Bedarf
kann der Bericht anschließend in Word als PDF gespeichert werden.

---


# Versionsnotizen der Hilfe

Diese Hilfedatei beschreibt den aktuellen Entwicklungsstand des Programms mit:

- automatischer Netzwerkerzeugung
- Trainingsdatenverwaltung
- Training und Test
- Trainings-Debugger
- Monitoring
- Trainingszeitanzeige
- Kopieren und Einfügen
- Rückgängig und Wiederholen
- projektbezogene Darstellungsoptionen
- projektbezogene Trainingshistorie und Kurvenvergleich
- kompakte adaptive Anzeige numerischer Werte
- mathematische Rechenwege für Neuronen und Verbindungen im Eigenschaftenfenster
- datensatzweiser Mathematikmodus mit Rückgängig und Rechenbericht
- frei formatierbare, projektbezogen gespeicherte Projektbeschreibung
- kompakte Projektübersicht und optionaler Projektablauf
- bearbeitbarer Projektbericht zum aktiven Trainingsergebnis

Eigene Ergänzungen können direkt unterhalb dieser Zeile eingetragen werden.

---
