uniform float uTime;
uniform float uSeparation;
uniform float uSplit;

varying vec3 vNormal;
varying vec3 vPosition;
varying vec3 vObjectDir;
varying float vChunkGlow;

float hash13(vec3 p) {
  p = fract(p * 0.3183099 + 0.1);
  p *= 17.0;
  return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
}

void main() {
  vec3 dir = normalize(position);
  vObjectDir = dir;

  // Segment the shell into coarse chunks so it can visibly separate.
  vec3 cellId = floor(dir * 3.0);
  float chunkRandom = hash13(cellId) * 2.0 - 1.0;
  vChunkGlow = clamp(uSeparation, 0.0, 1.0);

  // Fine volcanic surface roughness, always present.
  float fine = fbm(position * 6.0 + uTime * 0.05, 3);

  vec3 displaced = position
    + normal * chunkRandom * uSeparation * 0.22
    + normal * fine * 0.02;

  float side = sign(dir.x + 0.0001);
  displaced.x += side * uSplit * 1.1;

  vNormal = normalize(normalMatrix * normal);
  vPosition = (modelViewMatrix * vec4(displaced, 1.0)).xyz;

  gl_Position = projectionMatrix * modelViewMatrix * vec4(displaced, 1.0);
}
