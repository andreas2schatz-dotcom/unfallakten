# PRD-29 – E-Akte Auto-Parser: E-Brief-Filter

**Status:** ✅ Implementiert  
**Priorität:** mittel  
**Ziel:** Ausgehende Dokumente im E-Akte Auto-Parser zuverlässig herausfiltern, um
Falsch-Positive zu minimieren und die Klassifikationsqualität zu erhöhen.

---

## Hintergrund

Der E-Akte Auto-Parser (`GET /akten/<az>/belege/kandidaten`) durchsucht alle PDFs einer
Akte in `tblElo_AktenArchiv` nach Schadenposition-Kandidaten. Ausgehende Kanzleischreiben
haben oft keine Rubrik und landen trotzdem als Falsch-Positive in der Kandidatenliste.

---

## Analyse der tblElo_AktenArchiv-Felder (Session 2026-04-11)

Das ursprünglich geplante `DKz`-Feld **existiert nicht** in der Tabelle.

Untersuchte `Quelle`-Werte:

| Quelle | Bedeutung | Filterbar? |
|--------|-----------|-----------|
| `0`    | Manuell via Windows Explorer importiert | ❌ Nein (kann eingehend sein) |
| `1`    | RA-MICRO intern generiert (3–5/Akte) | Ja, aber zu wenige für SQL-Change |
| `11`   | Beide Richtungen (eingehend + ausgehend) | ❌ Nein |
| `37`   | WDM-Maske generiert | Ja, aber zu wenige für SQL-Change |
| `83`   | E-Mail-Anhang (beide Richtungen) | ❌ Nein |

## Lösung: Schlagwort "E-Brief" filtern

Das RA-MICRO E-Brief-Modul setzt `Schlagwort = "E-Brief"` **ausschließlich** bei
ausgehenden E-Mails, die die Kanzlei selbst veranlasst hat. Eingehende E-Mails erhalten
dieses Schlagwort **nicht**. Das Feld ist bereits in der SQL-Abfrage enthalten → kein
SQL-Change nötig.

---

## Implementierung

### `backend/routers/belege_routes.py` – `_eakte_dok_uberspringen`

```python
if (dok.get("schlagwort") or "").lower().strip() == "e-brief":
    return "schlagwort_ebrief"
```

Eingefügt **vor** dem Rubrik-Check (erste Prüfung in der Funktion).

### `frontend/src/sections/DokumenteSection.jsx` – `SKIP_LABEL`

```javascript
schlagwort_ebrief: "E-Brief (Ausgehend)",
```

---

## Erwartetes Ergebnis

Deutliche Reduktion der zu parsenden Dokumente pro Akte, da E-Brief-Dokumente
typischerweise den größten Anteil ausgehender Korrespondenz ausmachen.
