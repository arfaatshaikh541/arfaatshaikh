import { useMemo } from "react";

export interface OrbitDatum {
  radius: number;
  speed: number;
  phase: number;
  y: number;
  scale: number;
}

export function useOrbitingInstances(count: number, radiusRange: [number, number] = [2.4, 4.2]) {
  return useMemo<OrbitDatum[]>(() => {
    const items: OrbitDatum[] = [];
    for (let i = 0; i < count; i += 1) {
      items.push({
        radius: radiusRange[0] + Math.random() * (radiusRange[1] - radiusRange[0]),
        speed: 0.08 + Math.random() * 0.18,
        phase: Math.random() * Math.PI * 2,
        y: (Math.random() - 0.5) * 2.4,
        scale: 0.4 + Math.random() * 0.8,
      });
    }
    return items;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [count]);
}
