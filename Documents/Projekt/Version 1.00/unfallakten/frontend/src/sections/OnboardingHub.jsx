import React, { useState } from "react";

const T = {
  navy:    "#1B2A4A",
  border:  "#E2DDD3",
  amber:   "#d97706", amberBg: "#fffbeb", amberBorder: "#fde68a",
  green:   "#16a34a", greenBg: "#f0fdf4", greenBorder:  "#86efac",
  purple:  "#7c3aed", purpleBg: "#f5f3ff", purpleBorder: "#c4b5fd",
  fontDisplay: "var(--font-display)",
  fontBody:    "var(--font-ui)",
};

export default function OnboardingHub({ az, akte = {}, beteiligte = [], schaden = {}, dokumente = [], onTabWechsel }) {

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
    { key: "mandant",       label: "Mandant",              ok: !!mandant,        tab: "beteiligte"   },
    { key: "gegner",        label: "Gegner / Schädiger",   ok: !!gegner,         tab: "beteiligte"   },
    { key: "ghpv",          label: "GHPV (Versicherung)",  ok: !!ghpv,           tab: "beteiligte"   },
    { key: "unfalldetails", label: "Unfalldetails",         ok: hatUnfall,        tab: "unfalldetails"},
    { key: "schaden",       label: "Schadenspositionen",   ok: hatSchaden,       tab: "schaden"      },
    { key: "vollmacht",     label: "Vollmacht & Dokumente",ok: hatVollmacht,     tab: "dokumente"    },
    { key: "erstforderung", label: "Erstforderung",        ok: hatErstforderung, tab: "word", optional: true },
  ];

  const pflicht  = kacheln.filter(k => !k.optional);
  const erledigt = pflicht.filter(k => k.ok).length;
  const onboardingNoetig = pflicht.some(k => !k.ok);

  const storageKey = `onboarding_hub_versteckt_${az}`;
  const [versteckt, setVersteckt] = useState(
    () => localStorage.getItem(storageKey) === "true"
  );

  if (!onboardingNoetig || versteckt) return null;

  const Kachel = ({ k }) => {
    const bg     = k.ok ? T.greenBg    : k.optional ? T.purpleBg    : T.amberBg;
    const border = k.ok ? T.greenBorder: k.optional ? T.purpleBorder: T.amberBorder;
    const col    = k.ok ? T.green      : k.optional ? T.purple      : T.amber;

    return (
      <div
        onClick={() => onTabWechsel && onTabWechsel(k.tab)}
        style={{
          background: bg, border: `1px solid ${border}`,
          borderRadius: 7, padding: "9px 12px",
          cursor: onTabWechsel ? "pointer" : "default",
          transition: "opacity .15s",
        }}
        onMouseEnter={e => e.currentTarget.style.opacity = ".85"}
        onMouseLeave={e => e.currentTarget.style.opacity = "1"}
      >
        <div style={{ fontSize: "0.78rem", fontWeight: 700, color: col, fontFamily: T.fontDisplay }}>
          {k.ok ? "✓" : "○"} {k.label}
        </div>
        {k.optional && !k.ok && (
          <div style={{ fontSize: "0.65rem", color: T.purple, marginTop: 2 }}>optional</div>
        )}
      </div>
    );
  };

  return (
    <div style={{
      background: T.amberBg,
      border: `1px solid ${T.amberBorder}`,
      borderRadius: 9, margin: "12px 12px 0",
      padding: "12px 16px",
    }}>
      <div style={{ display: "flex", alignItems: "center", marginBottom: 12 }}>
        <span style={{ fontFamily: T.fontDisplay, fontWeight: 700, color: T.navy, fontSize: "0.9rem" }}>
          Onboarding — {erledigt} von {pflicht.length} Bereichen vollständig
        </span>
        <button
          onClick={() => { localStorage.setItem(storageKey, "true"); setVersteckt(true); }}
          style={{
            marginLeft: "auto", background: "transparent",
            border: `1px solid ${T.amber}`, borderRadius: 4,
            padding: "3px 12px", color: T.amber,
            cursor: "pointer", fontSize: "0.78rem", fontFamily: T.fontBody,
          }}
        >
          Zur normalen Ansicht →
        </button>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8 }}>
        {kacheln.map(k => <Kachel key={k.key} k={k} />)}
      </div>
    </div>
  );
}
