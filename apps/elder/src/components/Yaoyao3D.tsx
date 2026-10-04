"use client";

import { Suspense, useCallback, useEffect, useRef } from "react";
import { Canvas } from "@react-three/fiber";
import { ContactShadows, Environment, OrbitControls, useAnimations, useGLTF } from "@react-three/drei";
import { Group, LoopOnce, LoopRepeat } from "three";

export const YAOYAO_ACTIONS = [
  "Idle_Base",
  "Idle_Look",
  "Idle_Shift",
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

export const COMPANION_SKINS = [
  { id: "yaoyao", name: "遥遥", description: "温柔青年", swatch: "#75a78a" },
  { id: "xiaohe", name: "小禾", description: "双丸子头小女孩", swatch: "#ec9b66" },
  { id: "tuantuan", name: "团团", description: "蓝黄运动装小男孩", swatch: "#6fa5df" },
  { id: "nuannuan", name: "暖暖", description: "温柔短发女性", swatch: "#cf7d8b" }
] as const;

export type CompanionSkin = (typeof COMPANION_SKINS)[number]["id"];

const ACTION_LABELS: Record<YaoyaoAction, string> = {
  Idle_Base: "自然呼吸",
  Idle_Look: "环顾观察",
  Idle_Shift: "重心换腿",
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
  skin: CompanionSkin;
  requestedAction: YaoyaoAction;
  onPlaying: (action: YaoyaoAction) => void;
};

function Model({ skin, requestedAction, onPlaying }: ModelProps) {
  const group = useRef<Group>(null);
  const returnTimer = useRef<number | null>(null);
  const { scene, animations } = useGLTF(`/companion/${skin}-blockout-v1.glb`);
  const { actions } = useAnimations(animations, group);

  const play = useCallback((name: YaoyaoAction) => {
    const next = actions[name];
    if (!next) return;
    if (returnTimer.current !== null) window.clearTimeout(returnTimer.current);
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
      returnTimer.current = window.setTimeout(() => {
        next.fadeOut(0.22);
        const idle = actions.Idle_Base;
        if (!idle) return;
        idle.reset().setLoop(LoopRepeat, Infinity).fadeIn(0.25).play();
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
    <group ref={group} position={[0, -1.3, 0]} scale={0.65}>
      <primitive object={scene} />
    </group>
  );
}

type Props = {
  skin: CompanionSkin;
  action: YaoyaoAction;
  onPlaying: (action: YaoyaoAction) => void;
};

export function Yaoyao3D({ skin, action, onPlaying }: Props) {
  const skinName = COMPANION_SKINS.find((item) => item.id === skin)?.name ?? "陪伴角色";
  return (
    <Canvas
      camera={{ position: [0, -1.1, 11], fov: 38 }}
      dpr={[1, 1.75]}
      gl={{ antialias: true, alpha: true }}
      aria-label={`${skinName}三维角色动作预览`}
    >
      <color attach="background" args={["#e9f2eb"]} />
      <fog attach="fog" args={["#e9f2eb", 10, 18]} />
      <ambientLight intensity={1.45} />
      <directionalLight position={[4, 8, 6]} intensity={2.4} castShadow />
      <directionalLight position={[-5, 3, 3]} intensity={1.2} color="#d9cff7" />
      <Suspense fallback={null}>
        <Model key={skin} skin={skin} requestedAction={action} onPlaying={onPlaying} />
        <Environment preset="studio" environmentIntensity={0.35} />
      </Suspense>
      <ContactShadows position={[0, -1.32, 0]} opacity={0.35} scale={6} blur={2.6} far={4} />
      <OrbitControls
        makeDefault
        enablePan={false}
        enableZoom
        minDistance={8}
        maxDistance={15}
        minPolarAngle={Math.PI / 2.6}
        maxPolarAngle={Math.PI / 1.75}
        target={[0, -1.3, 0]}
      />
    </Canvas>
  );
}

export function actionLabel(action: YaoyaoAction): string {
  return ACTION_LABELS[action];
}

COMPANION_SKINS.forEach(({ id }) => useGLTF.preload(`/companion/${id}-blockout-v1.glb`));
