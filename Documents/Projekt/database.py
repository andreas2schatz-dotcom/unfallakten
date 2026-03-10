"""
database.py – SQLAlchemy-Modelle + SQLite-Setup
Führt beim ersten Start automatisch alle Tabellen an.
"""

from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Date,
    DateTime, ForeignKey, Text, CheckConstraint
)
from sqlalchemy.orm import DeclarativeBase, relationship, Session
from sqlalchemy.sql import func
from datetime import datetime

DATABASE_URL = "sqlite:///./kanzlei.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # für FastAPI nötig
)


class Base(DeclarativeBase):
    pass


# ──────────────────────────────────────────────────────────────
#  UNFALL  –  Kernakte
# ──────────────────────────────────────────────────────────────
class Unfall(Base):
    __tablename__ = "unfall"

    id                  = Column(Integer, primary_key=True, autoincrement=True)
    aktenzeichen        = Column(String, unique=True, nullable=False)
    unfalldatum         = Column(Date, nullable=False)
    unfallort           = Column(String)
    unfallbeschreibung  = Column(Text)
    status              = Column(
        String, default="offen",
        CheckConstraint("status IN ('offen','laufend','abgeschlossen','ruhend')")
    )
    erstellt_am         = Column(DateTime, default=func.now())
    aktualisiert_am     = Column(DateTime, default=func.now(), onupdate=func.now())

    # Beziehungen
    beteiligte      = relationship("Beteiligter",   back_populates="unfall", cascade="all, delete")
    fahrzeuge       = relationship("Fahrzeug",       back_populates="unfall", cascade="all, delete")
    versicherungen  = relationship("Versicherung",   back_populates="unfall", cascade="all, delete")
    gutachten       = relationship("Gutachten",      back_populates="unfall", cascade="all, delete")
    forderungen     = relationship("Forderung",      back_populates="unfall", cascade="all, delete")
    regulierungen   = relationship("Regulierung",    back_populates="unfall", cascade="all, delete")
    dokumente       = relationship("Dokument",       back_populates="unfall", cascade="all, delete")
    taetigkeiten    = relationship("Taetigkeit",     back_populates="unfall", cascade="all, delete")


# ──────────────────────────────────────────────────────────────
#  BETEILIGTE
# ──────────────────────────────────────────────────────────────
class Beteiligter(Base):
    __tablename__ = "beteiligte"

    id                  = Column(Integer, primary_key=True, autoincrement=True)
    unfall_id           = Column(Integer, ForeignKey("unfall.id", ondelete="CASCADE"), nullable=False)
    rolle               = Column(String, nullable=False)   # mandant | gegner | zeuge | fahrer
    anrede              = Column(String)
    vorname             = Column(String)
    nachname            = Column(String, nullable=False)
    strasse             = Column(String)
    plz                 = Column(String)
    ort                 = Column(String)
    telefon             = Column(String)
    email               = Column(String)
    geburtsdatum        = Column(Date)
    fuehrerscheinnummer = Column(String)

    unfall = relationship("Unfall", back_populates="beteiligte")


# ──────────────────────────────────────────────────────────────
#  FAHRZEUGE
# ──────────────────────────────────────────────────────────────
class Fahrzeug(Base):
    __tablename__ = "fahrzeuge"

    id                  = Column(Integer, primary_key=True, autoincrement=True)
    unfall_id           = Column(Integer, ForeignKey("unfall.id", ondelete="CASCADE"), nullable=False)
    eigentuemer_id      = Column(Integer, ForeignKey("beteiligte.id"))
    rolle               = Column(String, nullable=False)   # mandant | gegner
    kennzeichen         = Column(String)
    marke               = Column(String)
    modell              = Column(String)
    erstzulassung       = Column(Date)
    fahrgestellnummer   = Column(String)
    farbe               = Column(String)
    km_stand            = Column(Integer)

    unfall = relationship("Unfall", back_populates="fahrzeuge")


# ──────────────────────────────────────────────────────────────
#  VERSICHERUNGEN
# ──────────────────────────────────────────────────────────────
class Versicherung(Base):
    __tablename__ = "versicherungen"

    id                  = Column(Integer, primary_key=True, autoincrement=True)
    unfall_id           = Column(Integer, ForeignKey("unfall.id", ondelete="CASCADE"), nullable=False)
    versicherung_name   = Column(String, nullable=False)
    versicherung_typ    = Column(String)   # haftpflicht | kasko | rechtsschutz
    schadennummer       = Column(String)
    ansprechpartner     = Column(String)
    telefon             = Column(String)
    email               = Column(String)
    strasse             = Column(String)
    plz                 = Column(String)
    ort                 = Column(String)

    unfall = relationship("Unfall", back_populates="versicherungen")


# ──────────────────────────────────────────────────────────────
#  GUTACHTEN
# ──────────────────────────────────────────────────────────────
class Gutachten(Base):
    __tablename__ = "gutachten"

    id                      = Column(Integer, primary_key=True, autoincrement=True)
    unfall_id               = Column(Integer, ForeignKey("unfall.id", ondelete="CASCADE"), nullable=False)
    gutachter_name          = Column(String)
    gutachter_buero         = Column(String)
    gutachtennummer         = Column(String)
    gutachtendatum          = Column(Date)
    pdf_pfad                = Column(String)
    pdf_extrahiert_am       = Column(DateTime)

    # Fahrzeugwerte (KI-extrahiert)
    wiederbeschaffungswert  = Column(Float)
    restwert                = Column(Float)
    reparaturkosten_netto   = Column(Float)
    reparaturkosten_brutto  = Column(Float)
    wertminderung           = Column(Float)
    mietwagenklasse         = Column(String)
    totalschaden            = Column(Integer, default=0)

    ki_extraktion_roh       = Column(Text)   # JSON-String der KI-Antwort
    erstellt_am             = Column(DateTime, default=func.now())

    unfall          = relationship("Unfall", back_populates="gutachten")
    schadenpositionen = relationship("Schadenposition", back_populates="gutachten", cascade="all, delete")


# ──────────────────────────────────────────────────────────────
#  SCHADENPOSITIONEN
# ──────────────────────────────────────────────────────────────
class Schadenposition(Base):
    __tablename__ = "schadenpositionen"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    gutachten_id = Column(Integer, ForeignKey("gutachten.id", ondelete="CASCADE"), nullable=False)
    kategorie    = Column(String)
    beschreibung = Column(Text)
    betrag       = Column(Float, nullable=False)
    einheit      = Column(String, default="EUR")

    gutachten = relationship("Gutachten", back_populates="schadenpositionen")


# ──────────────────────────────────────────────────────────────
#  FORDERUNGEN
# ──────────────────────────────────────────────────────────────
class Forderung(Base):
    __tablename__ = "forderungen"

    id                   = Column(Integer, primary_key=True, autoincrement=True)
    unfall_id            = Column(Integer, ForeignKey("unfall.id", ondelete="CASCADE"), nullable=False)
    forderungsdatum      = Column(Date, nullable=False)
    frist_datum          = Column(Date)

    betrag_reparatur     = Column(Float, default=0.0)
    betrag_mietwagen     = Column(Float, default=0.0)
    betrag_wertminderung = Column(Float, default=0.0)
    betrag_schmerzensgeld= Column(Float, default=0.0)
    betrag_gutachter     = Column(Float, default=0.0)
    betrag_auslagen      = Column(Float, default=0.0)
    betrag_anwaltskosten = Column(Float, default=0.0)
    betrag_sonstiges     = Column(Float, default=0.0)
    betrag_gesamt        = Column(Float)

    dokument_id  = Column(Integer, ForeignKey("dokumente.id"))
    notiz        = Column(Text)
    erstellt_am  = Column(DateTime, default=func.now())

    unfall        = relationship("Unfall", back_populates="forderungen")
    regulierungen = relationship("Regulierung", back_populates="forderung")


# ──────────────────────────────────────────────────────────────
#  REGULIERUNGEN
# ──────────────────────────────────────────────────────────────
class Regulierung(Base):
    __tablename__ = "regulierungen"

    id                   = Column(Integer, primary_key=True, autoincrement=True)
    unfall_id            = Column(Integer, ForeignKey("unfall.id", ondelete="CASCADE"), nullable=False)
    forderung_id         = Column(Integer, ForeignKey("forderungen.id"))
    eingangsdatum        = Column(Date, nullable=False)

    betrag_reparatur     = Column(Float, default=0.0)
    betrag_mietwagen     = Column(Float, default=0.0)
    betrag_wertminderung = Column(Float, default=0.0)
    betrag_schmerzensgeld= Column(Float, default=0.0)
    betrag_gutachter     = Column(Float, default=0.0)
    betrag_auslagen      = Column(Float, default=0.0)
    betrag_anwaltskosten = Column(Float, default=0.0)
    betrag_sonstiges     = Column(Float, default=0.0)
    betrag_gesamt        = Column(Float, nullable=False)

    vollstaendig = Column(Integer, default=0)   # 0=Teilzahlung, 1=vollständig
    notiz        = Column(Text)
    erstellt_am  = Column(DateTime, default=func.now())

    unfall    = relationship("Unfall", back_populates="regulierungen")
    forderung = relationship("Forderung", back_populates="regulierungen")


# ──────────────────────────────────────────────────────────────
#  DOKUMENTE
# ──────────────────────────────────────────────────────────────
class Dokument(Base):
    __tablename__ = "dokumente"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    unfall_id    = Column(Integer, ForeignKey("unfall.id", ondelete="CASCADE"), nullable=False)
    dokumenttyp  = Column(String, nullable=False)   # forderungsschreiben | gutachten | mahnung | sonstiges
    dateiname    = Column(String, nullable=False)
    dateipfad    = Column(String, nullable=False)
    dateiformat  = Column(String)                   # pdf | docx
    erstellt_am  = Column(DateTime, default=func.now())
    notiz        = Column(Text)

    unfall = relationship("Unfall", back_populates="dokumente")


# ──────────────────────────────────────────────────────────────
#  TAETIGKEITEN  –  Aktivitätshistorie
# ──────────────────────────────────────────────────────────────
class Taetigkeit(Base):
    __tablename__ = "taetigkeiten"

    id               = Column(Integer, primary_key=True, autoincrement=True)
    unfall_id        = Column(Integer, ForeignKey("unfall.id", ondelete="CASCADE"), nullable=False)
    datum            = Column(DateTime, default=func.now())
    kategorie        = Column(String, nullable=False)   # Telefonat | Schreiben | Zahlung | PDF-Import | ...
    beschreibung     = Column(Text, nullable=False)
    erstellt_von     = Column(String, default="Anwalt")
    referenz_tabelle = Column(String)
    referenz_id      = Column(Integer)

    unfall = relationship("Unfall", back_populates="taetigkeiten")


# ──────────────────────────────────────────────────────────────
#  HILFSFUNKTION: DB-Session als Dependency
# ──────────────────────────────────────────────────────────────
def get_db():
    db = Session(engine)
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Erstellt alle Tabellen beim ersten Start."""
    Base.metadata.create_all(bind=engine)
    print("✅  Datenbank initialisiert: kanzlei.db")
