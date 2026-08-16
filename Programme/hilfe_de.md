# NeuronNetz – kompakte Hilfe

Diese integrierte Hilfe beantwortet die wichtigsten Fragen direkt im Programm. Das ausführliche bebilderte Handbuch kann über **Hilfe → Tutorials** als Word- oder PDF-Datei geöffnet werden.

---

# 1. Überblick

**NeuronNetz** ist ein grafischer Editor zum Erstellen, Trainieren und Untersuchen kleiner neuronaler Netze. Neuronen, Verbindungen, Gewichte, Aktivierungsfunktionen und Rechenwerte bleiben sichtbar und können gezielt bearbeitet werden.

Ein typischer Ablauf ist:

1. Projekt anlegen oder öffnen.
2. Netzwerk erstellen.
3. Trainingsdaten eingeben, importieren und skalieren.
4. Spalten den Input- und Output-Neuronen zuordnen.
5. Netzwerk prüfen und trainieren.
6. Ergebnis testen, analysieren oder im Experiment untersuchen.
7. Projekt speichern.

# 2. Programmoberfläche

Die **Zeichenfläche** zeigt Neuronen, Verbindungen und Kommentare. Das **Eigenschaftenfenster** rechts bearbeitet das ausgewählte Objekt und zeigt unter **Mathematik** dessen aktuellen Rechenweg.

Die Menüs und Werkzeugleisten führen zu denselben Funktionen. Die Statusleiste meldet Projektzustand, Datenzuordnung, Trainingsergebnisse und Zoom.

Wichtige Menüs:

- **Datei:** neues Projekt, öffnen, speichern, Beschreibung und Bericht.
- **Bearbeiten:** rückgängig, wiederholen, kopieren, einfügen und löschen.
- **Ansicht:** Darstellungsoptionen und Zoom.
- **Netzwerk:** erzeugen, anordnen, prüfen, erproben, trainieren und analysieren.
- **Trainingsdaten:** Trainings- und Testdaten verwalten.
- **Einstellungen:** Programmeinstellungen und Sprache.
- **Hilfe:** integrierte Hilfe, Tutorials und Programminformationen.

# 3. Neues Projekt

**Datei → Neu** öffnet die Auswahl des Einstiegs:

- **Leeres Projekt anlegen:** vollständig manuell beginnen.
- **Netzwerk automatisch erstellen:** Schichten und Neuronenzahlen festlegen.
- **Netzwerk aus Trainingsdaten erstellen:** zuerst Tabellenstruktur und Daten anlegen.
- **Eigene Projektidee entwickeln:** einen bearbeitbaren Prompt für eine externe KI vorbereiten.

Ein nachfolgender Einrichtungsdialog kann abgebrochen werden, ohne das aktuelle Projekt zu verändern. Der Projektassistent verändert das aktuelle Projekt grundsätzlich nicht.

Ein neues Projekt verwendet die Standardfarben, Standarddarstellung und Standard-Trainingsparameter. Allgemeine Programmeinstellungen bleiben erhalten.

# 4. Neuron erstellen

Ein Neuron wird über **Netzwerk → Neuron erstellen** oder das entsprechende Werkzeug angelegt. Danach auf die gewünschte Stelle der Zeichenfläche klicken.

Im Eigenschaftenfenster werden Name, Typ, Aktivierungsfunktion, Bias und weitere Werte festgelegt. Namen sollten kurz und eindeutig sein.

# 5. Neuronentypen

- **Input:** übernimmt einen Eingabewert. Input-Neuronen besitzen keinen Bias und keine eigene Aktivierungsfunktion.
- **Hidden:** verarbeitet gewichtete Eingänge und gibt das Ergebnis seiner Aktivierungsfunktion weiter.
- **Output:** berechnet die Ausgabe des Netzes und wird beim Training mit einem Sollwert verglichen.

Binäre äußere Werte verwenden 0 und 1. Analoge Werte sollten passend skaliert werden.

# 6. Eigenschaften eines Neurons

Die Registerkarte **Objekt** enthält Name, Typ, Aktivierungsfunktion, Bias und Position. Laufzeitwerte wie X, gewichtete Summe Σ und Ausgabe Y werden schreibgeschützt angezeigt.

Die Registerkarte **Mathematik** zerlegt die aktuelle Vorwärtsrechnung und – nach einem Lernschritt – die Rückwärtsrechnung. Bei Input-, Hidden- und Output-Neuronen werden nur fachlich passende Größen gezeigt.

# 7. Verbindungen erstellen

Mit **Netzwerk → Verbindung erstellen** zuerst das Quellneuron und danach das Zielneuron anklicken. Die Verbindung muss der Informationsrichtung folgen, typischerweise Input → Hidden → Output.

Schleifen, doppelte Verbindungen und fachlich unzulässige Richtungen werden verhindert oder bei der Netzwerkprüfung gemeldet.

# 8. Eigenschaften einer Verbindung

Eine ausgewählte Verbindung zeigt Quelle, Ziel, Gewicht und Rechenweg. Positive und negative Gewichte können durch Farbe und Linienstärke unterschieden werden.

Das Gewicht bestimmt, wie stark und in welcher Richtung die Ausgabe des Quellneurons auf das Zielneuron wirkt.

# 9. Kommentare

Kommentare beschriften Bereiche der Zeichenfläche und werden mit dem Projekt gespeichert. Text, Größe, Schriftgröße, Farbe und Position können im Eigenschaftenfenster geändert werden.

Kommentare beeinflussen die Netzwerkberechnung nicht.

# 10. Objekte auswählen und verschieben

- Klick wählt ein Objekt aus.
- **Strg+Klick** ergänzt oder entfernt ein Objekt aus der Auswahl.
- Ziehen in einem freien Bereich erzeugt eine Rechteckauswahl.
- Ziehen eines ausgewählten Neurons oder Kommentars verschiebt die Auswahl.
- Ziehen in einem freien Bereich verschiebt den sichtbaren Ausschnitt; **Alt** ermöglicht den Handmodus ebenfalls.

# 11. Kopieren, Ausschneiden und Einfügen

Neuronen, interne Verbindungen und Kommentare können kopiert, ausgeschnitten und eingefügt werden. Beim Einfügen entstehen neue IDs; externe Verbindungen zu nicht kopierten Objekten werden nicht erzeugt.

Die Zwischenablage des Editors ist projektintern. Nach strukturellen Änderungen sollte das Netzwerk erneut geprüft werden.

# 12. Rückgängig und Wiederholen

**Strg+Z** macht die letzte Editoränderung rückgängig, **Strg+Y** stellt sie wieder her. Dazu gehören unter anderem Erstellen, Löschen, Verschieben, Einfügen und Eigenschaftenänderungen.

Dateioperationen und abgeschlossene Trainingsläufe gehören nicht zur normalen Editor-Historie.

# 13. Ansicht und Zoom

- **Größer / Kleiner:** Zoom schrittweise ändern.
- **100 %:** Standardzoom herstellen.
- **Alles zeigen:** alle sichtbaren Projektobjekte in den verfügbaren Bereich einpassen.
- Mausrad: zoomen.
- Freien Bereich ziehen oder **Alt+Ziehen:** Ausschnitt verschieben.

Zoom und sichtbarer Mittelpunkt werden mit dem Projekt gespeichert.

# 14. Programmeinstellungen

Die Seiten **Darstellung** und **Farben** enthalten projektbezogene Einstellungen. Sie werden in der jeweiligen `.nnproj`-Datei gespeichert und beim Projektwechsel wiederhergestellt.

Projektbezogen sind insbesondere:

- sichtbare Gewichte, Rechenwerte, Namen, Ports, Kommentare und Kennlinien,
- Darstellung der Gewichte durch Farbe und Linienstärke,
- Farben von Neuronen, Verbindungen, Kommentaren und Zeichenfläche.

Projektunabhängig sind Werkzeugleisten, Eigenschaftenfenster, Projektvorschauen, Projektassistent, Editor-Bedienung, Programmstart, Projektordner und Sprache.

Ein neues Projekt beginnt mit den festen Standardwerten der projektbezogenen Einstellungen.

# 15. Netzwerk automatisch erzeugen

Der Einstieg erfolgt über **Datei → Neu → Netzwerk automatisch erstellen**. Festgelegt werden Input-Neuronen, Hidden-Schichten, Hidden-Neuronen, Output-Neuronen und Aktivierungsfunktionen.

Optional werden aufeinanderfolgende Schichten vollständig verbunden und eine leere Trainingsdatenstruktur angelegt. Erst **OK** erzeugt das neue Projekt; **Abbrechen** lässt das vorhandene Projekt unverändert.

Ein bestehendes Netzwerk kann über **Netzwerk → Anordnen** neu angeordnet werden, ohne Gewichte, Bias-Werte oder Verbindungen zu verändern.

# 16. Trainingsdaten

**Trainingsdaten → Trainingsdaten bearbeiten** öffnet die Tabelle. Jede Zeile ist ein Datensatz; jede Spalte gehört zu einem Input oder Output/Sollwert.

Mögliche Eingaben:

- Werte direkt eingeben,
- tabulatorgetrennte Werte aus der Zwischenablage einfügen,
- CSV-Datei importieren,
- vorhandene `.nndata`-Datei öffnen.

Es werden ausschließlich numerische Werte akzeptiert. Die Spaltenzahl eingefügter oder importierter Daten muss zur Tabellenstruktur passen; fehlende Spalten werden nicht mit Nullen ergänzt.

**Automatisch skalieren nach Tabellendaten** ist nur aktiv, wenn mindestens ein vollständiger numerischer Datensatz vorhanden ist.

# 17. Trainingsdaten zuordnen und skalieren

Ein Rechtsklick auf eine Spaltenüberschrift öffnet die Spalteneigenschaften. Dort werden Neuron, Rolle, binär/analog, Einheit und Skalierung festgelegt.

Analoge Werte außerhalb von −1 bis +1 sollten skaliert werden. Unskalierte Werte verhindern das Training nicht, können es aber langsam, instabil oder erfolglos machen. Gelbe Spaltenköpfe weisen auf eine empfohlene Skalierung hin; binäre 0/1-Spalten benötigen sie nicht.

**Eingabe-Array definieren** ordnet ausschließlich binäre Inputs als zweidimensionales Muster an. Die Funktion eignet sich beispielsweise zur Erkennung von Ziffern, Buchstaben oder Symbolen und ist nur aktiv, wenn alle Eingänge binär sind.

# 18. Training starten

Das Training wird über **Netzwerk → Mit Trainingsdaten trainieren** geöffnet. Voraussetzung sind ein gültiges Netzwerk, vollständige Datenzuordnungen und mindestens ein Trainingsdatensatz.

Das Trainingsfenster zeigt Projekt, Datensatzanzahl, Netzstruktur, Parameterzahl, Ergebniswerte und Fehlerverlauf. Warnungen zu unskalierten Daten sollten vor dem Start geprüft werden.

# 19. Trainingsparameter

Für einen neuen Lauf können Gewichte und Bias neu initialisiert werden. **Xavier/Glorot** für Gewichte und **Bias = 0** sind die empfohlenen Startwerte.

- **Lernrate:** Größe der Parameteränderungen.
- **Momentum:** Anteil der vorherigen Parameteränderung, der in den nächsten Lernschritt übernommen wird. `0` schaltet Momentum aus; hohe Werte können beschleunigen, aber auch Überschwingen verursachen.
- **Fehlergrenze:** gewünschter mittlerer Epochenfehler.
- **Maximale Epochen:** Sicherheitsgrenze des Laufes.
- **Einstellungen vorschlagen:** aus Netzwerkgröße, Aktivierungsfunktionen und zugeordneten Trainingsdaten einen konservativen Startvorschlag erzeugen. Der Vorschlag kann übernommen oder verworfen werden und garantiert keinen erfolgreichen Lauf.
- **Daten monitoren:** Netzwerk während des Trainings sichtbar aktualisieren. Ohne Haken bleibt die Netzwerkdarstellung bis zum Trainingsende eingefroren und das Training läuft mit maximaler Geschwindigkeit.
- **Fehlerkurve:** Verlauf ein- oder ausblenden.

Trainingsziele sind **1 Epoche**, eine feste **Anzahl** oder **Bis Fehlergrenze**.

# 20. Training bedienen und beobachten

- **Neues Training starten:** neuen Lauf mit den gewählten Initialisierungsoptionen beginnen.
- **Neues Training mit gleicher Initialisierung:** einen getrennten Lauf mit den ursprünglichen Gewichten und Bias-Werten des angezeigten Laufes beginnen. Die aktuell eingestellte Lernrate, das Momentum, die Fehlergrenze und die maximale Epochenzahl werden verwendet; Momentumzustände beginnen bei null. Die Funktion ist nur für künftig gespeicherte, zur aktuellen Netzwerkstruktur passende Läufe verfügbar.
- **Fortsetzen:** denselben Lauf mit Gewichten, Bias, Momentumzuständen, Epochenzähler und Fehlerkurve weiterführen. Lernrate und Momentum müssen dabei den ursprünglichen Werten entsprechen.
- **Stoppen:** den laufenden Rechenschritt kontrolliert beenden.
- **Erproben:** aktuellen trainierten Zustand interaktiv untersuchen.
- **Test und Analyse:** Trainings- oder Testdaten auswerten.
- **Training debuggen:** einen Lernschritt detailliert prüfen.
- **Trainingshistorie:** frühere Läufe vergleichen oder wiederherstellen.

Die Y-Achse der Fehlerkurve kann linear oder logarithmisch dargestellt werden. Voll-, Kompakt- und Minimalansicht verändern nur die Anzeige, nicht den Trainingszustand.

# 21. Test und Analyse

Das Analysefenster vergleicht Soll- und Istwerte für Trainings- oder getrennte Testdaten. Es enthält:

- Datensatzvergleich,
- Fehlerauswertung,
- Soll-Ist-Diagramm,
- Toleranzprüfung,
- Einflussanalyse.

Testdaten müssen dieselbe Spaltenstruktur und Zuordnung wie die Trainingsdaten besitzen. Sie prüfen das Netz, verändern aber keine Gewichte oder Bias-Werte.

# 22. Netzwerk erproben

Beim Erproben werden äußere Eingabewerte in ihren ursprünglichen Einheiten verändert. Das Netz führt sofort eine Vorwärtsrechnung aus und zeigt die resultierenden Outputs.

Binäre Inputs werden geschaltet, analoge Inputs über Zahlenfelder oder Regler verändert. **Zwischenwerte anzeigen** aktualisiert zusätzlich die Rechenwerte im Eigenschaftenfenster. Das Experiment verändert keine Gewichte und keinen gespeicherten Lernzustand.

# 23. Anwendungsansicht

Die Anwendungsansicht stellt die Ein- und Ausgaben eines trainierten Netzwerks in einem frei gestaltbaren Bedienbild dar. Dadurch müssen Ergebnisse nicht nur anhand von Zahlen beurteilt werden. Eingabewerte lassen sich direkt verändern, während Anzeigen, Schalter und Zeiger die Reaktion des Netzwerks unmittelbar sichtbar machen. Hintergrundgrafiken und Beschriftungen stellen den Bezug zu einer praktischen Anwendung her.

Die Funktion ist verfügbar, wenn ein gültiges Netzwerk vorhanden ist, Trainingsdaten zugeordnet sind und alle Ein- und Ausgänge gültig zugewiesen wurden.

Der **(i)-Button** links neben **Alles zeigen** ruft diese Einführung jederzeit im Fenster auf. Daneben öffnen **Beschreibung…** und **Testauswertung…** dieselben projektbezogenen Informationen und Auswertungen wie im normalen Erprobungsfenster.

## Bearbeiten und erproben

- Im Modus **Bearbeiten** werden Elemente eingefügt, ausgewählt, verschoben, vergrößert, verkleinert, gefärbt und angeordnet.
- Im Modus **Erproben** lassen sich Inputs und das binäre Eingabe-Array bedienen. Die Gestaltung ist dabei vor unbeabsichtigtem Verschieben geschützt.
- Das Fenster startet im Modus **Erproben**.

Im Menü **Gestaltung** blendet **Raster anzeigen** ein Hilfsraster ein. Über **Rasterabstand…** wird dessen Abstand zwischen 5 und 200 Pixeln festgelegt. Das Raster wird mit dem Projekt gespeichert und ist ausschließlich im Modus **Bearbeiten** sichtbar; beim Erproben wird es automatisch ausgeblendet.

Mit einem Rechtsklick auf eine freie Stelle können einzelne Eingänge und Ausgänge, das binäre Eingabe-Array, eine Grafik, Kommentare sowie Linien, Rechtecke und Kreise eingefügt werden. **Alle Ein- und Ausgänge hinzufügen** ergänzt in einem Schritt sämtliche noch nicht sichtbaren Neuronenkacheln, ohne vorhandene Kacheln zu verdoppeln. Nicht benötigte Ein- und Ausgänge lassen sich aus der Gestaltung entfernen, ohne die zugehörigen Neuronen aus dem Projekt zu löschen.

Analoge Eingänge besitzen Zahlenfeld und Regler, binäre Eingänge einen Ein-/Aus-Schalter. Analoge Ausgänge können als Balken oder Zeigerinstrument dargestellt werden. Binäre Ausgänge zeigen ihre Entscheidung; auf Wunsch werden zusätzlich Zwischenwert und daraus abgeleiteter Zustand angezeigt.

## Grafik, Kommentare und Formen

Eine Grafik kann aus einer Datei geladen, per Drag-and-drop abgelegt oder aus der Zwischenablage eingefügt werden. Beim Speichern wird sie in den Projektbereich übernommen. Kommentare enthalten frei formatierbaren Erklärungstext. Linien, Rechtecke und Kreise besitzen einstellbare Linien-, Flächen- und Transparenzfarben und liegen hinter den Bedienkacheln. Linien können am Ende eine Pfeilspitze tragen; **Pfeilrichtung umkehren** setzt die Spitze auf das jeweils andere Linienende.

## Auswählen, anordnen und speichern

Ein Auswahlrahmen markiert nur vollständig eingeschlossene Elemente. Markierte Elemente erhalten einen roten Rahmen und können gemeinsam verschoben, mit den Pfeiltasten pixelweise bewegt, ausgerichtet, verteilt oder in eine einheitliche Größe gebracht werden. Grafische Gestaltungselemente können mit **Strg+C** und **Strg+V** kopiert werden.

Das Mausrad zoomt um den Mauszeiger. Mit **Alt+Ziehen** wird die Ansicht verschoben; **Alles zeigen** passt die vollständige Gestaltung in das Fenster ein. Zoomstufe, Fenstergröße, sichtbare Elemente, Positionen, Größen und Farben werden mit dem Projekt gespeichert.

**Strg+S** speichert die Gestaltung. Ohne offene Änderung ist **Speichern** deaktiviert. Beim Schließen oder mit **Esc** wird bei ungespeicherten Änderungen nachgefragt. **Standardlayout** setzt Positionen und Größen nach Bestätigung zurück, behält aber die Hintergrundgrafik. Die Gestaltung liegt lesbar unter `grafisches_experiment/layout.json`; Netzwerk und Gewichte bleiben unverändert in der Projektdatei.

# 24. Training debuggen

Der Trainings-Debugger untersucht einen einzelnen Lernschritt mit Vorwärts- und Rückwärtsrechnung. Angezeigt werden Eingaben, Summen, Aktivierungen, Fehler, Deltas sowie Änderungen von Gewichten und Bias. Bei aktivem Momentum gehören auch vorherige Bewegung, Momentumanteil und neue Bewegung zum Rechenweg.

Er eignet sich zur Fehlersuche, wenn ein Netz nicht lernt oder ein Ergebnis mathematisch nachvollzogen werden soll. Der Zustand beim Öffnen kann wiederhergestellt werden.

# 25. Mathematikmodus

Der Mathematikmodus verarbeitet Trainingsdatensätze bewusst einzeln und arbeitet mit einer experimentellen Kopie des Netzwerks.

1. Ein Neuron auswählen.
2. Lernrate, Momentum, Anzeigegenauigkeit und Startart festlegen.
3. **Experiment starten**.
4. Die Phasen Startwerte, Eingaben, gewichtete Summe, Aktivierung, Fehler/Delta, neue Parameter und Ergebnis durchlaufen.
5. Den nächsten Datensatz oder die nächste Epoche beginnen.

Hidden-Neuronen zeigen Rückwärtssumme, Ableitung und Hidden-Delta; Output-Neuronen zeigen Sollwert, Fehler und Output-Delta. Bei den Parameteränderungen werden Gradient, vorherige Bewegung, Momentumanteil und neue Bewegung getrennt ausgewiesen. **Vollständiges Protokoll** enthält den gesamten Rechenweg. Rücknahmen stellen auch die Momentumzustände wieder her. Beim Schließen wird der ursprüngliche Projektzustand wiederhergestellt.

# 26. Projekt speichern und öffnen

**Speichern** schreibt das Projekt an seinen vorhandenen Pfad. **Speichern unter** erstellt auf Wunsch einen eigenen Projektordner mit:

```text
Projektname/
├── Projektname.nnproj
├── trainingsdaten/
├── testdaten/
└── exporte/
```

Der bevorzugte Projektordner wird unter **Programmeinstellungen → Editor → Projektpfad** gewählt. Ohne eigene Auswahl verwendet die deutsche Oberfläche `Projects_de`, die englische `Projects_en`. Ein frei gewählter Ordner kann unabhängig von der Programmsprache verwendet werden.

# 27. Trainings- und Testdatendateien

Trainings- und Testdaten werden als `.nndata` gespeichert. Zugeordnete Dateien können gemeinsam mit dem Projekt gespeichert oder bei **Speichern unter** in den neuen Projektordner übernommen werden.

Relative Verweise innerhalb eines strukturierten Projektordners erleichtern das Verschieben des vollständigen Projekts. Fehlende Datendateien werden beim Öffnen gemeldet und können neu ausgewählt werden.

# 28. Projektinformationen und Bericht

**Projektbeschreibung** speichert formatierten Text direkt im Projekt. **Projektübersicht** fasst Struktur, Daten und Trainingszustand zusammen. Der **Projektablauf** führt als Navigator durch wichtige Arbeitsschritte.

Der Projektbericht kann als Word- oder PDF-Dokument exportiert werden. Sprache und Dateiformat richten sich nach den gewählten Einstellungen beziehungsweise dem Speicherdialog.

# 29. Beispielprojekte und Projektassistent

Das Menü **Datei → Beispielprojekte** durchsucht den aktuell gewählten Projektordner nach entsprechend gekennzeichneten Projekten. Deutsche und englische Projektsammlungen können unabhängig von der Programmsprache gewählt werden.

Der Projektassistent hilft beim Entwickeln eigener Ideen. Er erzeugt einen bearbeitbaren Prompt für eine externe KI mit Projektbeschreibung, Inputs, Outputs, Wertebereichen, Grundlagen, Netzvorschlag und tabulatorgetrennten Trainingsdaten. NeuronNetz sendet selbst keine Daten an einen externen Dienst.

# 30. Typische Probleme

**Training startet nicht:** Netzwerk prüfen, Datenzuordnung kontrollieren und vollständige numerische Datensätze sicherstellen.

**Training lernt nicht:** Skalierung, Aktivierungsfunktionen, Lernrate, Sollwerte und Initialisierung prüfen.

**Fehler schwankt stark:** Lernrate verkleinern und Daten auf Ausreißer untersuchen.

**Sollwerte werden nicht erreicht:** Wertebereich der Output-Aktivierungsfunktion prüfen.

**Projekt- oder Datendatei fehlt:** vollständigen Projektordner verschieben und fehlende Datei neu zuordnen.

**Darstellung ist unübersichtlich:** Netzwerk anordnen, Gewichtswerte ausblenden oder Zoom und Alles zeigen verwenden.

# 31. Tastenkürzel

- **Strg+N:** Neues Projekt
- **Strg+O:** Projekt öffnen
- **Strg+S:** Speichern
- **Strg+Umschalt+S:** Speichern unter
- **Strg+Z:** Rückgängig
- **Strg+Y:** Wiederholen
- **Strg+X / Strg+C / Strg+V:** Ausschneiden, kopieren, einfügen
- **Entf:** Auswahl löschen
- **Alt+F4:** Programm beenden

# 32. Mathematische Grundlagen

Für ein Neuron gilt vereinfacht:

```text
Σ = Summe(Eingang × Gewicht) + Bias
Y = Aktivierungsfunktion(Σ)
```

Beim Training wird aus Sollwert und Ausgabe ein Fehler bestimmt. Backpropagation berechnet daraus Deltas und korrigiert Gewichte und Bias entgegen dem Fehlergradienten. Die Lernrate steuert die Größe dieser Korrektur.

Sigmoid liefert Werte zwischen 0 und 1, Tanh zwischen −1 und 1, ReLU setzt negative Summen auf 0 und Linear gibt die Summe unverändert weiter.

# 33. Trainingshistorie

Die Trainingshistorie speichert Läufe projektbezogen mit Parametern, Ergebniswerten und kompakter Fehlerkurve. Läufe können verglichen, als CSV exportiert, gelöscht oder – bei kompatibler Netzstruktur – wiederhergestellt werden.

Werden alle Läufe gelöscht, verschwinden Ergebnisanzeige und Kurve im geöffneten Trainingsfenster. Die aktuellen Gewichte und Bias-Werte des Netzwerks bleiben erhalten.

# 34. Ausführliches Handbuch

Diese Markdown-Datei ist eine kompakte Soforthilfe. Das vollständige bebilderte Handbuch erklärt sämtliche Fenster, Schaltflächen und ausführlichen Beispiele.

Über **Hilfe → Tutorials** kann das deutsche oder englische Handbuch als Word- oder PDF-Datei ausgewählt und mit dem zugeordneten Windows-Programm geöffnet werden. NeuronNetz merkt sich den zuletzt gewählten Tutorialordner.
