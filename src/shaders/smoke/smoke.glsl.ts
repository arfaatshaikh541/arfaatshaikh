export const smokeVertexShader = /* glsl */ `
attribute float aScale;
attribute float aSeed;
uniform float uTime;
varying float vSeed;
varying float vAlpha;

void main() {
  vSeed = aSeed;
  vec3 pos = position;
  pos.y += sin(uTime * 0.15 + aSeed * 6.28) * 0.4;
  pos.x += cos(uTime * 0.1 + aSeed * 3.14) * 0.3;

  vec4 mvPosition = modelViewMatrix * vec4(pos, 1.0);
  vAlpha = clamp(1.0 - (-mvPosition.z) / 40.0, 0.0, 1.0);
  gl_PointSize = aScale * (300.0 / -mvPosition.z);
  gl_Position = projectionMatrix * mvPosition;
}
`;

export const smokeFragmentShader = /* glsl */ `
uniform vec3 uColor;
uniform float uOpacity;
varying float vSeed;
varying float vAlpha;

void main() {
  vec2 uv = gl_PointCoord - 0.5;
  float d = length(uv);
  float soft = smoothstep(0.5, 0.0, d);
  gl_FragColor = vec4(uColor, soft * uOpacity * vAlpha);
}
`;
