import type { ModelVariant } from "@/types";
import SceneCanvas from "@/components/three/SceneCanvas";
import PrototypeModel from "@/components/three/PrototypeModel";

interface PageIntroProps {
  eyebrow: string;
  title: React.ReactNode;
  description: string;
  model?: ModelVariant;
  children?: React.ReactNode;
}

export default function PageIntro({ eyebrow, title, description, model, children }: PageIntroProps) {
  return (
    <section className="relative overflow-hidden border-b border-line bg-black pb-16 pt-14 md:pb-24 md:pt-20">
      <div className="pointer-events-none absolute inset-0 bg-grid-lines bg-[size:52px_52px] opacity-[0.25]" aria-hidden="true" />
      <div className="relative mx-auto grid max-w-[1440px] grid-cols-1 items-center gap-10 px-6 md:grid-cols-[1.2fr_0.8fr] md:px-10">
        <div>
          <p className="gk-eyebrow mb-5">{eyebrow}</p>
          <h1 className="gk-heading text-4xl text-warmwhite sm:text-5xl md:text-6xl">{title}</h1>
          <p className="mt-6 max-w-xl text-sm leading-relaxed text-muted md:text-base">{description}</p>
          {children}
        </div>
        {model && (
          <div className="relative mx-auto h-[280px] w-full max-w-[420px] md:h-[360px]">
            <SceneCanvas eager camera={{ position: [0, 0, 6.5], fov: 40 }} posterLabel={typeof title === "string" ? title : eyebrow}>
              <PrototypeModel variant={model} scale={0.95} />
            </SceneCanvas>
          </div>
        )}
      </div>
    </section>
  );
}
