import { redirect } from "next/navigation";

// Flux is no longer a standalone lens — the HIRO cumulative-flow pane now lives
// directly beneath the Fog price chart (shared time axis), so divergence reads
// at a glance. Old /flux links redirect to /fog.
export default function FluxPage() {
  redirect("/fog");
}
