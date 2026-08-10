import { tokenStore } from "../api.js";

function anredeZeile(check, mandant) {
  const name = check?.mandant_name || mandant?.name || "Mandant";
  const anrede = (mandant?.anrede || "").trim();
  if (["Herr", "Herrn", "Hr."].includes(anrede)) return `Sehr geehrter Herr ${name.split(" ").pop()},`;
  if (["Frau", "Fr."].includes(anrede))          return `Sehr geehrte Frau ${name.split(" ").pop()},`;
  return `Sehr geehrte/r ${name},`;
}

function empfaenger(check, mandant) {
  return check?.mandant_email || mandant?.email || "";
}

export function ibanAnfrageMailto(check, mandant) {
  const betreff = encodeURIComponent("Bankverbindung für Ihre Akte");
  const body = encodeURIComponent(
    `${anredeZeile(check, mandant)}\n\nfür die Geltendmachung Ihrer Schadensersatzansprüche benötigen wir noch Ihre Bankverbindung (IBAN).\n\nBitte teilen Sie uns Ihre IBAN baldmöglichst mit, damit wir eingegangene Zahlungen umgehend an Sie weiterleiten können.\n\nMit freundlichen Grüßen\nRechtsanwälte Koch, Schatz & Kollegen`
  );
  return `mailto:${empfaenger(check, mandant)}?subject=${betreff}&body=${body}`;
}

export function vollmachtAnfrageMailto(check, mandant) {
  const betreff = encodeURIComponent("Vollmacht – Bitte unterzeichnen und zurücksenden");
  const body = encodeURIComponent(
    `${anredeZeile(check, mandant)}\n\nim Anhang erhalten Sie die Vollmacht für die Bearbeitung Ihrer Schadenssache.\n\nBitte unterzeichnen Sie diese und senden Sie uns die Vollmacht baldmöglichst zurück – per E-Mail, Post oder Fax.\n\nFür Rückfragen stehen wir Ihnen gerne zur Verfügung.\n\nMit freundlichen Grüßen\nRechtsanwälte Koch, Schatz & Kollegen`
  );
  return `mailto:${empfaenger(check, mandant)}?subject=${betreff}&body=${body}`;
}

export async function vollmachtPdfLaden(akteId) {
  const token = tokenStore.getAccess();
  const base = (typeof import.meta !== "undefined" && import.meta.env?.VITE_API_URL) || "";
  const res = await fetch(`${base}/ramicro/akte/vollmacht?az=${encodeURIComponent(akteId)}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.fehler || err.typ || String(res.status));
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `Vollmacht_${(akteId || "").replace("/", "_")}.pdf`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}
