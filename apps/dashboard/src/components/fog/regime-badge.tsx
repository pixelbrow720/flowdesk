/**
 * RegimeBadge — long-gamma vs short-gamma indicator.
 * Long-gamma = dealer hedges WITH momentum (suppresses vol).
 * Short-gamma = dealer hedges AGAINST (amplifies vol). Brick highlight.
 */

type Props = {
  regime: "long-gamma" | "short-gamma";
};

export function RegimeBadge({ regime }: Props) {
  const isShort = regime === "short-gamma";
  return (
    <span
      className={[
        "inline-flex items-center gap-2 px-2.5 py-1.5 font-mono text-[11px] uppercase tracking-[0.18em] border",
        isShort
          ? "border-brick/50 bg-brick/15 text-brick-glow"
          : "border-[color:var(--hairline-strong)] text-bone-1",
      ].join(" ")}
    >
      <span
        className={[
          "h-1.5 w-1.5 rounded-full",
          isShort ? "bg-brick-glow animate-pulse" : "bg-bone-1",
        ].join(" ")}
      />
      {isShort ? "short γ" : "long γ"}
    </span>
  );
}

export default RegimeBadge;
