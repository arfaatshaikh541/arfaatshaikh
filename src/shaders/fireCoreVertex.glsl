uniform float uTime;
uniform float uTurbulence;

varying vec3 vNormal;
varying vec3 vPosition;
varying float vNoise;

void main() {
  vec3 p = position * 1.8 + vec3(0.0, -uTime * 0.5, uTime * 0.2);
  float n = fbm(p, 4);
  vNoise = n;

  vec3 displaced = position + normal * n * 0.08 * (0.35 + uTurbulence);

  vNormal = normalize(normalMatrix * normal);
  vPosition = (modelViewMatrix * vec4(displaced, 1.0)).xyz;

  gl_Position = projectionMatrix * modelViewMatrix * vec4(displaced, 1.0);
}
