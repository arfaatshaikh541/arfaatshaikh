uniform float uTime;
uniform float uIntensity;
uniform float uSeed;
uniform vec3 uColorBase;
uniform vec3 uColorHot;

varying vec2 vUv;

void main() {
  float widthEnvelope = mix(1.0, 0.12, vUv.y);
  float dist = abs(vUv.x - 0.5) / (0.5 * widthEnvelope + 0.001);
  float shape = 1.0 - smoothstep(0.55, 1.0, dist);

  float n = fbm(vec3(vUv.x * 3.0, vUv.y * 4.0 - uTime * 1.9, uSeed * 12.0), 4);
  float body = smoothstep(0.1, 0.85, n * 0.5 + 0.5 + (1.0 - vUv.y) * 0.35);

  float topFade = smoothstep(1.0, 0.6, vUv.y);
  float alpha = shape * body * topFade * uIntensity;

  vec3 color = mix(uColorBase, uColorHot, clamp(vUv.y * 1.4 + n * 0.35, 0.0, 1.0));

  gl_FragColor = vec4(color * 1.4, alpha);
}
