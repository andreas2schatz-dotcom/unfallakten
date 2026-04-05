# PRD-27: ReguWizard – Stellungnahme zum Abrechnungsschreiben
> Erstellt: 2026-04-05
> Status: **Planung offen**
> Bearbeiter: –

---

## Ziel

Einen geführten Wizard zur Erstellung einer **Stellungnahme auf ein Abrechnungsschreiben**
des gegnerischen Haftpflichtversicherers etablieren. Der Anwalt soll Schritt für Schritt
durch alle relevanten Kürzungspositionen geführt werden und am Ende ein fertiges
Antwortschreiben als Word-Dokument erhalten.

Analoges Gegenstück zum Klage-Wizard (PRD-26). Beide Wizards teilen Rubrum, Parteien
und Schadenstruktur – gemeinsame Komponenten sollen wiederverwendet werden.

---

## Hintergrund / Auslöser

Haftpflichtversicherer kürzen Schadenpositionen regelmäßig mit Standardargumenten
(Stundenverrechnungssatz, Restwert, Nutzungsausfall, Mietwagenklasse, etc.).
Die Stellungnahme ist ein wiederkehrendes Dokument mit strukturiertem Aufbau,
das sich für Automatisierung eignet.

---

## Abgrenzung zum Klage-Wizard

| Merkmal | Klage-Wizard | ReguWizard |
|---|---|---|
| Zieldokument | Klageschrift | Stellungnahme / Gegendarstellung |
| Adressat | Gericht | Haftpflichtversicherer |
| Rechtliche Grundlage | ZPO, StVG, BGB | BGB, StVG, Regulierungspraxis |
| Streitwert | ja | nein |
| RVG-Antrag | ja | nein |
| Gericht-Auswahl | ja (Step 1) | nein |

---

## Vorläufige Step-Ideen

| # | Label | Inhalt |
|---|---|---|
| 1 | Parteien | Kläger + Versicherung (aus Akte) |
| 2 | Abrechnungsschreiben | Datum + Aktenzeichen Versicherer + Gesamtbetrag der Regulierung |
| 3 | Kürzungen | Übersicht der gekürtzten Positionen; Eingabe Kürzungsbetrag je Position |
| 4 | Begründung | Je Kürzungsposition: Standard-Gegenargument wählen oder freitext |
| 5 | Frist | Zahlungsfrist setzen |
| 6 | Generieren | Zusammenfassung + Word-Export |

---

## Offene Planungsfragen

- [ ] Welche Kürzungstypen kommen in der Praxis am häufigsten vor?
      (Stundenverrechnungssatz, Restwert, Nutzungsausfall, Mietwagen, Wertminderung, …)
- [ ] Standard-Gegenargumente: Textbaustein-Bibliothek oder KI-generiert?
- [ ] Verknüpfung mit bestehendem Abrechnungsschreiben-Parser aus dem System?
- [ ] Soll das Schreiben direkt per E-Mail versendbar sein (Integration Modul 22d)?
- [ ] Gemeinsame Word-Vorlage mit Klage-Wizard oder eigene Vorlage?

---

## Abhängigkeiten

- PRD-26 (Klage-Wizard) – Architektur-Vorlage, wiederverwendbare Wizard-Komponenten
- PRD-23b (Rechnungs-Parser) – evtl. Kürzungsbeträge automatisch aus Schreiben lesen
- PRD-22d (E-Mail-Import) – optionaler Versand des fertigen Schreibens

---

## Nächste Schritte (Planung)

1. Anforderungsklärung: Welche Kürzungspositionen + Gegenargumente abdecken?
2. Wireframe der Steps
3. Word-Vorlage definieren
4. Implementierung (analog PRD-26)
