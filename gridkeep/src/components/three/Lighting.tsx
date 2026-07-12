"use client";

import { PALETTE } from "./materials";

type LightingProps = {
  keyPosition?: [number, number, number];
  rimPosition?: [number, number, number];
  ambient?: number;
};

/** Focused orange task lighting + soft warm rim, low ambient. No blurry fog fills. */
export default function Lighting({
  keyPosition = [4, 5, 4],
  rimPosition = [-5, 2, -4],
  ambient = 0.12,
}: LightingProps) {
  return (
    <>
      <ambientLight intensity={ambient} color={PALETTE.grey} />
      <spotLight
        position={keyPosition}
        angle={0.42}
        penumbra={0.55}
        intensity={26}
        color={PALETTE.orangeBright}
        distance={20}
        decay={2}
        castShadow
        shadow-mapSize={[1024, 1024]}
        shadow-bias={-0.0006}
      />
      <spotLight
        position={rimPosition}
        angle={0.6}
        penumbra={0.8}
        intensity={9}
        color={"#ffb37a"}
        distance={18}
        decay={2}
      />
      <pointLight position={[0, -2, 3]} intensity={2.4} color={PALETTE.orange} distance={8} decay={2} />
      <directionalLight position={[0, 6, -6]} intensity={0.35} color={"#3a3d3f"} />
    </>
  );
}
