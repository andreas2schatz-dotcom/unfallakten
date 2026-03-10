"""
main.py – FastAPI-Backend für das Kanzlei-Webtool

Starten:
    uvicorn main:app --reload --port 8000

API-Dokumentation:
    http://localhost:8000/docs
"""

import os
import shutil
from datetime import date, datetime
from pathlib import Path
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import (
    init_db, get_db,
    Unfall, Beteiligter, Fahrzeug, Versicherung,
    Gutachten, Forderung, Regulierung, Dokument, Taetigkeit
)
from pdf_extractor import process_gutachten_pdf
from word_generator import generiere_forderungsschreiben, lade_falldaten_fuer_schreiben

# ──────────────────────────────────────────────────────────────
#  APP-SETUP
# ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="Kanzlei Unfallverwaltung",
    description="Backend für die Verwaltung von Unfallakten",
    version="1.0.0"
)

# CORS – erlaubt Zugriff vom React-Frontend (localhost:3000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_ORDNER = Path("uploads")
UPLOAD_ORDNER.mkdir(exist_ok=True)

# Datenbank beim Start initialisieren
@app.on_event("startup")
def startup():
    init_db()


# ──────────────────────────────────────────────────────────────
#  PYDANTIC-SCHEMAS  (Request / Response)
# ──────────────────────────────────────────────────────────────
class UnfallCreate(BaseModel):
    aktenzeichen:       str
    unfalldatum:        date
    unfallort:          Optional[str] = None
    unfallbeschreibung: Optional[str] = None
    status:             Optional[str] = "offen"

class UnfallUpdate(BaseModel):
    unfalldatum:        Optional[date] = None
    unfallort:          Optional[str] = None
    unfallbeschreibung: Optional[str] = None
    status:             Optional[str] = None

class UnfallResponse(BaseModel):
    id:              int
    aktenzeichen:    str
    unfalldatum:     date
    unfallort:       Optional[str]
    status:          str
    erstellt_am:     datetime
    gesamt_gefordert: float = 0.0
    gesamt_reguliert: float = 0.0
    offen:            float = 0.0

    class Config:
        from_attributes = True

class BeteiligterCreate(BaseModel):
    unfall_id:           int
    rolle:               str
    anrede:              Optional[str] = None
    vorname:             Optional[str] = None
    nachname:            str
    strasse:             Optional[str] = None
    plz:                 Optional[str] = None
    ort:                 Optional[str] = None
    telefon:             Optional[str] = None
    email:               Optional[str] = None

class FahrzeugCreate(BaseModel):
    unfall_id:      int
    rolle:          str
    kennzeichen:    Optional[str] = None
    marke:          Optional[str] = None
    modell:         Optional[str] = None
    km_stand:       Optional[int] = None
    eigentuemer_id: Optional[int] = None

class VersicherungCreate(BaseModel):
    unfall_id:          int
    versicherung_name:  str
    versicherung_typ:   Optional[str] = "haftpflicht"
    schadennummer:      Optional[str] = None
    ansprechpartner:    Optional[str] = None
    telefon:            Optional[str] = None
    email:              Optional[str] = None
    strasse:            Optional[str] = None
    plz:                Optional[str] = None
    ort:                Optional[str] = None

class ForderungCreate(BaseModel):
    unfall_id:            int
    forderungsdatum:      date
    frist_datum:          Optional[date] = None
    betrag_reparatur:     float = 0.0
    betrag_mietwagen:     float = 0.0
    betrag_wertminderung: float = 0.0
    betrag_schmerzensgeld:float = 0.0
    betrag_gutachter:     float = 0.0
    betrag_auslagen:      float = 0.0
    betrag_anwaltskosten: float = 0.0
    betrag_sonstiges:     float = 0.0
    notiz:                Optional[str] = None

class RegulierungCreate(BaseModel):
    unfall_id:            int
    forderung_id:         Optional[int] = None
    eingangsdatum:        date
    betrag_reparatur:     float = 0.0
    betrag_mietwagen:     float = 0.0
    betrag_wertminderung: float = 0.0
    betrag_schmerzensgeld:float = 0.0
    betrag_gutachter:     float = 0.0
    betrag_auslagen:      float = 0.0
    betrag_anwaltskosten: float = 0.0
    betrag_sonstiges:     float = 0.0
    betrag_gesamt:        float
    vollstaendig:         int = 0
    notiz:                Optional[str] = None

class TaetigkeitCreate(BaseModel):
    unfall_id:    int
    kategorie:    str
    beschreibung: str


# ──────────────────────────────────────────────────────────────
#  HILFSFUNKTION: Finanzübersicht berechnen
# ──────────────────────────────────────────────────────────────
def _berechne_finanzen(unfall_id: int, db: Session) -> dict:
    forderungen   = db.query(Forderung).filter_by(unfall_id=unfall_id).all()
    regulierungen = db.query(Regulierung).filter_by(unfall_id=unfall_id).all()
    gefordert = sum((f.betrag_gesamt or 0) for f in forderungen)
    reguliert = sum((r.betrag_gesamt or 0) for r in regulierungen)
    return {"gesamt_gefordert": gefordert, "gesamt_reguliert": reguliert, "offen": gefordert - reguliert}


# ──────────────────────────────────────────────────────────────
#  ENDPUNKTE: UNFÄLLE
# ──────────────────────────────────────────────────────────────
@app.get("/unfaelle", response_model=List[UnfallResponse], tags=["Unfälle"])
def liste_unfaelle(status: Optional[str] = None, db: Session = Depends(get_db)):
    """Alle Unfälle abrufen, optional nach Status filtern."""
    q = db.query(Unfall)
    if status:
        q = q.filter(Unfall.status == status)
    unfaelle = q.order_by(Unfall.aktualisiert_am.desc()).all()

    result = []
    for u in unfaelle:
        fin = _berechne_finanzen(u.id, db)
        result.append(UnfallResponse(
            id=u.id, aktenzeichen=u.aktenzeichen,
            unfalldatum=u.unfalldatum, unfallort=u.unfallort,
            status=u.status, erstellt_am=u.erstellt_am,
            **fin
        ))
    return result


@app.post("/unfaelle", response_model=UnfallResponse, tags=["Unfälle"])
def erstelle_unfall(data: UnfallCreate, db: Session = Depends(get_db)):
    """Neuen Unfall anlegen."""
    unfall = Unfall(**data.model_dump())
    db.add(unfall)
    db.commit()
    db.refresh(unfall)
    _log_taetigkeit(db, unfall.id, "Akte angelegt", f"Unfall {unfall.aktenzeichen} angelegt.")
    return UnfallResponse(id=unfall.id, aktenzeichen=unfall.aktenzeichen,
        unfalldatum=unfall.unfalldatum, unfallort=unfall.unfallort,
        status=unfall.status, erstellt_am=unfall.erstellt_am)


@app.get("/unfaelle/{unfall_id}", tags=["Unfälle"])
def detail_unfall(unfall_id: int, db: Session = Depends(get_db)):
    """Vollständiges Dashboard für einen Unfall."""
    unfall = db.get(Unfall, unfall_id)
    if not unfall:
        raise HTTPException(404, "Unfall nicht gefunden")

    fin          = _berechne_finanzen(unfall_id, db)
    beteiligte   = db.query(Beteiligter).filter_by(unfall_id=unfall_id).all()
    fahrzeuge    = db.query(Fahrzeug).filter_by(unfall_id=unfall_id).all()
    versich      = db.query(Versicherung).filter_by(unfall_id=unfall_id).all()
    gutachten    = db.query(Gutachten).filter_by(unfall_id=unfall_id).all()
    forderungen  = db.query(Forderung).filter_by(unfall_id=unfall_id).order_by(Forderung.forderungsdatum).all()
    regulierungen= db.query(Regulierung).filter_by(unfall_id=unfall_id).order_by(Regulierung.eingangsdatum).all()
    taetigkeiten = db.query(Taetigkeit).filter_by(unfall_id=unfall_id).order_by(Taetigkeit.datum.desc()).all()

    def _ser(obj):
        if isinstance(obj, list):
            return [_ser(o) for o in obj]
        d = {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
        for k, v in d.items():
            if isinstance(v, (date, datetime)):
                d[k] = v.isoformat()
        return d

    return {
        "unfall":       _ser(unfall),
        "finanzen":     fin,
        "beteiligte":   _ser(beteiligte),
        "fahrzeuge":    _ser(fahrzeuge),
        "versicherungen":_ser(versich),
        "gutachten":    _ser(gutachten),
        "forderungen":  _ser(forderungen),
        "regulierungen":_ser(regulierungen),
        "taetigkeiten": _ser(taetigkeiten),
    }


@app.patch("/unfaelle/{unfall_id}", tags=["Unfälle"])
def aktualisiere_unfall(unfall_id: int, data: UnfallUpdate, db: Session = Depends(get_db)):
    """Status oder Details eines Unfalls aktualisieren."""
    unfall = db.get(Unfall, unfall_id)
    if not unfall:
        raise HTTPException(404, "Unfall nicht gefunden")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(unfall, k, v)
    db.commit()
    return {"ok": True}


# ──────────────────────────────────────────────────────────────
#  ENDPUNKTE: BETEILIGTE / FAHRZEUGE / VERSICHERUNGEN
# ──────────────────────────────────────────────────────────────
@app.post("/beteiligte", tags=["Stammdaten"])
def erstelle_beteiligten(data: BeteiligterCreate, db: Session = Depends(get_db)):
    b = Beteiligter(**data.model_dump())
    db.add(b); db.commit(); db.refresh(b)
    return {"id": b.id}

@app.post("/fahrzeuge", tags=["Stammdaten"])
def erstelle_fahrzeug(data: FahrzeugCreate, db: Session = Depends(get_db)):
    f = Fahrzeug(**data.model_dump())
    db.add(f); db.commit(); db.refresh(f)
    return {"id": f.id}

@app.post("/versicherungen", tags=["Stammdaten"])
def erstelle_versicherung(data: VersicherungCreate, db: Session = Depends(get_db)):
    v = Versicherung(**data.model_dump())
    db.add(v); db.commit(); db.refresh(v)
    return {"id": v.id}


# ──────────────────────────────────────────────────────────────
#  ENDPUNKTE: PDF-UPLOAD & GUTACHTEN-EXTRAKTION
# ──────────────────────────────────────────────────────────────
@app.post("/gutachten/upload", tags=["Gutachten"])
async def lade_gutachten_hoch(
    unfall_id:     int        = Form(...),
    use_local_llm: bool       = Form(False),
    datei:         UploadFile = File(...),
    db:            Session    = Depends(get_db)
):
    """
    PDF hochladen → Text extrahieren → KI-Analyse → in DB speichern.
    Gibt die extrahierten Daten zurück (zur manuellen Prüfung / Korrektur).
    """
    unfall = db.get(Unfall, unfall_id)
    if not unfall:
        raise HTTPException(404, "Unfall nicht gefunden")

    # PDF speichern
    pdf_pfad = UPLOAD_ORDNER / f"{unfall.aktenzeichen}_{datei.filename}"
    with open(pdf_pfad, "wb") as f:
        shutil.copyfileobj(datei.file, f)

    # Extraktion
    try:
        extrahiert = process_gutachten_pdf(str(pdf_pfad), use_local_llm=use_local_llm)
    except Exception as e:
        raise HTTPException(500, f"PDF-Extraktion fehlgeschlagen: {e}")

    import json
    from datetime import datetime as dt

    # Gutachten in DB speichern
    g = Gutachten(
        unfall_id             = unfall_id,
        gutachter_name        = extrahiert.get("gutachter_name"),
        gutachter_buero       = extrahiert.get("gutachter_buero"),
        gutachtennummer       = extrahiert.get("gutachtennummer"),
        gutachtendatum        = _parse_date(extrahiert.get("gutachtendatum")),
        pdf_pfad              = str(pdf_pfad),
        pdf_extrahiert_am     = dt.now(),
        wiederbeschaffungswert= extrahiert.get("wiederbeschaffungswert"),
        restwert              = extrahiert.get("restwert"),
        reparaturkosten_netto = extrahiert.get("reparaturkosten_netto"),
        reparaturkosten_brutto= extrahiert.get("reparaturkosten_brutto"),
        wertminderung         = extrahiert.get("wertminderung"),
        mietwagenklasse       = extrahiert.get("mietwagenklasse"),
        totalschaden          = 1 if extrahiert.get("totalschaden") else 0,
        ki_extraktion_roh     = json.dumps(extrahiert, ensure_ascii=False, default=str)
    )
    db.add(g)
    db.commit()
    db.refresh(g)

    _log_taetigkeit(db, unfall_id, "PDF-Import",
        f"Gutachten '{datei.filename}' importiert. Gutachter: {extrahiert.get('gutachter_name', '?')}")

    return {"gutachten_id": g.id, "extrahiert": extrahiert}


# ──────────────────────────────────────────────────────────────
#  ENDPUNKTE: FORDERUNGEN & REGULIERUNGEN
# ──────────────────────────────────────────────────────────────
@app.post("/forderungen", tags=["Finanzen"])
def erstelle_forderung(data: ForderungCreate, db: Session = Depends(get_db)):
    """Neue Forderung anlegen. Gesamtbetrag wird automatisch berechnet."""
    gesamt = (
        data.betrag_reparatur + data.betrag_mietwagen +
        data.betrag_wertminderung + data.betrag_schmerzensgeld +
        data.betrag_gutachter + data.betrag_auslagen +
        data.betrag_anwaltskosten + data.betrag_sonstiges
    )
    f = Forderung(**data.model_dump(), betrag_gesamt=gesamt)
    db.add(f); db.commit(); db.refresh(f)

    _log_taetigkeit(db, data.unfall_id, "Forderung",
        f"Forderung über {gesamt:,.2f} EUR erstellt (Frist: {data.frist_datum}).")
    return {"id": f.id, "betrag_gesamt": gesamt}


@app.post("/regulierungen", tags=["Finanzen"])
def erstelle_regulierung(data: RegulierungCreate, db: Session = Depends(get_db)):
    """Eingehende Zahlung erfassen."""
    r = Regulierung(**data.model_dump())
    db.add(r); db.commit(); db.refresh(r)

    _log_taetigkeit(db, data.unfall_id, "Zahlung eingegangen",
        f"Regulierung {data.betrag_gesamt:,.2f} EUR am {data.eingangsdatum} eingegangen.")
    return {"id": r.id}


# ──────────────────────────────────────────────────────────────
#  ENDPUNKTE: WORD-GENERIERUNG
# ──────────────────────────────────────────────────────────────
@app.post("/unfaelle/{unfall_id}/forderungsschreiben", tags=["Dokumente"])
def erstelle_forderungsschreiben(unfall_id: int, db: Session = Depends(get_db)):
    """
    Generiert ein Forderungsschreiben als .docx-Datei
    und gibt es direkt zum Download zurück.
    """
    try:
        falldaten = lade_falldaten_fuer_schreiben(db, unfall_id)
        pfad      = generiere_forderungsschreiben(falldaten)
    except Exception as e:
        raise HTTPException(500, f"Word-Generierung fehlgeschlagen: {e}")

    # In DB erfassen
    unfall = db.get(Unfall, unfall_id)
    dateiname = Path(pfad).name
    dok = Dokument(
        unfall_id   = unfall_id,
        dokumenttyp = "forderungsschreiben",
        dateiname   = dateiname,
        dateipfad   = pfad,
        dateiformat = "docx"
    )
    db.add(dok); db.commit()

    _log_taetigkeit(db, unfall_id, "Schreiben erstellt",
        f"Forderungsschreiben '{dateiname}' generiert.")

    return FileResponse(
        path=pfad,
        filename=dateiname,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )


# ──────────────────────────────────────────────────────────────
#  ENDPUNKTE: TÄTIGKEITEN
# ──────────────────────────────────────────────────────────────
@app.post("/taetigkeiten", tags=["Tätigkeiten"])
def erstelle_taetigkeit(data: TaetigkeitCreate, db: Session = Depends(get_db)):
    """Manuellen Tätigkeitseintrag hinzufügen."""
    t = Taetigkeit(**data.model_dump())
    db.add(t); db.commit()
    return {"ok": True}


@app.get("/unfaelle/{unfall_id}/taetigkeiten", tags=["Tätigkeiten"])
def liste_taetigkeiten(unfall_id: int, db: Session = Depends(get_db)):
    taetigkeiten = db.query(Taetigkeit).filter_by(unfall_id=unfall_id).order_by(Taetigkeit.datum.desc()).all()
    return [
        {
            "id": t.id, "datum": t.datum.isoformat(),
            "kategorie": t.kategorie, "beschreibung": t.beschreibung,
            "erstellt_von": t.erstellt_von
        }
        for t in taetigkeiten
    ]


# ──────────────────────────────────────────────────────────────
#  INTERNE HILFSFUNKTIONEN
# ──────────────────────────────────────────────────────────────
def _log_taetigkeit(db: Session, unfall_id: int, kategorie: str, beschreibung: str):
    t = Taetigkeit(unfall_id=unfall_id, kategorie=kategorie, beschreibung=beschreibung)
    db.add(t); db.commit()


def _parse_date(value) -> Optional[date]:
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


# ──────────────────────────────────────────────────────────────
#  HEALTH-CHECK
# ──────────────────────────────────────────────────────────────
@app.get("/", tags=["System"])
def root():
    return {"status": "ok", "app": "Kanzlei Unfallverwaltung", "version": "1.0.0"}
