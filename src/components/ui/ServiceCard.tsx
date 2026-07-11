import Link from "next/link";
import SceneCanvas from "@/components/three/SceneCanvas";
import PrototypeModel from "@/components/three/PrototypeModel";
import type { ServiceSummary } from "@/types";

export default function ServiceCard({ service }: { service: ServiceSummary }) {
  return (
    <Link
      href={`/services/${service.slug}`}
      className="gk-card group relative flex flex-col overflow-hidden p-5 transition-colors duration-200"
    >
      <div className="relative mb-4 h-28 w-full overflow-hidden bg-black-graphite">
        <SceneCanvas camera={{ position: [0, 0, 5.4], fov: 40 }} posterLabel={service.title} postFX={false}>
          <PrototypeModel variant={service.model} scale={0.62} />
        </SceneCanvas>
      </div>
      <span className="font-mono text-[11px] uppercase tracking-[0.14em] text-orange-primary">{service.title}</span>
      <p className="mt-2 text-xs leading-relaxed text-muted">{service.description}</p>
      <span
        className="mt-4 inline-flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-[0.14em] text-warmwhite/70 transition-colors group-hover:text-orange-bright"
        aria-hidden="true"
      >
        Explore <span className="transition-transform group-hover:translate-x-1">→</span>
      </span>
    </Link>
  );
}
