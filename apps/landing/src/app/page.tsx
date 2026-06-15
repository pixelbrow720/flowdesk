import { Nav } from "@/components/layout/nav";
import { Hero } from "@/components/sections/hero";
import { Manifesto } from "@/components/sections/manifesto";
import { Lenses } from "@/components/sections/lenses";
import { System } from "@/components/sections/system";
import { Marquee } from "@/components/sections/marquee";
import { Workflows } from "@/components/sections/workflows";
import { Exhibit } from "@/components/sections/exhibit";
import { Pricing } from "@/components/sections/pricing";
import { CTA, Footer } from "@/components/sections/cta";

export default function Page() {
  return (
    <>
      <Nav />
      <main>
        <Hero />
        <Manifesto />
        <Lenses />
        <System />
        <Marquee />
        <Workflows />
        <Exhibit />
        <Pricing />
        <CTA />
      </main>
      <Footer />
    </>
  );
}
