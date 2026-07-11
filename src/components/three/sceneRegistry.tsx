import type { ComponentType, MutableRefObject } from "react";
import type { SceneId } from "@/types";
import { CoreScene } from "./scenes/CoreScene";
import { NeuralScene } from "./scenes/NeuralScene";
import { AssemblyScene } from "./scenes/AssemblyScene";
import { ArchitectureScene } from "./scenes/ArchitectureScene";
import { VaultScene } from "./scenes/VaultScene";
import { OrbitScene } from "./scenes/OrbitScene";
import { WebLabScene } from "./scenes/WebLabScene";
import { NetworkScene } from "./scenes/NetworkScene";
import { CommandScene } from "./scenes/CommandScene";
import { PortalScene } from "./scenes/PortalScene";

export interface ScenePrototypeProps {
  progressRef?: MutableRefObject<number>;
}

export const SCENE_REGISTRY: Record<SceneId, ComponentType<ScenePrototypeProps>> = {
  core: CoreScene,
  neural: NeuralScene,
  assembly: AssemblyScene,
  architecture: ArchitectureScene,
  vault: VaultScene,
  orbit: OrbitScene,
  weblab: WebLabScene,
  network: NetworkScene,
  command: CommandScene,
  portal: PortalScene,
};

export const SCENE_CAMERA: Record<SceneId, [number, number, number]> = {
  core: [0, 0, 9],
  neural: [0, 0.5, 7],
  assembly: [1.5, 1.8, 8],
  architecture: [3, 1, 8],
  vault: [0, 0.5, 6.5],
  orbit: [3, 2.5, 8],
  weblab: [0, 0, 6.5],
  network: [2, 1.5, 7],
  command: [0, 1, 8.5],
  portal: [0, 0, 5],
};
