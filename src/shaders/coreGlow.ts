import * as THREE from "three";
import { shaderMaterial } from "@react-three/drei";

const vertexShader = /* glsl */ `
  varying vec3 vPos;
  void main() {
    vPos = position;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;

const fragmentShader = /* glsl */ `
  uniform float uTime;
  uniform float uIntensity;
  uniform vec3 uColor;
  varying vec3 vPos;

  float noise(vec3 p) {
    return fract(sin(dot(p, vec3(12.9898, 78.233, 45.164))) * 43758.5453);
  }

  void main() {
    float d = length(vPos);
    float flicker = noise(vPos * 3.0 + uTime * 0.6) * 0.12;
    float glow = smoothstep(1.0, 0.0, d) + flicker;
    vec3 color = uColor * (uIntensity + glow);
    gl_FragColor = vec4(color, glow);
  }
`;

export const CoreGlowMaterial = shaderMaterial(
  {
    uTime: 0,
    uIntensity: 1.6,
    uColor: new THREE.Color("#FF5A00"),
  },
  vertexShader,
  fragmentShader
);
