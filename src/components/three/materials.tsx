"use client";

import { shaderMaterial } from "@react-three/drei";
import { extend, type ThreeElement } from "@react-three/fiber";
import * as THREE from "three";
import { energyFragmentShader, energyVertexShader } from "@/shaders/energy/energy.glsl";
import { portalFragmentShader, portalVertexShader } from "@/shaders/portal/portal.glsl";
import { pulseLineFragmentShader, pulseLineVertexShader } from "@/shaders/data/pulseLine.glsl";
import { scanFragmentShader, scanVertexShader } from "@/shaders/scan/scan.glsl";
import { smokeFragmentShader, smokeVertexShader } from "@/shaders/smoke/smoke.glsl";

export const EnergyMaterial = shaderMaterial(
  {
    uColorDeep: new THREE.Color("#7A2200"),
    uColorBright: new THREE.Color("#FF7A1A"),
    uTime: 0,
    uActivation: 0.6,
    uPulseSpeed: 0.6,
    uFresnelPower: 2.2,
    uNoiseScale: 0.8,
    uIntensity: 1.0,
  },
  energyVertexShader,
  energyFragmentShader
);

export const ScanMaterial = shaderMaterial(
  {
    uColor: new THREE.Color("#FF5A00"),
    uTime: 0,
    uScanSpeed: 0.25,
    uThreatLevel: 0,
    uDensity: 26,
  },
  scanVertexShader,
  scanFragmentShader
);

export const PortalMaterial = shaderMaterial(
  {
    uTime: 0,
    uPointer: new THREE.Vector2(0, 0),
    uOpen: 0.15,
    uColorCore: new THREE.Color("#050505"),
    uColorEdge: new THREE.Color("#FF5A00"),
  },
  portalVertexShader,
  portalFragmentShader
);

export const PulseLineMaterial = shaderMaterial(
  {
    uColor: new THREE.Color("#FF5A00"),
    uTime: 0,
    uSpeed: 0.6,
    uPulseWidth: 0.08,
    uPulseCount: 3,
    uActive: 1,
  },
  pulseLineVertexShader,
  pulseLineFragmentShader
);

export const SmokeMaterial = shaderMaterial(
  {
    uTime: 0,
    uColor: new THREE.Color("#C84400"),
    uOpacity: 0.35,
  },
  smokeVertexShader,
  smokeFragmentShader
);

extend({
  EnergyMaterial,
  ScanMaterial,
  PortalMaterial,
  PulseLineMaterial,
  SmokeMaterial,
});

declare module "@react-three/fiber" {
  interface ThreeElements {
    energyMaterial: ThreeElement<typeof EnergyMaterial> & {
      uColorDeep?: THREE.Color | string;
      uColorBright?: THREE.Color | string;
      uTime?: number;
      uActivation?: number;
      uPulseSpeed?: number;
      uFresnelPower?: number;
      uNoiseScale?: number;
      uIntensity?: number;
    };
    scanMaterial: ThreeElement<typeof ScanMaterial> & {
      uColor?: THREE.Color | string;
      uTime?: number;
      uScanSpeed?: number;
      uThreatLevel?: number;
      uDensity?: number;
    };
    portalMaterial: ThreeElement<typeof PortalMaterial> & {
      uTime?: number;
      uPointer?: THREE.Vector2;
      uOpen?: number;
      uColorCore?: THREE.Color | string;
      uColorEdge?: THREE.Color | string;
    };
    pulseLineMaterial: ThreeElement<typeof PulseLineMaterial> & {
      uColor?: THREE.Color | string;
      uTime?: number;
      uSpeed?: number;
      uPulseWidth?: number;
      uPulseCount?: number;
      uActive?: number;
    };
    smokeMaterial: ThreeElement<typeof SmokeMaterial> & {
      uTime?: number;
      uColor?: THREE.Color | string;
      uOpacity?: number;
    };
  }
}
