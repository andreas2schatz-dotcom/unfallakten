"""
Modul 1 – Seed-Skript
======================
Befüllt die Datenbank mit realistischen Testdaten für die Entwicklung.

Verwendung:
    python -m backend.scripts.seed_db
    python -m backend.scripts.seed_db --reset   # Erst alles löschen
"""

import sys
import os
import logging

# Pfad für direkten Aufruf
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from backend.db.schema_manager import init_db, reset_database
from backend.models.benutzer import erstelle_benutzer
from backend.models.akte import erstelle_akte
from backend.models.schaden import (
    erstelle_beteiligten, setze_schadenpositionen, erstelle_regulierung
)
from backend.models.dokument import registriere_dokument, logge_aktivitaet

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def seed():
    logger.info("Seed-Daten werden eingespielt ...")

    # ── BENUTZER ──────────────────────────────────────────────────────────────
    admin = erstelle_benutzer(
        name="Peter Koch",
        email="koch@anwalt-offenbach.de",
        passwort="Kanzlei2024!",
        rolle="admin"
    )
    sb1 = erstelle_benutzer(
        name="Andreas Schatz",
        email="schatz@anwalt-offenbach.de",
        passwort="Sachbearbeiter1!",
        rolle="sachbearbeiter"
    )
    sb2 = erstelle_benutzer(
        name="Elsa Ihl",
        email="ihl@anwalt-offenbach.de",
        passwort="Sachbearbeiter2!",
        rolle="sachbearbeiter"
    )
    logger.info("✅ 3 Benutzer erstellt")

    # ── AKTE 1: In Regulierung, Teilzahlung ──────────────────────────────────
    akte1 = erstelle_akte(
        aktenzeichen="42/25",
        unfalldatum="2025-01-12",
        bearbeiter_id=admin.id,
        unfallort="Offenbach, Berliner Str. / Ecke Kaiserstr.",
        haftungsquote=100.0
    )
    erstelle_beteiligten(
        akte_id=akte1.id, rolle="mandant", name="Müller",
        vorname="Hans", anschrift="Friedensstr. 15",
        plz="63065", ort="Offenbach",
        telefon="069-123456", email="h.mueller@example.de",
        kfz_kennzeichen="OF-HM 100", kfz_typ="VW Passat 2.0 TDI",
        iban="DE89370400440532013000"
    )
    erstelle_beteiligten(
        akte_id=akte1.id, rolle="gegner", name="Bauer",
        vorname="Klaus", kfz_kennzeichen="HU-KB 222",
        kfz_typ="BMW 3er", versicherung="HUK Coburg",
        vers_nr="HUK-4711-88", schaden_nr="S-2025-00123"
    )
    erstelle_beteiligten(
        akte_id=akte1.id, rolle="sachverstaendiger", name="Dekra GmbH",
        telefon="069-99887766", email="gutachten@dekra.de"
    )
    setze_schadenpositionen(
        akte_id=akte1.id, bearbeiter_id=admin.id,
        reparaturkosten=6240.50,
        sv_kosten=890.00,
        nutzungsausfall=560.00,
        abschleppkosten=180.00,
        wertminderung=350.00,
        quelle="gutachten_pdf"
    )
    erstelle_regulierung(
        akte_id=akte1.id, datum="2025-02-18",
        betrag_gefordert=8220.50, betrag_reguliert=6180.00,
        bearbeiter_id=admin.id,
        vers_referenz="HUK-S-2025-00123-A",
        kuerz_begruendung="Wertminderung abgelehnt, SV-Kosten gekürzt um 40,50 €"
    )
    registriere_dokument(
        akte_id=akte1.id, typ="gutachten",
        dateiname="Gutachten_Dekra_42-25.pdf",
        dateipfad="uploads/42-25/Gutachten_Dekra_42-25.pdf",
        bearbeiter_id=admin.id, dateigroesse=2_450_000
    )
    logger.info("✅ Akte 42/25 (In Regulierung) erstellt")

    # ── AKTE 2: Vollständig reguliert ────────────────────────────────────────
    akte2 = erstelle_akte(
        aktenzeichen="41/25",
        unfalldatum="2025-01-09",
        bearbeiter_id=sb1.id,
        unfallort="Offenbach, Parkplatz Stadtring",
        haftungsquote=100.0
    )
    erstelle_beteiligten(
        akte_id=akte2.id, rolle="mandant", name="Schmidt",
        vorname="Anna", kfz_kennzeichen="OF-AS 55",
        kfz_typ="Toyota Yaris", telefon="069-555444",
        versicherung="ADAC", vers_nr="ADAC-9988"
    )
    erstelle_beteiligten(
        akte_id=akte2.id, rolle="gegner", name="Weber GmbH",
        firma="Weber Logistik GmbH", kfz_kennzeichen="OF-WL 1",
        versicherung="Allianz", schaden_nr="ALZ-2025-77001"
    )
    setze_schadenpositionen(
        akte_id=akte2.id, bearbeiter_id=sb1.id,
        reparaturkosten=2800.00,
        sv_kosten=650.00,
        nutzungsausfall=300.00,
        quelle="gutachten_pdf"
    )
    erstelle_regulierung(
        akte_id=akte2.id, datum="2025-02-05",
        betrag_gefordert=3750.00, betrag_reguliert=3750.00,
        bearbeiter_id=sb1.id,
        vers_referenz="ALZ-2025-77001-R1",
        status="vollreguliert"
    )
    logger.info("✅ Akte 41/25 (Abgeschlossen) erstellt")

    # ── AKTE 3: Nur Akte angelegt, noch kein Gutachten ───────────────────────
    akte3 = erstelle_akte(
        aktenzeichen="40/25",
        unfalldatum="2025-01-03",
        bearbeiter_id=sb2.id,
        unfallort="Offenbach, B44 Höhe Kaiserlei",
        haftungsquote=100.0
    )
    erstelle_beteiligten(
        akte_id=akte3.id, rolle="mandant", name="Weber",
        vorname="Klaus", kfz_kennzeichen="MKK-KW 3",
        kfz_typ="Mercedes C-Klasse W205",
        telefon="06181-123123"
    )
    erstelle_beteiligten(
        akte_id=akte3.id, rolle="gegner", name="Özdemir",
        vorname="Mehmet", kfz_kennzeichen="OF-MO 77",
        versicherung="Generali", schaden_nr="GEN-2025-44312"
    )
    setze_schadenpositionen(
        akte_id=akte3.id, bearbeiter_id=sb2.id,
        wiederbeschaffung=18500.00,
        restwert=3200.00,
        sv_kosten=1150.00,
        abschleppkosten=220.00,
        standkosten=180.00,
        mietwagenkosten=680.00,
        anabmeldekosten=53.50,
        quelle="gutachten_pdf"
    )
    logger.info("✅ Akte 40/25 (Offen, Totalschaden) erstellt")

    # ── AKTE 4: Klage ─────────────────────────────────────────────────────────
    akte4 = erstelle_akte(
        aktenzeichen="1098/24",
        unfalldatum="2024-11-15",
        bearbeiter_id=admin.id,
        unfallort="Frankfurt, Sachsenhausen",
        haftungsquote=100.0
    )
    erstelle_beteiligten(
        akte_id=akte4.id, rolle="mandant", name="Fischer",
        vorname="Maria", kfz_kennzeichen="F-MF 999",
        kfz_typ="Audi A4", email="m.fischer@example.de"
    )
    setze_schadenpositionen(
        akte_id=akte4.id, bearbeiter_id=admin.id,
        reparaturkosten=9200.00,
        sv_kosten=1100.00,
        schmerzensgeld=2500.00,
        nutzungsausfall=850.00,
        quelle="gutachten_pdf"
    )
    from backend.db.database import get_connection
    with get_connection() as conn:
        conn.execute(
            "UPDATE unfallakte SET status = 'klage' WHERE az = ?", (akte4.id,)
        )
    logger.info("✅ Akte 24-1098 (Klage) erstellt")

    print("\n" + "═" * 50)
    print("✅ Seed-Daten erfolgreich eingespielt!")
    print("═" * 50)
    print(f"  Benutzer  : 3 (1 Admin, 2 Sachbearbeiter)")
    print(f"  Akten     : 4")
    print(f"  Login     : koch@anwalt-offenbach.de / Kanzlei2024!")
    print("═" * 50 + "\n")


if __name__ == "__main__":
    if "--reset" in sys.argv:
        reset_database()
    else:
        init_db()
    seed()
