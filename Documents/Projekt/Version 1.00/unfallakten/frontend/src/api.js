/**
 * api.js – Unfallakten API Client
 * Koch, Schatz & Kollegen · Rechtsanwaltskanzlei Offenbach
 *
 * Features:
 *   - JWT Access + Refresh Token Management (sessionStorage)
 *   - Automatischer Token-Refresh bei 401 (einmaliger Retry)
 *   - Zentrales Error-Handling mit strukturierten ApiError-Objekten
 *   - Alle Backend-Endpunkte als benannte async-Funktionen
 *   - isDemoMode: liefert Mock-Daten wenn kein Backend erreichbar
 */
import React from 'react';

// ─────────────────────────────────────────────────────────────
// KONFIGURATION
// ─────────────────────────────────────────────────────────────
export const API_BASE   = (typeof import.meta !== 'undefined' && import.meta.env?.VITE_API_URL) ?? 'http://localhost:5000';
export const DEMO_MODE  = (typeof import.meta !== 'undefined' && import.meta.env?.VITE_DEMO_MODE === 'true') ?? true;

// ─────────────────────────────────────────────────────────────
// TOKEN-VERWALTUNG
// ─────────────────────────────────────────────────────────────
const KEY_ACCESS  = 'uas_access';
const KEY_REFRESH = 'uas_refresh';

export const tokenStore = {
  getAccess:   ()    => sessionStorage.getItem(KEY_ACCESS),
  getRefresh:  ()    => sessionStorage.getItem(KEY_REFRESH),
  setTokens:   (a,r) => { sessionStorage.setItem(KEY_ACCESS, a); if (r) sessionStorage.setItem(KEY_REFRESH, r); },
  clearTokens: ()    => { sessionStorage.removeItem(KEY_ACCESS); sessionStorage.removeItem(KEY_REFRESH); },
  hasTokens:   ()    => !!sessionStorage.getItem(KEY_ACCESS),
};

// ─────────────────────────────────────────────────────────────
// FEHLERKLASSE
// ─────────────────────────────────────────────────────────────
export class ApiError extends Error {
  constructor(status, message, details = null) {
    super(message);
    this.status  = status;
    this.details = details;
    this.name    = 'ApiError';
  }
}

// ─────────────────────────────────────────────────────────────
// HTTP-KERN
// ─────────────────────────────────────────────────────────────
let _isRefreshing = false;
let _refreshQueue = [];

async function _refreshAccessToken() {
  const refreshToken = tokenStore.getRefresh();
  if (!refreshToken) throw new ApiError(401, 'Kein Refresh-Token vorhanden.');
  const res = await fetch(`${API_BASE}/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${refreshToken}` },
  });
  if (!res.ok) { tokenStore.clearTokens(); throw new ApiError(401, 'Sitzung abgelaufen. Bitte erneut anmelden.'); }
  const data = await res.json();
  tokenStore.setTokens(data.access_token, data.refresh_token ?? refreshToken);
  return data.access_token;
}

export async function request(path, options = {}, _retry = true) {
  const accessToken = tokenStore.getAccess();
  const isFormData  = options.body instanceof FormData;
  const headers = {
    ...(!isFormData && options.body && { 'Content-Type': 'application/json' }),
    ...(accessToken && { 'Authorization': `Bearer ${accessToken}` }),
    ...(options.headers ?? {}),
  };

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (res.status === 401 && _retry) {
    if (_isRefreshing) {
      return new Promise((resolve, reject) => _refreshQueue.push({ resolve, reject }))
        .then(token => request(path, { ...options, headers: { ...headers, Authorization: `Bearer ${token}` } }, false));
    }
    _isRefreshing = true;
    try {
      const newToken = await _refreshAccessToken();
      _isRefreshing = false;
      _refreshQueue.forEach(cb => cb.resolve(newToken));
      _refreshQueue = [];
      return request(path, options, false);
    } catch (err) {
      _isRefreshing = false;
      _refreshQueue.forEach(cb => cb.reject(err));
      _refreshQueue = [];
      throw err;
    }
  }

  if (!res.ok) {
    let msg = `HTTP ${res.status}`, details = null;
    try { const b = await res.json(); msg = b.fehler ?? b.message ?? msg; details = b; } catch {}
    throw new ApiError(res.status, msg, details);
  }
  if (res.status === 204) return null;
  return res.json();
}

// ─────────────────────────────────────────────────────────────
// AUTH
// ─────────────────────────────────────────────────────────────
export const auth = {
  login: async (email, passwort) => {
    const data = await request('/auth/login', { method: 'POST', body: JSON.stringify({ email, passwort }) });
    tokenStore.setTokens(data.access_token, data.refresh_token);
    return data.benutzer;
  },
  logout: async () => {
    try { await request('/auth/logout', { method: 'POST' }); } catch {}
    tokenStore.clearTokens();
  },
  profil:               ()           => request('/auth/profil'),
  passwortAendern:      (alt, neu)   => request('/auth/passwort-aendern', { method: 'POST', body: JSON.stringify({ altes_passwort: alt, neues_passwort: neu }) }),
  benutzerListe:        ()           => request('/auth/benutzer'),
  benutzerErstellen:    (p)          => request('/auth/benutzer', { method: 'POST', body: JSON.stringify(p) }),
  benutzerAktualisieren:(id, p)      => request(`/auth/benutzer/${id}`, { method: 'PATCH', body: JSON.stringify(p) }),
  benutzerLoeschen:     (id)         => request(`/auth/benutzer/${id}`, { method: 'DELETE' }),
};

// ─────────────────────────────────────────────────────────────
// AKTEN
// ─────────────────────────────────────────────────────────────
export const akten = {
  liste: (params = {}) => {
    const qs = new URLSearchParams(Object.fromEntries(Object.entries(params).filter(([,v]) => v != null && v !== ''))).toString();
    return request(`/akten${qs ? '?' + qs : ''}`);
  },
  erstellen:     (p)        => request('/akten', { method: 'POST', body: JSON.stringify(p) }),
  detail:        (id)       => request(`/akten/${id}`),
  aktualisieren: (id, p)    => request(`/akten/${id}`, { method: 'PATCH', body: JSON.stringify(p) }),
  loeschen:      (id)       => request(`/akten/${id}`, { method: 'DELETE' }),
  aktivitaeten:  (id)       => request(`/akten/${id}/aktivitaeten`),
  aktivitaetLoeschen: (akteId, aktivitaetId) =>
    request(`/akten/${akteId}/aktivitaeten/${aktivitaetId}`, { method: "DELETE" }),
  statistik:     ()         => request('/akten/statistik'),
  pwaMessage: (az, text, vorlageKey = "freitext") =>
    request(`/akten/${encodeURIComponent(az)}/pwa-nachricht`, {
      method: "POST",
      body: JSON.stringify({ text, vorlage_key: vorlageKey }),
    }),
};

// ─────────────────────────────────────────────────────────────
// BETEILIGTE
// ─────────────────────────────────────────────────────────────
export const beteiligte = {
  liste:         (aId)        => request(`/akten/${aId}/beteiligte`),
  erstellen:     (aId, p)     => request(`/akten/${aId}/beteiligte`, { method: 'POST', body: JSON.stringify(p) }),
  aktualisieren: (aId, id, p) => request(`/akten/${aId}/beteiligte/${id}`, { method: 'PATCH', body: JSON.stringify(p) }),
  loeschen:      (aId, id)    => request(`/akten/${aId}/beteiligte/${id}`, { method: 'DELETE' }),
};

// ─────────────────────────────────────────────────────────────
// SCHADEN
// ─────────────────────────────────────────────────────────────
export const schaden = {
  holen:               (aId)     => request(`/akten/${aId}/schaden`),
  speichern:           (aId, p)  => request(`/akten/${aId}/schaden`, { method: 'PUT',  body: JSON.stringify(p) }),
  regulierungen:       (aId)     => request(`/akten/${aId}/regulierungen`),
  regulierungErfassen: (aId, p)  => request(`/akten/${aId}/regulierungen`, { method: 'POST', body: JSON.stringify(p) }),
  regulierungStatus:   (aId)     => request(`/akten/${aId}/regulierungen/status`),
};

// ─────────────────────────────────────────────────────────────
// DOKUMENTE
// ─────────────────────────────────────────────────────────────

// Zuverlässiger Browser-Download (funktioniert in Chrome/Firefox/Edge)
function _triggerDownload(blob, dateiname) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = dateiname || 'dokument';
  a.style.display = 'none';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 10000);
}

export const dokumente = {
  liste:    (aId)        => request(`/akten/${aId}/dokumente`),
  detail:   (aId, id)   => request(`/akten/${aId}/dokumente/${id}`),
  loeschen: (aId, id)   => request(`/akten/${aId}/dokumente/${id}`, { method: 'DELETE' }),
  klassifikation: (aId, id, klasse) => request(`/akten/${aId}/dokumente/${id}/klassifikation`, {
    method: 'POST', body: JSON.stringify({ dokumentenklasse: klasse })
  }),

  hochladen: async (aId, file, typ, onProgress) => {
    const token = tokenStore.getAccess();
    const form  = new FormData();
    form.append('datei', file);
    form.append('typ',   typ);
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open('POST', `${API_BASE}/akten/${aId}/dokumente`);
      if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`);
      xhr.upload.onprogress = e => { if (e.lengthComputable && onProgress) onProgress(Math.round(e.loaded/e.total*100)); };
      xhr.onload  = () => { if (xhr.status >= 200 && xhr.status < 300) { try { resolve(JSON.parse(xhr.responseText)); } catch { resolve(null); } } else { reject(new ApiError(xhr.status, 'Upload fehlgeschlagen')); } };
      xhr.onerror = () => reject(new ApiError(0, 'Netzwerkfehler'));
      xhr.send(form);
    });
  },

  download: async (aId, id, dateiname) => {
    const token = tokenStore.getAccess();
    const res = await fetch(`${API_BASE}/akten/${aId}/dokumente/${id}/datei`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new ApiError(res.status, 'Download fehlgeschlagen');
    const blob = await res.blob();
    _triggerDownload(blob, dateiname);
  },

  parse:    (aId, id) => request(`/akten/${aId}/dokumente/${id}/parse`),
  korrektur: (aId, id, body) => request(`/akten/${aId}/dokumente/${id}/korrektur`, {
    method: 'POST', body: JSON.stringify(body),
  }),

  // PDF im Browser-Tab oeffnen (statt Download)
  oeffnen: async (aId, id, dateiname) => {
    const token = tokenStore.getAccess();
    const res = await fetch(`${API_BASE}/akten/${aId}/dokumente/${id}/datei`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new ApiError(res.status, 'Dokument konnte nicht geladen werden');
    const blob = await res.blob();
    const typ  = blob.type || 'application/octet-stream';
    const url  = URL.createObjectURL(blob);
    if (typ === 'application/pdf' || dateiname?.toLowerCase().endsWith('.pdf')) {
      window.open(url, '_blank');
      setTimeout(() => URL.revokeObjectURL(url), 30000);
    } else {
      // Nicht-PDF: Download-Fallback
      const a = document.createElement('a');
      a.href = url; a.download = dateiname || 'anhang';
      a.style.display = 'none';
      document.body.appendChild(a); a.click(); document.body.removeChild(a);
      setTimeout(() => URL.revokeObjectURL(url), 10000);
    }
  },
};

// ─────────────────────────────────────────────────────────────
// WORD
// ─────────────────────────────────────────────────────────────
export const forderungen = {
  liste:            (az, params = {}) => {
    const qs = new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([,v]) => v != null))
    ).toString();
    return request(`/akten/${az}/forderungen${qs ? '?' + qs : ''}`);
  },
  zusammenfassung:  (az) => request(`/akten/${az}/forderungen/zusammenfassung`),
  nachSchreiben:    (az) => request(`/akten/${az}/forderungen/schreiben`),
  aktualisieren:    (az, id, daten) =>
    request(`/akten/${az}/forderungen/${id}`, { method: 'PATCH', body: JSON.stringify(daten) }),
  klageFlagSetzen:  (az, ids, flag) =>
    request(`/akten/${az}/forderungen/klage`, {
      method: 'POST',
      body: JSON.stringify({ position_ids: ids, fuer_klage: flag }),
    }),
};

export const word = {
  generieren: (aId, typ, adressatId = null) =>
    request(`/akten/${aId}/dokumente/word`, {
      method: 'POST',
      body: JSON.stringify({ typ, ...(adressatId ? { adressat_id: adressatId } : {}) })
    }),

  vorschau: async (aId, typ) => {
    const token = tokenStore.getAccess();
    const res = await fetch(`${API_BASE}/akten/${aId}/dokumente/word/${typ}/vorschau`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new ApiError(res.status, 'Vorschau fehlgeschlagen');
    const blob = await res.blob();
    _triggerDownload(blob, `${typ}_${aId}.docx`);
  },
};

// ─────────────────────────────────────────────────────────────
// KLAGE
// ─────────────────────────────────────────────────────────────
export const apiKlage = {
  daten:           (az)         => request(`/akten/${az}/klage/daten`),
  rvgBerechnen:    (az, body)   => request(`/akten/${az}/klage/rvg-berechnen`, {
                                     method: 'POST', body: JSON.stringify(body) }),
  unfalldetails:   (az)         => request(`/akten/${az}/unfalldetails`),
  unfalldetailsSpeichern: (az, body) => request(`/akten/${az}/unfalldetails`, {
                                     method: 'PUT', body: JSON.stringify(body) }),
  // Expliziter WDM-Import: lädt frisch aus RA-Micro, ignoriert SQLite-Werte
  wdmLaden:        (az)         => request(`/akten/${az}/unfalldetails?force_wdm=1`),
  gerichte:        (az, q='', typ='') => request(`/akten/${az}/klage/gerichte?q=${encodeURIComponent(q)}&typ=${typ}`),
  gerichtSpeichern:(az, gericht)     => request(`/akten/${az}/klage/gericht`, {
                                         method: 'PUT', body: JSON.stringify(gericht) }),
  kiHaftung:       (az, schilderung, hq) => request(`/akten/${az}/klage/ki-haftung`, {
                                         method: 'POST',
                                         body: JSON.stringify({ schilderung, hq }) }),
  sgAnalyse:       (az)           => request(`/akten/${az}/klage/sg-analyse`),
  sgRecherche:     (az, profil)   => request(`/akten/${az}/klage/sg-recherche`, {
                                       method: 'POST', body: JSON.stringify({ profil }) }),
  sgText:          (az, body)     => request(`/akten/${az}/klage/sg-text`, {
                                       method: 'POST', body: JSON.stringify(body) }),
  generieren: async (az, klagenConfig, overrides = null) => {
    const token = tokenStore.getAccess();
    const reqBody = { klage_config: klagenConfig, in_db: true };
    if (overrides !== null) reqBody.overrides = overrides;
    const res = await fetch(`${API_BASE}/akten/${az}/klage/generieren`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(reqBody),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new ApiError(res.status, err.fehler || 'Klageschrift-Generierung fehlgeschlagen');
    }
    const blob = await res.blob();
    const cd   = res.headers.get('Content-Disposition') || '';
    const m    = cd.match(/filename="?([^"]+)"?/);
    _triggerDownload(blob, m ? m[1] : `${az}_klageschrift.docx`);
    return { ok: true };
  },
};

// ─────────────────────────────────────────────────────────────
// PERSONENSCHADEN
// ─────────────────────────────────────────────────────────────
export const apiPersonenschaden = {
  laden:    (az)       => request(`/akten/${az}/personenschaden`),
  speichern:(az, daten) => request(`/akten/${az}/personenschaden`, {
                             method: 'PUT', body: JSON.stringify(daten) }),
};

// ─────────────────────────────────────────────────────────────
// E-MAIL-IMPORT
// ─────────────────────────────────────────────────────────────
export const emailImport = {
  starten:    (body = {}) => request('/email/import', { method: 'POST', body: JSON.stringify(body) }),
  status:     ()          => request('/email/import/status'),
  statistik:  ()          => request('/email/import/log/statistik'),
  log: (params = {}) => {
    const qs = new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([,v]) => v != null && v !== ''))
    ).toString();
    return request(`/email/import/log${qs ? '?' + qs : ''}`);
  },
  zuordnen: (logId, az) => request(
    `/email/import/log/${logId}/zuordnen`,
    { method: 'POST', body: JSON.stringify({ az }) }
  ),
  aktensuche: (q) => {
    const qs = new URLSearchParams({ q }).toString();
    return request(`/email/import/aktensuche?${qs}`);
  },
  // Dokumente eines Log-Eintrags abrufen
  dokumente:  (logId) => request(`/email/import/log/${logId}/dokumente`),
  // Anhang-Metadaten + Body-Text aus .eml laden
  meta: (logId) => request(`/email/import/log/${logId}/meta`),
  // Anhang direkt aus .eml oeffnen (PDF/Bild im Browser)
  anhangOeffnen: async (logId, index, dateiname) => {
    const token = tokenStore.getAccess();
    const res = await fetch(
      `${API_BASE}/email/import/log/${logId}/anhang/${index}`,
      { headers: token ? { Authorization: `Bearer ${token}` } : {} }
    );
    if (!res.ok) throw new ApiError(res.status, 'Anhang nicht verfuegbar');
    const blob = await res.blob();
    const url  = URL.createObjectURL(blob);
    const typ  = blob.type || '';
    if (typ.includes('pdf') || typ.includes('image')) {
      window.open(url, '_blank');
      setTimeout(() => URL.revokeObjectURL(url), 30000);
    } else {
      const a = document.createElement('a');
      a.href = url; a.download = dateiname || 'anhang';
      a.style.display = 'none';
      document.body.appendChild(a); a.click(); document.body.removeChild(a);
      setTimeout(() => URL.revokeObjectURL(url), 10000);
    }
  },
  // Anhaenge + .eml in Akte importieren
  inAkte:     (logId) => request(`/email/import/log/${logId}/in-akte`, { method: 'POST' }),
  // Regulierungsschreiben bestaetigen
  regulierungBestaetigen: (logId) => request(`/email/import/log/${logId}/regulierung-bestaetigen`, { method: 'POST' }),
  // Aktion-Badge erledigt markieren
  aktionErledigt: (az) => request(`/akten/${az}/aktion-erledigt`, { method: 'POST' }),
  // Absender-Vorlagen
  vorlagen:   () => request('/email/import/absender-vorlagen'),
  vorlageSpeichern: (d) => request('/email/import/absender-vorlagen', { method: 'POST', body: JSON.stringify(d) }),
  vorlageAktualisieren: (id, d) => request(`/email/import/absender-vorlagen/${id}`, { method: 'PATCH', body: JSON.stringify(d) }),
  vorlageLoeschen: (id) => request(`/email/import/absender-vorlagen/${id}`, { method: 'DELETE' }),
  // Fragebogen-Erstkontakte (PRD-22d)
  fragebogenErstkontakt: (params = {}) => {
    const qs = new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([,v]) => v != null && v !== ''))
    ).toString();
    return request(`/email/fragebogen-erstkontakt${qs ? '?' + qs : ''}`);
  },
  fragebogenErstkontaktStatus: (id, status) => request(
    `/email/fragebogen-erstkontakt/${id}/status`,
    { method: 'PATCH', body: JSON.stringify({ status }) }
  ),
};

// ─────────────────────────────────────────────────────────────
// HEALTH CHECK
// ─────────────────────────────────────────────────────────────
export const ping = () =>
  fetch(`${API_BASE}/health`).then(r => r.ok).catch(() => false);

// ─────────────────────────────────────────────────────────────
// REACT HOOKS
// ─────────────────────────────────────────────────────────────

/**
 * useApi – Datenfetch-Hook mit Loading/Error State und Auto-Reload
 *
 * const { data, loading, error, reload } = useApi(
 *   () => akten.liste({ status: filter }),
 *   [filter]
 * );
 */
export function useApi(fetcher, deps = [], initial = null) {
  const [data,    setData]    = React.useState(initial);
  const [loading, setLoading] = React.useState(true);
  const [error,   setError]   = React.useState(null);
  const counter = React.useRef(0);

  const load = React.useCallback(async () => {
    const id = ++counter.current;
    setLoading(true);
    setError(null);
    try {
      const result = await fetcher();
      if (id === counter.current) { setData(result); setLoading(false); }
    } catch (err) {
      if (id === counter.current) { setError(err); setLoading(false); }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  React.useEffect(() => { load(); }, [load]);
  return { data, loading, error, reload: load, setData };
}

/**
 * useMutation – Hook für CUD-Operationen
 *
 * const save = useMutation(payload => beteiligte.erstellen(akteId, payload));
 * await save.execute(formData);
 */
export function useMutation(fn) {
  const [loading, setLoading] = React.useState(false);
  const [error,   setError]   = React.useState(null);
  const fnRef = React.useRef(fn);
  fnRef.current = fn;

  const execute = React.useCallback(async (...args) => {
    setLoading(true); setError(null);
    try {
      const result = await fnRef.current(...args);
      setLoading(false);
      return result;
    } catch (err) {
      setError(err); setLoading(false);
      throw err;
    }
  }, []);

  return { execute, loading, error, reset: () => setError(null) };
}

export const isDemoMode = () => DEMO_MODE;

// ── Modul 8: Wiedervorlage / Sachstandsanfragen ──────────────────────────────

export const wiedervorlage = {
  /** RA-Micro Verbindungsstatus prüfen */
  status: () => request("/wiedervorlage/status"),

  /**
   * Fällige Wiedervorlagen laden (Stellungnahme Gegner)
   * @param {boolean} nurHeute  nur exakt heute fällige
   * @param {string}  sb        Sachbearbeiter-Kürzel filtern
   */
  liste: ({ nurHeute = false, nurStellungnahme = true, sb = null, grund = null } = {}) => {
    const p = new URLSearchParams();
    if (nurHeute)        p.set("nur_heute", "true");
    if (!nurStellungnahme) p.set("alle_gruende", "true");
    if (sb)              p.set("sb", sb);
    if (grund)           p.set("grund", grund);
    const qs = p.toString();
    return request(`/wiedervorlage/${qs ? "?" + qs : ""}`);
  },

  /** Aktenzeichen für die bereits eine Sachstandsanfrage erstellt wurde */
  bereitsErstellt: () => request("/wiedervorlage/bereits-erstellt"),

  /**
   * Einzelne Sachstandsanfrage generieren und herunterladen
   * @param {string} guid  GUIDWiedervorlage
   * @param {string} az    Aktenzeichen (für Dateiname)
   */
  sachstandsanfrage: async (guid, az, adressNr = null) => {
    const body = adressNr != null ? JSON.stringify({ adress_nr: adressNr }) : undefined;
    const res = await fetch(`${API_BASE}/wiedervorlage/${guid}/sachstandsanfrage`, {
      method:  "POST",
      headers: {
        Authorization:  `Bearer ${tokenStore.getAccess()}`,
        ...(body ? { "Content-Type": "application/json" } : {}),
      },
      ...(body ? { body } : {}),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new ApiError(res.status, body.fehler || "Fehler beim Generieren");
    }
    const blob = await res.blob();
    const sicheresAz = az.replace(/\//g, "-").replace(/\\/g, "-").trim();
    const datum = new Date().toISOString().slice(0, 10);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${sicheresAz}_sachstandsanfrage_${datum}.docx`;
    a.style.display = 'none';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 10000);
  },

  /**
   * Batch-Sachstandsanfragen als ZIP herunterladen
   * @param {string[]} guids  Array von GUIDWiedervorlage
   */
  batchZip: async (guids) => {
    const res = await fetch(`${API_BASE}/wiedervorlage/batch-sachstandsanfrage`, {
      method:  "POST",
      headers: {
        Authorization:  `Bearer ${tokenStore.getAccess()}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ guids }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new ApiError(res.status, body.fehler || "Fehler beim Batch-Export");
    }
    const blob = await res.blob();
    const datum = new Date().toISOString().slice(0, 10);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `sachstandsanfragen_${datum}.zip`;
    a.style.display = 'none';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 10000);
  },

  /** Alle Beteiligten einer Akte (für Adressaten-Dropdown) */
  beteiligte: (guid, { grund = "", bezeichnung = "", referat = 0 } = {}) => {
    const p = new URLSearchParams();
    if (grund)       p.set("grund", grund);
    if (bezeichnung) p.set("bezeichnung", bezeichnung);
    if (referat)     p.set("referat", referat);
    const qs = p.toString();
    return request(`/wiedervorlage/${guid}/beteiligte${qs ? "?" + qs : ""}`);
  },

  /** Wiedervorlage-Statistik (WV-Gründe nach Häufigkeit) */
  statistik: () => request("/wiedervorlage/statistik"),
};


// ══════════════════════════════════════════════════════════════════════════════
// MODUL 9 – KÜRZUNGSARTEN & ABRECHNUNGSSCHREIBEN
// ══════════════════════════════════════════════════════════════════════════════

/** Kürzungsarten (Stammdaten) */
export const kuerzungsarten = {
  liste:    (nurAktive = false) =>
    request(`/kuerzungsarten${nurAktive ? "?nur_aktive=1" : ""}`),
  erstelle: (daten) =>
    request("/kuerzungsarten", { method: "POST", body: JSON.stringify(daten) }),
  update:   (id, daten) =>
    request(`/kuerzungsarten/${id}`, { method: "PUT", body: JSON.stringify(daten) }),
  toggleAktiv: (id, aktiv) =>
    request(`/kuerzungsarten/${id}/aktiv`, { method: "PATCH", body: JSON.stringify({ aktiv }) }),
};

/** Abrechnungsschreiben */
export const abrechnungen = {
  liste:     (akteId)        => request(`/akten/${akteId}/abrechnungen`),
  erstelle:  (akteId, daten) =>
    request(`/akten/${akteId}/abrechnungen`, { method: "POST", body: JSON.stringify(daten) }),
  loesche:   (akteId, abid)  =>
    request(`/akten/${akteId}/abrechnungen/${abid}`, { method: "DELETE" }),
  updatePos: (akteId, abid, pid, daten) =>
    request(`/akten/${akteId}/abrechnungen/${abid}/positionen/${pid}`,
      { method: "PATCH", body: JSON.stringify(daten) }),
  klagebetrag: (akteId)      => request(`/akten/${akteId}/abrechnungen/klagebetrag`),
};

/** Prüfberichte */
export const pruefberichte = {
  liste:    (akteId)        => request(`/akten/${akteId}/pruefberichte`),
  erstelle: (akteId, daten) =>
    request(`/akten/${akteId}/pruefberichte`, { method: "POST", body: JSON.stringify(daten) }),
};

/** PDF-Parser (Modul 9) – Upload eines Versicherungs-PDFs */
export const parsePdf = {
  /**
   * Lädt ein PDF hoch und gibt das strukturierte Parse-Ergebnis zurück.
   * Verwendet FormData (kein JSON-Body, da Datei-Upload).
   */
  parse: (akteId, datei) => {
    const form = new FormData();
    form.append("datei", datei);
    // request() setzt Content-Type automatisch für FormData weg (Browser übernimmt boundary)
    const token = tokenStore.getAccess() || "";
    return fetch(`${API_BASE}/akten/${akteId}/parse-pdf`, {
      method: "POST",
      headers: token ? { "Authorization": `Bearer ${token}` } : {},
      body: form,
    }).then(async r => {
      const data = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(data.fehler || `HTTP ${r.status}`);
      return data;
    });
  },

  /** Parst ein bereits vorhandenes PDF aus dem Dokumenten-Tab (kein Upload nötig). */
  parseVorhandenes: (akteId, dokId, typ) =>
    request(`/akten/${akteId}/dokumente/${dokId}/parsen${typ ? '?typ=' + typ : ''}`, { method: "POST" }),

  /**
   * Streaming-Parse via Server-Sent Events (PRD-30).
   * Ruft onEvent(data) für jeden SSE-Frame auf.
   * Gibt eine Funktion zurück, mit der der Stream abgebrochen werden kann.
   *
   * Event-Daten:
   *   { schritt: "ocr",    status: "laeuft" }
   *   { schritt: "ocr",    status: "fertig", zeichen: 2840 }
   *   { schritt: "parsen", status: "laeuft" }
   *   { schritt: "parsen", status: "fertig", klasse: "abrechnungsschreiben" }
   *   { schritt: "fertig", ergebnis: {...}, dokument_id: 123, dateiname: "..." }
   *   { schritt: "fehler", meldung: "..." }
   */
  parseStream: (akteId, dokId, onEvent) => {
    const token = tokenStore.getAccess() || "";
    const url = `${API_BASE}/akten/${akteId}/dokumente/${dokId}/parsen-stream`;
    const es = new EventSource(
      token ? `${url}?token=${encodeURIComponent(token)}` : url
    );
    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        onEvent(data);
        if (data.schritt === "fertig" || data.schritt === "fehler") es.close();
      } catch { /* ignorieren */ }
    };
    es.onerror = () => {
      onEvent({ schritt: "fehler", meldung: "Verbindung zum Server unterbrochen." });
      es.close();
    };
    return () => es.close();
  },
};

export const belege = {
  /** Alle Beleg-Zuordnungen einer Akte */
  liste: (akteId) => request(`/akten/${akteId}/belege`),
  /** Rechnungskandidaten für Auto-Zuordnung (PRD-23b) */
  kandidaten: (akteId, force) =>
    request(`/akten/${akteId}/belege/kandidaten${force ? '?force=true' : ''}`),
  /** Beleg einer Schadenposition zuordnen */
  zuordnen: (akteId, positionKey, dokumentId, betrag) =>
    request(`/akten/${akteId}/belege`, {
      method: "POST",
      body: JSON.stringify({ position_key: positionKey, dokument_id: dokumentId, betrag_aus_beleg: betrag }),
    }),
  /** Beleg-Zuordnung entfernen */
  entfernen: (akteId, belegId) =>
    request(`/akten/${akteId}/belege/${belegId}`, { method: "DELETE" }),
  /** Lokale Dokumente neu parsen (aktualisiert parse_json in DB) */
  neuParsen: (akteId) =>
    request(`/akten/${akteId}/belege/neu-parsen`, { method: "POST" }),
};

export const aktensuche = {
  /** Az (mit /) → Aktenzeichen-Suche; ohne / → Namenssuche */
  suchen: (az) =>
    request(`/aktensuche?az=${encodeURIComponent(az)}`),
  /** KFZ-Kennzeichen via WDM-Variable varM-KZ */
  nachKennzeichen: (kz) =>
    request(`/aktensuche?kz=${encodeURIComponent(kz)}`),
  /** Schadentag via WDM-Variable varU-TAG (Format DD.MM.YYYY oder YYYY-MM-DD) */
  nachSchadentag: (tag) =>
    request(`/aktensuche?tag=${encodeURIComponent(tag)}`),
  // Alias für Rückwärtskompatibilität
  nachAktenzeichen: (az) =>
    request(`/aktensuche?az=${encodeURIComponent(az)}`),
};

export const ramicroAkte = {
  /** Lädt alle RA-Micro Daten einer Akte (Stamm + Beteiligte + WDM). */
  laden: (az) =>
    request(`/ramicro/akte?az=${encodeURIComponent(az)}`),
};

export const ramicroListe = {
  /** Paginierte Aktenliste aus RA-Micro */
  laden: (seite=1, limit=50, sb=null) => {
    const qs = new URLSearchParams({ seite, limit, ...(sb ? { sb } : {}) });
    return request(`/ramicro/akte/liste?${qs}`);
  },
  /** Akte on-demand in lokaler SQLite anlegen */
  onDemand: (az) =>
    request('/ramicro/akte/on-demand', { method: 'POST', body: JSON.stringify({ az }) }),
};

export const ramicroWdm = {
  /** Alle WDM-Variablen einer Akte – zur Ermittlung der Variablennamen */
  discovery: (az) =>
    request(`/ramicro/akte/wdm-discovery?az=${encodeURIComponent(az)}`),
  /** Schadenpositionen aus konfiguriertem WDM-Mapping */
  schaden: (az) =>
    request(`/ramicro/akte/wdm-schaden?az=${encodeURIComponent(az)}`),
};

export const eakte = {
  /** E-Akte-Dokumente einer Akte auflisten */
  liste: (az, emails = false) =>
    request(`/akten/${az}/eakte${emails ? '?emails=true' : ''}`),
  /** E-Akte-PDF herunterladen (Phase 2) */
  download: async (az, nr, dateiname) => {
    const token = tokenStore.getAccess();
    const res = await fetch(`${API_BASE}/akten/${az}/eakte/${nr}/datei`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new ApiError(res.status, 'E-Akte Download fehlgeschlagen');
    const blob = await res.blob();
    _triggerDownload(blob, dateiname || `eakte_${nr}.pdf`);
  },
  /** E-Akte-PDF in Pipeline importieren (Phase 3a) */
  importieren: (az, nr) =>
    request(`/akten/${az}/eakte/${nr}/importieren`, { method: 'POST' }),
};

export const apiDistanz = {
  /** Extrahiert Verweisbetrieb-Daten aus PDF-Text */
  parsen: (text) => request('/distanz/parsen', {
    method: 'POST',
    body: JSON.stringify({ text }),
  }),
  /** Prüft echte Entfernung via ORS */
  prüfen: (mandantAdresse, werkstattAdresse, werkstattName, kmGenannt) => request('/distanz/prüfen', {
    method: 'POST',
    body: JSON.stringify({
      mandant_adresse:   mandantAdresse,
      werkstatt_adresse: werkstattAdresse,
      werkstatt_name:    werkstattName,
      km_genannt:        kmGenannt,
    }),
  }),
  /** Komplett: pb_id (Prüfbericht-ID) oder dok_id + Akte-ID → alles in einem */
  prüfenAusDokument: (akteId, dokId, pbId) => request('/distanz/prüfen-aus-dokument', {
    method: 'POST',
    body: JSON.stringify({ akte_id: akteId, dok_id: dokId || null, pb_id: pbId || null }),
  }),
};

export const apiFirmen = {
  vertreter:         (name) => request(`/firmen/vertreter?name=${encodeURIComponent(name)}`),
  vertreterSpeichern:(id, name, funk) => request('/firmen/vertreter/speichern', {
    method: 'POST',
    body: JSON.stringify({ beteiligter_id: id, vertreter_name: name, vertreter_funktion: funk }),
  }),
};

// ── Modul: Stellungnahme zum Abrechnungsschreiben ─────────────────────────────
export const apiStellungnahme = {
  /**
   * Lädt Kürzungspositionen mit Textbaustein-Vorschlägen für den Wizard.
   * @param {string} az  Aktenzeichen
   */
  vorschau: async (az) => {
    const token = tokenStore.getAccess();
    const res = await fetch(`${API_BASE}/akten/${encodeURIComponent(az)}/stellungnahme/vorschau`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) throw new Error(`Vorschau fehlgeschlagen: ${res.status}`);
    return res.json();
  },

  /**
   * Generiert die Stellungnahme als .docx und löst Download aus.
   * @param {string} az              Aktenzeichen
   * @param {number|null} abId       Optional: nur dieses Abrechnungsschreiben
   * @param {Object|null} custom_texte  Optional: {gruppe_key: text} Mapping aus Wizard
   */
  generieren: async (az, abId = null, custom_texte = null) => {
    const token = tokenStore.getAccess();
    const body = abId ? { abrechnungsschreiben_id: abId } : {};
    if (custom_texte !== null) body.custom_texte = custom_texte;
    const res = await fetch(`${API_BASE}/akten/${az}/stellungnahme/generieren`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      let msg = 'Stellungnahme konnte nicht generiert werden.';
      try { const d = await res.json(); msg = d.fehler || msg; } catch {}
      throw new ApiError(res.status, msg);
    }
    const blob = await res.blob();
    const cd   = res.headers.get('Content-Disposition') || '';
    const m    = cd.match(/filename="?([^"]+)"?/);
    const sicheresAz = az.replace(/\//g, '-');
    _triggerDownload(blob, m ? m[1] : `${sicheresAz}_stellungnahme.docx`);
  },

  texteHolen: async (az) => {
    const token = tokenStore.getAccess();
    const res = await fetch(`${API_BASE}/akten/${encodeURIComponent(az)}/stellungnahme/texte`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) return {};
    return res.json();
  },

  texteSpeichern: async (az, texte) => {
    const token = tokenStore.getAccess();
    const res = await fetch(`${API_BASE}/akten/${encodeURIComponent(az)}/stellungnahme/texte`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ texte }),
    });
    if (!res.ok) {
      let msg = 'Speichern fehlgeschlagen.';
      try { const d = await res.json(); msg = d.fehler || msg; } catch {}
      throw new Error(msg);
    }
    return res.json();
  },
};

// ── PRD-01: To-Do-System ──────────────────────────────────────────────────────
export const apiTodos = {
  liste:    (az)           => request(`/akten/${az}/todos`),
  erstelle: (az, daten)    => request(`/akten/${az}/todos`,
                               { method: 'POST', body: JSON.stringify(daten) }),
  update:   (az, id, daten) => request(`/akten/${az}/todos/${id}`,
                               { method: 'PATCH', body: JSON.stringify(daten) }),
  loesche:  (az, id)       => request(`/akten/${az}/todos/${id}`,
                               { method: 'DELETE' }),
};

export const apiDashboard = {
  actionItems: () => request('/dashboard/action-items'),

  onboardingOffen: () =>
    request("/dashboard/onboarding-offen"),

  nachrichtenNeu: () =>
    request("/dashboard/nachrichten-neu"),

  ramicroFristen: () =>
    request("/dashboard/ramicro-fristen"),
};

// ── Einstellungen ─────────────────────────────────────────────────────────────
export const apiEinstellungen = {
  staFristen:          ()      => request('/einstellungen/sta-fristen'),
  staFristenSpeichern: (daten) => request('/einstellungen/sta-fristen', {
    method: 'PUT',
    body: JSON.stringify(daten),
  }),
  trainingStats:          ()      => request('/einstellungen/klassifikation-training'),
  kiEinstellungen:        ()      => request('/einstellungen/ki'),
  kiEinstellungenSpeichern: (d)  => request('/einstellungen/ki', {
    method: 'PUT', body: JSON.stringify(d),
  }),
  lgGrenzwert:            ()      => request('/einstellungen/lg-grenzwert'),
  lgGrenzwertSpeichern:   (wert)  => request('/einstellungen/lg-grenzwert', {
    method: 'PUT', body: JSON.stringify({ lg_grenzwert: wert }),
  }),
  llmStatus:      ()           => request('/einstellungen/llm-status'),
  llmAktivieren:  (aktiviert)  => request('/einstellungen/llm-aktivieren', {
    method: 'PUT', body: JSON.stringify({ aktiviert }),
  }),
  llmTest:        (prompt)     => request('/einstellungen/llm-test', {
    method: 'POST', body: JSON.stringify({ prompt }),
  }),
  llmModellSetzen: (modell)   => request('/einstellungen/llm-modell', {
    method: 'PUT', body: JSON.stringify({ modell }),
  }),
};

// ── PRD-25d: Intelligente Sachstandsanfrage ───────────────────────────────────
export const apiSta = {
  kontext: (az, stufe) => {
    const q = stufe != null ? `?stufe=${stufe}` : "";
    return request(`/akten/${az}/sta/kontext${q}`);
  },

  generieren: async (az, stufe, brieftext) => {
    const token = tokenStore.getAccess();
    const res = await fetch(`${API_BASE}/akten/${az}/sta/generieren`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ stufe, brieftext }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new ApiError(res.status, err.fehler || "STA-Generierung fehlgeschlagen");
    }
    const blob = await res.blob();
    const cd   = res.headers.get("Content-Disposition") || "";
    const m    = cd.match(/filename="?([^"]+)"?/);
    const azSafe = az.replace(/\//g, "-");
    _triggerDownload(blob, m ? m[1] : `${azSafe}_sachstandsanfrage_stufe${stufe}.docx`);
    return { ok: true };
  },
};

// ─────────────────────────────────────────────────────────────
// PORTAL (PORTAL-A1)
// ─────────────────────────────────────────────────────────────
export const portalAkteAktivieren = (az, aktiv) =>
  request(`/portal/akten/${encodeURIComponent(az)}/aktivieren`, {
    method: "POST",
    body: JSON.stringify({ aktiv }),
  });

export const portalEinladen = (az, data) =>
  request(`/portal/akten/${encodeURIComponent(az)}/einladen`, {
    method: "POST",
    body: JSON.stringify(data),
  });

export const portalSyncStatus = () =>
  request("/portal/status");

export const setzePortalSichtbar = (az, dokId, sichtbar) =>
  request(`/akten/${encodeURIComponent(az)}/dokumente/${dokId}/portal-sichtbar`, {
    method: "PATCH",
    body: JSON.stringify({ portal_sichtbar: sichtbar }),
  });

// ─────────────────────────────────────────────────────────────
// GEBÜHRENASSISTENT (PRD-28)
// ─────────────────────────────────────────────────────────────
export const apiGebuehren = {
  laden:      (az)        => request(`/akten/${az}/gebuehren`),
  analysieren:(az, body)  => request(`/akten/${az}/gebuehren/analysieren`, {
                               method: 'POST', body: JSON.stringify(body || {}) }),
  speichern:  (az, body)  => request(`/akten/${az}/gebuehren`, {
                               method: 'PUT', body: JSON.stringify(body) }),
  word:       (az)        => request(`/akten/${az}/gebuehren/word`, { method: 'POST' }),
};

// ─────────────────────────────────────────────────────────────
// SV-PORTAL
// ─────────────────────────────────────────────────────────────
export const apiSvPortal = {
  liste: () =>
    request('/einstellungen/sv-portal'),

  vorschau: (adressnr) =>
    request(`/einstellungen/sv-portal/vorschau/${adressnr}`),

  anlegen: (adressnr) =>
    request('/einstellungen/sv-portal', {
      method: 'POST',
      body: JSON.stringify({ adressnr }),
    }),

  loeschen: (adressnr) =>
    request(`/einstellungen/sv-portal/${adressnr}`, { method: 'DELETE' }),

  toggleAktiv: (adressnr, aktiv) =>
    request(`/einstellungen/sv-portal/${adressnr}`, {
      method: 'PATCH',
      body: JSON.stringify({ portal_aktiv: aktiv ? 1 : 0 }),
    }),

  einladungSenden: (adressnr) =>
    request(`/einstellungen/sv-portal/${adressnr}/einladung`, { method: 'POST' }),

  akten: (adressnr) =>
    request(`/einstellungen/sv-portal/${adressnr}/akten`),

  togglePortalAktiv: (akte_az, aktiv) =>
    request(
      `/einstellungen/sv-portal/akten/${encodeURIComponent(akte_az)}/portal_aktiv`,
      { method: 'PATCH', body: JSON.stringify({ portal_aktiv: aktiv ? 1 : 0 }) }
    ),
};
