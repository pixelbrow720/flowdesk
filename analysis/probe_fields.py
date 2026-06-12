"""Zero-hallucination probe: dump ALL fields on GLBX trade + statistics records.
Looks for any open/close, customer/firm, or order-type flag we might be missing.
Wrapper-safe output (no colons/datetime reprs)."""
import databento as db

out = []

# --- TRADES: full field inventory ---
tf = "data/raw/trades/trades_20260602_20260611.dbn.zst"
store = db.DBNStore.from_file(tf)
n = 0
for r in store:
    out.append("=== TRADE record type=" + type(r).__name__ + " ===")
    attrs = [a for a in dir(r) if not a.startswith("_") and not callable(getattr(r, a))]
    for a in attrs:
        try:
            v = getattr(r, a)
            out.append("  trades." + a + " = " + repr(v))
        except Exception as e:
            out.append("  trades." + a + " ERR " + type(e).__name__)
    n += 1
    if n >= 2:
        break

# --- STATISTICS: distinct stat_type codes + their meaning hints ---
sf = "data/raw/statistics/statistics_20260602_20260611.dbn.zst"
store = db.DBNStore.from_file(sf)
seen_types = {}
stat_attrs = None
cnt = 0
for r in store:
    if stat_attrs is None:
        stat_attrs = [a for a in dir(r) if not a.startswith("_") and not callable(getattr(r, a))]
    st = int(getattr(r, "stat_type", -1))
    seen_types[st] = seen_types.get(st, 0) + 1
    cnt += 1
    if cnt >= 200000:
        break
out.append("")
out.append("=== STATISTICS fields ===")
out.append("  " + ",".join(stat_attrs or []))
out.append("=== STATISTICS stat_type codes seen (code -> count) in first 200k ===")
for k in sorted(seen_types):
    out.append("  stat_type " + str(k) + " -> " + str(seen_types[k]))

# --- DEFINITION: is there a user-defined / customer field? ---
df = "data/raw/definition/definition_20260602_20260611.dbn.zst"
store = db.DBNStore.from_file(df)
for r in store:
    da = [a for a in dir(r) if not a.startswith("_") and not callable(getattr(r, a))]
    out.append("")
    out.append("=== DEFINITION fields ===")
    out.append("  " + ",".join(da))
    break

open("analysis/probe_fields.txt", "w", encoding="utf-8").write("\n".join(out) + "\n")
print("WROTE", len(out), "lines")
