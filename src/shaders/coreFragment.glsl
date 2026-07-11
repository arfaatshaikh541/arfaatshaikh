uniform float uTime;
uniform float uBrightness;
uniform float uTurbulence;
uniform vec3 uColorDeep;
uniform vec3 uColorHot;

varying vec3 vNormal;
varying vec3 vPosition;
varying float vNoise;

void main() {
  vec3 viewDir = normalize(-vPosition);
  float fresnel = pow(1.0 - max(dot(vNormal, viewDir), 0.0), 2.2);

  float flow = fbm(vPosition * 2.2 + vec3(0.0, uTime * 0.4, uTime * 0.22), 5);
  float veins = smoothstep(0.15, 0.85, flow * 0.5 + vNoise * 0.5);

  float pulse = 0.65 + 0.35 * sin(uTime * 1.6);
  float energy = clamp(veins * (0.6 + uTurbulence) * pulse * uBrightness, 0.0, 1.6);

  vec3 color = mix(uColorDeep, uColorHot, clamp(energy, 0.0, 1.0));
  color += fresnel * uColorHot * (0.8 + 0.6 * uTurbulence);
  color *= 0.6 + uBrightness * 0.6;

  gl_FragColor = vec4(color, 1.0);
}
