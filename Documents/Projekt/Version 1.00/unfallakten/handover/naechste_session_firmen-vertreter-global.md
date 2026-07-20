# Nächste Session: Globaler Firmen-Vertreter-Speicher (Klage-Wizard)

> Erstellt 2026-07-20 · Folge aus dem Browser-Nachtest von Paket 2 (UI-Führung), Akte 828/24
> Entscheidung RA Schatz: Ansatz **„Vertreter global je Firma speichern"**; eigener größerer Fix → frische Session.

## Problem (verifiziert an Akte 828/24)

Im Klage-Wizard bleibt „⚠ Firma ohne Vertreter" (Schritt 2 + Schritt 11) **dauerhaft rot**, obwohl der Vertreter-Lookup ausgeführt und übernommen wurde. Das blockiert zusätzlich den „Generieren"-Button (`firmenOhneVertreter.length > 0` ⇒ `gesperrt`, `KlageWizard.jsx` StepZusammenfassung).

**Root Cause (zweistufig):**
1. **Schema-Drift (in der Nachtest-Session bereits repariert):** `beteiligte.vertreter_name`/`vertreter_funktion` (Migration 23) fehlten auf der Dev-DB trotz `schema_version=61`. Dev-DB per `ALTER TABLE` nachgezogen (Backup `unfallakten.db.bak_20260720_vertreter_drift`). **Prod-Bestands-DBs haben die Drift vermutlich auch → vor App-Start prüfen/ALTER.** Das VertreterModal verschluckte den `no such column`-Fehler still → jetzt Toast (`5e5b438b`).
2. **Der eigentliche, noch offene Fix — Persistenz greift für RA-MICRO-/synthetische Beklagte nicht:** Akte 828/24 hat **null** `beteiligte`-Zeilen in SQLite; alle Parteien kommen zur Laufzeit aus RA-MICRO plus dem **synthetischen § 115-VVG-GHPV-Eintrag** (`klage_routes.py:1007`, `id: -1`, `vertreter_name: ""`). Der Speicherweg `POST /firmen/vertreter/speichern` macht `UPDATE beteiligte … WHERE id=?` (`firmen_routes.py:395`) → trifft **keine** Zeile (id -1 / RA-MICRO-id existiert nicht in SQLite) → Vertreter wird nie persistiert → bei jedem Neuaufbau wieder leer.

Der In-Wizard-Lookup (aus der Nachtest-Session, `00e3f820`) **klärt die Warnung in der laufenden Sitzung** (lokales `setBek`), aber nichts bleibt über Reload/Neuöffnen erhalten. Für echte SQLite-Firmen (mit Zeile) persistiert es seit dem Spalten-Fix.

## Gewählte Lösung: globaler Firmen-Vertreter-Speicher

Vertreter nicht (nur) am Beteiligten, sondern **zentral je Firmenname** ablegen und beim Aufbau der Beklagten nachschlagen. Löst die synthetische Versicherung (kein Zeilen-Bezug nötig) und merkt Organe **aktenübergreifend** (z.B. „ADAC Autoversicherung AG → Vorstand Stefan Daehne" gilt dann in jeder Akte). **Abwärtskompatibel:** ein direkt am Beteiligten gespeicherter `vertreter_name` hat Vorrang.

### Umsetzungsplan (TDD, superpowers:writing-plans zuerst)

1. **Migration (nächste Version, z.B. 62):** neue Tabelle
   ```sql
   CREATE TABLE firmen_vertreter (
     firma_norm         TEXT PRIMARY KEY,   -- normalisiert: lower + Whitespace-Kollaps
     firma_anzeige      TEXT,               -- Originalschreibweise (Anzeige)
     vertreter_name     TEXT NOT NULL,
     vertreter_funktion TEXT,
     aktualisiert_am    TEXT
   );
   ```
   Regeln beachten: **kein `executescript()`**, explizites `conn.commit()` vor+nach ALTER/CREATE, Migration in **einem** Edit schreiben (Reloader-Trap [[feedback_migration_reloader_trap]]); aktive DB = Docker-Volume `dev-data` (`/app/data/unfallakten.db`), nicht `backend/data/`.

2. **Backend `firmen_routes.speichern` (`firmen_routes.py:379`):** Body zusätzlich `firma` akzeptieren. Wenn `firma` gesetzt: UPSERT in `firmen_vertreter` (Key = `_norm(firma)`). Wenn `beteiligter_id` eine **echte** Zeile trifft: zusätzlich wie bisher `UPDATE beteiligte` (Vorrang-Quelle). Beides best-effort, Fehler klar zurückgeben (Toast ist frontendseitig schon da).

3. **Serializer — Global-Lookup einweben:** Helper `hole_firmen_vertreter(conn, firma_norm) -> (name, funktion)|None`.
   - **Primär:** `klage_routes.py` `b_dict` (~Z. 891) — nach dem Bauen jedes Beklagten: wenn Firma (`versicherung||firma||name-ohne-vorname`) **und** kein eigener `vertreter_name`, aus `firmen_vertreter` per Name füllen. **Auch am synthetischen GHPV-Append (~Z. 1007)** anwenden (dort `firma`/`name` = Versicherungsname).
   - Optional konsistenzhalber `models/beteiligte.py::beteiligter_as_dict` (Z. 16) analog, falls andere Views denselben Effekt brauchen.
   - Normalisierung EXAKT wie beim Speichern (`_norm`), damit Treffer sicher.

4. **Frontend:** `api.js:818` `vertreterSpeichern` um `firma` erweitern (`vertreterSpeichern(id, name, funk, firma)`); Aufrufer im `VertreterModal` (`KlageSection.jsx`) übergeben `vertreterModal.name` (= Firmenname) als `firma`. In-Wizard-Lookup-Knöpfe existieren bereits (Schritt 2 `StepRubrum`, Schritt 11 `StepZusammenfassung`).

5. **Tests:** Migration (Tabelle da, idempotent); Endpoint (UPSERT global + optional beteiligte, Konflikt-Update); Serializer-E2E (**Kernfall:** Akte ohne SQLite-Beteiligte + synthetischer GHPV → nach globalem Speichern liefert `apiKlage.daten` den Vertreter, Warnung/`gesperrt` weg); Frontend `vertreterSpeichern`-Payload + Modal.

### Abgrenzung / Vorsicht
- **KEIN Auto-Apply** des Web-Lookups (RA muss das Organ bestätigen — Alt-Bug „Vorstand war Aufsichtsrätin", Paket-1-Nachtest). Der globale Speicher wird nur beim expliziten „Übernehmen" gefüllt.
- RA-MICRO bleibt **read-only** — geschrieben wird ausschließlich SQLite (`firmen_vertreter`, ggf. `beteiligte`).
- Normalisierung konservativ (nur lower + Whitespace), **Rechtsform NICHT strippen** — sonst würden verschiedene Gesellschaften desselben Konzerns zusammenfallen.

## Stand des Branches `klage-wizard-ui-fuehrung` (13 Commits `65f657bc..5e5b438b`)
- Paket 2 (UI-Führung) komplett + Whole-Branch-Review „ready to merge".
- Nachtest-Fixes: klarer Schließen-Dialog + In-Wizard-Lookup (`00e3f820`), Swallow-Härtung (`5e5b438b`).
- Volle Frontend-Suite **314/314** + Build grün.
- **Offen (dieser Plan):** globale Vertreter-Persistenz. Bis dahin klärt der Wizard die Vertreter-Warnung nur in der laufenden Sitzung (reicht, um zu generieren), persistiert aber für RA-MICRO-/GHPV-Versicherungen nicht.
- Merge-Entscheidung (Paket 2 jetzt vs. zusammen mit diesem Fix) offen — RA Schatz.
