function fmtEuro(v) {
  if (v==null) return "–";
  return new Intl.NumberFormat("de-DE",{style:"currency",currency:"EUR",minimumFractionDigits:2,maximumFractionDigits:2}).format(v);
}

function fmtSize(bytes) {
  if (!bytes) return "";
  return bytes < 1048576 ? `${Math.round(bytes/1024)} KB` : `${(bytes/1048576).toFixed(1)} MB`;
}

// KW-09: wortgleich zu backend/word/klage_service.py::_fmt_datum
function fmtDatumDe(iso) {
  if (!iso) return "";
  const s = String(iso).trim();
  try {
    if (s.includes("-") && s[4] === "-") {
      const teile = s.slice(0, 10).split("-");
      return `${teile[2]}.${teile[1]}.${teile[0]}`;
    }
    if (s.includes(".")) {
      const teile = s.split(".");
      if (teile.length === 3) {
        let j = teile[2].trim();
        if (j.length === 2) j = `20${j}`;
        return `${teile[0].padStart(2, "0")}.${teile[1].padStart(2, "0")}.${j}`;
      }
    }
  } catch {
    // ignore, fall through
  }
  return s;
}


// KW-10: Vorbelegung Verzugseintritt = Schreibdatum + 14 Tage (Kanzlei-Standardfrist)
function verzugEintrittDefault(schreibDatum) {
  const de = fmtDatumDe(schreibDatum);
  const m = de.match(/^(\d{2})\.(\d{2})\.(\d{4})$/);
  if (!m) return "";
  const d = new Date(Date.UTC(+m[3], +m[2] - 1, +m[1] + 14));
  return `${String(d.getUTCDate()).padStart(2, "0")}.${String(d.getUTCMonth() + 1).padStart(2, "0")}.${d.getUTCFullYear()}`;
}

function summenAusPositionsstatus(positionen) {
  const eintraege = Object.values(positionen || {});
  if (!eintraege.length) return null;
  return eintraege.reduce((acc, p) => ({
    gefordert: acc.gefordert + Number(p.gefordert || 0),
    reguliert: acc.reguliert + Number(p.anerkannt || 0),
    offen:     acc.offen     + Number(p.offen     || 0),
  }), { gefordert: 0, reguliert: 0, offen: 0 });
}

export function todoDringlichkeit(todo, heute = new Date()) {
  const h = new Date(heute); h.setHours(0, 0, 0, 0);
  if (todo.faellig_am) {
    const frist = new Date(todo.faellig_am); frist.setHours(0, 0, 0, 0);
    const tage = Math.round((frist - h) / 86400000);
    const stufe = tage < 3 ? "rot" : tage < 7 ? "orange" : tage < 14 ? "gelb" : "grau";
    return todo.frist_typ === "verjaehrung"
      ? { rot: "rot", orange: "rot", gelb: "orange", grau: "gelb" }[stufe] || stufe
      : stufe;
  }
  const erstellt = new Date(todo.erstellt_am); erstellt.setHours(0, 0, 0, 0);
  const alter = Math.round((h - erstellt) / 86400000);
  if (alter >= 15) return "rot";
  if (alter >= 8)  return "orange";
  if (alter >= 4)  return "gelb";
  return "grau";
}

export { fmtEuro, fmtSize, fmtDatumDe, verzugEintrittDefault, summenAusPositionsstatus };
