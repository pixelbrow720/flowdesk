/**
 * WallsList — top-3 gamma-dollar walls untuk satu side (call atau put).
 * Bar lebar = relative gamma-dollar; angka strike + $B di kanan.
 *
 * Per LOCKED CONTRACT (AGENTS.md §5): walls = gamma-dollar (gamma·OI per side),
 * static, Top-3.
 */

type Wall = { strike: number; gammaDollar: number };
type Props = {
  rows: Wall[];
  side: "call" | "put";
};

export function WallsList({ rows, side }: Props) {
  const max = Math.max(...rows.map((r) => r.gammaDollar), 1);
  const tone =
    side === "call"
      ? { bar: "bg-bone-1/40", text: "text-bone-0" }
      : { bar: "bg-brick/55", text: "text-brick-glow" };

  return (
    <ul className="flex flex-col gap-2.5">
      {rows.map((r, i) => {
        const pct = (r.gammaDollar / max) * 100;
        return (
          <li key={r.strike} className="flex items-center gap-3">
            <span className="font-mono text-[10px] tabular-nums text-bone-3 w-3">
              {i + 1}
            </span>
            <span className={`font-mono text-[13px] tabular-nums ${tone.text} w-14`}>
              {r.strike.toFixed(0)}
            </span>
            <div className="flex-1 h-1.5 bg-[color:var(--hairline)] overflow-hidden">
              <div
                className={`h-full ${tone.bar}`}
                style={{ width: `${pct}%` }}
              />
            </div>
            <span className="font-mono text-[10px] tabular-nums text-bone-2 w-12 text-right">
              ${(r.gammaDollar / 1e9).toFixed(1)}B
            </span>
          </li>
        );
      })}
    </ul>
  );
}

export default WallsList;
