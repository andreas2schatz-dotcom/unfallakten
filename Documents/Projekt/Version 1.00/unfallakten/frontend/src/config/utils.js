function fmtEuro(v) {
  if (v==null) return "–";
  return new Intl.NumberFormat("de-DE",{style:"currency",currency:"EUR",minimumFractionDigits:2,maximumFractionDigits:2}).format(v);
}

function fmtSize(bytes) {
  if (!bytes) return "";
  return bytes < 1048576 ? `${Math.round(bytes/1024)} KB` : `${(bytes/1048576).toFixed(1)} MB`;
}


export { fmtEuro, fmtSize };
