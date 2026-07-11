import SceneCanvas from "@/components/three/SceneCanvas";
import PrototypeModel from "@/components/three/PrototypeModel";
import SectionLabel from "@/components/ui/SectionLabel";
import { LinkButton } from "@/components/ui/Button";
import { ecosystemNodes } from "@/data/ecosystem";

export default function Ecosystem() {
  return (
    <section className="relative border-t border-line bg-black-near py-20 md:py-28" aria-labelledby="ecosystem-heading">
      <div className="mx-auto grid max-w-[1440px] grid-cols-1 items-center gap-14 px-6 md:grid-cols-2 md:px-10">
        <div>
          <SectionLabel>The GRIDKEEP System</SectionLabel>
          <h2 id="ecosystem-heading" className="gk-heading mt-5 text-4xl text-warmwhite sm:text-5xl">
            EVERY SYSTEM.
            <br />
            <span className="text-orange-primary">ONE ECOSYSTEM.</span>
          </h2>
          <p className="mt-5 max-w-md text-sm leading-relaxed text-muted md:text-base">
            Connected systems. Unified data. Intelligent operations. Built to scale with your business.
          </p>
          <LinkButton href="/gridkeep-system" variant="secondary" className="mt-8">
            Explore The Ecosystem →
          </LinkButton>
        </div>

        <div className="relative mx-auto aspect-square w-full max-w-[520px]">
          <SceneCanvas camera={{ position: [0, 0, 8], fov: 40 }} posterLabel="GRIDKEEP ecosystem diagram">
            <PrototypeModel variant="ecosystem" scale={0.85} float={false} />
          </SceneCanvas>
          <ul className="pointer-events-none absolute inset-0" aria-hidden="true">
            {ecosystemNodes.map((node) => {
              const rad = (node.angle * Math.PI) / 180;
              const x = 50 + Math.cos(rad) * 42;
              const y = 50 + Math.sin(rad) * 42;
              return (
                <li
                  key={node.id}
                  className="absolute -translate-x-1/2 -translate-y-1/2 border border-line bg-black/80 px-2.5 py-1 font-mono text-[9px] uppercase tracking-[0.1em] text-warmwhite/85"
                  style={{ left: `${x}%`, top: `${y}%` }}
                >
                  {node.label}
                </li>
              );
            })}
          </ul>
        </div>
      </div>

      <nav aria-label="GRIDKEEP ecosystem components" className="sr-only">
        <ul>
          {ecosystemNodes.map((node) => (
            <li key={node.id}>{node.label}</li>
          ))}
        </ul>
      </nav>
    </section>
  );
}
