import { Nav } from "@/components/layout/nav";
import { Hero } from "@/components/sections/hero";
import { Problem } from "@/components/sections/problem";
import { System } from "@/components/sections/system";
import { Lenses } from "@/components/sections/lenses";
import { Flow } from "@/components/sections/flow";
import { Honest } from "@/components/sections/honest";
import { Access } from "@/components/sections/access";
import { Footer } from "@/components/sections/footer";

/**
 * Landing — narrative arc:
 *   Nav → Hero (hook) → Problem (agitate) → System (reveal) →
 *   Lenses (depth) → Flow (architecture) → Honest (trust) →
 *   Access (single CTA) → Footer
 *
 * Per user direction: NO buttons in hero / nav / cards.
 * The ONLY Login-with-Discord CTA on the entire page lives in <Access />.
 */
export default function Page() {
  return (
    <>
      <Nav />
      <main>
        <Hero />
        <Problem />
        <System />
        <Lenses />
        <Flow />
        <Honest />
        <Access />
      </main>
      <Footer />
    </>
  );
}
