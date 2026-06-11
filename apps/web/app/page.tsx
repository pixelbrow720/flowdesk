// Skeleton landing surface. No business logic — establishes the dark,
// data-art aesthetic and the FlowDesk wordmark in Space Grotesk.
export default function HomePage() {
  return (
    <main className="flex min-h-screen flex-col justify-between px-6 py-8 md:px-10 md:py-10">
      <header className="flex items-baseline justify-between border-b border-white/10 pb-6">
        <span className="font-mono text-[0.7rem] uppercase tracking-[0.4em] text-white/40">
          0DTE · GEX / DEX
        </span>
        <span className="font-mono text-[0.7rem] uppercase tracking-[0.4em] text-white/40">
          /ES · /NQ
        </span>
      </header>

      <section className="flex flex-1 flex-col justify-center">
        <h1 className="font-display text-[20vw] font-bold leading-[0.82] tracking-tight text-white md:text-[11rem]">
          Flow<span className="text-turquoise">Desk</span>
        </h1>
        <p className="mt-8 max-w-xl font-display text-base leading-relaxed text-white/50">
          Real-time dealer gamma &amp; delta exposure terminal. VOL-based,
          0DTE-focused, built for /ES and /NQ futures.
        </p>
      </section>

      <footer className="flex items-center justify-between border-t border-white/10 pt-6 font-mono text-[0.7rem] text-white/40">
        <span className="tabular-nums">v0.1.0 · skeleton</span>
        <span className="tabular-nums">RTH 09:30–16:00 ET</span>
      </footer>
    </main>
  );
}
