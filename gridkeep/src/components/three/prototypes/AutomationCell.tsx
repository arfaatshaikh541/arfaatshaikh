"use client";

import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import { gunmetal, brushedSteel, darkAnodized, orangeEmissive, rubberSeal } from "../materials";
import { StatusLight } from "../Parts";
import type { ProgressRef } from "@/hooks/useScrollProgress";

const CYCLE = 4.4;

export default function AutomationCell({ progressRef, hover = 0 }: { progressRef?: ProgressRef; hover?: number }) {
  const chassisMat = useMemo(() => gunmetal(), []);
  const railMat = useMemo(() => brushedSteel(), []);
  const cabinetMat = useMemo(() => darkAnodized(), []);
  const payloadMat = useMemo(() => orangeEmissive(2.2), []);
  const beamMat = useMemo(() => orangeEmissive(3), []);
  const seal = useMemo(() => rubberSeal(), []);

  const payloadRef = useRef<THREE.Mesh>(null);
  const armUpper = useRef<THREE.Group>(null);
  const armLower = useRef<THREE.Group>(null);
  const gripper = useRef<THREE.Group>(null);
  const beamRef = useRef<THREE.Mesh>(null);
  const camGroup = useRef<THREE.Group>(null);

  useFrame((state) => {
    const speed = 1 + hover * 0.5 + (progressRef?.current.value ?? 0) * 0.2;
    const t = ((state.clock.elapsedTime * speed) % CYCLE) / CYCLE;

    if (payloadRef.current) {
      if (t < 0.45) {
        // travel along conveyor toward scan zone
        payloadRef.current.position.x = THREE.MathUtils.lerp(-0.85, 0, t / 0.45);
        payloadRef.current.position.y = 0.06;
        payloadRef.current.visible = true;
      } else if (t < 0.6) {
        // held under scanner
        payloadRef.current.position.x = 0;
        payloadRef.current.visible = true;
      } else if (t < 1) {
        const accept = Math.sin(state.clock.elapsedTime * 0.35) > -0.2;
        const localT = (t - 0.6) / 0.4;
        if (accept) {
          payloadRef.current.position.x = THREE.MathUtils.lerp(0, 0.85, localT);
          payloadRef.current.position.y = 0.06;
        } else {
          payloadRef.current.position.x = THREE.MathUtils.lerp(0, 0.35, localT);
          payloadRef.current.position.y = THREE.MathUtils.lerp(0.06, -0.35, localT * localT);
        }
      }
    }

    // scanner beam pulses during hold phase
    if (beamRef.current) {
      const scanning = t > 0.4 && t < 0.62;
      beamRef.current.visible = scanning;
      const mat = beamRef.current.material as THREE.MeshStandardMaterial;
      mat.emissiveIntensity = 2.4 + Math.sin(state.clock.elapsedTime * 12) * 1.2;
    }
    if (camGroup.current) {
      camGroup.current.rotation.z = Math.sin(state.clock.elapsedTime * 0.6) * 0.08;
    }

    // robotic arm reaches toward payload during accept/reject window
    const reach = t > 0.55 && t < 0.95 ? Math.sin(((t - 0.55) / 0.4) * Math.PI) : 0;
    if (armUpper.current) armUpper.current.rotation.z = -0.3 - reach * 0.5;
    if (armLower.current) armLower.current.rotation.z = 0.5 + reach * 0.6;
    if (gripper.current) gripper.current.rotation.z = reach * 0.4 - 0.1;
  });

  return (
    <group position={[0, -0.1, 0]}>
      {/* base platform */}
      <mesh position={[0, -0.42, 0]} material={railMat} receiveShadow castShadow>
        <boxGeometry args={[2.2, 0.1, 1.1]} />
      </mesh>

      {/* safety enclosure posts */}
      {[
        [-1.05, -0.5],
        [1.05, -0.5],
        [-1.05, 0.5],
        [1.05, 0.5],
      ].map(([x, z], i) => (
        <mesh key={i} position={[x, 0.35, z]} material={chassisMat} castShadow>
          <cylinderGeometry args={[0.03, 0.03, 1.5, 8]} />
        </mesh>
      ))}
      <mesh position={[0, 1.1, 0]} material={chassisMat} castShadow>
        <boxGeometry args={[2.16, 0.05, 1.06]} />
      </mesh>

      {/* conveyor bed */}
      <mesh position={[0, 0, 0]} material={cabinetMat} receiveShadow castShadow>
        <boxGeometry args={[2, 0.14, 0.34]} />
      </mesh>
      <mesh position={[0, 0.075, 0]} material={seal}>
        <boxGeometry args={[1.96, 0.01, 0.3]} />
      </mesh>

      {/* payload block traveling on belt */}
      <mesh ref={payloadRef} position={[-0.85, 0.06, 0]} material={payloadMat} castShadow>
        <boxGeometry args={[0.14, 0.12, 0.14]} />
      </mesh>

      {/* vision camera + scan beam above the belt */}
      <group ref={camGroup} position={[0, 0.75, 0]}>
        <mesh material={chassisMat} castShadow>
          <boxGeometry args={[0.12, 0.1, 0.12]} />
        </mesh>
        <mesh position={[0, -0.06, 0]}>
          <sphereGeometry args={[0.025, 10, 10]} />
          <meshPhysicalMaterial color="#050505" roughness={0.05} transmission={0.7} thickness={0.2} />
        </mesh>
      </group>
      <mesh ref={beamRef} position={[0, 0.4, 0]} material={beamMat}>
        <coneGeometry args={[0.09, 0.66, 12, 1, true]} />
      </mesh>

      {/* robotic arm */}
      <group position={[-0.55, 0.07, 0.35]}>
        <mesh material={chassisMat} castShadow>
          <cylinderGeometry args={[0.07, 0.09, 0.14, 12]} />
        </mesh>
        <group ref={armUpper} position={[0, 0.07, 0]} rotation={[0, 0, -0.3]}>
          <mesh position={[0, 0.22, 0]} material={railMat} castShadow>
            <boxGeometry args={[0.06, 0.44, 0.06]} />
          </mesh>
          <group ref={armLower} position={[0, 0.44, 0]} rotation={[0, 0, 0.5]}>
            <mesh position={[0, 0.18, 0]} material={railMat} castShadow>
              <boxGeometry args={[0.05, 0.36, 0.05]} />
            </mesh>
            <group ref={gripper} position={[0, 0.36, 0]}>
              <mesh material={darkAnodized()} castShadow>
                <boxGeometry args={[0.09, 0.06, 0.09]} />
              </mesh>
              <mesh position={[-0.035, -0.05, 0]} material={railMat}>
                <boxGeometry args={[0.015, 0.06, 0.02]} />
              </mesh>
              <mesh position={[0.035, -0.05, 0]} material={railMat}>
                <boxGeometry args={[0.015, 0.06, 0.02]} />
              </mesh>
            </group>
          </group>
        </group>
      </group>

      {/* sorting rails diverging past the scan zone */}
      <mesh position={[0.6, 0.06, 0]} rotation={[0, 0, 0]} material={railMat}>
        <boxGeometry args={[0.8, 0.02, 0.02]} />
      </mesh>
      <mesh position={[0.45, -0.25, 0]} rotation={[0, 0, -0.6]} material={railMat}>
        <boxGeometry args={[0.5, 0.02, 0.02]} />
      </mesh>

      {/* output tray + reject bin */}
      <mesh position={[1.1, 0.02, 0]} material={cabinetMat} castShadow>
        <boxGeometry args={[0.24, 0.08, 0.34]} />
      </mesh>
      <mesh position={[0.55, -0.42, 0]} material={chassisMat} castShadow>
        <boxGeometry args={[0.3, 0.16, 0.34]} />
      </mesh>

      {/* control cabinet */}
      <group position={[-1.35, 0.1, 0.2]}>
        <mesh material={cabinetMat} castShadow>
          <boxGeometry args={[0.22, 0.7, 0.3]} />
        </mesh>
        <mesh position={[0, 0.15, 0.16]} material={orangeEmissive(1)}>
          <planeGeometry args={[0.14, 0.16]} />
        </mesh>
        <StatusLight position={[0.07, -0.15, 0.16]} offset={0} />
        <StatusLight position={[0.02, -0.15, 0.16]} offset={0.5} />
      </group>
    </group>
  );
}
