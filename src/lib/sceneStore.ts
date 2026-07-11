// A plain, mutable singleton that GSAP tweens directly and R3F components
// read every frame via useFrame. Deliberately not React state — the sphere
// updates ~60 times a second and routing that through React would cause
// constant re-renders for no benefit.

export const sceneState = {
  camX: 0,
  camY: 0,
  camZ: 6.2,
  targetX: 0,
  targetY: 0,
  targetZ: 0,
  parallaxX: 0,
  parallaxY: 0,

  shellOpen: 0.04,
  separation: 0,
  coreBrightness: 0.35,
  turbulence: 0.15,
  flameIntensity: 0.08,
  bloomStrength: 0.55,
  particleMix: 0.1,
  ringsVisible: 0,
  splitAmount: 0,
  rotationSpeed: 0.06,
  vignette: 0.55,
  chromaticAb: 0.1,
  heatDistortion: 0.15,
};

export type SceneState = typeof sceneState;

const CHAPTER_KEYS: (keyof SceneState)[] = [
  "camX",
  "camY",
  "camZ",
  "targetX",
  "targetY",
  "targetZ",
  "shellOpen",
  "separation",
  "coreBrightness",
  "turbulence",
  "flameIntensity",
  "bloomStrength",
  "particleMix",
  "ringsVisible",
  "splitAmount",
  "rotationSpeed",
  "vignette",
  "chromaticAb",
  "heatDistortion",
];

function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

/**
 * Drives sceneState from a single continuous scroll progress value (0..1)
 * spanning every chapter, called from the homepage's ScrollTrigger onUpdate.
 */
export function applyChapterProgress(progress: number, chapters: SceneState[]) {
  const clamped = Math.min(1, Math.max(0, progress));
  const scaled = clamped * (chapters.length - 1);
  const index = Math.min(chapters.length - 2, Math.floor(scaled));
  const fraction = scaled - index;
  const from = chapters[index];
  const to = chapters[index + 1];

  for (const key of CHAPTER_KEYS) {
    sceneState[key] = lerp(from[key], to[key], fraction);
  }
}

export const CHAPTER_STATES: SceneState[] = [
  // 0 Dormant
  {
    ...sceneState,
    camX: 0,
    camY: 0.1,
    camZ: 6.4,
    targetY: 0,
    shellOpen: 0.02,
    separation: 0,
    coreBrightness: 0.28,
    turbulence: 0.1,
    flameIntensity: 0.04,
    bloomStrength: 0.45,
    particleMix: 0.06,
    ringsVisible: 0,
    splitAmount: 0,
    rotationSpeed: 0.05,
    vignette: 0.6,
    chromaticAb: 0.08,
    heatDistortion: 0.08,
  },
  // 1 Awakening
  {
    ...sceneState,
    camX: 0.6,
    camY: 0.05,
    camZ: 5.2,
    targetY: 0,
    shellOpen: 0.22,
    separation: 0.05,
    coreBrightness: 0.75,
    turbulence: 0.35,
    flameIntensity: 0.35,
    bloomStrength: 0.85,
    particleMix: 0.25,
    ringsVisible: 0,
    splitAmount: 0,
    rotationSpeed: 0.09,
    vignette: 0.55,
    chromaticAb: 0.12,
    heatDistortion: 0.22,
  },
  // 2 AI
  {
    ...sceneState,
    camX: -0.9,
    camY: 0.25,
    camZ: 4.4,
    targetY: 0.05,
    shellOpen: 0.42,
    separation: 0.32,
    coreBrightness: 1.15,
    turbulence: 0.75,
    flameIntensity: 0.55,
    bloomStrength: 1.15,
    particleMix: 0.45,
    ringsVisible: 0,
    splitAmount: 0,
    rotationSpeed: 0.14,
    vignette: 0.5,
    chromaticAb: 0.18,
    heatDistortion: 0.35,
  },
  // 3 Automation
  {
    ...sceneState,
    camX: 1.1,
    camY: -0.15,
    camZ: 4.1,
    targetY: -0.05,
    shellOpen: 0.5,
    separation: 0.4,
    coreBrightness: 1.3,
    turbulence: 0.8,
    flameIntensity: 0.6,
    bloomStrength: 1.25,
    particleMix: 0.55,
    ringsVisible: 0.15,
    splitAmount: 0,
    rotationSpeed: 0.18,
    vignette: 0.48,
    chromaticAb: 0.16,
    heatDistortion: 0.4,
  },
  // 4 Software
  {
    ...sceneState,
    camX: -0.4,
    camY: 0.4,
    camZ: 4.6,
    targetY: 0.1,
    shellOpen: 0.4,
    separation: 0.22,
    coreBrightness: 1.1,
    turbulence: 0.6,
    flameIntensity: 0.45,
    bloomStrength: 1.05,
    particleMix: 0.4,
    ringsVisible: 0.1,
    splitAmount: 0,
    rotationSpeed: 0.12,
    vignette: 0.5,
    chromaticAb: 0.14,
    heatDistortion: 0.3,
  },
  // 5 Cybersecurity
  {
    ...sceneState,
    camX: 0,
    camY: 0,
    camZ: 4.8,
    targetY: 0,
    shellOpen: 0.1,
    separation: -0.35,
    coreBrightness: 1.4,
    turbulence: 0.55,
    flameIntensity: 0.3,
    bloomStrength: 1.0,
    particleMix: 0.3,
    ringsVisible: 0.2,
    splitAmount: 0,
    rotationSpeed: 0.1,
    vignette: 0.55,
    chromaticAb: 0.1,
    heatDistortion: 0.2,
  },
  // 6 Cloud & DevOps
  {
    ...sceneState,
    camX: 0.8,
    camY: 0.3,
    camZ: 5.4,
    targetY: 0.05,
    shellOpen: 0.18,
    separation: -0.1,
    coreBrightness: 1.2,
    turbulence: 0.4,
    flameIntensity: 0.28,
    bloomStrength: 0.95,
    particleMix: 0.35,
    ringsVisible: 1.0,
    splitAmount: 0,
    rotationSpeed: 0.08,
    vignette: 0.5,
    chromaticAb: 0.1,
    heatDistortion: 0.18,
  },
  // 7 GRIDKEEP
  {
    ...sceneState,
    camX: 0,
    camY: 0.05,
    camZ: 5.6,
    targetY: 0,
    shellOpen: 0.16,
    separation: 0,
    coreBrightness: 1.5,
    turbulence: 0.5,
    flameIntensity: 0.3,
    bloomStrength: 1.3,
    particleMix: 0.3,
    ringsVisible: 0.5,
    splitAmount: 0,
    rotationSpeed: 0.07,
    vignette: 0.5,
    chromaticAb: 0.12,
    heatDistortion: 0.2,
  },
  // 8 Contact
  {
    ...sceneState,
    camX: 0,
    camY: 0,
    camZ: 5.0,
    targetY: 0,
    shellOpen: 0.5,
    separation: 0.1,
    coreBrightness: 2.0,
    turbulence: 0.95,
    flameIntensity: 0.85,
    bloomStrength: 1.9,
    particleMix: 0.7,
    ringsVisible: 0.2,
    splitAmount: 1,
    rotationSpeed: 0.03,
    vignette: 0.42,
    chromaticAb: 0.22,
    heatDistortion: 0.5,
  },
];
