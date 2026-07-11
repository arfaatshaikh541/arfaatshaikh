export const pulseLineVertexShader = /* glsl */ `
varying vec2 vUv;

void main() {
  vUv = uv;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
`;

export const pulseLineFragmentShader = /* glsl */ `
uniform vec3 uColor;
uniform float uTime;
uniform float uSpeed;
uniform float uPulseWidth;
uniform float uPulseCount;
uniform float uActive;

varying vec2 vUv;

void main() {
  float t = fract(vUv.x * uPulseCount - uTime * uSpeed);
  float pulse = smoothstep(0.0, uPulseWidth, t) * smoothstep(uPulseWidth * 2.0, uPulseWidth, t);

  float base = 0.06;
  float edge = smoothstep(0.0, 0.5, 1.0 - abs(vUv.y - 0.5) * 2.0);

  float intensity = (base + pulse * uActive) * edge;
  gl_FragColor = vec4(uColor * (1.0 + pulse * 1.5), intensity);
}
`;
