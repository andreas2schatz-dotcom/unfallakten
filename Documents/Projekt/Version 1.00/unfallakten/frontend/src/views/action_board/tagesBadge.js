export function tagesBadge(tage) {
  if (tage === null || tage === undefined) return null;
  if (tage <= 0) {
    const label = tage === 0 ? "HEUTE" : `${tage}T`;
    return { label, color: "#ffffff", bg: "#dc2626" };
  }
  return { label: `+${tage}T`, color: "#9ca3af", bg: "#374151" };
}
