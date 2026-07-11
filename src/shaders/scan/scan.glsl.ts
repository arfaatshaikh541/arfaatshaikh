export const scanVertexShader = /* glsl */ `
varying vec2 vUv;
varying vec3 vNormal;

void main() {
  vUv = uv;
  vNormal = normalize(normalMatrix * normal);
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
`;

export const scanFragmentShader = /* glsl */ `
uniform vec3 uColor;
uniform float uTime;
uniform float uScanSpeed;
uniform float uThreatLevel;
uniform float uDensity;

varying vec2 vUv;
varying vec3 vNormal;

void main() {
  float band = fract(vUv.y * uDensity - uTime * uScanSpeed);
  float line = smoothstep(0.0, 0.02, band) * smoothstep(0.08, 0.02, band);

  float rim = pow(1.0 - abs(vNormal.z), 2.0);
  float base = rim * 0.15;

  vec3 color = uColor * (line * 1.6 + base + uThreatLevel * 0.35);
  float alpha = clamp(line * 0.9 + base + uThreatLevel * 0.2, 0.0, 1.0);

  gl_FragColor = vec4(color, alpha);
}
`;
