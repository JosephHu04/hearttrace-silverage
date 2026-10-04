"use client";

import { Suspense, useCallback, useEffect, useRef } from "react";
import { Canvas } from "@react-three/fiber";
import { ContactShadows, Environment, OrbitControls, useAnimations, useGLTF } from "@react-three/drei";
import { Group, LoopOnce, LoopRepeat } from "three";

export const YAOYAO_ACTIONS = [
  "Idle_Base",
  "Idle_Wave",
  "Listen",
  "Think",
  "Talk",
  "Nod",
  "Cheer",
  "Concern",
  "Alert"
] as const;

export type YaoyaoAction = (typeof YAOYAO_ACTIONS)[number];

const ACTION_LABELS: Record<YaoyaoAction, string> = {
  Idle_Base: "自然待机",
  Idle_Wave: "招手问候",
  Listen: "认真倾听",
  Think: "思考回应",
  Talk: "开口说话",
  Nod: "点头回应",
  Cheer: "开心鼓励",
  Concern: "关切安慰",
  Alert: "紧急提醒"
};

type ModelProps = {
  requestedAction: YaoyaoAction;
  onPlaying: (action: YaoyaoAction) => void;
};

function Model({ requestedAction, onPlaying }: ModelProps) {
  const group = useRef<Group>(null);
  const { scene, animations } = useGLTF("/companion/yaoyao-blockout-v1.glb");
  const { actions } = useAnimations(animations, group);

  const play = useCallback((name: YaoyaoAction) => {
    const next = actions[name];
    if (!next) return;
    Object.values(actions).forEach((action) => action?.fadeOut(0.2));
    next.reset().fadeIn(0.22);
    if (name === "Idle_Base") {
      next.setLoop(LoopRepeat, Infinity);
      next.clampWhenFinished = false;
    } else {
      next.setLoop(LoopOnce, 1);
      next.clampWhenFinished = true;
    }
    next.play();
    onPlaying(name);

    if (name !== "Idle_Base") {
      const duration = Math.max(1.2, next.getClip().duration);
      window.setTimeout(() => {
        next.fadeOut(0.22);
        const idle = actions.Idle_Base;
        if (!idle) return;
        idle.reset().setLoop(LoopRepeat, Infinity).fadeIn(0.25).play();
        onPlaying("Idle_Base");
      }, duration * 1000);
    }
  }, [actions, onPlaying]);

  useEffect(() => {
    play(requestedAction);
  }, [play, requestedAction]);

  return (
    <group ref={group} position={[0, -2.9, 0]}>
      <primitive object={scene} />
    </group>
  );
}

type Props = {
  action: YaoyaoAction;
  onPlaying: (action: YaoyaoAction) => void;
};

export function Yaoyao3D({ action, onPlaying }: Props) {
  return (
    <Canvas
      camera={{ position: [0, 2.7, 9.4], fov: 36 }}
      dpr={[1, 1.75]}
      gl={{ antialias: true, alpha: true }}
      aria-label="遥遥三维角色动作预览"
    >
      <color attach="background" args={["#e9f2eb"]} />
      <fog attach="fog" args={["#e9f2eb", 10, 18]} />
      <ambientLight intensity={1.45} />
      <directionalLight position={[4, 8, 6]} intensity={2.4} castShadow />
      <directionalLight position={[-5, 3, 3]} intensity={1.2} color="#d9cff7" />
      <Suspense fallback={null}>
        <Model requestedAction={action} onPlaying={onPlaying} />
        <Environment preset="studio" environmentIntensity={0.35} />
      </Suspense>
      <ContactShadows position={[0, -2.92, 0]} opacity={0.35} scale={8} blur={2.6} far={4} />
      <OrbitControls
        makeDefault
        enablePan={false}
        enableZoom
        minDistance={7}
        maxDistance={12}
        minPolarAngle={Math.PI / 2.6}
        maxPolarAngle={Math.PI / 1.75}
        target={[0, 0.2, 0]}
      />
    </Canvas>
  );
}

export function actionLabel(action: YaoyaoAction): string {
  return ACTION_LABELS[action];
}

useGLTF.preload("/companion/yaoyao-blockout-v1.glb");
