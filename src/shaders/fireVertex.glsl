uniform float uTime;
uniform float uSeed;

varying vec2 vUv;

void main() {
  vUv = uv;
  vec3 pos = position;
  float sway = sin(uTime * 2.4 + uSeed * 6.28 + uv.y * 3.0) * 0.03 * uv.y;
  pos.x += sway;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(pos, 1.0);
}
