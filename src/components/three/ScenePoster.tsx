import type { SceneId } from "@/types";
import { cn } from "@/lib/utils";

const POSTER_STYLES: Record<SceneId, string> = {
  core: "radial-gradient(circle at 50% 50%, rgba(255,90,0,0.28), rgba(5,5,5,0.9) 55%, #000 100%)",
  neural: "radial-gradient(circle at 40% 30%, rgba(255,122,26,0.22), #050505 60%, #000 100%)",
  assembly: "linear-gradient(115deg, rgba(200,68,0,0.2), #0b0b0b 45%, #000 100%)",
  architecture: "linear-gradient(160deg, rgba(255,90,0,0.16), #111 50%, #000 100%)",
  vault: "radial-gradient(circle at 50% 45%, rgba(255,90,0,0.25), #0b0b0b 55%, #000 100%)",
  orbit: "radial-gradient(circle at 60% 40%, rgba(255,122,26,0.2), #050505 60%, #000 100%)",
  weblab: "linear-gradient(135deg, rgba(255,90,0,0.18), #111 50%, #000 100%)",
  network: "radial-gradient(circle at 45% 55%, rgba(200,68,0,0.22), #0b0b0b 55%, #000 100%)",
  command: "radial-gradient(circle at 50% 50%, rgba(255,90,0,0.32), #050505 55%, #000 100%)",
  portal: "radial-gradient(circle at 50% 50%, rgba(255,90,0,0.4), #000 65%)",
};

export function ScenePoster({ scene, className }: { scene: SceneId; className?: string }) {
  return (
    <div
      role="presentation"
      aria-hidden="true"
      className={cn("absolute inset-0", className)}
      style={{ background: POSTER_STYLES[scene] }}
    />
  );
}
