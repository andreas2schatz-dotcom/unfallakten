"""Reiht pipeline_fehler-Text-Dokumente einmalig neu ein (Text-Pfad-Deploy).

Idempotent: verarbeitet nur queue_status='pipeline_fehler' AND payload_typ='text'
(und verworfen_am IS NULL). Nach dem Deploy des Text-Zweigs (verarbeite_dokument
verarbeitet payload_typ='text' ohne Arbeitskopie) laufen die zuvor an
"Arbeitskopie fehlt" gescheiterten E-Mail-Texte beim naechsten Worker-Tick durch.

Vor dem Lauf MUSS ein DB-Backup existieren (siehe Plan Task 6, Step 2)."""
from backend.db.database import get_connection
from backend.intake.queue import enqueue

with get_connection() as conn:
    ids = [r["id"] for r in conn.execute(
        "SELECT id FROM intake_dokumente "
        "WHERE queue_status='pipeline_fehler' AND payload_typ='text' "
        "  AND verworfen_am IS NULL"
    ).fetchall()]

print(f"Neu einzureihen: {len(ids)} Text-Dokumente")
for i in ids:
    enqueue(i)
print("Fertig. Worker verarbeitet sie beim naechsten Tick (max. 10s).")
