import { redirect } from "next/navigation";

/**
 * Dashboard root — redirect to Fog (the default lens).
 * Order: Fog (positioning) → Flux (orderflow) → Arc (surface) → Settings.
 */
export default function Page() {
  redirect("/fog");
}
