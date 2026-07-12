"use client";

import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { Sparkles } from "@react-three/drei";
import { gunmetal, brushedSteel, darkAnodized, orangeEmissive, orangeGlass } from "../materials";
import { BoltField, circleOfBolts } from "../Instanced";
import { CableRun, StatusLight } from "../Parts";
import type { ProgressRef } from "@/hooks/useScrollProgress";

const SHUTTER_COUNT = 10;

export default function HeroReactor({ progressRef }: { progressRef?: ProgressRef }) {
  const outerRing = useRef<THREE.Group>(null);
  const innerRing = useRef<THREE.Group>(null);
  const coreGroup = useRef<THREE.Group>(null);
  const coreMesh = useRef<THREE.Mesh>(null);
  const hingeRefs = useRef<Array<THREE.Group | null>>([]);
  const smokeA = useRef<THREE.Mesh>(null);
  const smokeB = useRef<THREE.Mesh>(null);

  const outerMat = useMemo(() => gunmetal(), []);
  const innerMat = useMemo(() => brushedSteel(), []);
  const shutterMat = useMemo(() => darkAnodized(), []);
  const coreMat = useMemo(() => orangeGlass(2.2), []);
  const coreInnerMat = useMemo(() => orangeEmissive(3.4), []);
  const smokeMat = useMemo(
    () => new THREE.MeshBasicMaterial({ color: "#3a3a38", transparent: true, opacity: 0.06 }),
    []
  );

  const boltPositionsOuter = useMemo(() => circleOfBolts(28, 1.62), []);
  const boltPositionsInner = useMemo(() => circleOfBolts(20, 0.62), []);

  const shutterAngles = useMemo(
    () => Array.from({ length: SHUTTER_COUNT }, (_, i) => (i / SHUTTER_COUNT) * Math.PI * 2),
    []
  );

  useFrame((state, delta) => {
    const progress = progressRef?.current.value ?? 0.35;

    if (outerRing.current) outerRing.current.rotation.z += delta * 0.05;
    if (innerRing.current) innerRing.current.rotation.z -= delta * 0.09;
    if (coreGroup.current) coreGroup.current.rotation.z += delta * 0.14;

    const targetHinge = -0.08 - progress * 1.25;
    hingeRefs.current.forEach((hinge, i) => {
      if (!hinge) return;
      const stagger = i * 0.015;
      hinge.rotation.x = THREE.MathUtils.lerp(hinge.rotation.x, targetHinge - stagger, 0.08);
    });

    if (coreMesh.current) {
      const s = 0.72 + progress * 0.5;
      coreMesh.current.scale.setScalar(THREE.MathUtils.lerp(coreMesh.current.scale.x, s, 0.06));
    }
    coreInnerMat.emissiveIntensity = 2.2 + progress * 3.4 + Math.sin(state.clock.elapsedTime * 2.2) * 0.4;
    coreMat.emissiveIntensity = 1.4 + progress * 2.4;

    const t = state.clock.elapsedTime;
    if (smokeA.current) {
      const phaseA = (t * 0.06) % 1.4;
      smokeA.current.position.y = -1.1 + phaseA;
      (smokeA.current.material as THREE.MeshBasicMaterial).opacity = 0.05 * (1 - phaseA / 1.4);
    }
    if (smokeB.current) {
      const phaseB = (t * 0.05 + 0.6) % 1.4;
      smokeB.current.position.y = -1.15 + phaseB;
      (smokeB.current.material as THREE.MeshBasicMaterial).opacity = 0.045 * (1 - phaseB / 1.4);
    }
  });

  return (
    <group>
      {/* rear support housing */}
      <mesh position={[0, 0, -0.62]} material={outerMat} castShadow receiveShadow>
        <cylinderGeometry args={[1.28, 1.42, 0.34, 24]} />
      </mesh>
      <mesh position={[0, 0, -0.5]} material={shutterMat} receiveShadow>
        <cylinderGeometry args={[0.9, 0.9, 0.06, 32]} />
      </mesh>

      {/* structural struts to rear plate */}
      {[0, 1, 2, 3].map((i) => {
        const a = (i / 4) * Math.PI * 2 + Math.PI / 4;
        return (
          <mesh
            key={i}
            position={[Math.cos(a) * 1.1, Math.sin(a) * 1.1, -0.4]}
            rotation={[Math.PI / 2, 0, a]}
            material={brushedSteel()}
            castShadow
          >
            <cylinderGeometry args={[0.035, 0.035, 0.5, 8]} />
          </mesh>
        );
      })}

      {/* maintenance panels on rear housing */}
      {[-1, 1].map((side) => (
        <group key={side} position={[side * 0.55, -0.85, -0.6]} rotation={[0, 0, side * 0.06]}>
          <mesh material={shutterMat} castShadow>
            <boxGeometry args={[0.42, 0.28, 0.05]} />
          </mesh>
          <mesh position={[0.14, 0, 0.035]} rotation={[0, 0, Math.PI / 2]} material={brushedSteel()}>
            <cylinderGeometry args={[0.014, 0.014, 0.06, 8]} />
          </mesh>
        </group>
      ))}

      {/* outer structural ring */}
      <group ref={outerRing}>
        <mesh material={outerMat} castShadow receiveShadow>
          <torusGeometry args={[1.5, 0.16, 16, 64]} />
        </mesh>
        <BoltField positions={boltPositionsOuter} rotation={[Math.PI / 2, 0, 0]} radius={0.024} length={0.05} />
        {/* sensor modules on outer ring */}
        {[0, 0.33, 0.66].map((f, i) => {
          const a = f * Math.PI * 2 + 0.4;
          return (
            <group key={i} position={[Math.cos(a) * 1.5, Math.sin(a) * 1.5, 0.14]}>
              <mesh material={shutterMat} castShadow>
                <boxGeometry args={[0.12, 0.12, 0.08]} />
              </mesh>
              <mesh position={[0, 0, 0.05]}>
                <sphereGeometry args={[0.03, 12, 12]} />
                <meshPhysicalMaterial color="#050505" roughness={0.05} transmission={0.7} thickness={0.2} />
              </mesh>
            </group>
          );
        })}
      </group>

      {/* mid ring, cooling vents */}
      <mesh material={brushedSteel()} castShadow receiveShadow>
        <torusGeometry args={[1.18, 0.05, 12, 64]} />
      </mesh>

      {/* inner counter-rotating ring */}
      <group ref={innerRing}>
        <mesh material={innerMat} castShadow receiveShadow>
          <torusGeometry args={[0.98, 0.06, 12, 48]} />
        </mesh>
        <BoltField positions={boltPositionsInner} rotation={[Math.PI / 2, 0, 0]} radius={0.016} length={0.03} />
        {Array.from({ length: 16 }).map((_, i) => {
          const a = (i / 16) * Math.PI * 2;
          return (
            <mesh key={i} position={[Math.cos(a) * 0.98, Math.sin(a) * 0.98, 0.07]} material={orangeEmissive(1.4)}>
              <boxGeometry args={[0.05, 0.02, 0.02]} />
            </mesh>
          );
        })}
      </group>

      {/* armored aperture shutters */}
      {shutterAngles.map((angle, i) => (
        <group key={i} position={[Math.cos(angle) * 0.62, Math.sin(angle) * 0.62, 0.02]} rotation={[0, 0, angle - Math.PI / 2]}>
          <group ref={(el) => { hingeRefs.current[i] = el; }}>
            <mesh position={[0, 0.34, 0]} material={shutterMat} castShadow receiveShadow>
              <boxGeometry args={[0.36, 0.68, 0.06]} />
            </mesh>
            <mesh position={[0, 0.62, 0.032]} material={orangeEmissive(1.6)}>
              <boxGeometry args={[0.3, 0.02, 0.01]} />
            </mesh>
          </group>
        </group>
      ))}

      {/* internal energy core */}
      <group ref={coreGroup}>
        <mesh ref={coreMesh} material={coreMat} castShadow>
          <icosahedronGeometry args={[0.42, 1]} />
        </mesh>
        <mesh material={coreInnerMat}>
          <icosahedronGeometry args={[0.24, 1]} />
        </mesh>
      </group>

      {/* rim status lights */}
      {Array.from({ length: 8 }).map((_, i) => {
        const a = (i / 8) * Math.PI * 2 + 0.2;
        return (
          <StatusLight key={i} position={[Math.cos(a) * 1.5, Math.sin(a) * 1.5, 0.17]} offset={i * 0.4} />
        );
      })}

      {/* cable bundles routed from rear housing to outer ring */}
      <CableRun
        points={[
          [-0.3, -1.0, -0.55],
          [-0.9, -1.1, -0.3],
          [-1.3, -0.7, -0.1],
        ]}
        radius={0.028}
      />
      <CableRun
        points={[
          [0.3, -1.0, -0.55],
          [0.85, -1.15, -0.28],
          [1.28, -0.75, -0.08],
        ]}
        radius={0.024}
        color="#141414"
      />

      {/* subtle contained sparks */}
      <Sparkles count={18} scale={[2.6, 2.6, 0.6]} size={1.6} speed={0.25} color="#ff8a44" opacity={0.5} />

      {/* controlled smoke wisps near base */}
      <mesh ref={smokeA} position={[-0.4, -1.1, -0.1]} material={smokeMat}>
        <planeGeometry args={[0.9, 0.9]} />
      </mesh>
      <mesh ref={smokeB} position={[0.5, -1.2, -0.05]} material={smokeMat}>
        <planeGeometry args={[0.7, 0.7]} />
      </mesh>
    </group>
  );
}
