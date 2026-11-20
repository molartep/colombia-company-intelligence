// Media scale of the implemented design system; the application's CSS is unchanged.
export const theme = {
  canvas: "#f7f8f7",
  surface: "#ffffff",
  subtle: "#f3f6f5",
  selected: "#edf4ef",
  ink: "#17333c",
  muted: "#52665f",
  green: "#285f4b",
  action: "#183e40",
  border: "#dce3df",
  focus: "#167c72",
  black: "#000000",
  chart: "#2f6b59",
  font: "'Avenir Next', 'Segoe UI', sans-serif",
};
export const money = (v: string) => {
  if (!/^-?\d+(\.\d+)?$/.test(v)) throw new Error("Invalid decimal amount");
  const [whole, fraction] = v.split(".");
  return (
    new Intl.NumberFormat("es-CO", { maximumFractionDigits: 0 }).format(
      BigInt(whole),
    ) + (fraction === undefined ? "" : "," + fraction)
  );
};
export const dt = (v: string) =>
  new Intl.DateTimeFormat("es-CO", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(
    new Date(
      v.length === 8
        ? `${v.slice(0, 4)}-${v.slice(4, 6)}-${v.slice(6, 8)}T12:00:00Z`
        : `${v}T12:00:00Z`,
    ),
  );
