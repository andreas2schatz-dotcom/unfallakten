// GENERIERT von tools/gen_dokumentenklassen.py — NICHT von Hand editieren.
const DOK_TYPEN = [
  {
    "value": "abrechnungsschreiben",
    "label": "Abrechnungsschreiben"
  },
  {
    "value": "abschlepprechnung",
    "label": "Abschlepprechnung"
  },
  {
    "value": "arbeitsunfaehigkeitsbescheinigung",
    "label": "Arbeitsunfaehigkeitsbescheinigung (AU)"
  },
  {
    "value": "arztbericht",
    "label": "Arztbericht"
  },
  {
    "value": "attest",
    "label": "Attest"
  },
  {
    "value": "forderungsschreiben",
    "label": "Forderungsschreiben"
  },
  {
    "value": "gutachten",
    "label": "Gutachten"
  },
  {
    "value": "kaufvertrag",
    "label": "Kaufvertrag"
  },
  {
    "value": "klage",
    "label": "Klage"
  },
  {
    "value": "klagedrohung",
    "label": "Klagedrohung / Fristsetzung"
  },
  {
    "value": "krankenhausbericht",
    "label": "Krankenhausbericht"
  },
  {
    "value": "mahnschreiben",
    "label": "Mahnschreiben"
  },
  {
    "value": "mietwagenrechnung",
    "label": "Mietwagenrechnung"
  },
  {
    "value": "nachbesichtigung",
    "label": "Nachbesichtigung"
  },
  {
    "value": "pruefbericht",
    "label": "Prüfbericht"
  },
  {
    "value": "rechnung",
    "label": "Rechnung (Auffang)"
  },
  {
    "value": "reparaturrechnung",
    "label": "Reparatur-/Werkstattrechnung"
  },
  {
    "value": "sachstandsanfrage",
    "label": "Sachstandsanfrage"
  },
  {
    "value": "sonstiges",
    "label": "Sonstiges"
  },
  {
    "value": "standkostenrechnung",
    "label": "Standkostenrechnung"
  },
  {
    "value": "sv_rechnung",
    "label": "SV-/Gutachterrechnung"
  },
  {
    "value": "verdienstausfall_nachweis",
    "label": "Verdienstausfall-Nachweis"
  }
];
const KLASSE_TO_POS = {
  "abschlepprechnung": [
    "abschleppkosten"
  ],
  "mietwagenrechnung": [
    "mietwagenkosten"
  ],
  "reparaturrechnung": [
    "rep_rechnung_brutto"
  ],
  "standkostenrechnung": [
    "standkosten"
  ],
  "sv_rechnung": [
    "sv_kosten"
  ]
};
export { DOK_TYPEN, KLASSE_TO_POS };
