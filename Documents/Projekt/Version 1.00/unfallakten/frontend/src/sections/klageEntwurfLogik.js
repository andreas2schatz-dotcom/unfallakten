// Klage-Wizard "Entwurf speichern" (Paket 1): reine Logik ohne React/API.
// ENTWURF_FORMAT_VERSION bei jedem Umbau des Entwurf-Schemas hochzaehlen --
// alte Entwuerfe bieten dann im Oeffnen-Dialog nur noch "Neu beginnen".

export const ENTWURF_FORMAT_VERSION = 1;

export function serialisiereEntwurf(s) {
  return {
    wizardStep: s.wizardStep,
    wizardMaxStep: s.wizardMaxStep,
    aktLegTyp: s.aktLegTyp,
    aktLegFreigabe: s.aktLegFreigabe,
    aktLegDatum: s.aktLegDatum,
    auslandsunfall: !!s.auslandsunfall,
    wizardSachverhaltText: s.wizardSachverhaltText,
    wizardSachverhaltManuell: !!s.wizardSachverhaltManuell,
    wizardUnfallText: s.wizardUnfallText,
    wizardRwText: s.wizardRwText,
    wizardVerzugText: s.wizardVerzugText,
    wizardVerzugManuell: !!s.wizardVerzugManuell,
    wizardVerzugDatum: s.wizardVerzugDatum,
    wizardVerzugDokDatum: s.wizardVerzugDokDatum,
    wizardAntraegeText: s.wizardAntraegeText,
    wizardAntraegeManuell: !!s.wizardAntraegeManuell,
    wizardAntraegeBasis: s.wizardAntraegeBasis ?? null,
    wizardGebuehrenText: s.wizardGebuehrenText,
    wizardGebuehrenManuell: !!s.wizardGebuehrenManuell,
    positionen: (s.wizardPos || []).map(p => ({
      key: p.key,
      checked: !!p.checked,
      betrag: p.betrag ?? 0,
      label: p.label ?? p.key,
    })),
    wizardMitSG: !!s.wizardMitSG,
    wizardSGMind: s.wizardSGMind ?? 0,
    wizardHq: s.wizardHq ?? 100,
    wizardHqTyp: s.wizardHqTyp ?? "gegnerisch",
    wizardHb: s.wizardHb ?? "",
    wizardMitFestSg: !!s.wizardMitFestSg,
    wizardMitFestSach: !!s.wizardMitFestSach,
    wizardRvgAussergOv: s.wizardRvgAussergOv ?? "",
    wizardRvgBereitsGezahlt: s.wizardRvgBereitsGezahlt ?? "",
    wizardGerichtBest: !!s.wizardGerichtBest,
  };
}

export function parseEntwurf(row) {
  if (!row || typeof row.entwurf_json !== "string") return { ok: false };
  if (row.format_version !== ENTWURF_FORMAT_VERSION) return { ok: false };
  try {
    const entwurf = JSON.parse(row.entwurf_json);
    if (!entwurf || typeof entwurf !== "object" || Array.isArray(entwurf)) {
      return { ok: false };
    }
    return { ok: true, entwurf };
  } catch {
    return { ok: false };
  }
}

const fmtEur = n =>
  (Number(n) || 0).toFixed(2).replace(".", ",") + " €";

export function reconcilePositionen(entwurfPositionen, frischePositionen) {
  const alt = new Map((entwurfPositionen || []).map(p => [p.key, p]));
  const frischKeys = new Set((frischePositionen || []).map(p => p.key));
  const aenderungen = [];

  const positionen = (frischePositionen || []).map(p => {
    const a = alt.get(p.key);
    if (!a) {
      aenderungen.push(`Neue Position: ${p.label ?? p.key}`);
      return { ...p, checked: false };
    }
    if (Math.abs((Number(a.betrag) || 0) - (Number(p.betrag) || 0)) > 0.005) {
      aenderungen.push(
        `Betrag geändert: ${p.label ?? p.key} (${fmtEur(a.betrag)} → ${fmtEur(p.betrag)})`
      );
    }
    return { ...p, checked: !!a.checked };
  });

  (entwurfPositionen || []).forEach(a => {
    if (!frischKeys.has(a.key)) {
      aenderungen.push(`Position entfallen: ${a.label ?? a.key}`);
    }
  });

  return { positionen, aenderungen };
}

export function formatGespeichertAm(iso) {
  if (!iso) return "";
  const m = String(iso).match(/^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/);
  if (!m) return String(iso);
  return `${m[3]}.${m[2]}., ${m[4]}:${m[5]}`;
}
