import * as THREE from "three";

/**
 * Shared PBR material palette for every GRIDKEEP prototype.
 * Kept as factories (not singletons) so each mesh can own its instance
 * without cross-talk when hover/scroll states tweak emissiveIntensity etc.
 */

export const PALETTE = {
  black: "#050505",
  nearBlack: "#0a0a0a",
  graphite: "#141414",
  gunmetal: "#1c1e1f",
  steel: "#2a2c2e",
  steelLight: "#3a3d3f",
  orange: "#ff5a1f",
  orangeBright: "#ff7a33",
  orangeBurnt: "#b8420f",
  orangeDim: "#7a2f10",
  white: "#f4f1ec",
  grey: "#8a8a86",
};

export function powderCoatBlack() {
  return new THREE.MeshPhysicalMaterial({
    color: PALETTE.black,
    metalness: 0.55,
    roughness: 0.62,
    clearcoat: 0.15,
    clearcoatRoughness: 0.6,
    envMapIntensity: 0.9,
  });
}

export function gunmetal() {
  return new THREE.MeshPhysicalMaterial({
    color: PALETTE.gunmetal,
    metalness: 0.85,
    roughness: 0.38,
    envMapIntensity: 1.1,
  });
}

export function brushedSteel() {
  return new THREE.MeshPhysicalMaterial({
    color: PALETTE.steel,
    metalness: 0.9,
    roughness: 0.28,
    anisotropy: 0.4,
    envMapIntensity: 1.3,
  });
}

export function darkAnodized() {
  return new THREE.MeshPhysicalMaterial({
    color: "#101112",
    metalness: 0.7,
    roughness: 0.34,
    clearcoat: 0.4,
    clearcoatRoughness: 0.35,
    envMapIntensity: 1.2,
  });
}

export function matteHousing() {
  return new THREE.MeshStandardMaterial({
    color: PALETTE.graphite,
    metalness: 0.15,
    roughness: 0.85,
  });
}

export function rubberSeal() {
  return new THREE.MeshStandardMaterial({
    color: "#0d0d0d",
    metalness: 0,
    roughness: 0.95,
  });
}

export function darkGlass() {
  return new THREE.MeshPhysicalMaterial({
    color: "#050505",
    metalness: 0,
    roughness: 0.05,
    transmission: 0.85,
    thickness: 0.4,
    ior: 1.4,
    envMapIntensity: 1,
  });
}

export function copperContact() {
  return new THREE.MeshPhysicalMaterial({
    color: "#8a4a2a",
    metalness: 1,
    roughness: 0.35,
    envMapIntensity: 1.2,
  });
}

export function orangeEmissive(intensity = 2.2) {
  return new THREE.MeshStandardMaterial({
    color: PALETTE.orangeBurnt,
    emissive: PALETTE.orange,
    emissiveIntensity: intensity,
    metalness: 0.2,
    roughness: 0.4,
    toneMapped: true,
  });
}

export function orangeGlass(intensity = 1.6) {
  return new THREE.MeshPhysicalMaterial({
    color: PALETTE.orangeDim,
    emissive: PALETTE.orange,
    emissiveIntensity: intensity,
    metalness: 0,
    roughness: 0.15,
    transmission: 0.4,
    thickness: 0.3,
  });
}

export function boltMaterial() {
  return new THREE.MeshStandardMaterial({
    color: "#0f0f10",
    metalness: 0.95,
    roughness: 0.42,
  });
}
