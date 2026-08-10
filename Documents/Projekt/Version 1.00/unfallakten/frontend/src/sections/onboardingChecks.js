export function berechneOnboardingChecks({ akte = {}, beteiligte = [], schaden = {}, dokumente = [] } = {}) {
  const rolleVon  = (b) => (b.rolle || b.kuerzel || "").toLowerCase();
  const klasseVon = (d) => (d.dokumentenklasse || d.klasse || "").toLowerCase();

  const mandant     = beteiligte.find(b => rolleVon(b) === "mandant");
  const gegner      = beteiligte.find(b => rolleVon(b) === "gegner");
  const ghpv        = beteiligte.find(b => ["ghpv", "ghv", "gbev", "versicherung", "ghpv_versicherung"].includes(rolleVon(b)));
  const hatUnfall   = !!(akte?.unfalldatum && akte?.unfallort);
  const hatSchaden  = (parseFloat(schaden?.abrechnungsberechnung?.gesamt_brutto) || parseFloat(schaden?.gesamt_brutto) || 0) > 0;
  const hatVollmacht = dokumente.some(d => klasseVon(d).includes("vollmacht"));
  const hatErstforderung = dokumente.some(d => klasseVon(d) === "forderungsschreiben");

  const kacheln = [
    { key: "mandant",       label: "Mandant",               ok: !!mandant,        tab: "beteiligte"    },
    { key: "gegner",        label: "Gegner / Schädiger",    ok: !!gegner,         tab: "beteiligte"    },
    { key: "ghpv",          label: "GHPV (Versicherung)",   ok: !!ghpv,           tab: "beteiligte"    },
    { key: "unfalldetails", label: "Unfalldetails",          ok: hatUnfall,        tab: "unfalldetails" },
    { key: "schaden",       label: "Schadenspositionen",    ok: hatSchaden,       tab: "schaden"       },
    { key: "vollmacht",     label: "Vollmacht & Dokumente", ok: hatVollmacht,     tab: "dokumente"     },
    { key: "erstforderung", label: "Erstforderung",         ok: hatErstforderung, tab: "word", optional: true },
  ];

  const pflicht = kacheln.filter(k => !k.optional);
  return {
    kacheln,
    pflichtAnzahl: pflicht.length,
    erledigt: pflicht.filter(k => k.ok).length,
    noetig: pflicht.some(k => !k.ok),
  };
}
