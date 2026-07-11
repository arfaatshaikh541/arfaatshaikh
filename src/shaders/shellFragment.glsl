uniform float uTime;
uniform float uOpenAmount;
uniform float uSeparation;
uniform float uBrightness;
uniform vec3 uLightDir;
uniform vec3 uRimColor;

varying vec3 vNormal;
varying vec3 vPosition;
varying vec3 vObjectDir;
varying float vChunkGlow;

float openingMaskFor(vec3 dir, vec3 center, float seed) {
  float angle = 1.0 - dot(dir, center);
  float noiseAmount = mix(0.015, 0.18, smoothstep(0.0, 0.35, uOpenAmount));
  float edgeNoise = fbm(dir * 5.0 + seed, 3) * noiseAmount;
  float radius = mix(0.0, 0.5, uOpenAmount) + edgeNoise;
  float softness = mix(0.02, 0.09, uOpenAmount);
  return 1.0 - smoothstep(radius - softness, radius, angle);
}

void main() {
  vec3 dir = normalize(vObjectDir);

  float m1 = openingMaskFor(dir, normalize(vec3(0.9, 0.35, 0.2)), 1.0);
  float m2 = openingMaskFor(dir, normalize(vec3(-0.6, -0.4, 0.7)), 2.0);
  float m3 = openingMaskFor(dir, normalize(vec3(-0.2, 0.85, -0.5)), 3.0);
  float m4 = openingMaskFor(dir, normalize(vec3(0.3, -0.75, -0.6)), 4.0);
  float m5 = openingMaskFor(dir, normalize(vec3(-0.8, 0.15, -0.55)), 5.0);
  float openingMask = max(m1, max(m2, max(m3, max(m4, m5))));

  vec3 warp = vec3(
    fbm(dir * 3.5 + 11.0, 3),
    fbm(dir * 3.5 + 22.0, 3),
    fbm(dir * 3.5 + 33.0, 3)
  );
  vec3 cellF = (dir + warp * 0.09) * 3.0;
  vec3 cellUv = fract(cellF);
  float edgeDist = min(min(cellUv.x, 1.0 - cellUv.x), min(min(cellUv.y, 1.0 - cellUv.y), min(cellUv.z, 1.0 - cellUv.z)));
  float crackMask = smoothstep(0.05, 0.0, edgeDist) * clamp(uSeparation * 1.6, 0.0, 1.0);

  if (openingMask > 0.5) {
    discard;
  }

  vec3 viewDir = normalize(-vPosition);
  float ndotl = max(dot(vNormal, normalize(uLightDir)), 0.0);
  float fresnel = pow(1.0 - max(dot(vNormal, viewDir), 0.0), 3.0);
  float roughnessNoise = fbm(dir * 10.0 + uTime * 0.02, 3) * 0.5 + 0.5;

  vec3 base = mix(vec3(0.006, 0.005, 0.005), vec3(0.045, 0.04, 0.04), roughnessNoise);
  vec3 color = base * (0.18 + ndotl * 0.55);
  color += fresnel * uRimColor * 0.55;
  color += crackMask * uRimColor * (0.8 + uBrightness * 0.6);

  float edgeGlow = smoothstep(0.12, 0.5, openingMask) * (1.0 - smoothstep(0.5, 0.72, openingMask));
  color += edgeGlow * uRimColor * (1.0 + uBrightness) * 1.4;

  gl_FragColor = vec4(color, 1.0);
}
