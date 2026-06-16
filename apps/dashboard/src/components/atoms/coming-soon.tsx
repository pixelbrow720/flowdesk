/**
 * ComingSoon — placeholder card for lenses not yet built.
 * Used by /flux, /arc, /settings sebelum implementasi penuh.
 */
export function ComingSoon({ title, hint }: { title: string; hint: string }) {
  return (
    <div className="grid min-h-[calc(100vh-12rem)] place-items-center px-6">
      <div className="text-center max-w-md">
        <p className="font-mono text-[11px] uppercase tracking-[0.22em] text-bone-3 mb-4">
          Lens
        </p>
        <h1 className="font-display text-display-2 text-bone-0 leading-none mb-6">
          {title}
        </h1>
        <p className="font-mono text-[12px] uppercase tracking-[0.18em] text-bone-2 mb-10">
          {hint}
        </p>
        <div className="inline-flex items-center gap-3 px-4 py-2 border border-[color:var(--hairline)] font-mono text-[10px] uppercase tracking-[0.22em] text-bone-3">
          <span className="h-1.5 w-1.5 rounded-full bg-brick animate-pulse" />
          Coming soon
        </div>
      </div>
    </div>
  );
}

export default ComingSoon;
