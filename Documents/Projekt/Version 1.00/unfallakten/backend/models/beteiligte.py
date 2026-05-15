"""Single Source of Truth: Beteiligter-Objekt → API-Dict."""


def beteiligter_as_dict(b) -> dict:
    return {
        "id": b.id, "akte_id": b.akte_id, "rolle": b.rolle,
        "name": b.name, "vorname": b.vorname, "firma": b.firma,
        "anschrift": b.anschrift, "plz": b.plz, "ort": b.ort,
        "telefon": b.telefon, "email": b.email,
        "kfz_kennzeichen": b.kfz_kennzeichen, "kfz_typ": b.kfz_typ,
        "versicherung": b.versicherung, "vers_nr": b.vers_nr,
        "schaden_nr": b.schaden_nr, "iban": b.iban, "notizen": b.notizen,
        "vollstaendiger_name":  b.vollstaendiger_name,
        "anrede":               getattr(b, "anrede",             "") or "",
        "vorsteuer":            getattr(b, "vorsteuer",          "N") or "N",
        "vertreter_name":       getattr(b, "vertreter_name",     "") or "",
        "vertreter_funktion":   getattr(b, "vertreter_funktion", "") or "",
        "kuerzel":              getattr(b, "kuerzel",            "") or "",
        "briefanrede":          getattr(b, "briefanrede",        "") or "",
        "betreff1":             getattr(b, "betreff1",           "") or "",
        "betreff2":             getattr(b, "betreff2",           "") or "",
        "betreff3":             getattr(b, "betreff3",           "") or "",
        "ist_halter":           int(getattr(b, "ist_halter",     0) or 0),
    }
