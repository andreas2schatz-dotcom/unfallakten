import T from "./theme.js";
import { request } from '../api.js';

const STATUS_MAP = {
  offen:          { label:"Offen",          color:T.blue,  bg:T.blueBg  },
  in_regulierung: { label:"In Regulierung", color:T.amber, bg:T.amberBg },
  abgeschlossen:  { label:"Abgeschlossen",  color:T.green, bg:T.greenBg },
  klage:          { label:"Klage",          color:T.red,   bg:T.redBg   },
};

const REG_STATUS = {
  vollreguliert: { label:"Vollreguliert", color:T.green },
  teilreguliert: { label:"Teilreguliert", color:T.amber },
  abgelehnt:     { label:"Abgelehnt",     color:T.red   },
  ausstehend:    { label:"Ausstehend",    color:T.textMuted },
};


const INITIAL_STATE = {};

const IMAP_CONFIG = {
  host:"mail.anwalt-offenbach.de", port:993, ssl:true,
  user:"import@anwalt-offenbach.de", ordner:"INBOX", max_fetch:50,
  letzte_sync:"09.03.2026 08:00", naechste_sync:"09.03.2026 09:00",
  status:"verbunden",
};


const KLAGE_SECTION_COLORS = [
  { bg:"rgba(59,130,246,0.10)",  border:"rgba(59,130,246,0.25)",  text:"#1e40af" },  // 1. Gericht – Blau
  { bg:"rgba(99,102,241,0.10)", border:"rgba(99,102,241,0.25)",  text:"#3730a3" },  // 2. Parteien – Indigo
  { bg:"rgba(16,185,129,0.10)", border:"rgba(16,185,129,0.25)",  text:"#065f46" },  // 3. Schadenpositionen – Grün
  { bg:"rgba(236,72,153,0.10)", border:"rgba(236,72,153,0.25)",  text:"#9d174d" },  // 4. Personenschaden – Pink
  { bg:"rgba(245,158,11,0.10)", border:"rgba(245,158,11,0.25)",  text:"#92400e" },  // 5. Zinsen – Amber
  { bg:"rgba(139,92,246,0.10)", border:"rgba(139,92,246,0.25)",  text:"#4c1d95" },  // 6. RVG – Violett
];

const MONATS = [
  {m:"Okt",a:6,r:42000},{m:"Nov",a:9,r:67000},{m:"Dez",a:11,r:89000},
  {m:"Jan",a:8,r:54000},{m:"Feb",a:14,r:103000},{m:"Mär",a:12,r:88000},
];

const HAFTUNGSART_CFG = {
  vollhaftung: { label:"Vollhaftung",  color:T.green,  bg:T.greenBg  },
  mithaftung:  { label:"Mithaftung",   color:T.amber,  bg:T.amberBg  },
  quote:       { label:"Quote",        color:T.amber,  bg:T.amberBg  },
  ablehnung:   { label:"Abgelehnt",    color:T.red,    bg:T.redBg    },
};



const TIMELINE_FILTER = [
  { id: "alle",         label: "Alles" },
  { id: "regulierung",  label: "Regulierung" },
  { id: "taetigkeit",   label: "Tätigkeit" },
];

const TIMELINE_TYPE_CFG = {
  abrechnung:  { dot: T.green,   badge: T.greenBg,  badgeText: T.green,  label: "Abrechnung"  },
  ablehnung:   { dot: T.red,     badge: T.redBg,    badgeText: T.red,    label: "Ablehnung"   },
  pruefbericht:{ dot: T.amber,   badge: T.amberBg,  badgeText: T.amber,  label: "Prüfbericht" },
  taetigkeit:  { dot: "#7c6bdb", badge: "#ede9fe",  badgeText: "#5b47c8",label: "Tätigkeit"   },
};

const ROLLEN = [
  {value:"mandant",           label:"Mandant"},
  {value:"gegner",            label:"Gegner"},
  {value:"gericht",           label:"Gericht"},
  {value:"polizei",           label:"Polizei"},
  {value:"staatsanwaltschaft",label:"Staatsanwaltschaft"},
  {value:"sachverstaendiger", label:"Sachverständiger"},
  {value:"sonstiger",         label:"Sonstige Beteiligte"},
];

const ROLLEN_MIT_AZ = new Set(["gericht","polizei","staatsanwaltschaft"]);

const ROLLEN_C = {
  mandant:           {c:T.blue,   bg:T.blueBg},
  gegner:            {c:T.red,    bg:T.redBg},
  gericht:           {c:"#7c3aed",bg:"#ede9fe"},
  polizei:           {c:"#0369a1",bg:"#e0f2fe"},
  staatsanwaltschaft:{c:"#b45309",bg:"#fef3c7"},
  sachverstaendiger: {c:T.green,  bg:T.greenBg},
  sonstiger:         {c:T.textMuted,bg:T.surface},
};

const ROLLEN_LABEL = {
  arzt:"Behandelnder Arzt", krankenhaus:"Krankenhaus",
  physiotherapeut:"Physiotherapeut", arbeitgeber:"Arbeitgeber",
  krankenkasse:"Krankenkasse", bg:"Berufsgenossenschaft",
};

const ROLLEN_ICON = {
  arzt:"🩺", krankenhaus:"🏥", physiotherapeut:"🧘",
  arbeitgeber:"🏢", krankenkasse:"💊", bg:"🏭",
};

const SCHADEN_F = [
  {k:"rep_gutachten_netto",  l:"Reparaturkosten lt. Gutachten (netto)",   hint:"fiktiv, laut SV"},
  {k:"rep_rechnung_brutto",  l:"Reparaturkosten lt. Rechnung (brutto)",   hint:"konkret, inkl. MwSt"},
  {k:"wiederbeschaffung",    l:"Wiederbeschaffungswert (WBW)"},
  {k:"restwert",             l:"Restwert",                                abzug:true},
  {k:"wertminderung",        l:"Merkantile Wertminderung"},
  {k:"nutzungsausfall",      l:"Nutzungsausfallschaden"},
  {k:"mietwagenkosten",      l:"Mietwagenkosten (brutto)"},
  {k:"sv_kosten",            l:"SV-/Gutachterkosten (brutto)"},
  {k:"abschleppkosten",      l:"Abschleppkosten (brutto)"},
  {k:"standkosten",          l:"Standkosten (brutto)"},
  {k:"anabmeldekosten",      l:"An-/Abmeldekosten (brutto)"},
  {k:"schmerzensgeld",       l:"Schmerzensgeldvorschuss"},
  {k:"verdienstausfall",     l:"Verdienstausfall"},
  {k:"haushalt",             l:"Haushaltsführungsschaden"},
  {k:"unkostenpauschale",    l:"Unkostenpauschale (30 €)"},
  {k:"sonstiges",            l:"Sonstiges"},
];

/**
 * Ermittelt die Abrechnungsart automatisch aus den Schadendaten.
 * @param {object} schaden  - Schaden-State (form oder gespeicherter Schaden)
 * @param {boolean} vorsteuer - true wenn Mandant vorsteuerabzugsberechtigt
 * @returns {{ art: string, begruendung: string } | null}
 */
// ── Personenschaden API ────────────────────────────────────────────────────

const POSITION_LABELS_FE = {
  reparaturkosten: "Reparaturkosten", wiederbeschaffung: "Wiederbeschaffung",
  restwert: "Restwert", wertminderung: "Wertminderung",
  nutzungsausfall: "Nutzungsausfall", mietwagenkosten: "Mietwagenkosten",
  sv_kosten: "SV-Kosten", abschleppkosten: "Abschleppkosten",
  standkosten: "Standkosten", anabmeldekosten: "An-/Abmeldekosten",
  schmerzensgeld: "Schmerzensgeld", sonstiges: "Sonstiges",
  // PDF-Parser-Arten (werden via position_key gesetzt)
  reparatur_brutto: "Reparaturkosten (brutto)", reparatur_netto: "Reparaturkosten (netto)",
  wbw: "Wiederbeschaffungswert", wbw_netto: "WBW (netto)", wbw_brutto: "WBW (brutto)",
  fahrzeugschaden: "Fahrzeugschaden", fahrzeugschaden_netto: "Fahrzeugschaden", kostenpauschale: "Kostenpauschale",
  ra_gebuehren: "RA-Gebühren", mwst_abzug: "Abzug MwSt.", pruefbericht_abzug: "Abzug Prüfbericht",
  // Fehlende Schaden-Keys (in SCHADEN_POS_MAP aber bisher nicht hier):
  verdienstausfall:  "Verdienstausfall",
  haushalt:          "Haushaltsführungsschaden",
  unkostenpauschale: "Unkostenpauschale",
  kostennb:          "Nachbesichtigungskosten",
  // WDM-Regulierung: Fahrzeugschaden-Keys (werden als position_key gesetzt)
  rep_gutachten_netto:  "Reparaturkosten lt. Gutachten (netto)",
  rep_rechnung_netto:   "Reparaturkosten lt. Rechnung (netto)",
  rep_rechnung_brutto:  "Reparaturkosten lt. Rechnung (brutto)",
  // WDM-Regulierungsvariablen ohne Schaden-Gegenstück:
  vorschuss:         "Vorschuss (frei verrechenbar)",
  sonstiges_wdm_1:   "Sonstiger Schaden 1",
  sonstiges_wdm_2:   "Sonstiger Schaden 2",
  sonstiges_wdm_3:   "Sonstiger Schaden 3",
  sonstiges_wdm_4:   "Sonstiger Schaden 4",
  sonstiges_wdm_5:   "Sonstiger Schaden 5",
  sonstiges_wdm_6:   "Sonstiger Schaden 6",
};

// Bug 5: Restwert ist ein Abzugsposten – höherer Wert der Versicherung = schlechter für Mandant

const POSITION_IST_ABZUG = { restwert: true };

const POSITION_KEYS_FE = Object.keys(POSITION_LABELS_FE);

const ART_LABEL = {
  reparatur_brutto:   "Reparaturkosten (brutto)",
  reparatur_netto:    "Reparaturkosten (netto)",
  reparatur_fiktiv:   "Reparaturkosten (fiktiv)",
  sv_kosten:          "Sachverständigenkosten",
  wbw:                "Wiederbeschaffungswert",
  wbw_netto:          "Wiederbeschaffungswert (netto)",
  wbw_brutto:         "Wiederbeschaffungswert (brutto)",
  restwert:           "Restwert",
  fahrzeugschaden:    "Fahrzeugschaden",
  kostenpauschale:    "Kostenpauschale",
  wertminderung:      "Wertminderung",
  ra_gebuehren:       "Rechtsanwaltsgebühren",
  mwst_abzug:         "Abzug MwSt.",
  pruefbericht_abzug: "Abzug Prüfbericht",
};

const ABRECHNUNG_ART_LABEL = {
  reparatur_fiktiv:   "Reparatur fiktiv",
  reparatur_konkret:  "Reparatur konkret",
  totalschaden:       "Totalschaden",
  unbekannt:          "Unbekannt",
};

const DOK_TYPEN = [{value:"gutachten",label:"Gutachten"},{value:"abrechnungsschreiben",label:"Abrechnungsschreiben"},{value:"pruefbericht",label:"Prüfbericht"},{value:"reparaturrechnung",label:"Reparaturrechnung"},{value:"sv_rechnung",label:"SV-Honorarrechnung"},{value:"gutachterrechnung",label:"Gutachterrechnung"},{value:"abschlepprechnung",label:"Abschlepprechnung"},{value:"mietwagenrechnung",label:"Mietwagenrechnung"},{value:"arztbericht",label:"Arztbericht"},{value:"krankenhausbericht",label:"Krankenhausbericht"},{value:"verdienstausfall_nachweis",label:"Verdienstausfall-Nachweis"},{value:"haushalt_attest",label:"Attest Haushaltsführung"},{value:"kaufvertrag",label:"Kaufvertrag"},{value:"nachbesichtigung",label:"Nachbesichtigung"},{value:"forderungsschreiben",label:"Forderungsschreiben"},{value:"sachstandsanfrage",label:"Sachstandsanfrage"},{value:"klage",label:"Klage"},{value:"sonstiges",label:"Sonstiges"}];

const POS_KUERZUNG_KATEGORIE = {
  fahrzeugschaden_netto: ["fahrzeugschaden"],
  rep_gutachten_netto:  ["fahrzeugschaden"],
  rep_rechnung_netto:   ["fahrzeugschaden"],
  rep_rechnung_brutto:  ["fahrzeugschaden"],
  reparaturkosten:      ["fahrzeugschaden"],
  wiederbeschaffung:    ["fahrzeugschaden", "ersatzbeschaffung"],
  restwert:             ["fahrzeugschaden"],
  wertminderung:        ["fahrzeugschaden", "sonstiger_schaden"],
  sv_kosten:            ["technisch_gutachten"],
  nutzungsausfall:      ["sonstiger_schaden"],
  mietwagenkosten:      ["sonstiger_schaden"],
  unkostenpauschale:    ["sonstiger_schaden"],
  schmerzensgeld:       ["sonstiger_schaden"],
  verdienstausfall:     ["sonstiger_schaden"],
  haushalt:             ["sonstiger_schaden"],
  abschleppkosten:      ["sonstiger_schaden"],
  standkosten:          ["sonstiger_schaden"],
  anabmeldekosten:      ["ersatzbeschaffung", "sonstiger_schaden"],
  sonstiges:            ["sonstiger_schaden"],
};

// Kürzungskatalog – Kategorie-Konfiguration (Label + Badge-Farben)

const KATEGORIE_CFG = {
  fahrzeugschaden:    { label: "Fahrzeugschaden",       bg: "#dbeafe", color: "#1e40af" },
  ersatzbeschaffung:  { label: "Ersatzbeschaffung",     bg: "#d1fae5", color: "#065f46" },
  sonstiger_schaden:  { label: "Sonstiger Schaden",     bg: "#fef3c7", color: "#92400e" },
  technisch_gutachten:{ label: "Technisch / Gutachten", bg: "#fce7f3", color: "#9d174d" },
};

const DEMO_KUERZUNGSARTEN = [
  { id:1,  bezeichnung:"Stundenverrechnungssätze",        kategorie:"fahrzeugschaden",    standard_gegenargument:"Werkstattrisiko liegt beim Schädiger; fiktiv nach Stundenverrechnungssatz der Fachwerkstatt zu ersetzen.", hinweis_intern:"Verweisbetrieb prüfen", sv_stellungnahme_erforderlich:false, aktiv:true, rechtsgrundlagen:"", sortierung:10 },
  { id:2,  bezeichnung:"Wertminderung",                   kategorie:"fahrzeugschaden",    standard_gegenargument:"Wertminderung ist nach Gutachten zu ersetzen; MwSt-Abzug nur bei gewerblicher Nutzung.", hinweis_intern:"MwSt / Berechnungsmethode", sv_stellungnahme_erforderlich:false, aktiv:true, rechtsgrundlagen:"", sortierung:20 },
  { id:3,  bezeichnung:"Ersatzteilaufschläge / UPE-Zuschläge", kategorie:"fahrzeugschaden", standard_gegenargument:"UPE-Zuschläge sind auch bei fiktiver Abrechnung zu ersetzen.", hinweis_intern:"auch fiktiv", sv_stellungnahme_erforderlich:false, aktiv:true, rechtsgrundlagen:"", sortierung:30 },
  { id:4,  bezeichnung:"Verbringungskosten",              kategorie:"fahrzeugschaden",    standard_gegenargument:"Verbringungskosten sind ortsüblich und auch fiktiv erstattungsfähig.", hinweis_intern:"auch fiktiv", sv_stellungnahme_erforderlich:false, aktiv:true, rechtsgrundlagen:"", sortierung:40 },
  { id:5,  bezeichnung:"Beilackierung",                   kategorie:"fahrzeugschaden",    standard_gegenargument:"Zu ersetzen wenn Sachverständiger dies vorsieht; kein Abzug zulässig.", hinweis_intern:"SV-Gutachten maßgeblich", sv_stellungnahme_erforderlich:false, aktiv:true, rechtsgrundlagen:"", sortierung:50 },
  { id:6,  bezeichnung:"Kürzung Reparaturrechnung",       kategorie:"fahrzeugschaden",    standard_gegenargument:"Unzulässig; Werkstattrisiko liegt allein beim Schädiger.", hinweis_intern:"nie zulässig", sv_stellungnahme_erforderlich:false, aktiv:true, rechtsgrundlagen:"BGH VI ZR 398/02", sortierung:60 },
  { id:7,  bezeichnung:"Tankrest",                        kategorie:"fahrzeugschaden",    standard_gegenargument:"Zu ersetzen wenn im Gutachten ausgewiesen.", hinweis_intern:"Gutachten prüfen", sv_stellungnahme_erforderlich:false, aktiv:true, rechtsgrundlagen:"", sortierung:70 },
  { id:8,  bezeichnung:"Batteriestützbetrieb",            kategorie:"fahrzeugschaden",    standard_gegenargument:"Notwendige Reparaturmaßnahme, auch fiktiv erstattungsfähig.", hinweis_intern:"auch fiktiv", sv_stellungnahme_erforderlich:false, aktiv:true, rechtsgrundlagen:"", sortierung:80 },
  { id:9,  bezeichnung:"Fehlerspeicher auslesen",         kategorie:"fahrzeugschaden",    standard_gegenargument:"Unfallbedingte Reparaturkosten, auch fiktiv zu ersetzen.", hinweis_intern:"auch fiktiv", sv_stellungnahme_erforderlich:false, aktiv:true, rechtsgrundlagen:"", sortierung:90 },
  { id:10, bezeichnung:"Kleinteilpauschale",              kategorie:"fahrzeugschaden",    standard_gegenargument:"Bestandteil der Reparaturkalkulation, auch fiktiv zu ersetzen.", hinweis_intern:"auch fiktiv", sv_stellungnahme_erforderlich:false, aktiv:true, rechtsgrundlagen:"", sortierung:100 },
  { id:11, bezeichnung:"Technische Kürzungen",            kategorie:"technisch_gutachten",standard_gegenargument:"Abweichender Reparaturweg bedarf SV-Stellungnahme; einseitige Kürzung unzulässig.", hinweis_intern:"SV-Stellungnahme erforderlich", sv_stellungnahme_erforderlich:true, aktiv:true, rechtsgrundlagen:"", sortierung:110 },
  { id:12, bezeichnung:"Zulassungsdienst",                kategorie:"ersatzbeschaffung",  standard_gegenargument:"Erstattungsfähige Nebenkosten bei Ersatzbeschaffung.", hinweis_intern:null, sv_stellungnahme_erforderlich:false, aktiv:true, rechtsgrundlagen:"", sortierung:120 },
  { id:13, bezeichnung:"Kennzeichen / Schilderkosten",    kategorie:"ersatzbeschaffung",  standard_gegenargument:"Notwendige Nebenkosten der Wiederbeschaffung.", hinweis_intern:null, sv_stellungnahme_erforderlich:false, aktiv:true, rechtsgrundlagen:"", sortierung:130 },
  { id:14, bezeichnung:"Wunschkennzeichen",               kategorie:"ersatzbeschaffung",  standard_gegenargument:"Mehrkosten nicht erstattungsfähig; Grundkosten schon.", hinweis_intern:"nur Grundbetrag", sv_stellungnahme_erforderlich:false, aktiv:true, rechtsgrundlagen:"", sortierung:140 },
  { id:15, bezeichnung:"Unkostenpauschale",               kategorie:"sonstiger_schaden",  standard_gegenargument:"Mindestens 30 € nach ständiger Rechtsprechung; Kürzung auf 25 € unzulässig.", hinweis_intern:"mind. 30 €", sv_stellungnahme_erforderlich:false, aktiv:true, rechtsgrundlagen:"", sortierung:150 },
  { id:16, bezeichnung:"Nutzungsausfall",                 kategorie:"sonstiger_schaden",  standard_gegenargument:"Dauer richtet sich nach Reparaturdauer laut Gutachten zzgl. Wiederbeschaffungszeit.", hinweis_intern:"Dauer prüfen", sv_stellungnahme_erforderlich:false, aktiv:true, rechtsgrundlagen:"", sortierung:160 },
  { id:17, bezeichnung:"Kürzung Sachverständigenrechnung",kategorie:"sonstiger_schaden",  standard_gegenargument:"Vollständig zu ersetzen; Werkstattrisiko-Grundsatz gilt analog.", hinweis_intern:"wie Werkstattrisiko", sv_stellungnahme_erforderlich:false, aktiv:true, rechtsgrundlagen:"BGH VI ZR 67/06", sortierung:170 },
  { id:18, bezeichnung:"Mietwagenrechnung",               kategorie:"sonstiger_schaden",  standard_gegenargument:"Erstattung nach Schwacke/Fraunhofer; Kürzung nur bei erheblicher Überschreitung.", hinweis_intern:"Tabelle prüfen", sv_stellungnahme_erforderlich:false, aktiv:true, rechtsgrundlagen:"", sortierung:180 },
  { id:19, bezeichnung:"Verdienstausfall",                kategorie:"sonstiger_schaden",  standard_gegenargument:"Durch Lohnbescheinigung zu belegen; Abzug nur bei fehlendem Nachweis.", hinweis_intern:"Nachweis prüfen", sv_stellungnahme_erforderlich:false, aktiv:true, rechtsgrundlagen:"", sortierung:190 },
];


const EMAIL_STATUS = {
  zugeordnet:       { label:"Zugeordnet",       color:T.green,    bg:T.greenBg  },
  nicht_zugeordnet: { label:"Nicht zugeordnet", color:T.amber,    bg:T.amberBg  },
  fehler:           { label:"Fehler",           color:T.red,      bg:T.redBg    },
  duplikat:         { label:"Duplikat",         color:T.textMuted,bg:T.surface  },
};

const MATCH_LABELS = {
  aktenzeichen:    { label:"Aktenzeichen",    color:T.blue  },
  kfz_kennzeichen: { label:"KFZ-Kennzeichen", color:T.green },
  absender_email:  { label:"Absender-E-Mail", color:T.amber },
};

const EMAIL_TYP_LABELS = {
  gutachten:             { label:"Gutachten",         color:T.blue,      icon:"📑" },
  regulierungsschreiben: { label:"Regulierung",       color:T.green,     icon:"📄" },
  sachstandsanfrage:     { label:"Sachstandsanfrage", color:"#D97706",   icon:"📋" },
  neues_mandat:          { label:"Neues Mandat",      color:T.gold,      icon:"⭐" },
  sonstiges:             { label:"Sonstiges",         color:T.textMuted, icon:"📧" },
};

const IMPORT_STEPS = [
  "Verbinde mit IMAP-Server …",
  "Prüfe auf neue E-Mails …",
  "Lade Nachrichten herunter …",
  "Parse E-Mail-Header …",
  "Ordne Akten zu …",
  "Speichere Anhänge …",
  "Aktualisiere Import-Log …",
];


const KATEGORIEN = [
  { id:"gutachter",   label:"Gutachter",   color:T.blue   },
  { id:"versicherung",label:"Versicherung",color:T.amber  },
  { id:"gericht",     label:"Gericht",     color:T.red    },
  { id:"sonstiges",   label:"Sonstiges",   color:T.textMuted },
];

const AKTION_LABELS = {
  sachstandsanfrage:       { label:"Sachstandsanfrage eingegangen", icon:"📋" },
  regulierung_eingegangen: { label:"Regulierungsschreiben eingegangen", icon:"📄" },
  gutachten_eingegangen:   { label:"Gutachten eingegangen", icon:"📑" },
};

const SUCHMODUS_LABEL = {
  aktenzeichen: "Aktenzeichen",
  name:         "Name (Mandant / Gegner)",
  kennzeichen:  "KFZ-Kennzeichen",
  schadentag:   "Schadentag",
};

const positionKuerzungBetrag = (pos) => {
  if (POSITION_IST_ABZUG[pos.position_key]) {
    // Versicherung setzt höheren Restwert an → Mehrbelastung für Mandant
    const reguliert = parseFloat(pos.betrag_reguliert) || 0;
    const gefordert = parseFloat(pos.betrag_gefordert) || 0;
    return Math.round((reguliert - gefordert) * 100) / 100; // positiv = Mehrbelastung
  }
  const gefordert = parseFloat(pos.betrag_gefordert) || 0;
  const reguliert = parseFloat(pos.betrag_reguliert) || 0;
  return Math.round((gefordert - reguliert) * 100) / 100;
};

function fmtEuroHlp(v) {
  return new Intl.NumberFormat("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(v || 0) + " €";
}

function ermittleAbrechnungsart(schaden, vorsteuer = false) {
  const g = k => parseFloat(schaden?.[k]) || 0;
  const repGutNetto  = g("rep_gutachten_netto") || g("reparaturkosten");
  const repRechNetto = g("rep_rechnung_netto");
  const repRechBrutto= g("rep_rechnung_brutto");
  const wbw          = g("wiederbeschaffung");
  const rst          = g("restwert");
  const nFzg         = wbw - rst;

  const hatGutachten = repGutNetto  > 0;
  const hatRechnung  = repRechNetto > 0;
  const hatWbw       = wbw > 0;

  // ── Fall 1: Rechnung + Gutachten vorhanden ────────────────────────────
  if (hatRechnung && hatGutachten) {
    // Vergleichswert auf Rechnungsseite je nach Vorsteuer
    const rechnungsVergleich = vorsteuer ? repRechNetto : repRechBrutto || (repRechNetto * 1.19);
    if (repGutNetto > rechnungsVergleich) {
      return {
        art: "fiktiv",
        begruendung: vorsteuer
          ? `Gutachten (${fmtEuroHlp(repGutNetto)} netto) > Rechnung netto (${fmtEuroHlp(repRechNetto)}) → fiktive Abrechnung (VSt.-berechtigt)`
          : `Gutachten (${fmtEuroHlp(repGutNetto)} netto) > Rechnung brutto (${fmtEuroHlp(rechnungsVergleich)}) → fiktive Abrechnung`
      };
    }
    return {
      art: "konkret",
      begruendung: `Rechnung (${fmtEuroHlp(vorsteuer ? repRechNetto : rechnungsVergleich)}) günstiger als Gutachten → konkrete Abrechnung`
    };
  }

  // ── Fall 2: Nur Rechnung ──────────────────────────────────────────────
  if (hatRechnung && !hatGutachten) {
    if (!hatWbw) {
      return { art: "konkret", begruendung: `Reparaturrechnung vorhanden (${fmtEuroHlp(repRechNetto)} netto), kein WBW → konkrete Abrechnung` };
    }
    if (repRechNetto > 1.3 * wbw) {
      return { art: "totalschaden", begruendung: `Rechnung (${fmtEuroHlp(repRechNetto)}) > 130% WBW (${fmtEuroHlp(1.3*wbw)}) → wirtschaftlicher Totalschaden` };
    }
    if (repRechNetto > nFzg) {
      return { art: "konkret", begruendung: `Rechnung (${fmtEuroHlp(repRechNetto)}) > WBW−Restwert (${fmtEuroHlp(nFzg)}) aber ≤ 130% → konkrete Abrechnung (130%-Fall)` };
    }
    return { art: "konkret", begruendung: `Reparaturrechnung (${fmtEuroHlp(repRechNetto)} netto) ≤ WBW−Restwert → konkrete Abrechnung` };
  }

  // ── Fall 3: Nur Gutachten ─────────────────────────────────────────────
  if (hatGutachten && !hatRechnung) {
    if (!hatWbw) {
      return { art: "fiktiv", begruendung: `Nur Gutachten vorhanden (${fmtEuroHlp(repGutNetto)} netto), kein WBW → fiktive Abrechnung` };
    }
    if (repGutNetto > nFzg) {
      return { art: "totalschaden", begruendung: `Gutachten (${fmtEuroHlp(repGutNetto)}) > WBW−Restwert (${fmtEuroHlp(nFzg)}) → Totalschaden` };
    }
    return { art: "fiktiv", begruendung: `Gutachten (${fmtEuroHlp(repGutNetto)} netto) ≤ WBW−Restwert → fiktive Abrechnung` };
  }

  // ── Fall 4: Nur WBW, keine Reparaturkosten ───────────────────────────
  if (hatWbw && !hatGutachten && !hatRechnung) {
    return { art: "totalschaden", begruendung: `Nur WBW (${fmtEuroHlp(wbw)}) ohne Reparaturkosten → Totalschaden` };
  }

  return null; // Nicht genug Daten
}

function positionenVorlage(schaden) {
  // Abrechnungsart bestimmt welche Fahrzeugschaden-Positionen relevant sind
  const art = schaden?.abrechnungsart || null;
  const repN  = parseFloat(schaden?.rep_gutachten_netto || schaden?.reparaturkosten || 0);
  const repRN = parseFloat(schaden?.rep_rechnung_netto || 0);
  const effRep = repRN > 0 ? repRN : repN;
  const wbw   = parseFloat(schaden?.wiederbeschaffung || 0);
  const rst   = parseFloat(schaden?.restwert || 0);
  const nettoFzg = wbw - rst;
  const ist130 = repRN > 0 && wbw > 0 && repRN > nettoFzg && repRN <= 1.3 * wbw;

  // Fahrzeugschaden-Positions-Logik (identisch zum Generator)
  let fahrzeugKeys = [];
  if (art === "totalschaden" || (art == null && wbw > 0 && (effRep === 0 || (!ist130 && effRep > nettoFzg)))) {
    // Totalschaden: WBW − Restwert
    fahrzeugKeys = ["wiederbeschaffung", "restwert"];
  } else if (art === "konkret" || (art == null && repRN > 0)) {
    // Konkrete Abrechnung (inkl. 130%-Fall): Rechnungsbetrag
    fahrzeugKeys = ["rep_rechnung_netto"];
  } else if (art === "fiktiv" || (art == null && repN > 0)) {
    // Fiktive Abrechnung: Gutachtenbetrag netto
    fahrzeugKeys = ["rep_gutachten_netto"];
  } else if (wbw > 0) {
    // Fallback: WBW vorhanden, keine Reparaturkosten → Totalschaden
    fahrzeugKeys = ["wiederbeschaffung", "restwert"];
  }

  // Weitere Standard-Positionen (ohne Fahrzeugschaden-Positionen)
  const WEITERE_BASIS = ["sv_kosten", "wertminderung", "nutzungsausfall", "unkostenpauschale"];

  // Alle Positions-Keys die > 0 sind (außer Fahrzeug-Keys die wir schon haben)
  const fahrzeugKeySet = new Set(fahrzeugKeys);
  const allePositivenKeys = POSITION_KEYS_FE.filter(k =>
    !fahrzeugKeySet.has(k) && (schaden?.[k] || 0) > 0
  );

  const keys = [...new Set([...fahrzeugKeys, ...WEITERE_BASIS, ...allePositivenKeys])];

  // Betrag je Position
  const getBetrag = (k) => {
    if (k === "rep_rechnung_netto") return repRN;
    if (k === "rep_gutachten_netto") return repN;
    if (k === "wiederbeschaffung") return wbw;
    if (k === "restwert") return rst;
    return parseFloat(schaden?.[k]) || 0;
  };

  return keys.map(k => ({
    position_key:          k,
    betrag_gefordert:      getBetrag(k),
    betrag_reguliert:      getBetrag(k),
    kuerzungsart_id:       null,
    kuerzung_freitext:     "",
    fuer_klage_vorgemerkt: false,
  })).filter(p => p.betrag_gefordert > 0 || ["wiederbeschaffung","restwert","rep_gutachten_netto","rep_rechnung_netto"].includes(p.position_key));
}


function _mapPdfPos(pdfPositionen) {
  return pdfPositionen.map(p => {
    const betrag = Number(
      ((p.betrag_netto ?? p.betrag_brutto ?? p.betrag_gefordert ?? 0)).toFixed(2)
    );
    return {
      position_key:          p.art || p.position_key || "sonstiges",
      betrag_gefordert:      betrag,
      betrag_reguliert:      betrag,
      kuerzungsart_id:       null,
      kuerzung_freitext:     "",
      fuer_klage_vorgemerkt: false,
    };
  });
}


function normalisiereLogEintrag(e) {
  let absenderEmail = "", absenderName = e.von_name || "";
  if (e.absender) {
    const m = e.absender.match(/<([^>]+)>/);
    absenderEmail = m ? m[1] : e.absender;
    if (!absenderName) absenderName = m
      ? e.absender.replace(/<[^>]+>/, "").trim()
      : e.absender;
  }
  return { ...e,
    akte_az:         e.akte_az || e.akte_id || null,
    absender_email:  e.absender_email || absenderEmail,
    von_name:        absenderName || absenderEmail || "",
    als_gelesen:     e.als_gelesen ?? true,
    anhaenge_anzahl: e.anhaenge_anzahl || 0,
    versicherer_name: e.versicherer_name || null,
    versicherer_kuerzel: e.versicherer_kuerzel || null,
  };
}

const apiPS = {
  laden:   (az) => request(`/akten/${az}/personenschaden`),
  speichern: (az, daten) => request(`/akten/${az}/personenschaden`,
    {method:"PUT", body:JSON.stringify(daten)}),
  beteiligteLaden: (az) => request(`/akten/${az}/personenschaden/beteiligte`),
  beteiligterSpeichern: (az, daten) => request(`/akten/${az}/personenschaden/beteiligte`,
    {method:"POST", body:JSON.stringify(daten)}),
  beteiligterLoeschen: (az, id) => request(`/akten/${az}/personenschaden/beteiligte/${id}`,
    {method:"DELETE"}),
  beteiligterAktualisieren: (az, id, daten) => request(`/akten/${az}/personenschaden/beteiligte/${id}`,
    {method:"PATCH", body:JSON.stringify(daten)}),
  wdmLaden: (az) => request(`/akten/${az}/personenschaden/wdm`),
  adressSuche: (q) => request(`/ramicro/akte/adressen/suche?q=${encodeURIComponent(q)}&limit=10`),
};


export {
  STATUS_MAP,
  REG_STATUS,
  INITIAL_STATE,
  IMAP_CONFIG,
  KLAGE_SECTION_COLORS,
  MONATS,
  HAFTUNGSART_CFG,
  TIMELINE_FILTER,
  TIMELINE_TYPE_CFG,
  ROLLEN,
  ROLLEN_MIT_AZ,
  ROLLEN_C,
  ROLLEN_LABEL,
  ROLLEN_ICON,
  SCHADEN_F,
  POSITION_LABELS_FE,
  POSITION_IST_ABZUG,
  POSITION_KEYS_FE,
  ART_LABEL,
  ABRECHNUNG_ART_LABEL,
  DOK_TYPEN,
  POS_KUERZUNG_KATEGORIE,
  KATEGORIE_CFG,
  DEMO_KUERZUNGSARTEN,
  EMAIL_STATUS,
  MATCH_LABELS,
  EMAIL_TYP_LABELS,
  IMPORT_STEPS,
  KATEGORIEN,
  AKTION_LABELS,
  SUCHMODUS_LABEL,
  positionKuerzungBetrag,
  fmtEuroHlp,
  ermittleAbrechnungsart,
  positionenVorlage,
  _mapPdfPos,
  normalisiereLogEintrag,
  apiPS
};
