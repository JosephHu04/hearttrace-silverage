"use client";

import { Suspense, useCallback, useEffect, useRef } from "react";
import { Canvas } from "@react-three/fiber";
import { ContactShadows, Environment, OrbitControls, useAnimations, useGLTF } from "@react-three/drei";
import { Group, LoopOnce, LoopRepeat } from "three";

export const RIG_ACTIONS = [
  "Idle_Base",
  "Idle_Wave",
  "Talk",
  "Sitting_Idle",
  "Sitting_Talk"
] as const;

export type RigAction = (typeof RIG_ACTIONS)[number];

export const RIG_ACTION_META: Record<RigAction, { label: string; hint: string }> = {
  Idle_Base: { label: "自然待机", hint: "呼吸、脊柱和手臂微动" },
  Idle_Wave: { label: "招手互动", hint: "肩、肘、腕和手指协同" },
  Talk: { label: "站立说话", hint: "上身随语气自然表达" },
  Sitting_Idle: { label: "坐姿待机", hint: "适合桌面陪伴与长时间展示" },
  Sitting_Talk: { label: "坐姿说话", hint: "坐姿下的对话手势" }
};

type ModelProps = {
  requestedAction: RigAction;
  onPlaying: (action: RigAction) => void;
};

function RigModel({ requestedAction, onPlaying }: ModelProps) {
  const group = useRef<Group>(null);
  const returnTimer = useRef<number | null>(null);
  const { scene, animations } = useGLTF("/companion/candidates/xiaohe-rig-base-v1.glb");
  const { actions } = useAnimations(animations, group);

  const play = useCallback((name: RigAction) => {
    const next = actions[name];
    if (!next) return;

    if (returnTimer.current !== null) window.clearTimeout(returnTimer.current);
    Object.values(actions).forEach((action) => action?.fadeOut(0.22));
    next.reset().fadeIn(0.28);

    if (name === "Idle_Wave") {
      next.setLoop(LoopOnce, 1);
      next.clampWhenFinished = true;
    } else {
      next.setLoop(LoopRepeat, Infinity);
      next.clampWhenFinished = false;
    }

    next.play();
    onPlaying(name);

    if (name === "Idle_Wave") {
      const duration = Math.max(1.4, next.getClip().duration);
      returnTimer.current = window.setTimeout(() => {
        next.fadeOut(0.24);
        const idle = actions.Idle_Base;
        if (!idle) return;
        idle.reset().setLoop(LoopRepeat, Infinity).fadeIn(0.3).play();
        onPlaying("Idle_Base");
        returnTimer.current = null;
      }, duration * 1000);
    }
  }, [actions, onPlaying]);

  useEffect(() => {
    play(requestedAction);
  }, [play, requestedAction]);

  useEffect(() => () => {
    if (returnTimer.current !== null) window.clearTimeout(returnTimer.current);
  }, []);

  return (
    <group ref={group} position={[0, -2.08, 0]} scale={2.45}>
      <primitive object={scene} />
    </group>
  );
}

type Props = {
  action: RigAction;
  onPlaying: (action: RigAction) => void;
};

export function XiaoheRigPreview({ action, onPlaying }: Props) {
  return (
    <Canvas
      camera={{ position: [0, 0.15, 7.6], fov: 35 }}
      dpr={[1, 1.75]}
      gl={{ antialias: true, alpha: false }}
      shadows
      aria-label="小禾骨骼候选模型动作验收"
    >
      <color attach="background" args={["#18251f"]} />
      <fog attach="fog" args={["#18251f", 9, 16]} />
      <ambientLight intensity={1.25} />
      <directionalLight position={[4, 7, 6]} intensity={3.2} castShadow color="#fff3df" />
      <directionalLight position={[-4, 3, 4]} intensity={2.2} color="#a8e0c1" />
      <pointLight position={[0, 4, -3]} intensity={1.8} color="#d8c7ff" />
      <Suspense fallback={null}>
        <RigModel requestedAction={action} onPlaying={onPlaying} />
        <Environment preset="studio" environmentIntensity={0.45} />
      </Suspense>
      <ContactShadows position={[0, -2.07, 0]} opacity={0.52} scale={7} blur={2.8} far={4.5} />
      <OrbitControls
        makeDefault
        enablePan={false}
        enableZoom
        minDistance={5.8}
        maxDistance={11}
        minPolarAngle={Math.PI / 2.8}
        maxPolarAngle={Math.PI / 1.72}
        target={[0, -0.2, 0]}
      />
    </Canvas>
  );
}

useGLTF.preload("/companion/candidates/xiaohe-rig-base-v1.glb");
