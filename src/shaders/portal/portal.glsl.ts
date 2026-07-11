import { simplexNoise3D } from "../core/noise.glsl";

export const portalVertexShader = /* glsl */ `
uniform float uTime;
uniform vec2 uPointer;
varying vec2 vUv;

void main() {
  vUv = uv;
  vec3 pos = position;
  float dist = distance(uv, vec2(0.5) + uPointer * 0.15);
  pos.z += sin(dist * 14.0 - uTime * 1.6) * 0.06 * (1.0 - dist);
  gl_Position = projectionMatrix * modelViewMatrix * vec4(pos, 1.0);
}
`;

export const portalFragmentShader = /* glsl */ `
uniform float uTime;
uniform float uOpen;
uniform vec3 uColorCore;
uniform vec3 uColorEdge;
varying vec2 vUv;

${simplexNoise3D}

void main() {
  vec2 centered = vUv - 0.5;
  float radius = length(centered);
  float angle = atan(centered.y, centered.x);

  float tunnel = snoise(vec3(angle * 2.0, radius * 6.0 - uTime * 1.4, uTime * 0.2));
  float ring = smoothstep(0.46, 0.5, radius) - smoothstep(0.5, 0.54, radius);

  float aperture = smoothstep(0.5 * (1.0 - uOpen), 0.5 * (1.0 - uOpen) + 0.06, radius);
  float glow = smoothstep(0.0, 0.5, radius) * (0.6 + 0.4 * tunnel);

  vec3 color = mix(uColorCore, uColorEdge, clamp(radius * 2.0, 0.0, 1.0));
  color += ring * uColorEdge * 1.4;

  float alpha = clamp((glow * 0.8 + ring * 1.2) * aperture, 0.0, 1.0);
  gl_FragColor = vec4(color, alpha);
}
`;
