import * as THREE from "three";
import { shaderMaterial } from "@react-three/drei";

const vertexShader = /* glsl */ `
  varying vec2 vUv;
  varying vec3 vNormal;
  void main() {
    vUv = uv;
    vNormal = normalize(normalMatrix * normal);
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

const fragmentShader = /* glsl */ `
  uniform float uTime;
  uniform float uIntensity;
  uniform vec3 uColorHot;
  uniform vec3 uColorDeep;
  uniform float uSegments;
  varying vec2 vUv;
  varying vec3 vNormal;

  void main() {
    float angle = atan(vUv.y - 0.5, vUv.x - 0.5);
    float seam = sin(angle * uSegments + uTime * 1.4) * 0.5 + 0.5;
    seam = pow(seam, 4.0);

    float pulse = sin(uTime * 2.2) * 0.15 + 0.85;
    float rim = pow(1.0 - abs(dot(vNormal, vec3(0.0, 0.0, 1.0))), 2.0);

    vec3 color = mix(uColorDeep, uColorHot, seam * pulse);
    float alpha = clamp(seam * uIntensity + rim * 0.3, 0.0, 1.0);

    gl_FragColor = vec4(color * uIntensity, alpha);
  }
`;

export const EnergySeamMaterial = shaderMaterial(
  {
    uTime: 0,
    uIntensity: 1.2,
    uColorHot: new THREE.Color("#FFA048"),
    uColorDeep: new THREE.Color("#C94700"),
    uSegments: 18,
  },
  vertexShader,
  fragmentShader
);
