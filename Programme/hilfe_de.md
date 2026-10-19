# NeuronNetz – kompakte Hilfe

Diese integrierte Hilfe beantwortet die wichtigsten Fragen direkt im Programm. Das ausführliche bebilderte Handbuch kann über **Hilfe → Tutorials** als Word- oder PDF-Datei geöffnet werden.

## Einordnung und besonderer Nutzen von NeuronNetz

NeuronNetz ist ein transparentes Entwicklungs- und Lernwerkzeug für kleine
neuronale Netze in der Automatisierungstechnik. Das Tool verbindet die
Bearbeitung der Trainingsdaten, den grafischen Aufbau des Netzes, das Training,
die Prüfung der Ergebnisse, die Gestaltung einer Anwendungsansicht und den
Export des trainierten Netzes als SPS-Code in einer gemeinsamen
Arbeitsumgebung.

Im Mittelpunkt steht die Nachvollziehbarkeit. Der Anwender sieht nicht nur,
dass ein neuronales Netz ein Ergebnis liefert, sondern kann untersuchen, wie
dieses Ergebnis entsteht. Netzwerkstruktur, Neuronen, Verbindungen, Gewichte,
Bias-Werte und Aktivierungsfunktionen bleiben sichtbar. Auch der Lernprozess
kann anhand der Fehlerentwicklung, einzelner Datensätze und gespeicherter
Vergleichsläufe verfolgt werden.

### Ein durchgängiger Arbeitsablauf

NeuronNetz begleitet ein Projekt von den Ausgangsdaten bis zur späteren
Verwendung des trainierten Netzes:

1. Trainingsdaten erstellen, importieren und beschreiben.
2. Eingänge und Ausgänge den Neuronen zuordnen.
3. Analoge Werte skalieren und binäre Werte kennzeichnen.
4. Eine geeignete Netzwerkstruktur aufbauen.
5. Das Netz trainieren und den Lernverlauf beobachten.
6. Frühere Trainingsläufe miteinander vergleichen.
7. Das Netz mit Trainingsdaten und getrennten Testdaten prüfen.
8. Kennlinien, Abweichungen, Toleranzen und Einflüsse untersuchen.
9. Eine übersichtliche Anwendungsansicht gestalten.
10. Das geprüfte Netz als nachvollziehbaren SPS-Code exportieren.

Dadurch bleiben Daten, Netzwerk und spätere Anwendung miteinander verbunden.
Änderungen an der Datenstruktur, Skalierung oder Netzwerkstruktur werden
sichtbar und können gezielt geprüft werden.

### Sichtbarer und nachvollziehbarer Lernprozess

Viele Werkzeuge behandeln ein trainiertes Modell hauptsächlich als fertige
Datei. NeuronNetz legt den Schwerpunkt auf die einzelnen Schritte, die zu
diesem Modell führen.

Der Anwender kann unter anderem untersuchen:

- wie das Netzwerk aufgebaut ist,
- welche Neuronen und Verbindungen beteiligt sind,
- wie sich Gewichte und Bias-Werte während des Trainings verändern,
- wie Eingabewerte intern skaliert werden,
- wie ein einzelner Datensatz vorwärts und rückwärts durch das Netz verarbeitet
  wird,
- wie sich der mittlere Fehler entwickelt,
- wie groß der maximale Fehler eines einzelnen Datensatzes ist,
- ob ein kleiner mittlerer Fehler möglicherweise größere Einzelabweichungen
  verdeckt,
- wie sich verschiedene Initialisierungen und Trainingsparameter auswirken.

Gespeicherte Vergleichsläufe machen sichtbar, ob ein neuer Trainingslauf
tatsächlich eine Verbesserung bringt. Die Fehlerkurven können über ihre gesamte
Länge verglichen werden. Dadurch lassen sich unterschiedliche Lernraten,
Initialisierungen und Netzstrukturen beurteilen, ohne nur das Endergebnis zu
betrachten.

### Umfassendere Prüfung des trainierten Netzes

Ein kleiner mittlerer Trainingsfehler allein reicht nicht aus, um die Qualität
eines Netzes zu beurteilen. Deshalb stellt NeuronNetz mehrere ergänzende
Auswertungen bereit.

Dazu gehören:

- Datensatzvergleich,
- Fehlerauswertung,
- maximaler Einzelfehler,
- Soll-Ist-Diagramm,
- Netzkennlinie,
- Toleranzprüfung,
- Einflussanalyse,
- Prüfung mit getrennten Testdaten.

Die Netzkennlinie zeigt, wie der Ausgang auf Veränderungen eines ausgewählten
Eingangs reagiert. Die Einflussanalyse macht sichtbar, welche Eingänge das
gewählte Ausgangsneuron besonders stark beeinflussen. Mit der Toleranzprüfung
lässt sich untersuchen, wie häufig und wie stark die berechneten Werte von den
Sollwerten abweichen.

Diese Funktionen helfen, unplausible Zusammenhänge, unzureichend abgedeckte
Wertebereiche und einzelne problematische Datensätze zu erkennen. Sie ersetzen
keine fachliche Prüfung, ermöglichen aber eine deutlich gründlichere
Beurteilung als die alleinige Betrachtung des Trainingsfehlers.

### Bedeutung der Trainingsdaten

Die Aussagekraft eines neuronalen Netzes hängt wesentlich von seinen
Trainingsdaten ab. Deshalb unterscheidet NeuronNetz die Herkunft der Daten:

- **Empirische Messdaten**
- **Formelbasiert erzeugte Daten**
- **Simulationsdaten**
- **Gemischte Daten**
- **Nicht angegeben**

Formelbasiert erzeugte Daten eignen sich besonders als Lernbeispiele. Sie
zeigen anschaulich, dass ein neuronales Netz einen bekannten mathematischen
Zusammenhang erlernen und annähern kann. Solche Projekte sind hilfreich, um
Netzwerkstruktur, Skalierung, Training und Fehlerentwicklung zu verstehen.

Für eine reale Steuerungsaufgabe ist die direkte Programmierung einer bekannten
Formel jedoch häufig einfacher, genauer und leichter nachzuweisen. Ein
neuronales Netz bietet vor allem dann einen praktischen Vorteil, wenn der
Zusammenhang zwischen Eingängen und Ausgängen nicht vollständig als Formel
beschrieben werden kann.

Empirische Messdaten stammen beispielsweise aus Versuchen, Prüfständen,
Laboruntersuchungen oder aufgezeichneten Anlagenzuständen. Sie enthalten häufig
Messrauschen, Streuungen, ungleichmäßig verteilte Betriebspunkte und seltene
Sonderfälle. Genau diese Eigenschaften machen sie für praktische Anwendungen
interessant.

Geeignete Anwendungsfälle sind beispielsweise:

- Schätzung einer nur im Labor bestimmbaren Produktqualität aus laufend
  verfügbaren Prozesswerten,
- Erkennung von Motor-, Pumpen- oder Anlagenzuständen,
- Abschätzung von Werkzeugverschleiß,
- Vorhersage des tatsächlichen Energiebedarfs,
- Ermittlung eines experimentell bestimmten Wirkungsgrades,
- Erkennung von Raumbelegung aus mehreren Sensordaten,
- Schätzung von Emissionen oder anderen schwer direkt messbaren Größen.

Simulationsdaten können sinnvoll sein, wenn ein Prozessmodell komplexe
Betriebszustände abbildet oder reale Messungen nur schwer, teuer oder gefährlich
durchführbar sind. Dabei sollte dokumentiert werden, auf welchem Modell die
Simulation beruht und welche Vereinfachungen vorgenommen wurden.

Gemischte Daten verbinden beispielsweise reale Messwerte mit ergänzenden
Simulationsdaten. In solchen Fällen muss erkennbar bleiben, welche Bestandteile
gemessen und welche künstlich erzeugt wurden.

Die Kennzeichnung der Datenherkunft verändert weder die Datensätze noch das
Training. Sie hilft dem Anwender, den Zweck und die Aussagekraft eines Projekts
richtig einzuordnen.

### Training auf dem PC und Ausführung in der SPS

Für industrielle Anwendungen ist ein kontrollierter Ablauf sinnvoll:

1. Die SPS oder ein anderes Erfassungssystem sammelt Prozess- und Messdaten.
2. Fehlende Sollwerte werden durch Laborergebnisse, Qualitätsprüfungen oder
   bestätigte Anlagenzustände ergänzt.
3. Die Daten werden außerhalb der SPS aufbereitet.
4. NeuronNetz trainiert und prüft das Netzwerk.
5. Der Anwender bewertet Trainings- und Testdaten, Fehlerverlauf und
   Einzelfehler.
6. Das freigegebene Netz wird als versionierter SPS-Funktionsbaustein
   exportiert.
7. Die SPS führt im Betrieb nur die Vorwärtsberechnung des geprüften Netzes aus.
8. Neue Betriebsdaten können später für ein kontrolliertes Nachtraining
   verwendet werden.

Dieser Ablauf trennt das Lernen des Netzes von seinem produktiven Einsatz. Ein
neuer Trainingsstand beeinflusst die Anlage erst, nachdem er geprüft und
bewusst freigegeben wurde. Der deterministische SPS-Zyklus wird nicht durch
einen laufenden Trainingsvorgang belastet.

Ein selbstständiges und unkontrolliertes Weiterlernen in der SPS ist nicht das
Ziel von NeuronNetz. Änderungen am Modell sollen nachvollziehbar, vergleichbar
und bei Bedarf rückgängig zu machen sein.

### Einordnung gegenüber industriellen KI-Lösungen

Industrielle KI-Plattformen konzentrieren sich häufig auf die Ausführung bereits
vorbereiteter Modelle, die Verwaltung vieler Modellversionen, leistungsfähige
Hardware und die Einbindung in größere Daten- und Automatisierungsstrukturen.
Dafür werden je nach Hersteller besondere Laufzeitkomponenten, Edge-Geräte oder
zusätzliche Lizenzen benötigt.

NeuronNetz verfolgt einen überschaubaren und transparenten Ansatz:

| NeuronNetz | Typische industrielle KI-Plattform |
|---|---|
| Netzwerk kann grafisch aufgebaut werden | Modell wird häufig mit externen Werkzeugen erstellt |
| Lernvorgang ist sichtbar und untersuchbar | Training bleibt meist außerhalb der Laufzeitumgebung |
| Gewichte, Bias-Werte und Rechenschritte sind nachvollziehbar | Modell wird überwiegend als fertige Datei eingesetzt |
| Trainingsdaten können direkt bearbeitet und skaliert werden | Schwerpunkt liegt häufig auf Datenanbindung und Modellbereitstellung |
| Vergleichsläufe und Einzelfehler können untersucht werden | Schwerpunkt liegt häufig auf Betrieb und Verwaltung freigegebener Modelle |
| Exportiert nachvollziehbaren Structured Text | Modell wird häufig durch eine besondere Laufzeit ausgeführt |
| Keine zusätzliche KI-Laufzeit für den erzeugten SPS-Code erforderlich | Je nach Lösung werden Laufzeitlizenz oder Edge-Hardware benötigt |
| Für kleine und verständliche Netze ausgelegt | Auch für große und komplexe Modelle geeignet |
| Lern-, Analyse- und Engineeringwerkzeug | Industrielle Infrastruktur- und Ausführungsplattform |

NeuronNetz ersetzt keine umfassende industrielle KI-Infrastruktur. Seine Stärke
liegt in der Verbindung von Verständlichkeit, Datenbearbeitung, sichtbarem
Training, ausführlicher Analyse und nachvollziehbarem SPS-Code.

Das Tool nimmt damit eine Position zwischen einfachen Lernprogrammen und
umfangreichen industriellen KI-Plattformen ein: Das Netz wird auf dem PC
verständlich entwickelt und geprüft; das freigegebene Modell kann anschließend
ohne besondere KI-Laufzeit als normaler SPS-Code ausgeführt werden.

### Grenzen und Verantwortung

Ein erfolgreiches Training beweist nicht automatisch, dass ein Netz für eine
reale Anlage geeignet ist. Entscheidend sind die Qualität und
Repräsentativität der Daten, die Abdeckung aller zulässigen Betriebszustände,
getrennte Testdaten und eine fachliche Bewertung der Ergebnisse.

Vor einem praktischen Einsatz müssen insbesondere folgende Fragen geklärt
werden:

- Sind alle relevanten Betriebsbereiche in den Daten vertreten?
- Wurden Trainings- und Testdaten sinnvoll getrennt?
- Sind Messfehler und Ausreißer geprüft worden?
- Verhalten sich die Ausgänge auch zwischen den vorhandenen Datensätzen
  plausibel?
- Was geschieht bei Eingaben außerhalb des bekannten Datenbereichs?
- Ist eine direkte Formel oder klassische Regelung möglicherweise besser
  geeignet?
- Wurde das exportierte Netz unter realistischen Bedingungen geprüft?
- Sind die Anforderungen an Sicherheit, Dokumentation und Freigabe erfüllt?

NeuronNetz unterstützt diese Beurteilung durch transparente Darstellung und
verschiedene Prüfwerkzeuge. Die Verantwortung für Datenqualität, fachliche
Plausibilität und den sicheren Einsatz des exportierten Netzes bleibt beim
Anwender.

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
- **SPS-Export:** trainierte Netze als Mitsubishi-Funktionsbaustein übertragen.
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

Projektunabhängig sind Werkzeugleisten, Eigenschaftenfenster, Projektvorschauen, Projektassistent, Editor-Bedienung, Programmstart, Projektordner, Sprache und experimentelle Funktionen.

Auf der Seite **Experimentell** blendet **SPS-Export in der Menüleiste anzeigen** das vollständige SPS-Menü unmittelbar ein oder aus. Die Auswahl wird in `settings.json` gespeichert und verändert das Projekt nicht.

Ein neues Projekt beginnt mit den festen Standardwerten der projektbezogenen Einstellungen.

# 15. Netzwerk automatisch erzeugen

Der Einstieg erfolgt über **Datei → Neu → Netzwerk automatisch erstellen**. Festgelegt werden Input-Neuronen, Hidden-Schichten, Hidden-Neuronen, Output-Neuronen und Aktivierungsfunktionen.

Optional werden aufeinanderfolgende Schichten vollständig verbunden und eine leere Trainingsdatenstruktur angelegt. Erst **OK** erzeugt das neue Projekt; **Abbrechen** lässt das vorhandene Projekt unverändert.

Ein bestehendes Netzwerk kann über **Netzwerk → Anordnen** neu angeordnet werden, ohne Gewichte, Bias-Werte oder Verbindungen zu verändern.

# 16. Trainingsdaten

**Trainingsdaten → Trainingsdaten bearbeiten** öffnet die Tabelle. Jede Zeile ist ein Datensatz; jede Spalte gehört zu einem Input oder Output/Sollwert.

Oben rechts kennzeichnet **Herkunft der Trainingsdaten**, wie die Werte entstanden sind: empirische Messdaten, formelbasiert erzeugte Daten, Simulationsdaten, gemischte Daten oder nicht angegeben. Neue und ältere Dateien verwenden zunächst **Nicht angegeben**. Die Auswahl wird in der `.nndata`-Datei gespeichert und im Trainingsfenster sowie in Trainingsberichten angezeigt.

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

Für einen neuen Lauf können Gewichte und Bias neu initialisiert werden. Empfohlen sind **Automatisch nach Aktivierungsfunktion** für Gewichte und **Bias = 0**. Im Automatikmodus wird für ReLU **He**, für Sigmoid, Tanh und Linear **Xavier/Glorot** verwendet. Alternativ können Xavier/Glorot oder He für alle Gewichte gewählt werden; **Alle Gewichte = 0** ist ausschließlich für Testzwecke vorgesehen.

- **Lernrate:** Größe der Parameteränderungen.
- **Momentum:** Anteil der vorherigen Parameteränderung, der in den nächsten Lernschritt übernommen wird. `0` schaltet Momentum aus; hohe Werte können beschleunigen, aber auch Überschwingen verursachen.
- **Fehlergrenze:** gewünschter mittlerer Epochenfehler.
- **Maximale Epochen:** Sicherheitsgrenze des Laufes.
- **Einstellungen vorschlagen:** aus Netzwerkgröße, Aktivierungsfunktionen und zugeordneten Trainingsdaten einen konservativen Startvorschlag erzeugen. Der Vorschlag kann übernommen oder verworfen werden und garantiert keinen erfolgreichen Lauf.
- **Daten monitoren:** Netzwerk während des Trainings sichtbar aktualisieren. Ohne Haken bleibt die Netzwerkdarstellung bis zum Trainingsende eingefroren und das Training läuft mit maximaler Geschwindigkeit. Beim Start eines neuen Trainings ist die Option immer ausgeschaltet und kann anschließend bewusst aktiviert werden.
- **Fehlerkurve:** Verlauf ein- oder ausblenden.

Trainingsziele sind **1 Epoche**, eine feste **Anzahl** oder **Bis Fehlergrenze**.

# 20. Training bedienen und beobachten

- **Neues Training starten:** neuen Lauf mit den gewählten Initialisierungsoptionen beginnen.
- **Neues Training mit gleicher Initialisierung:** einen getrennten Lauf mit den ursprünglichen Gewichten und Bias-Werten des angezeigten Laufes beginnen. Die aktuell eingestellte Lernrate, das Momentum, die Fehlergrenze und die maximale Epochenzahl werden verwendet; Momentumzustände beginnen bei null. Die Funktion ist nur für künftig gespeicherte, zur aktuellen Netzwerkstruktur passende Läufe verfügbar.
- **Fortsetzen:** Bei unveränderter Lernrate und unverändertem Momentum wird derselbe Lauf mit Gewichten, Bias, Momentumzuständen, Epochenzähler und Fehlerkurve weitergeführt. Wurden Lernrate oder Momentum geändert, können entweder die ursprünglichen Werte wiederhergestellt oder die aktuellen Gewichte und Bias-Werte in einen neuen, mit dem bisherigen Lauf verknüpften Lauf übernommen werden. Im neuen Lauf beginnen Momentumzustände und Fehlerkurve neu.
- **Stoppen:** den laufenden Rechenschritt kontrolliert beenden.
- **Erproben:** aktuellen trainierten Zustand interaktiv untersuchen.
- **Test und Analyse:** Trainings- oder Testdaten auswerten.
- **Training debuggen:** einen Lernschritt detailliert prüfen.
- **Trainingshistorie:** frühere Läufe vergleichen oder wiederherstellen.

Die Y-Achse der Fehlerkurve kann linear oder logarithmisch dargestellt werden. Voll-, Kompakt- und Minimalansicht verändern nur die Anzeige, nicht den Trainingszustand.

**Kurvenanzeige** oben im Ergebnisrahmen wechselt zwischen mittlerem Epochenfehler (MSE), maximalem Einzelfehler in internen Netzwerten und **Netzkennlinie**. MSE und maximaler Einzelfehler werden beim Training aufgezeichnet und mit dem Lauf gespeichert. Die Fehlergrenze gilt ausschließlich für den MSE. Für die Netzkennlinie werden Eingang, Ausgang und Bezugsdatensatz gewählt; nur der ausgewählte Eingang wird verändert. Sie zeigt den aktuellen Netzstand, wird nur bei ausgewählter Ansicht berechnet und verändert weder Training noch Gewichte oder Bias-Werte. Vergleichsläufe ohne den gewählten Verlauf bleiben ausgewählt, werden aber nicht gezeichnet und mit „Kein Verlauf vorhanden“ gekennzeichnet. Bei fortgesetzten alten Läufen beginnt die Maximalfehlerkurve erst mit den neu trainierten Epochen.

**Vergleichsläufe…** im Bereich **Fehlerverlauf** öffnet eine kompakte Auswahl früherer Läufe mit Laufnummer, Datum, Epochenzahl und maximalem Einzelfehler am gespeicherten Laufende. Häkchen blenden bis zu drei Vergleichskurven ein oder aus, während das Training weiterläuft. Bei drei ausgewählten Läufen muss zunächst einer abgewählt werden. Die farbige Legende steht platzsparend in der oberen Zeile zwischen Vergleichsauswahl und Y-Achse. Der aktuelle Lauf bleibt kräftig blau; Vergleichskurven erscheinen dünner in anderen Farben und reichen standardmäßig bis zur aktuellen Epoche. Ein Klick auf den Lauf in der Legende blendet ihn aus. Für einen aussagekräftigen Vergleich müssen Trainingsdaten und Skalierung unverändert sein; die Zuordnung erfolgt anhand der in der Historie gespeicherten Trainingsdatei. Die Trainingshistorie dient weiterhin zum Verwalten und Wiederherstellen der Läufe.

**Gesamten Verlauf anzeigen** steht direkt neben **Vergleichsläufe…** und kann bereits ohne ausgewählten Vergleichslauf aktiviert werden. Die Option verlängert jeden später gewählten Vergleichslauf bis zu seiner gespeicherten letzten Epoche. Der längste sichtbare Lauf bestimmt dann die Epochenachse. Ohne Haken enden die Vergleichskurven bei der aktuellen Epoche. Werden alle Vergleichsläufe abgewählt, erscheint der aktuelle Lauf wieder über seine vollständige bisherige Dauer.

# 21. Test und Analyse

Das Analysefenster vergleicht Soll- und Istwerte für Trainings- oder getrennte Testdaten. Es enthält:

- Datensatzvergleich,
- Fehlerauswertung,
- Soll-Ist-Diagramm,
- Netzkennlinie,
- Toleranzprüfung,
- Einflussanalyse.

Testdaten müssen dieselbe Spaltenstruktur und Zuordnung wie die Trainingsdaten besitzen. Sie prüfen das Netz, verändern aber keine Gewichte oder Bias-Werte.

Bei umfangreichen Datensätzen zeigen Datensatzvergleich und Einflussanalyse während der Berechnung einen Fortschrittsbalken, der nach Abschluss wieder verschwindet. Die Netzwerkzeichnung im Hintergrund bleibt dabei eingefroren, damit die Auswertung schneller läuft. Die Datenquelleninformation wird bereits vor der Berechnung angezeigt.

Im Soll-Ist-Diagramm kann ein Ausgang oder **Alle Outputs** gewählt werden. Auch die gemeinsame Ansicht besitzt eine Toleranzanzeige. Bei unterschiedlichen Einheiten verwendet sie eine einheitenunabhängige prozentuale Toleranz; die nicht passende Auswahl bleibt gesperrt.

# 22. Netzwerk erproben

Beim Erproben werden äußere Eingabewerte in ihren ursprünglichen Einheiten verändert. Das Netz führt sofort eine Vorwärtsrechnung aus und zeigt die resultierenden Outputs.

Binäre Inputs werden geschaltet, analoge Inputs über Zahlenfelder oder Regler verändert. **Zwischenwerte anzeigen** aktualisiert zusätzlich die Rechenwerte im Eigenschaftenfenster. Das Experiment verändert keine Gewichte und keinen gespeicherten Lernzustand.

Wertebereiche stehen in drei sauber ausgerichteten Spalten für Minimum, Trennzeichen und Maximum. Übliche Grenzen werden mit höchstens zwei Nachkommastellen angezeigt; sehr kleine Werte unter 0,01 bleiben in geeigneter Genauigkeit erhalten. Die Fensterhöhe richtet sich nach dem Inhalt und muss nicht unnötig vergrößert werden.

# 23. Anwendungsansicht

Die Anwendungsansicht stellt die Ein- und Ausgaben eines trainierten Netzwerks in einem frei gestaltbaren Bedienbild dar. Dadurch müssen Ergebnisse nicht nur anhand von Zahlen beurteilt werden. Eingabewerte lassen sich direkt verändern, während Anzeigen, Schalter und Zeiger die Reaktion des Netzwerks unmittelbar sichtbar machen. Hintergrundgrafiken und Beschriftungen stellen den Bezug zu einer praktischen Anwendung her.

Die Funktion ist verfügbar, wenn ein gültiges Netzwerk vorhanden ist, Trainingsdaten zugeordnet sind und alle Ein- und Ausgänge gültig zugewiesen wurden.

Der **(i)-Button** links neben **Alles zeigen** ruft diese Einführung jederzeit im Fenster auf. Daneben öffnen **Beschreibung…** und **Testauswertung…** dieselben projektbezogenen Informationen und Auswertungen wie im normalen Erprobungsfenster.

## Bearbeiten und erproben

- Im Modus **Bearbeiten** werden Elemente eingefügt, ausgewählt, verschoben, vergrößert, verkleinert, gefärbt und angeordnet.
- Im Modus **Erproben** lassen sich Inputs und das binäre Eingabe-Array bedienen. Die Gestaltung ist dabei vor unbeabsichtigtem Verschieben geschützt.
- Das Fenster startet im Modus **Erproben**.

Binäre Eingänge und Zellen des binären Eingabe-Arrays lassen sich nur im Modus **Erproben** schalten. Im Bearbeitungsmodus dienen Mausklicks ausschließlich der Gestaltung.

Im Menü **Gestaltung** blendet **Raster anzeigen** ein Hilfsraster ein. Über **Rasterabstand…** wird dessen Abstand zwischen 5 und 200 Pixeln festgelegt. **Am Raster einrasten** richtet Elemente beim Einfügen, Verschieben und Ändern der Größe am sichtbaren Raster aus; dies gilt auch für Gruppen, Hintergründe und Linienendpunkte. Die Option wird mit dem Projekt gespeichert. Beim Erproben wird das Raster automatisch ausgeblendet. Positionen älterer Projekte ändern sich erst, wenn ein Element bearbeitet wird.

Mit einem Rechtsklick auf eine freie Stelle können einzelne Eingänge und Ausgänge, das binäre Eingabe-Array, eine Grafik, Kommentare sowie Linien, Rechtecke und Kreise eingefügt werden. **Alle Ein- und Ausgänge hinzufügen** ergänzt in einem Schritt sämtliche noch nicht sichtbaren Neuronenkacheln, ohne vorhandene Kacheln zu verdoppeln. Nicht benötigte Ein- und Ausgänge lassen sich aus der Gestaltung entfernen, ohne die zugehörigen Neuronen aus dem Projekt zu löschen.

Analoge Eingänge besitzen ein kompaktes, zentriertes Zahlenfeld und einen Regler, binäre Eingänge einen Ein-/Aus-Schalter. Analoge Ausgänge können als Balken oder Zeigerinstrument dargestellt werden; beide Skalen zeigen **0 %** bis **100 %**. Lange Namen und Einheiten passen sich an die Kartengröße an und bleiben vollständig als Hinweis verfügbar. Analoge Werte werden mit höchstens zwei Nachkommastellen angezeigt, Werte unter 0,01 bei Bedarf genauer. Bei jedem binären Ausgang kann im eigenen Kontextmenü individuell gewählt werden, ob nur die Entscheidung oder zusätzlich Zwischenwert und daraus abgeleiteter Zustand angezeigt werden.

## Grafik, Kommentare und Formen

Eine Grafik kann aus einer Datei geladen, per Drag-and-drop abgelegt oder aus der Zwischenablage eingefügt werden. Beim Speichern wird sie in den Projektbereich übernommen. Kommentare enthalten frei formatierbaren Erklärungstext. Linien, Rechtecke und Kreise besitzen einstellbare Linien-, Flächen- und Transparenzfarben und liegen hinter den Bedienkacheln. Linien können am Ende eine Pfeilspitze tragen; **Pfeilrichtung umkehren** setzt die Spitze auf das jeweils andere Linienende. Eine nach Kategorien gegliederte Symbolbibliothek enthält auch logische Symbole. Dieselbe Auswahl erscheint beim Einfügen und bei **Symbol ändern…** im Kontextmenü.

## Auswählen, anordnen und speichern

Ein Auswahlrahmen markiert nur vollständig eingeschlossene Elemente. Markierte Elemente erhalten einen roten Rahmen und können gemeinsam verschoben, mit den Pfeiltasten pixelweise bewegt, ausgerichtet, verteilt oder in eine einheitliche Größe gebracht werden. Grafische Gestaltungselemente können mit **Strg+C** und **Strg+V** kopiert werden.

Das Kontextmenü kann einzelne oder mehrere Elemente **sperren** und wieder **entsperren**. Gesperrte Elemente sind im Bearbeitungsmodus durch ein kleines Schloss gekennzeichnet, lassen sich weiterhin auswählen und entsperren, aber weder verschieben, verändern noch löschen. **In den Vordergrund** und **In den Hintergrund** ändern die gespeicherte Ebenenreihenfolge; das Hintergrundbild bleibt immer ganz hinten. Rechtecke und Kreise bleiben auch mit transparenter Füllung über ihre gesamte Fläche greifbar.

Bei einer aktiven Mehrfachauswahl zeigt der rechte Informationsbereich gemeinsame Angaben zur Auswahl. Ohne Mehrfachauswahl erscheint dort wieder die normale Projektanzeige.

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

Die zuletzt geöffneten Projekte werden innerhalb derselben `settings.json` getrennt für Deutsch und Englisch geführt. Dadurch erscheinen in der englischen Oberfläche keine Einträge aus der deutschen Liste und umgekehrt.

# 27. Trainings- und Testdatendateien

Trainings- und Testdaten werden als `.nndata` gespeichert. Zugeordnete Dateien können gemeinsam mit dem Projekt gespeichert oder bei **Speichern unter** in den neuen Projektordner übernommen werden.

Relative Verweise innerhalb eines strukturierten Projektordners erleichtern das Verschieben des vollständigen Projekts. Fehlende Datendateien werden beim Öffnen gemeldet und können neu ausgewählt werden.

# 28. Projektinformationen und Bericht

**Projektbeschreibung** speichert formatierten Text direkt im Projekt. Markierter Text kann unmittelbar in Schriftart, Schriftgröße, Fett, Kursiv und Unterstrichen geändert werden. Enthält eine Markierung unterschiedliche Formatierungen, zeigen die Bedienelemente keinen irreführenden Einzelwert. Tabulatoren, Zeilenumbrüche, Einzüge und eingefügte mathematische Schreibweisen bleiben erhalten.

**Projektübersicht** fasst Struktur, Daten und Trainingszustand zusammen. Der **Projektablauf** führt als Navigator durch wichtige Arbeitsschritte.

**Netzwerk prüfen…** zeigt Struktur, Datenzuordnung und festgestellte Hinweise in einem modalen Prüfungsfenster. Eine Schaltfläche zum erneuten Prüfen ist dort nicht erforderlich, weil das Projekt während des geöffneten Fensters nicht geändert werden kann. Nach einer Änderung wird die Prüfung erneut über das Netzwerkmenü geöffnet.

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

Beim Löschen von Ein- oder Ausgängen erscheint nur die ausführliche Warnung mit **Löschen und Trainingsdaten anpassen…**, **Nur löschen** und **Abbrechen**. Die zusätzliche allgemeine Löschbestätigung entfällt hier. Beim Bearbeiten löst nur ein Typwechsel zwischen Input, Hidden und Output diese Datenstrukturwarnung aus; Namens- und Aktivierungsänderungen lösen sie nicht aus. Beim Typwechsel bleiben die Schaltflächen mit **Ändern** beschriftet.

Beim Löschen von Ein- oder Ausgängen erscheint nur die ausführliche Warnung mit **Löschen und Trainingsdaten anpassen…**, **Nur löschen** und **Abbrechen**. Die zusätzliche allgemeine Löschbestätigung entfällt hier. Beim Bearbeiten löst nur ein Typwechsel zwischen Input, Hidden und Output diese Datenstrukturwarnung aus; Namens- und Aktivierungsänderungen lösen sie nicht aus. Beim Typwechsel bleiben die Schaltflächen mit **Ändern** beschriftet.

Beim Löschen, Hinzufügen durch Kopieren oder Typwechsel von Ein- und Ausgängen erscheint vor der Änderung eine Warnung: Alle Trainingsläufe werden gelöscht und die Trainingsdatenstruktur muss angepasst werden. **Ändern und Trainingsdaten anpassen…** öffnet nach der Änderung die vorhandene Datenanpassung; **Nur ändern** verschiebt die Datenanpassung auf später. **Abbrechen** erhält Struktur und Historie. Ein späterer Abbruch der Datenanpassung nimmt die bereits bestätigte Änderung nicht zurück. Reine Umbenennungen erhalten die Historie. Gegebenenfalls müssen auch Testdaten angepasst werden.

Die Trainingshistorie speichert Läufe projektbezogen mit Parametern, Ergebniswerten und kompakter Fehlerkurve. Läufe können verglichen, als CSV exportiert, gelöscht oder – bei kompatibler Netzstruktur – wiederhergestellt werden.

Werden alle Läufe gelöscht, verschwinden Ergebnisanzeige und Kurve im geöffneten Trainingsfenster. Die aktuellen Gewichte und Bias-Werte des Netzwerks bleiben erhalten.

# 34. SPS-Export

Der experimentelle SPS-Export überträgt die Vorwärtsberechnung eines bereits trainierten Netzes in einen SPS-Funktionsbaustein. Das Training bleibt in NeuronNetz; der Export verändert keine Gewichte oder Bias-Werte.

Aktivieren Sie das Menü mit **Einstellungen → Programmeinstellungen... → Experimentell → SPS-Export in der Menüleiste anzeigen**. Praktisch geprüft sind **Mitsubishi GX Works2** und **Mitsubishi GX Works3**. CODESYS, TwinCAT und Siemens SCL sind als **In Vorbereitung** sichtbar, aber deaktiviert.

Voraussetzungen sind ein gültiges Netzwerk, vollständig zugeordnete und kalibrierte Trainingsspalten sowie ein zur aktuellen Struktur passender abgeschlossener Trainingslauf.

Das Exportfenster enthält zwei schreibgeschützte Ausgabebereiche:

1. Deklaration mit Ein- und Ausgängen, internen Variablen, Skalierungswerten, Gewichten und Bias-Werten.
2. Eingerückter und farblich hervorgehobener Structured Text für die Vorwärtsberechnung.

Oberhalb der Exportdaten zeigt NeuronNetz die Anzahl der Variablen, getrennt nach Ein-/Ausgängen, Skalierung, Gewichten `W`, Bias-Werten `B`, internen Neuronwerten `N` und Hilfswerten. Eine statische Aufwandsschätzung nennt Multiplikationen, Additionen, `EXP`-Aufrufe und eine Größenklasse. Sie ist keine garantierte Zykluszeit; diese hängt von SPS-Typ, CPU und Projekt ab.

Der Metadatenkopf enthält Exportdatum, NeuronNetz-Version, editierbare Modellversion, automatisch berechnete Modellkennung, Netzarchitektur, Aktivierungsfunktionen und Angaben zum Trainingslauf.

Der Menüpunkt **IEC 61131-10 XML** verwendet einen eigenen herstellerneutralen IEC-Generator. Er enthält weder Mitsubishi-Bezeichnungen noch GX-Works-spezifische Funktionsaufrufe. Der getrennte Menüpunkt **Mitsubishi GX Works3 – XML** verwendet denselben Aufbau mit Einzelvariablen und denselben GX-Works3-kompatiblen ST-Code, schreibt Variablenkommentare aber als allgemeinen Kommentar Nr. 1 in Mitsubishis `AddData/VariableComments`-Struktur. Damit bleibt der neutrale Export unverändert und die Herstellererweiterung klar abgegrenzt. Wie vollständig eine Entwicklungsumgebung den IEC-61131-10-Standard importiert, muss im jeweiligen Zielsystem praktisch geprüft werden.

Ein exportierter Baustein kann den Freigabeeingang `Enable` und den Statusausgang `Network_Active` besitzen. Die optionale Plausibilitätsprüfung wird mit `Enable_Range_Check` aktiviert. `Range_Tolerance_Percent` erweitert die beim Training gespeicherten Min-/Max-Grenzen standardmäßig um 10 %. `Input_Range_Error` meldet eine Verletzung; `Invalid_Input_Number` enthält die Nummer des ersten ungültigen Eingangs (0 = kein Fehler). Bei deaktiviertem Netz oder Eingangsfehler können die `Fallback_...`-Ersatzwerte ausgegeben werden; mit `Hold_Last_Output` bleiben stattdessen die letzten Ausgänge erhalten. Diese Betriebsfunktionen sind keine Sicherheitsfunktionen. Die aufklappbare FB-Vorschau im Exportfenster zeigt alle Anschlüsse; über `(i)` werden Steuerung, Prüfung, Diagnose und Fallback-Verhalten erklärt.

Im Bereich **Bausteineinstellungen** können diese Zusatzanschlüsse einzeln ausgewählt werden. Nicht sinnvolle abhängige Optionen werden automatisch deaktiviert. Ohne Fallback-Anschlüsse bleiben die letzten Ausgangswerte bei einer übersprungenen Berechnung erhalten. Ist Fallback gewählt, aber `Hold_Last_Output` nicht, werden die Ersatzwerte immer ausgegeben. Mit beiden Anschlüssen kann das Verhalten zur Laufzeit gewählt werden. Wird `Range_Tolerance_Percent` nicht als Eingang erzeugt, bleibt die Toleranz als interne Konstante von 10 % erhalten. Vorschau, Deklarationen, ST-, ASC- und XML-Code werden bei jeder Auswahl unmittelbar neu erzeugt.

Deklarationen, Structured Text und XML sind im Exportfenster schreibgeschützt. Änderbar bleiben FB-Name, Modellversion und die Auswahl der Zusatzanschlüsse; daraus erzeugt NeuronNetz die Ausgabedaten neu. Falls individuelle Codeänderungen erforderlich sind, nehmen Sie diese nach dem Export in der SPS-Entwicklungsumgebung oder einem externen Editor vor. Die abschließende Prüfung, Übersetzung und Freigabe erfolgt stets im Compiler des jeweiligen SPS-Zielsystems.

Unter jedem Bereich steht eine eigene Kopiertaste. Legen Sie in der SPS-Umgebung zuerst einen leeren Funktionsbaustein an, übertragen Sie danach die Deklaration und anschließend den ST-Programmkörper. `REAL` wird als **FLOAT (Single Precision)** erkannt, `BOOL` als **Bit**.

Alternativ speichert **Vollständige ASC-Datei speichern...** den gesamten Funktionsbaustein für GX Works2 oder GX Works3. **IEC 61131-10 XML...** öffnet den vollständigen, schreibgeschützten und herstellerneutral erzeugten XML-Code. Für den direkten Import in GX Works3 ist **Mitsubishi GX Works3 – XML...** vorgesehen. Mit **XML kopieren** wird das jeweilige Dokument vollständig in die Zwischenablage übernommen; **XML-Datei speichern...** speichert genau den sichtbaren Inhalt. Geringfügige Ergebnisabweichungen gegenüber NeuronNetz können durch die 32-Bit-Single-Precision-Rechnung der jeweiligen SPS entstehen.

## Sicherheit und Verantwortung

Der erzeugte SPS-Code dient als technische Unterstützung und muss vor dem produktiven Einsatz durch eine qualifizierte Fachkraft geprüft, getestet und für die konkrete Anlage freigegeben werden. Der Anwender ist für die korrekte Integration, Validierung, Risikobeurteilung und Einhaltung aller geltenden Sicherheitsvorschriften verantwortlich. Der Code ist nicht als Sicherheitsfunktion, Not-Aus-Funktion oder Ersatz für zertifizierte Schutzmaßnahmen vorgesehen. NeuronNetz übernimmt keine Verantwortung für Schäden, Betriebsunterbrechungen oder Fehlfunktionen, die aus der ungeprüften oder unsachgemäßen Verwendung des erzeugten Codes entstehen.

Beim ersten SPS-Export erscheint dieser Verantwortungshinweis einmalig zur Bestätigung. Im Exportfenster bleibt eine Kurzfassung sichtbar; das Informationssymbol **(i)** öffnet jederzeit den vollständigen Text. Auch der erzeugte ST-Code enthält einen kompakten Sicherheitshinweis.

## GX Works2

Die Deklarationsreihenfolge lautet:

```text
Class | Label Name | Data Type | Constant | Comment
```

Markieren Sie die erste freie Local-Label-Zeile und fügen Sie die kopierte Deklaration ein. Übertragen Sie danach den ST-Code. GX Works2 verwendet für die Exponentialfunktion:

```st
EXP(TRUE, -1.0 * N_N_15_Sum, EXP_Ergebnis);
```

## GX Works3

Aktivieren Sie im Local-Label-Editor vor dem Einfügen unbedingt **Show Details**. Die erweiterte Reihenfolge lautet:

```text
Label Name | Data Type | Class | Initial Value | Constant | Comment
```

**Initial Value** bleibt für `VAR_CONSTANT` leer. Gewichte, Bias und Skalierungswerte müssen unter **Constant**, die Beschreibungen unter **Comment** erscheinen. NeuronNetz stellt dafür eine Excel-ähnliche HTML-Tabelle und tabulatorgetrennten Text gleichzeitig in der Windows-Zwischenablage bereit.

GX Works3 verwendet die IEC-Schreibweise mit Rückgabewert:

```st
EXP_Ergebnis := EXP(-1.0 * N_N_15_Sum);
```

Prüfen Sie nach der Übertragung Konstanten, Eingangsskalierung, mindestens einen analogen Ausgang und vorhandene binäre Ausgänge. GX Works2 und GX Works3 wurden mit einem Feder-Masse-Netz praktisch getestet und lieferten bei gleichen Eingängen dieselben Ergebnisse wie NeuronNetz.

# 35. Ausführliches Handbuch

Diese Markdown-Datei ist eine kompakte Soforthilfe. Das vollständige bebilderte Handbuch erklärt sämtliche Fenster, Schaltflächen und ausführlichen Beispiele.

Über **Hilfe → Tutorials** kann das deutsche oder englische Handbuch als Word- oder PDF-Datei ausgewählt und mit dem zugeordneten Windows-Programm geöffnet werden. NeuronNetz merkt sich den zuletzt gewählten Tutorialordner.
