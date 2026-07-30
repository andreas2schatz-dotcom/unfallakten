import React, { useEffect, useRef, useState } from "react";
import T from "../config/theme.js";
import { apiAktenanlage } from "../api.js";

export const LEERES_FORMULAR = {
  mandant: { anrede: "", titel: "", vorname: "", nachname: "", strasse: "",
             plz: "", ort: "", telefon: "", email: "", geburtstag: "",
             iban: "", bank: "", rsv_name: "", rsv_nummer: "",
             bekannt_adressnr: "" },
  unfall: { unfalldatum: "", unfallort: "", kennzeichen: "" },
  gegner: { anrede: "", vorname: "", nachname: "", strasse: "", plz: "",
            ort: "", kennzeichen: "" },
  versicherung: { name: "", schadennummer: "" },
  gutachter: { bezeichnung: "", strasse: "", plz: "", ort: "", telefon: "",
               email: "", gutachten_nr: "" },
};

export function mischeVorbefuellung(prefill) {
  const basis = JSON.parse(JSON.stringify(LEERES_FORMULAR));
  if (!prefill) return basis;
  for (const gruppe of Object.keys(basis)) {
    Object.assign(basis[gruppe], prefill[gruppe] || {});
  }
  return basis;
}

export function validiereFormular(felder) {
  const e = {};
  if (!(felder.mandant?.nachname || "").trim()) e.nachname = "Pflichtfeld";
  const datum = (felder.unfall?.unfalldatum || "").trim();
  if (!datum) e.unfalldatum = "Pflichtfeld";
  else if (!/^\d{4}-\d{2}-\d{2}$/.test(datum))
    e.unfalldatum = "Format JJJJ-MM-TT";
  return e;
}

export function baueVorbefuellung(detail, absenderInfo) {
  const f = detail?.parse?.felder || {};
  const s = (v) => (v == null ? "" : String(v));
  return mischeVorbefuellung({
    mandant: {
      anrede: s(f.auftraggeber_anrede).toLowerCase(),
      vorname: s(f.auftraggeber_vorname),
      nachname: s(f.auftraggeber_nachname),
      strasse: s(f.auftraggeber_strasse),
      plz: s(f.auftraggeber_plz),
      ort: s(f.auftraggeber_ort),
    },
    unfall: {
      unfalldatum: s(f.schadendatum),
      kennzeichen: s(f.kennzeichen),
    },
    versicherung: {
      name: s(f.versicherung_name),
      schadennummer: s(f.schadennummer_versicherung),
    },
    gutachter: {
      bezeichnung: s(absenderInfo?.name || f.sv_buero || f.gutachter),
      strasse: s(absenderInfo?.adresse?.strasse),
      plz: s(absenderInfo?.adresse?.plz),
      ort: s(absenderInfo?.adresse?.ort),
      telefon: s(absenderInfo?.adresse?.telefon),
      email: s(absenderInfo?.adresse?.email),
      gutachten_nr: s(f.auftragsnummer),
    },
  });
}

const ANREDE_OPTIONEN = [["", "—"], ["herr", "Herr"], ["frau", "Frau"],
                         ["firma", "Firma"]];

export default function AktenanlageDialog({
  intakeDokumentId = null, zustellungId = null, prefill = null,
  onClose, onAngelegt, onUebernehmeAz = null,
}) {
  const [felder, setFelder] = useState(() => mischeVorbefuellung(prefill));
  const [fehler, setFehler] = useState({});
  const [speichert, setSpeichert] = useState(false);
  const [adressTreffer, setAdressTreffer] = useState(null);
  const [adressAkten, setAdressAkten] = useState(null);
  const [sucheVerfuegbar, setSucheVerfuegbar] = useState(true);
  const [namensWarnung, setNamensWarnung] = useState(null);
  const suchTimer = useRef(null);
  const suchLauf = useRef(0);

  const set = (gruppe, key, wert) => {
    setFelder(f => ({ ...f, [gruppe]: { ...f[gruppe], [key]: wert } }));
    if (gruppe === "mandant" && key === "nachname") setNamensWarnung(null);
  };

  useEffect(() => {
    const q = (felder.mandant.nachname || "").trim();
    if (q.length < 2 || felder.mandant.bekannt_adressnr) {
      suchLauf.current += 1;
      setAdressTreffer(null);
      return;
    }
    suchTimer.current = setTimeout(async () => {
      const lauf = ++suchLauf.current;
      try {
        const d = await apiAktenanlage.adressSuche(q);
        if (lauf === suchLauf.current) {
          setAdressTreffer(d.treffer || []);
          setSucheVerfuegbar(d.verfuegbar !== false);
        }
      } catch {
        if (lauf === suchLauf.current) setAdressTreffer(null);
      }
    }, 300);
    return () => suchTimer.current && clearTimeout(suchTimer.current);
  }, [felder.mandant.nachname, felder.mandant.bekannt_adressnr]);

  const uebernehmeAdresse = async (adressnr) => {
    try {
      const d = await apiAktenanlage.adressDetail(adressnr);
      const a = d.adresse;
      if (a) {
        setFelder(f => ({ ...f, mandant: { ...f.mandant,
          anrede: a.anrede === "2" ? "frau" : a.anrede === "4" ? "firma" : "herr",
          vorname: a.vorname || f.mandant.vorname,
          nachname: a.name || f.mandant.nachname,
          strasse: a.strasse || f.mandant.strasse,
          plz: a.plz || f.mandant.plz,
          ort: a.ort || f.mandant.ort,
          telefon: a.telefon || f.mandant.telefon,
          email: a.email || f.mandant.email,
          bekannt_adressnr: String(adressnr),
        }}));
      }
      setAdressAkten(d.akten || []);
      setAdressTreffer(null);
    } catch { /* Anlage bleibt moeglich */ }
  };

  const anlegen = async () => {
    const errs = validiereFormular(felder);
    if (Object.keys(errs).length) { setFehler(errs); return; }

    if (intakeDokumentId == null && !namensWarnung) {
      try {
        const d = await apiAktenanlage.offen();
        const nachname = felder.mandant.nachname.trim().toLowerCase();
        const treffer = (d.vorgaenge || []).find(v =>
          (v.mandant_name || "").toLowerCase().includes(nachname));
        if (treffer) {
          setNamensWarnung(treffer.mandant_name);
          return;
        }
      } catch { /* Warnpruefung optional */ }
    }

    setSpeichert(true); setFehler({});
    try {
      const res = await apiAktenanlage.anlegen({
        intake_dokument_id: intakeDokumentId,
        zustellung_id: zustellungId,
        formular: felder,
      });
      onAngelegt(res.vorgang);
    } catch (e) {
      setFehler({ allgemein: e?.message || "Fehler bei der Aktenanlage." });
    } finally { setSpeichert(false); }
  };

  const inp = (gruppe, key, label, opts = {}) => (
    <label style={{ display: "block", marginBottom: 8, flex: opts.flex || 1 }}>
      <span style={{ fontSize: T.textXs, color: T.textMuted }}>
        {label}{opts.pflicht ? " *" : ""}
      </span>
      <input
        value={felder[gruppe][key]}
        onChange={e => set(gruppe, key, e.target.value)}
        placeholder={opts.placeholder || ""}
        style={{ width: "100%", boxSizing: "border-box", padding: "6px 10px",
                 border: `1px solid ${opts.fehler ? T.red : T.border}`,
                 borderRadius: 4, fontSize: T.textSm }}
      />
      {opts.fehler && (
        <span style={{ fontSize: T.textXs, color: T.redText }}>
          {opts.fehler}
        </span>
      )}
    </label>
  );

  const gruppeTitel = (text) => (
    <div style={{ fontSize: T.textSm, fontWeight: 600, color: T.navy,
                  margin: "14px 0 6px", borderBottom: `1px solid ${T.border}`,
                  paddingBottom: 4 }}>
      {text}
    </div>
  );

  return (
    <div
      style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.45)",
               zIndex: 1000, display: "flex", alignItems: "center",
               justifyContent: "center" }}
      onClick={e => e.target === e.currentTarget && onClose()}>
      <div style={{ background: T.cardBg, borderRadius: 12,
                    boxShadow: "0 8px 40px rgba(0,0,0,0.22)",
                    padding: "1.5rem", width: "100%", maxWidth: 640,
                    maxHeight: "90vh", overflowY: "auto" }}>
        <div style={{ display: "flex", justifyContent: "space-between",
                      alignItems: "center", marginBottom: 8 }}>
          <h2 style={{ margin: 0, fontFamily: T.fontDisplay, color: T.navy,
                       fontSize: T.textLg }}>
            Neue Akte anlegen (RA-MICRO)
          </h2>
          <button onClick={onClose}
            style={{ border: "none", background: "transparent",
                     cursor: "pointer", fontSize: "1.1rem" }}>✕</button>
        </div>
        <div style={{ background: T.amberBg, color: T.amberText,
                      border: `1px solid ${T.amber}`, borderRadius: 4,
                      padding: "6px 10px", fontSize: T.textXs,
                      marginBottom: 10 }}>
          Erzeugt eine OMA-XML im überwachten Ordner — RA-MICRO legt die Akte
          selbstständig an und vergibt das Aktenzeichen.
        </div>

        {gruppeTitel("Mandant")}
        <div style={{ display: "flex", gap: 8 }}>
          <label style={{ display: "block", marginBottom: 8, width: 110 }}>
            <span style={{ fontSize: T.textXs, color: T.textMuted }}>Anrede</span>
            <select value={felder.mandant.anrede}
              onChange={e => set("mandant", "anrede", e.target.value)}
              style={{ width: "100%", padding: "6px 4px",
                       border: `1px solid ${T.border}`, borderRadius: 4,
                       fontSize: T.textSm }}>
              {ANREDE_OPTIONEN.map(([v, t]) =>
                <option key={v} value={v}>{t}</option>)}
            </select>
          </label>
          {inp("mandant", "vorname", "Vorname")}
          {inp("mandant", "nachname", "Nachname",
               { pflicht: true, fehler: fehler.nachname })}
        </div>
        {!sucheVerfuegbar && (
          <div style={{ background: T.amberBg, color: T.amberText,
                        border: `1px solid ${T.amber}`, borderRadius: 4,
                        padding: "6px 10px", fontSize: T.textXs,
                        marginBottom: 8 }}>
            ⚠ RA-MICRO-Adresssuche nicht verfügbar — Dubletten-Prüfung
            derzeit nicht möglich, Anlage bleibt möglich.
          </div>
        )}
        {felder.mandant.bekannt_adressnr && (
          <div style={{ background: T.blueBg, color: T.blueText,
                        borderRadius: 4, padding: "4px 8px",
                        fontSize: T.textXs, marginBottom: 8 }}>
            Bestandsmandant — RA-MICRO Adressnummer{" "}
            {felder.mandant.bekannt_adressnr}
            <button onClick={() => { set("mandant", "bekannt_adressnr", "");
                                     setAdressAkten(null); }}
              style={{ marginLeft: 8, border: "none",
                       background: "transparent", color: T.blueText,
                       cursor: "pointer", textDecoration: "underline",
                       fontSize: T.textXs }}>
              lösen
            </button>
          </div>
        )}
        {adressTreffer && adressTreffer.length > 0 && (
          <div style={{ border: `1px solid ${T.amber}`, background: T.amberBg,
                        borderRadius: 4, padding: 8, marginBottom: 8 }}>
            <div style={{ fontSize: T.textXs, color: T.amberText,
                          marginBottom: 4 }}>
              ⚠ Im RA-MICRO-Adressbestand gefunden — Dublette vermeiden:
            </div>
            {adressTreffer.map(t => (
              <button key={t.adressnr} onClick={() => uebernehmeAdresse(t.adressnr)}
                style={{ display: "block", width: "100%", textAlign: "left",
                         border: "none", background: "transparent",
                         cursor: "pointer", padding: "4px 2px",
                         fontSize: T.textSm }}>
                <code>AdrNr {t.adressnr}</code> — {t.vorname} {t.name}
                {t.email ? ` · ${t.email}` : ""}
              </button>
            ))}
          </div>
        )}
        {adressAkten && adressAkten.length > 0 && (
          <div style={{ border: `1px solid ${T.blue}`, background: T.blueBg,
                        borderRadius: 4, padding: 8, marginBottom: 8 }}>
            <div style={{ fontSize: T.textXs, color: T.blueText,
                          marginBottom: 4 }}>
              Bestehende Akten dieser Person — gehört der Unfall dazu?
            </div>
            {adressAkten.map(a => (
              <div key={a.az} style={{ display: "flex", gap: 8,
                                       alignItems: "center",
                                       fontSize: T.textSm, padding: "2px 0" }}>
                <code>{a.az}</code>
                <span style={{ flex: 1 }}>{a.kurzbezeichnung}</span>
                {onUebernehmeAz && (
                  <button onClick={() => onUebernehmeAz(a.az)}
                    style={{ border: `1px solid ${T.blue}`,
                             background: "transparent", color: T.blueText,
                             borderRadius: 4, padding: "2px 8px",
                             cursor: "pointer", fontSize: T.textXs }}>
                    Dokument dieser Akte zuordnen
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
        <div style={{ display: "flex", gap: 8 }}>
          {inp("mandant", "strasse", "Straße Nr.", { flex: 2 })}
          {inp("mandant", "plz", "PLZ")}
          {inp("mandant", "ort", "Ort", { flex: 2 })}
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          {inp("mandant", "telefon", "Telefon")}
          {inp("mandant", "email", "E-Mail", { flex: 2 })}
        </div>
        <details style={{ marginBottom: 8 }}>
          <summary style={{ fontSize: T.textXs, color: T.textMuted,
                            cursor: "pointer" }}>
            Weitere Mandantendaten (Geburtsdatum, Bank, Rechtsschutz)
          </summary>
          <div style={{ display: "flex", gap: 8, marginTop: 6 }}>
            {inp("mandant", "geburtstag", "Geburtsdatum (JJJJ-MM-TT)")}
            {inp("mandant", "iban", "IBAN", { flex: 2 })}
            {inp("mandant", "bank", "Bank")}
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            {inp("mandant", "rsv_name", "Rechtsschutzversicherung", { flex: 2 })}
            {inp("mandant", "rsv_nummer", "RSV-Versicherungsnummer")}
          </div>
        </details>

        {gruppeTitel("Unfall")}
        <div style={{ display: "flex", gap: 8 }}>
          {inp("unfall", "unfalldatum", "Unfalldatum (JJJJ-MM-TT)",
               { pflicht: true, fehler: fehler.unfalldatum })}
          {inp("unfall", "unfallort", "Unfallort", { flex: 2 })}
          {inp("unfall", "kennzeichen", "Amtl. Kennzeichen")}
        </div>

        {gruppeTitel("Gegner (optional)")}
        <div style={{ display: "flex", gap: 8 }}>
          {inp("gegner", "vorname", "Vorname")}
          {inp("gegner", "nachname", "Nachname")}
          {inp("gegner", "kennzeichen", "Kennzeichen")}
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          {inp("gegner", "strasse", "Straße Nr.", { flex: 2 })}
          {inp("gegner", "plz", "PLZ")}
          {inp("gegner", "ort", "Ort", { flex: 2 })}
        </div>

        {gruppeTitel("Gegnerische Versicherung (optional)")}
        <div style={{ display: "flex", gap: 8 }}>
          {inp("versicherung", "name", "Name", { flex: 2 })}
          {inp("versicherung", "schadennummer", "Schadennummer")}
        </div>

        {gruppeTitel("Gutachter")}
        <div style={{ display: "flex", gap: 8 }}>
          {inp("gutachter", "bezeichnung", "Bezeichnung", { flex: 2 })}
          {inp("gutachter", "gutachten_nr", "Gutachten-Nr.")}
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          {inp("gutachter", "strasse", "Straße Nr.", { flex: 2 })}
          {inp("gutachter", "plz", "PLZ")}
          {inp("gutachter", "ort", "Ort", { flex: 2 })}
        </div>

        {fehler.allgemein && (
          <div style={{ background: T.redBg, color: T.redText,
                        border: `1px solid ${T.redLight}`, borderRadius: 4,
                        padding: "8px 10px", fontSize: T.textSm,
                        marginBottom: 8 }}>
            {fehler.allgemein}
          </div>
        )}
        {namensWarnung && (
          <div style={{ background: T.amberBg, color: T.amberText,
                        border: `1px solid ${T.amber}`, borderRadius: 4,
                        padding: "8px 10px", fontSize: T.textSm,
                        marginBottom: 8 }}>
            ⚠ Für „{namensWarnung}" läuft bereits eine Aktenanlage. Erneut
            auf „Akte anlegen" klicken, um trotzdem anzulegen.
          </div>
        )}
        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end",
                      marginTop: 12 }}>
          <button onClick={onClose} disabled={speichert}
            style={{ padding: "8px 16px", background: T.offWhite,
                     border: `1px solid ${T.border}`, borderRadius: 4,
                     cursor: speichert ? "wait" : "pointer" }}>
            Abbrechen
          </button>
          <button onClick={anlegen} disabled={speichert}
            style={{ padding: "8px 16px", background: T.accent,
                     color: T.white, border: "none", borderRadius: 4,
                     cursor: speichert ? "wait" : "pointer",
                     fontWeight: 600 }}>
            {speichert ? "Wird angelegt …" : "Akte anlegen"}
          </button>
        </div>
      </div>
    </div>
  );
}
