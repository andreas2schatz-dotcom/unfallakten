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

export default function OnboardingHub({ az, beteiligte = [], schaden = {}, dokumente = [], aktivitaeten = [], onTabWechsel }) {

  const mandant     = beteiligte.find(b => b.rolle === "mandant");
  const gegner      = beteiligte.find(b => b.rolle === "gegner");
  const ghpv        = beteiligte.find(b => ["ghpv", "versicherung", "ghpv_versicherung"].includes(b.rolle));
  const hatUnfall   = !!(schaden?.unfalldatum && schaden?.unfallort);
  const hatSchaden  = (schaden?.positionen?.length || 0) > 0;
  const hatVollmacht = dokumente.some(d => (d.klasse || "").toLowerCase().includes("vollmacht"));
  const hatErstforderung = aktivitaeten.some(a => a.typ === "forderungsschreiben");

  const onboardingNoetig = !mandant || !mandant.iban;

  const storageKey = `onboarding_hub_versteckt_${az}`;
  const [versteckt, setVersteckt] = useState(
    () => localStorage.getItem(storageKey) === "true"
  );

  if (!onboardingNoetig || versteckt) return null;

  const erledigt = [!!mandant, !!gegner, !!ghpv, hatUnfall, hatSchaden, hatVollmacht]
    .filter(Boolean).length;

  const kacheln = [
    { key: "mandant",       label: "Mandant",              ok: !!mandant,        tab: "beteiligte"   },
    { key: "gegner",        label: "Gegner / Schädiger",   ok: !!gegner,         tab: "beteiligte"   },
    { key: "ghpv",          label: "GHPV (Versicherung)",  ok: !!ghpv,           tab: "beteiligte"   },
    { key: "unfalldetails", label: "Unfalldetails",         ok: hatUnfall,        tab: "unfalldetails"},
    { key: "schaden",       label: "Schadenspositionen",   ok: hatSchaden,       tab: "schaden"      },
    { key: "vollmacht",     label: "Vollmacht & Dokumente",ok: hatVollmacht,     tab: "dokumente"    },
    { key: "erstforderung", label: "Erstforderung",        ok: hatErstforderung, tab: "word", optional: true },
  ];

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
          Onboarding — {erledigt} von 6 Bereichen vollständig
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
