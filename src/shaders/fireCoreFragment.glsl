uniform float uTime;
uniform float uBrightness;
uniform float uTurbulence;
uniform vec3 uColorEdge;
uniform vec3 uColorMid;
uniform vec3 uColorCore;

varying vec3 vNormal;
varying vec3 vPosition;
varying float vNoise;

void main() {
  vec3 viewDir = normalize(-vPosition);
  float fresnel = pow(1.0 - max(dot(vNormal, viewDir), 0.0), 2.0);

  float flow = fbm(vPosition * 2.6 + vec3(0.0, -uTime * 0.9, uTime * 0.3), 5);
  float licks = fbm(vPosition * 5.0 + vec3(uTime * 0.6, -uTime * 1.6, 0.0), 4);
  float energy = clamp(flow * 0.5 + 0.5, 0.0, 1.0);
  float hot = smoothstep(0.35, 0.95, energy + licks * 0.25 + vNoise * 0.3 + uTurbulence * 0.2);

  vec3 color = mix(uColorEdge, uColorMid, smoothstep(0.0, 0.6, hot));
  color = mix(color, uColorCore, smoothstep(0.55, 1.0, hot));
  color += fresnel * uColorMid * 0.6;

  float pulse = 0.75 + 0.25 * sin(uTime * 3.1);
  color *= (0.7 + uBrightness * 0.9) * pulse;

  gl_FragColor = vec4(color, 1.0);
}
