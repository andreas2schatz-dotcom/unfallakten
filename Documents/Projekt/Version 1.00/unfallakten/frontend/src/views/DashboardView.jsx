import React, { useState, useEffect, useCallback, useMemo } from "react";
import T from "../config/theme.js";
import Ic from "../config/icons.jsx";
import { STATUS_MAP } from "../config/constants.js";
import { StatusBadge, Card, Btn, Skeleton, ApiErrorBanner } from "../components/common.jsx";
import { apiDashboard, ramicroListe } from "../api.js";
import { fmtEuro } from "../config/utils.js";

// ─────────────────────────────────────────────────────────────
//  Hilfsfunktionen
// ─────────────────────────────────────────────────────────────

function fmtDatum(iso) {
  if (!iso) return "–";
  const d = new Date(iso.slice(0, 10));
  if (isNaN(d)) return iso;
  return d.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" });
}

// ─────────────────────────────────────────────────────────────
//  Dringlichkeitsfarbe für Fristen
// ─────────────────────────────────────────────────────────────

function fristFarbe(tage, ueberfaellig) {
  if (ueberfaellig || tage < 0) return { border: T.red,   bg: T.redBg,   text: T.red   };
  if (tage <= 7)                 return { border: T.amber, bg: T.amberBg, text: T.amber };
  return                                { border: T.blue,  bg: T.blueBg,  text: T.blue  };
}

// ─────────────────────────────────────────────────────────────
//  Vorschlag-Badge
// ─────────────────────────────────────────────────────────────

const VORSCHLAG_CONF = {
  sachstandsanfrage:         { label: "STA senden",       bg: T.blueBg,   color: T.blue  },
  sachstandsanfrage_dringend:{ label: "STA dringend",     bg: T.amberBg,  color: T.amber },
  klage_pruefen:             { label: "Klage prüfen",     bg: T.redBg,    color: T.red   },
  keine:                     { label: "Keine Aktion",     bg: T.surface,  color: T.textMuted },
};

function VorschlagBadge({ vorschlag }) {
  const cfg = VORSCHLAG_CONF[vorschlag] || VORSCHLAG_CONF.keine;
  return (
    <span style={{
      display: "inline-block", padding: "3px 9px", borderRadius: 20,
      background: cfg.bg, color: cfg.color,
      fontFamily: "'Figtree',sans-serif", fontSize: "0.78rem", fontWeight: 700,
    }}>
      {cfg.label}
    </span>
  );
}

// ─────────────────────────────────────────────────────────────
//  Abschnitts-Header
// ─────────────────────────────────────────────────────────────

function SectionHeader({ icon, title, count, color }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 9, marginBottom: "1rem" }}>
      <span style={{ color: color || T.navy, fontSize: "1.1rem", flexShrink: 0 }}>{icon}</span>
      <h3 style={{
        fontFamily: "'Bricolage Grotesque',sans-serif", fontSize: "1.1rem",
        fontWeight: 700, color: T.navy, margin: 0, letterSpacing: "-0.01em",
      }}>
        {title}
      </h3>
      {count > 0 && (
        <span style={{
          background: color || T.navy, color: "#fff",
          fontFamily: "'Figtree',sans-serif", fontSize: "0.74rem", fontWeight: 700,
          borderRadius: 20, padding: "2px 8px", marginLeft: 2, flexShrink: 0,
        }}>
          {count}
        </span>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
//  Leere-Liste Hinweis
// ─────────────────────────────────────────────────────────────

function EmptyHint({ text }) {
  return (
    <div style={{
      textAlign: "center", padding: "1.1rem 1rem",
      color: T.textFaint, fontFamily: "'Figtree',sans-serif", fontSize: "0.875rem",
    }}>
      {text}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
//  Block 1: Fristen
// ─────────────────────────────────────────────────────────────

function FristenBlock({ fristen, loadingAction, onOpenAkte }) {
  if (loadingAction) return <SkeletonRows n={3} />;
  if (!fristen || fristen.length === 0) return <EmptyHint text="Keine offenen Fristen in den nächsten 30 Tagen." />;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      {fristen.map(f => {
        const farbe = fristFarbe(f.tage_bis_faellig, f.ueberfaellig);
        return (
          <div key={f.id} onClick={() => onOpenAkte && onOpenAkte({ az: f.akte_az })} style={{
            display: "flex", alignItems: "center", gap: 12,
            background: farbe.bg, border: `1px solid ${farbe.border}44`,
            borderRadius: 8, padding: "10px 14px",
            cursor: onOpenAkte ? "pointer" : "default", transition: "filter 0.12s",
          }}
            onMouseEnter={e => onOpenAkte && (e.currentTarget.style.filter = "brightness(0.96)")}
            onMouseLeave={e => onOpenAkte && (e.currentTarget.style.filter = "")}
          >
            {/* Tage-Badge */}
            <div style={{
              minWidth: 52, textAlign: "center",
              background: farbe.bg, borderRadius: 7, padding: "4px 6px",
            }}>
              <div style={{ fontFamily: "'Figtree',sans-serif", fontSize: "1.15rem", fontWeight: 800, color: farbe.text, lineHeight: 1 }}>
                {f.ueberfaellig ? "!" : Math.abs(f.tage_bis_faellig)}
              </div>
              <div style={{ fontFamily: "'Figtree',sans-serif", fontSize: "0.65rem", color: farbe.text, lineHeight: 1, marginTop: 2 }}>
                {f.ueberfaellig ? "ÜBERFÄLLIG" : "Tage"}
              </div>
            </div>

            {/* Info */}
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                <span style={{ fontFamily: "ui-monospace,monospace", fontSize: "0.825rem", fontWeight: 700, color: T.navy }}>{f.akte_az}</span>
                {f.mandant_name && <span style={{ fontFamily: "'Figtree',sans-serif", fontSize: "0.84rem", color: T.textMid }}>· {f.mandant_name}</span>}
              </div>
              <div style={{ fontFamily: "'Figtree',sans-serif", fontSize: "0.875rem", color: T.textMid, marginTop: 2, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {f.text}
              </div>
            </div>

            {/* Datum */}
            <div style={{ textAlign: "right", flexShrink: 0 }}>
              <div style={{ fontFamily: "'Figtree',sans-serif", fontSize: "0.82rem", color: T.textMuted }}>fällig</div>
              <div style={{ fontFamily: "ui-monospace,monospace", fontSize: "0.84rem", fontWeight: 700, color: farbe.text }}>{fmtDatum(f.faellig_am)}</div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
//  Block 2: Neue Eingänge
// ─────────────────────────────────────────────────────────────

function EingaengeBlock({ eingaenge, loadingAction, onNavigate }) {
  if (loadingAction) return <SkeletonRows n={1} />;
  if (!eingaenge) return null;

  const kacheln = [
    {
      key: "emails",
      label: "E-Mails nicht zugeordnet",
      count: eingaenge.emails_nicht_zugeordnet,
      icon: "✉",
      color: T.blue,
      bg: T.blueBg,
    },
    {
      key: "fragebogen",
      label: "Fragebogen (neu)",
      count: eingaenge.fragebogen_neu,
      icon: "📋",
      color: T.green,
      bg: T.greenBg,
    },
  ];

  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(200px,1fr))", gap: 12 }}>
      {kacheln.map(k => (
        <div key={k.key} onClick={() => k.count > 0 && onNavigate && onNavigate("email-import")} style={{
          background: k.count > 0 ? k.bg : T.surface,
          border: `1px solid ${k.count > 0 ? k.color + "44" : T.border}`,
          borderRadius: 10, padding: "1rem 1.25rem",
          display: "flex", alignItems: "center", gap: 12,
          cursor: k.count > 0 ? "pointer" : "default", transition: "opacity 0.12s",
        }}
          onMouseEnter={e => k.count > 0 && (e.currentTarget.style.opacity = "0.85")}
          onMouseLeave={e => (e.currentTarget.style.opacity = "1")}
        >
          <span style={{ fontSize: "1.6rem" }}>{k.icon}</span>
          <div>
            <div style={{ fontFamily: "'Figtree',sans-serif", fontSize: "0.82rem", color: T.textMuted, fontWeight: 600 }}>{k.label}</div>
            <div style={{
              fontFamily: "'Bricolage Grotesque',sans-serif",
              fontSize: "2rem", fontWeight: 700, lineHeight: 1, marginTop: 2,
              color: k.count > 0 ? k.color : T.textFaint,
            }}>
              {k.count}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
//  Block 3: Regulierung offen
// ─────────────────────────────────────────────────────────────

function RegulierungBlock({ items, loadingAction, onOpenAkte }) {
  if (loadingAction) return <SkeletonRows n={3} />;
  if (!items || items.length === 0) return <EmptyHint text="Keine offenen Regulierungen." />;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      {items.map((r, i) => {
        const isPflvg = r.typ === "pflvg";
        const farbe = isPflvg
          ? (r.pflvg_tage <= 7 ? { border: T.red, bg: T.redBg, text: T.red } : { border: T.amber, bg: T.amberBg, text: T.amber })
          : { border: T.blue, bg: T.blueBg, text: T.blue };

        return (
          <div key={i} onClick={() => onOpenAkte && onOpenAkte({ az: r.akte_az })} style={{
            display: "flex", alignItems: "center", gap: 12,
            background: farbe.bg, border: `1px solid ${farbe.border}44`,
            borderRadius: 8, padding: "10px 14px",
            cursor: onOpenAkte ? "pointer" : "default", transition: "filter 0.12s",
          }}
            onMouseEnter={e => onOpenAkte && (e.currentTarget.style.filter = "brightness(0.96)")}
            onMouseLeave={e => onOpenAkte && (e.currentTarget.style.filter = "")}
          >
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                <span style={{ fontFamily: "ui-monospace,monospace", fontSize: "0.825rem", fontWeight: 700, color: T.navy }}>{r.akte_az}</span>
                {r.mandant_name && <span style={{ fontFamily: "'Figtree',sans-serif", fontSize: "0.84rem", color: T.textMid }}>· {r.mandant_name}</span>}
                {isPflvg && (
                  <span style={{ background: farbe.bg, color: farbe.text, fontFamily: "'Figtree',sans-serif", fontSize: "0.74rem", fontWeight: 700, borderRadius: 20, padding: "2px 8px" }}>
                    §3a PflVG
                  </span>
                )}
              </div>
              <div style={{ fontFamily: "'Figtree',sans-serif", fontSize: "0.84rem", color: T.textMuted, marginTop: 3 }}>
                {isPflvg
                  ? `Frist läuft ab: ${fmtDatum(r.pflvg_faellig)} (noch ${r.pflvg_tage} Tage)`
                  : `Status: ${r.status} · seit ${r.tage_seit_eingang} Tagen`}
              </div>
            </div>

            {!isPflvg && r.betrag_differenz != null && (
              <div style={{ textAlign: "right", flexShrink: 0 }}>
                <div style={{ fontFamily: "'Figtree',sans-serif", fontSize: "0.78rem", color: T.textMuted }}>offen</div>
                <div style={{ fontFamily: "ui-monospace,monospace", fontSize: "0.9rem", fontWeight: 700, color: T.navy }}>
                  {fmtEuro(r.betrag_differenz)}
                </div>
              </div>
            )}

            {r.pflvg_tage != null && !isPflvg && (
              <div style={{ background: farbe.bg, borderRadius: 7, padding: "4px 8px", flexShrink: 0, textAlign: "center" }}>
                <div style={{ fontFamily: "'Figtree',sans-serif", fontSize: "0.7rem", fontWeight: 700, color: farbe.text }}>§3a PflVG</div>
                <div style={{ fontFamily: "ui-monospace,monospace", fontSize: "0.9rem", fontWeight: 800, color: farbe.text }}>{r.pflvg_tage}d</div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
//  Block 4: Akten ohne Bewegung
// ─────────────────────────────────────────────────────────────

function AktenOhneBewegungBlock({ items, loadingAction, onOpenAkte }) {
  if (loadingAction) return <SkeletonRows n={3} />;
  if (!items || items.length === 0) return <EmptyHint text="Keine inaktiven Akten." />;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      {items.map((a, i) => (
        <div key={i} style={{
          display: "flex", alignItems: "center", gap: 12,
          background: T.surface, border: `1px solid ${T.border}`,
          borderRadius: 8, padding: "10px 14px",
          cursor: onOpenAkte ? "pointer" : "default",
          transition: "filter 0.12s",
        }}
          onClick={() => onOpenAkte && onOpenAkte({ az: a.akte_az })}
          onMouseEnter={e => onOpenAkte && (e.currentTarget.style.filter = "brightness(0.97)")}
          onMouseLeave={e => onOpenAkte && (e.currentTarget.style.filter = "")}
        >
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
              <span style={{ fontFamily: "ui-monospace,monospace", fontSize: "0.825rem", fontWeight: 700, color: T.navy }}>{a.akte_az}</span>
              {a.mandant_name && <span style={{ fontFamily: "'Figtree',sans-serif", fontSize: "0.84rem", color: T.textMid }}>· {a.mandant_name}</span>}
            </div>
            <div style={{ fontFamily: "'Figtree',sans-serif", fontSize: "0.84rem", color: T.textMuted, marginTop: 3 }}>
              {a.tage_ohne_bewegung} Tage ohne Aktivität
              {a.letzte_aktivitaet && ` · zuletzt ${fmtDatum(a.letzte_aktivitaet)}`}
              {a.sta_anzahl > 0 && ` · ${a.sta_anzahl}× STA bereits versandt`}
            </div>
          </div>
          <VorschlagBadge vorschlag={a.vorschlag} />
        </div>
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
//  Skeleton-Hilfskomponente
// ─────────────────────────────────────────────────────────────

function SkeletonRows({ n = 3 }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      {Array.from({ length: n }).map((_, i) => (
        <div key={i} style={{ background: T.surface, borderRadius: 8, padding: "14px 16px", border: `1px solid ${T.border}` }}>
          <div style={{ background: T.border, borderRadius: 4, height: 12, width: "40%", marginBottom: 8, animation: "pulse 1.5s infinite" }} />
          <div style={{ background: T.border, borderRadius: 4, height: 10, width: "65%", animation: "pulse 1.5s infinite" }} />
        </div>
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
//  Haupt-Komponente
// ─────────────────────────────────────────────────────────────

function DashboardView({ onOpenAkte, aktenState, onNavigate }) {
  // Tabs
  const [activeTab, setActiveTab] = useState("action");

  // Action Board State
  const [actionItems, setActionItems]     = useState(null);
  const [loadingAction, setLoadingAction] = useState(true);
  const [actionError, setActionError]     = useState(null);

  // Akten-Liste State
  const [suche, setSuche]     = useState("");
  const [filter, setFilter]   = useState("alle");
  const [sortK, setSortK]     = useState("az");
  const [sortD, setSortD]     = useState("asc");
  const [apiError, setApiError]       = useState(null);
  const [liveAkten, setLiveAkten]     = useState(null);
  const [gesamt, setGesamt]           = useState(0);
  const [seite, setSeite]             = useState(1);
  const [seiten, setSeiten]           = useState(1);
  const [loadingAkten, setLoading]    = useState(true);
  const [ramicroAktiv, setRaAktiv]    = useState(true);

  // ── Daten laden ────────────────────────────────────────────

  const ladeActionItems = useCallback(() => {
    setLoadingAction(true);
    setActionError(null);
    apiDashboard.actionItems()
      .then(data => setActionItems(data))
      .catch(err => setActionError(err))
      .finally(() => setLoadingAction(false));
  }, []);

  const ladeAkten = useCallback((s = 1) => {
    setLoading(true);
    setApiError(null);
    ramicroListe.laden(s, 50)
      .then(data => {
        setLiveAkten(data.akten || []);
        setGesamt(data.gesamt  || 0);
        setSeite(data.seite    || 1);
        setSeiten(data.seiten  || 1);
        setRaAktiv(data.ramicro_aktiv !== false);
      })
      .catch(err => { setApiError(err); setLiveAkten([]); })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    ladeActionItems();
    ladeAkten(1);
    const timer = setInterval(ladeActionItems, 5 * 60 * 1000);
    return () => clearInterval(timer);
  }, [ladeActionItems, ladeAkten]);

  // ── Akten-Tabellen-Logik ───────────────────────────────────

  const akten = useMemo(() =>
    (liveAkten || []).map(a => ({
      ...a,
      id:     a.az,
      status: aktenState[a.az]?.status || a.status || "offen",
      brutto: 0,
      hq:     100,
    })),
    [liveAkten, aktenState]
  );

  const stats = useMemo(() => ({
    gesamt: gesamt,
    offen:  akten.filter(a => a.status === "offen").length,
    in_reg: akten.filter(a => a.status === "in_regulierung").length,
    abg:    akten.filter(a => a.status === "abgeschlossen").length,
    klage:  akten.filter(a => a.status === "klage").length,
  }), [akten, gesamt]);

  const gefiltert = useMemo(() => akten
    .filter(a => filter === "alle" || a.status === filter)
    .filter(a => {
      if (!suche) return true;
      const s = suche.toLowerCase();
      return [a.az, a.kurzbezeichnung, a.mandant, a.kennzeichen, a.sachbearbeiter]
        .some(f => f?.toLowerCase().includes(s));
    })
    .sort((a, b) => {
      const va = a[sortK] ?? "", vb = b[sortK] ?? "";
      return sortD === "asc"
        ? String(va).localeCompare(String(vb))
        : String(vb).localeCompare(String(va));
    }),
    [akten, filter, suche, sortK, sortD]
  );

  const sortBy = k => {
    if (sortK === k) setSortD(d => d === "asc" ? "desc" : "asc");
    else { setSortK(k); setSortD("asc"); }
  };
  const SortIc = ({ k }) => (
    <span style={{ opacity: sortK === k ? 1 : 0.3, marginLeft: 3, fontSize: "0.785rem" }}>
      {sortK === k ? (sortD === "asc" ? "▲" : "▼") : "▲"}
    </span>
  );

  // ── Action-Board Zusammenfassung ───────────────────────────

  const actionGesamt = useMemo(() => {
    if (!actionItems) return 0;
    return (
      (actionItems.fristen?.length || 0) +
      (actionItems.eingaenge?.gesamt || 0) +
      (actionItems.regulierung_offen?.length || 0) +
      (actionItems.akten_ohne_bewegung?.length || 0)
    );
  }, [actionItems]);

  // ── Render ─────────────────────────────────────────────────

  return (
    <div style={{ flex: 1, overflowY: "auto", background: T.offWhite }}>
      <div style={{ maxWidth: 1300, margin: "0 auto", padding: "1.75rem" }}>

        {/* ── Seitenkopf ─────────────────────────────────── */}
        <div style={{ marginBottom: "1.25rem", display: "flex", alignItems: "flex-end", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
          <div>
            <h1 style={{ fontFamily: "'Bricolage Grotesque',sans-serif", fontSize: "2.5rem", fontWeight: 800, color: T.navy, margin: 0, letterSpacing: "-0.02em", lineHeight: 1 }}>
              Tagesübersicht
            </h1>
            <p style={{ fontFamily: "'Figtree',sans-serif", fontSize: "0.9rem", color: T.textMuted, marginTop: 5, marginBottom: 0, fontWeight: 500 }}>
              {new Date().toLocaleDateString("de-DE", { weekday: "long", year: "numeric", month: "long", day: "numeric" })}
            </p>
          </div>
          {activeTab === "action" && (
            <Btn size="sm" variant="ghost" onClick={ladeActionItems} disabled={loadingAction}>
              {Ic.refresh || "↺"} Aktualisieren
            </Btn>
          )}
        </div>

        {/* ── Tab-Leiste ──────────────────────────────────── */}
        <div style={{ display: "flex", gap: 4, marginBottom: "1.25rem" }}>
          {[
            { key: "action", label: "Action Board", badge: loadingAction ? null : actionGesamt },
            { key: "akten",  label: "Alle Akten",   badge: null },
          ].map(tab => {
            const aktiv = activeTab === tab.key;
            return (
              <button key={tab.key} onClick={() => setActiveTab(tab.key)} style={{
                display: "flex", alignItems: "center", gap: 6,
                padding: "8px 18px", borderRadius: 24,
                border: aktiv ? `1.5px solid ${T.navy}` : `1px solid ${T.border}`,
                background: aktiv ? T.navy : T.white,
                color: aktiv ? T.white : T.textMid,
                fontFamily: "'Figtree',sans-serif", fontSize: "0.9rem", fontWeight: 600,
                cursor: "pointer", transition: "all 0.15s",
              }}>
                {tab.label}
                {tab.badge != null && tab.badge > 0 && (
                  <span style={{
                    background: aktiv ? "rgba(255,255,255,0.25)" : T.redBg,
                    color: aktiv ? T.white : T.red,
                    borderRadius: 20, padding: "1px 7px",
                    fontSize: "0.775rem", fontWeight: 700,
                  }}>
                    {tab.badge}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {/* ═══════════════════════════════════════════════════
            TAB 1: ACTION BOARD
        ═══════════════════════════════════════════════════ */}
        {activeTab === "action" && (
          <div>
            {actionError && (
              <ApiErrorBanner error={actionError} onRetry={ladeActionItems} />
            )}

            {/* Zuletzt-aktualisiert Zeile */}
            {actionItems?.generiert_am && (
              <div style={{
                fontFamily: "'Figtree',sans-serif", fontSize: "0.82rem", color: T.textFaint,
                marginBottom: "1rem",
              }}>
                Zuletzt aktualisiert: {fmtDatum(actionItems.generiert_am)}
              </div>
            )}

            <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: "1.25rem" }}>

              {/* ── Block 1: Fristen ──────────────────────── */}
              <Card style={{ padding: "1.25rem 1.4rem" }}>
                <SectionHeader
                  icon={Ic.clock || "⏰"}
                  title="Fristen"
                  count={actionItems?.fristen?.length || 0}
                  color={T.red}
                />
                <FristenBlock fristen={actionItems?.fristen} loadingAction={loadingAction} onOpenAkte={onOpenAkte} />
              </Card>

              {/* ── Block 2: Neue Eingänge ─────────────────── */}
              <Card style={{ padding: "1.25rem 1.4rem" }}>
                <SectionHeader
                  icon={Ic.mail || "✉"}
                  title="Neue Eingänge"
                  count={actionItems?.eingaenge?.gesamt || 0}
                  color={T.blue}
                />
                <EingaengeBlock
                  eingaenge={actionItems?.eingaenge}
                  loadingAction={loadingAction}
                  onNavigate={onNavigate}
                />
              </Card>

              {/* ── Block 3: Regulierung offen ─────────────── */}
              <Card style={{ padding: "1.25rem 1.4rem" }}>
                <SectionHeader
                  icon={Ic.scale || "⚖"}
                  title="Regulierung offen"
                  count={actionItems?.regulierung_offen?.length || 0}
                  color={T.amber}
                />
                <RegulierungBlock
                  items={actionItems?.regulierung_offen}
                  loadingAction={loadingAction}
                  onOpenAkte={onOpenAkte}
                />
              </Card>

              {/* ── Block 4: Akten ohne Bewegung ──────────── */}
              <Card style={{ padding: "1.25rem 1.4rem" }}>
                <SectionHeader
                  icon={Ic.folder || "📁"}
                  title="Akten ohne Bewegung"
                  count={actionItems?.akten_ohne_bewegung?.length || 0}
                  color={T.textMuted}
                />
                <AktenOhneBewegungBlock
                  items={actionItems?.akten_ohne_bewegung}
                  loadingAction={loadingAction}
                  onOpenAkte={onOpenAkte}
                />
              </Card>

            </div>
          </div>
        )}

        {/* ═══════════════════════════════════════════════════
            TAB 2: ALLE AKTEN
        ═══════════════════════════════════════════════════ */}
        {activeTab === "akten" && (
          <div>
            <ApiErrorBanner error={apiError} onRetry={() => ladeAkten(seite)} />

            {!ramicroAktiv && (
              <div style={{
                background: T.amberBg, border: `1px solid ${T.amber}44`,
                borderRadius: 8, padding: "10px 14px", marginBottom: "1rem",
                fontFamily: "'Figtree',sans-serif", fontSize: "0.855rem", color: T.amber,
              }}>
                ℹ RA-Micro nicht verbunden — keine Aktenliste verfügbar. Bitte RAMICRO_AKTIV=true in .env setzen.
              </div>
            )}

            {/* KPI-Kacheln */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(155px,1fr))", gap: "1rem", marginBottom: "1.25rem" }}>
              {loadingAkten
                ? Array.from({ length: 5 }).map((_, i) => (
                    <div key={i} style={{ background: T.surface, borderRadius: 12, padding: "1rem 1.25rem", border: `1px solid ${T.border}` }}>
                      <div style={{ background: T.border, borderRadius: 4, height: 10, width: "55%", marginBottom: 10, animation: "pulse 1.5s infinite" }} />
                      <div style={{ background: T.border, borderRadius: 4, height: 30, width: "35%", animation: "pulse 1.5s infinite" }} />
                    </div>
                  ))
                : [
                    { label: "Gesamt",        v: stats.gesamt, c: T.navy,  f: "alle"           },
                    { label: "Offen",         v: stats.offen,  c: T.blue,  f: "offen"          },
                    { label: "Regulierung",   v: stats.in_reg, c: T.amber, f: "in_regulierung" },
                    { label: "Abgeschlossen", v: stats.abg,    c: T.green, f: "abgeschlossen"  },
                    { label: "Klage",         v: stats.klage,  c: T.red,   f: "klage"          },
                  ].map((k, i) => (
                    <div key={i} onClick={() => setFilter(k.f)} style={{
                      background: k.c + "0d", borderRadius: 12, padding: "1rem 1.25rem",
                      border: `1.5px solid ${k.c}30`,
                      cursor: "pointer", transition: "filter 0.15s",
                    }}
                      onMouseEnter={e => { e.currentTarget.style.filter = "brightness(0.96)"; }}
                      onMouseLeave={e => { e.currentTarget.style.filter = ""; }}
                    >
                      <div style={{ fontFamily: "'Figtree',sans-serif", fontSize: "0.75rem", fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color: k.c, marginBottom: 8, opacity: 0.8 }}>{k.label}</div>
                      <div style={{ fontFamily: "'Bricolage Grotesque',sans-serif", fontSize: "2.5rem", fontWeight: 800, color: k.c, lineHeight: 1 }}>{k.v}</div>
                    </div>
                  ))}
            </div>

            {/* Tabelle */}
            <Card>
              <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "0.9rem 1.4rem", borderBottom: `1px solid ${T.border}`, flexWrap: "wrap" }}>
                <h2 style={{ fontFamily: "'Bricolage Grotesque',sans-serif", fontSize: "1.35rem", fontWeight: 700, color: T.navy, margin: 0, flex: 1 }}>Akten</h2>
                <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                  {[["alle", "Alle"], ["offen", "Offen"], ["in_regulierung", "Regulierung"], ["abgeschlossen", "Abgeschlossen"], ["klage", "Klage"]].map(([s, l]) => {
                    const cnt = s === "alle" ? akten.length : akten.filter(a => a.status === s).length;
                    const sm  = STATUS_MAP[s];
                    return (
                      <button key={s} onClick={() => setFilter(s)} style={{
                        padding: "4px 9px", borderRadius: 20,
                        border: `1px solid ${filter === s ? (sm?.color || T.navy) : T.border}`,
                        background: filter === s ? (sm?.bg || T.accentPale) : "transparent",
                        color: filter === s ? (sm?.color || T.navy) : T.textMuted,
                        fontFamily: "'Figtree',sans-serif", fontSize: "0.825rem", fontWeight: 600, cursor: "pointer",
                      }}>
                        {l} ({cnt})
                      </button>
                    );
                  })}
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 7, background: T.surface, border: `1px solid ${T.border}`, borderRadius: 8, padding: "5px 10px" }}>
                  <span style={{ color: T.textFaint }}>{Ic.search}</span>
                  <input
                    placeholder="Az., Mandant, Ort …"
                    value={suche}
                    onChange={e => setSuche(e.target.value)}
                    style={{ border: "none", background: "transparent", outline: "none", fontFamily: "'Figtree',sans-serif", fontSize: "0.955rem", color: T.text, width: 180 }}
                  />
                </div>
              </div>

              <div style={{ overflowX: "auto" }}>
                <table style={{ width: "100%", borderCollapse: "collapse" }}>
                  <thead>
                    <tr style={{ background: T.surface }}>
                      {[
                        { k: "az",              l: "Aktenzeichen"   },
                        { k: "kurzbezeichnung", l: "Kurzbezeichnung"},
                        { k: "mandant",         l: "Mandant"        },
                        { k: "kennzeichen",     l: "KFZ"            },
                        { k: "sachbearbeiter",  l: "SB"             },
                        { k: "status",          l: "Status"         },
                      ].map(c => (
                        <th key={c.l} onClick={() => c.k && sortBy(c.k)} style={{
                          padding: "8px 14px", textAlign: "left",
                          fontFamily: "'Figtree',sans-serif", fontSize: "0.815rem", fontWeight: 600,
                          color: T.textMuted, letterSpacing: "0.06em", textTransform: "uppercase",
                          borderBottom: `1px solid ${T.border}`, cursor: c.k ? "pointer" : "default",
                          whiteSpace: "nowrap", userSelect: "none",
                        }}>
                          {c.l}{c.k && <SortIc k={c.k} />}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {gefiltert.map((a, i) => (
                      <tr key={a.az} onClick={() => onOpenAkte(a)} style={{
                        cursor: "pointer", borderBottom: `1px solid ${T.borderSoft}`,
                        background: i % 2 === 0 ? T.white : T.surface, transition: "background 0.1s",
                      }}
                        onMouseEnter={e => e.currentTarget.style.background = T.accentPale}
                        onMouseLeave={e => e.currentTarget.style.background = i % 2 === 0 ? T.white : T.surface}
                      >
                        <td style={{ padding: "10px 14px" }}>
                          <span style={{ fontFamily: "ui-monospace,monospace", fontSize: "0.955rem", fontWeight: 600, color: T.navy }}>{a.az}</span>
                        </td>
                        <td style={{ padding: "10px 14px", maxWidth: 220, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          <div style={{ fontFamily: "'Figtree',sans-serif", fontSize: "0.9rem", fontWeight: 600, color: T.textMid }}>{a.kurzbezeichnung || "–"}</div>
                          {a.bezeichnung && <div style={{ fontFamily: "'Figtree',sans-serif", fontSize: "0.78rem", color: T.textMuted, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{a.bezeichnung}</div>}
                        </td>
                        <td style={{ padding: "10px 14px", fontFamily: "'Figtree',sans-serif", fontSize: "0.9rem", color: T.textMid }}>{a.mandant || "–"}</td>
                        <td style={{ padding: "10px 14px" }}>
                          {a.kennzeichen
                            ? <span style={{ fontFamily: "ui-monospace,monospace", fontSize: "0.84rem", fontWeight: 700, color: T.blue }}>{a.kennzeichen}</span>
                            : <span style={{ color: T.textFaint }}>–</span>}
                        </td>
                        <td style={{ padding: "10px 14px" }}>
                          {a.sachbearbeiter && (
                            <span style={{ fontFamily: "ui-monospace,monospace", fontSize: "0.84rem", background: T.accentPale, color: T.navy, border: `1px solid ${T.accentTrim}`, borderRadius: 5, padding: "2px 7px", fontWeight: 600 }}>
                              {a.sachbearbeiter}
                            </span>
                          )}
                        </td>
                        <td style={{ padding: "10px 14px" }}><StatusBadge status={aktenState[a.az]?.status || a.status} /></td>
                      </tr>
                    ))}
                    {gefiltert.length === 0 && !loadingAkten && (
                      <tr>
                        <td colSpan={6} style={{ padding: "2rem", textAlign: "center", color: T.textFaint, fontFamily: "'Figtree',sans-serif" }}>
                          Keine Akten gefunden.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>

              {/* Paginierung */}
              <div style={{
                padding: "8px 1.4rem", borderTop: `1px solid ${T.border}`,
                display: "flex", justifyContent: "space-between", alignItems: "center",
                fontFamily: "'Figtree',sans-serif", fontSize: "0.845rem", color: T.textFaint,
              }}>
                <span>{gefiltert.length} gefiltert · {gesamt} gesamt in RA-Micro</span>
                {seiten > 1 && (
                  <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
                    <Btn size="sm" variant="ghost" disabled={seite <= 1} onClick={() => ladeAkten(seite - 1)}>‹ Zurück</Btn>
                    <span style={{ padding: "0 8px" }}>Seite {seite} / {seiten}</span>
                    <Btn size="sm" variant="ghost" disabled={seite >= seiten} onClick={() => ladeAkten(seite + 1)}>Weiter ›</Btn>
                  </div>
                )}
              </div>
            </Card>
          </div>
        )}

      </div>
    </div>
  );
}

export default DashboardView;
