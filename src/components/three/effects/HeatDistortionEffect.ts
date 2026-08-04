import { Effect, BlendFunction } from "postprocessing";
import { Uniform } from "three";

const fragmentShader = /* glsl */ `
  uniform float uTime;
  uniform float uIntensity;

  float hash(vec2 p) {
    return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453);
  }

  void mainImage(const in vec4 inputColor, const in vec2 uv, out vec4 outputColor) {
    float n1 = sin((uv.y * 26.0) + uTime * 1.6);
    float n2 = hash(uv * 8.0 + uTime * 0.25) - 0.5;
    vec2 offset = vec2(n1 * 0.0015, n2 * 0.001) * uIntensity;
    outputColor = texture2D(inputBuffer, uv + offset);
  }
`;

export class HeatDistortionEffect extends Effect {
  constructor({ intensity = 0.2 }: { intensity?: number } = {}) {
    super("HeatDistortionEffect", fragmentShader, {
      blendFunction: BlendFunction.NORMAL,
      uniforms: new Map<string, Uniform>([
        ["uTime", new Uniform(0)],
        ["uIntensity", new Uniform(intensity)],
      ]),
    });
  }

  update(_renderer: unknown, _inputBuffer: unknown, deltaTime: number) {
    const time = this.uniforms.get("uTime");
    if (time) time.value += deltaTime;
  }

  setIntensity(value: number) {
    const uniform = this.uniforms.get("uIntensity");
    if (uniform) uniform.value = value;
  }
}
