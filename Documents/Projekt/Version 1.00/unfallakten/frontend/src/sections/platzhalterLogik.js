// Wortgleiche FE-Portierung von backend/word/stellungnahme_service.py:
// ersetze_platzhalter + _GENUS_FORMEN. Aenderungen dort hier nachziehen.

export const GENUS_FORMEN = {
  m: { ANREDE: "Herr", ANREDE_DEKL: "Herrn", PRON: "er",
       PRON_GROSS: "Er", PRON_DAT: "ihm", PRON_AKK: "ihn",
       POSS: "sein", POSS_E: "seine", POSS_EM: "seinem",
       POSS_EN: "seinen", POSS_ER: "seiner", POSS_ES: "seines",
       MANDANT_NOM: "Mandant", MANDANT_OBL: "Mandanten",
       UNSER: "unser", UNSER_GROSS: "Unser",
       UNSERES: "unseres", UNSEREM: "unserem" },
  f: { ANREDE: "Frau", ANREDE_DEKL: "Frau", PRON: "sie",
       PRON_GROSS: "Sie", PRON_DAT: "ihr", PRON_AKK: "sie",
       POSS: "ihr", POSS_E: "ihre", POSS_EM: "ihrem",
       POSS_EN: "ihren", POSS_ER: "ihrer", POSS_ES: "ihres",
       MANDANT_NOM: "Mandantin", MANDANT_OBL: "Mandantin",
       UNSER: "unsere", UNSER_GROSS: "Unsere",
       UNSERES: "unserer", UNSEREM: "unserer" },
  p: { ANREDE: "", ANREDE_DEKL: "", PRON: "sie",
       PRON_GROSS: "Sie", PRON_DAT: "ihnen", PRON_AKK: "sie",
       POSS: "ihr", POSS_E: "ihre", POSS_EM: "ihrem",
       POSS_EN: "ihren", POSS_ER: "ihrer", POSS_ES: "ihres",
       MANDANT_NOM: "Mandanten", MANDANT_OBL: "Mandanten",
       UNSER: "unsere", UNSER_GROSS: "Unsere",
       UNSERES: "unserer", UNSEREM: "unseren" },
};

export function genusKontext(weiblich) {
  return { ...GENUS_FORMEN[weiblich ? "f" : "m"] };
}

export function ersetzePlatzhalter(text, kontext) {
  if (!text) return text;
  let out = text;
  for (const [key, value] of Object.entries(kontext || {})) {
    out = out.split(`<${key}>`).join(value ? String(value) : "");
  }
  return out.replace(/<([A-Z_]+)>/g, "[FEHLT: <$1>]");
}
