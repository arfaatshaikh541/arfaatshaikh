uniform float uTime;
uniform float uTurbulence;
uniform float uSplit;

varying vec3 vNormal;
varying vec3 vPosition;
varying float vNoise;

void main() {
  vec3 p = position * 1.6 + vec3(0.0, 0.0, uTime * 0.15);
  float n = fbm(p, 4);
  vNoise = n;

  vec3 displaced = position + normal * n * 0.06 * (0.3 + uTurbulence);

  float side = sign(position.x + 0.0001);
  displaced.x += side * uSplit * 0.65;

  vNormal = normalize(normalMatrix * normal);
  vPosition = (modelViewMatrix * vec4(displaced, 1.0)).xyz;

  gl_Position = projectionMatrix * modelViewMatrix * vec4(displaced, 1.0);
}
