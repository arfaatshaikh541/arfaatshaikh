import Link from "next/link";
import SceneCanvas from "@/components/three/SceneCanvas";
import PrototypeModel from "@/components/three/PrototypeModel";
import type { PrototypeChapter } from "@/types";

export default function PrototypeCard({ chapter }: { chapter: PrototypeChapter }) {
  return (
    <Link
      href={`/gridkeep-system#${chapter.slug}`}
      className="prototype-card gk-card group relative flex min-h-[380px] flex-col justify-between overflow-hidden p-5"
    >
      <div className="absolute inset-0 -z-0">
        <SceneCanvas camera={{ position: [0, 0, 6], fov: 42 }} posterLabel={chapter.title} postFX={false}>
          <PrototypeModel variant={chapter.model} scale={0.85} />
        </SceneCanvas>
      </div>
      <div className="relative z-10 flex items-start justify-between">
        <span className="font-display text-4xl text-warmwhite/25 transition-colors group-hover:text-orange-primary/40">
          {chapter.index}
        </span>
      </div>
      <div className="relative z-10">
        <h3 className="font-display text-lg uppercase tracking-wide text-warmwhite">{chapter.title}</h3>
        <p className="mt-2 text-xs leading-relaxed text-muted">{chapter.description}</p>
        <span className="mt-4 inline-flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-[0.14em] text-orange-primary transition-colors group-hover:text-orange-bright">
          Explore <span className="transition-transform group-hover:translate-x-1">→</span>
        </span>
      </div>
    </Link>
  );
}
