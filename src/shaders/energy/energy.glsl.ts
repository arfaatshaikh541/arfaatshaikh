import { simplexNoise3D } from "../core/noise.glsl";

export const energyVertexShader = /* glsl */ `
varying vec3 vNormal;
varying vec3 vViewPosition;
varying vec3 vWorldPosition;

void main() {
  vNormal = normalize(normalMatrix * normal);
  vec4 worldPosition = modelMatrix * vec4(position, 1.0);
  vWorldPosition = worldPosition.xyz;
  vec4 mvPosition = viewMatrix * worldPosition;
  vViewPosition = -mvPosition.xyz;
  gl_Position = projectionMatrix * mvPosition;
}
`;

export const energyFragmentShader = /* glsl */ `
uniform vec3 uColorDeep;
uniform vec3 uColorBright;
uniform float uTime;
uniform float uActivation;
uniform float uPulseSpeed;
uniform float uFresnelPower;
uniform float uNoiseScale;
uniform float uIntensity;

varying vec3 vNormal;
varying vec3 vViewPosition;
varying vec3 vWorldPosition;

${simplexNoise3D}

void main() {
  vec3 viewDir = normalize(vViewPosition);
  float fresnel = pow(1.0 - clamp(dot(vNormal, viewDir), 0.0, 1.0), uFresnelPower);

  float noise = snoise(vWorldPosition * uNoiseScale + vec3(0.0, 0.0, uTime * uPulseSpeed));
  float pulse = 0.5 + 0.5 * sin(uTime * uPulseSpeed * 2.0 + noise * 3.0);

  float energy = clamp(fresnel * 0.7 + pulse * 0.5 * uActivation, 0.0, 1.4);
  vec3 color = mix(uColorDeep, uColorBright, clamp(energy, 0.0, 1.0));

  float alpha = clamp((fresnel * 0.6 + 0.25) * uIntensity * (0.35 + uActivation * 0.65), 0.0, 1.0);

  gl_FragColor = vec4(color * uIntensity, alpha);
}
`;
