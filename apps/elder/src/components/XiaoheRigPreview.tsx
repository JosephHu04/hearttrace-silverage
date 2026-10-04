"use client";

import { Suspense, useCallback, useEffect, useMemo, useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { ContactShadows, Environment, OrbitControls, useAnimations, useGLTF } from "@react-three/drei";
import { Bone, Group, LoopRepeat, Quaternion, Vector3 } from "three";

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
  const time = useRef(0);
  const actionTime = useRef(0);
  const currentAction = useRef<RigAction>("Idle_Base");
  const { scene, animations } = useGLTF("/companion/preview/xiaohe-motion-v2.glb");
  const { actions } = useAnimations(animations, group);
  const bones = useMemo(() => ({
    head: scene.getObjectByName("Head") as Bone | undefined,
    spine: scene.getObjectByName("spine_02") as Bone | undefined,
    rightUpperArm: scene.getObjectByName("upperarm_r") as Bone | undefined,
    rightLowerArm: scene.getObjectByName("lowerarm_r") as Bone | undefined,
    rightHand: scene.getObjectByName("hand_r") as Bone | undefined,
    leftUpperArm: scene.getObjectByName("upperarm_l") as Bone | undefined
  }), [scene]);
  const rotation = useMemo(() => new Quaternion(), []);
  const screenAxis = useMemo(() => new Vector3(0, 0, 1), []);
  const turnAxis = useMemo(() => new Vector3(0, 1, 0), []);
  const worldPosition = useMemo(() => new Vector3(), []);
  const childPosition = useMemo(() => new Vector3(), []);
  const currentDirection = useMemo(() => new Vector3(), []);
  const desiredDirection = useMemo(() => new Vector3(), []);
  const worldRotation = useMemo(() => new Quaternion(), []);
  const parentRotation = useMemo(() => new Quaternion(), []);
  const targetRotation = useMemo(() => new Quaternion(), []);
  const fingerBones = useMemo(() => {
    const fingers: Bone[] = [];
    scene.traverse((object) => {
      if (object instanceof Bone && /^(index|middle|ring|pinky|thumb)_/.test(object.name)) {
        fingers.push(object);
      }
    });
    return fingers;
  }, [scene]);

  useFrame((_, delta) => {
    time.current += delta;
    actionTime.current += delta;
    const t = time.current;
    const add = (bone: Bone | undefined, axis: Vector3, radians: number) => {
      if (bone) bone.quaternion.premultiply(rotation.setFromAxisAngle(axis, radians));
    };
    const pointBone = (bone: Bone | undefined, nextBone: Bone | undefined, target: Vector3, amount: number) => {
      if (!bone || !nextBone || !bone.parent) return;
      bone.updateWorldMatrix(true, true);
      bone.getWorldPosition(worldPosition);
      nextBone.getWorldPosition(childPosition);
      currentDirection.subVectors(childPosition, worldPosition).normalize();
      desiredDirection.copy(target).normalize();
      rotation.setFromUnitVectors(currentDirection, desiredDirection);
      bone.getWorldQuaternion(worldRotation);
      bone.parent.getWorldQuaternion(parentRotation);
      targetRotation.copy(parentRotation.invert()).multiply(rotation).multiply(worldRotation);
      bone.quaternion.slerp(targetRotation, amount);
      bone.updateWorldMatrix(true, true);
    };

    // Small, asynchronous head, torso and hand movement keeps the idle alive.
    const breathing = Math.sin(t * 2.2);
    const lookPhase = (t % 9.5) / 9.5;
    const look = Math.sin(Math.PI * Math.min(1, Math.max(0, (lookPhase - .14) / .66))) ** 2;
    const shiftPhase = ((t + 3.5) % 12) / 12;
    const shift = Math.sin(Math.PI * Math.min(1, Math.max(0, (shiftPhase - .17) / .61))) ** 2;
    add(bones.spine, screenAxis, breathing * .011 + shift * .024);
    add(bones.spine, turnAxis, look * .022);
    add(bones.head, turnAxis, Math.sin(t * .87) * .025 + Math.sin(t * 1.47) * .007 + look * .072);
    add(bones.head, screenAxis, Math.sin(t * 1.12) * .012);
    add(bones.leftUpperArm, screenAxis, Math.sin(t * 1.53 + .8) * .012 + shift * .015);
    for (const finger of fingerBones) finger.quaternion.slerp(targetRotation.identity(), .14);

    if (currentAction.current === "Idle_Wave") {
      const length = 2.8;
      const progress = Math.min(1, actionTime.current / length);
      const ease = Math.sin(progress * Math.PI) ** 2;
      const side = (bones.rightUpperArm?.getWorldPosition(worldPosition).x ?? -1) >= 0 ? 1 : -1;
      pointBone(bones.rightUpperArm, bones.rightLowerArm, new Vector3(side * .9, .75, .05), ease);
      pointBone(bones.rightLowerArm, bones.rightHand, new Vector3(side * .08, .98, .08), ease);
      add(bones.rightHand, screenAxis, Math.sin(progress * Math.PI * 6) * .16 * ease);
      for (const finger of fingerBones) {
        if (finger.name.endsWith("_r")) finger.quaternion.slerp(targetRotation.identity(), ease * .7);
      }
    } else if (currentAction.current === "Talk" || currentAction.current === "Sitting_Talk") {
      add(bones.head, screenAxis, Math.sin(t * 3.4) * .018);
      add(bones.rightHand, screenAxis, Math.sin(t * 2.6) * .045);
    }
  });

  const play = useCallback((name: RigAction) => {
    const next = name === "Idle_Wave" ? actions.Idle_Base : actions[name];
    if (!next) return;

    if (returnTimer.current !== null) window.clearTimeout(returnTimer.current);
    Object.values(actions).forEach((action) => action?.fadeOut(0.22));
    next.reset().fadeIn(0.28);

    next.setLoop(LoopRepeat, Infinity);
    next.clampWhenFinished = false;

    next.play();
    currentAction.current = name;
    actionTime.current = 0;
    onPlaying(name);

    if (name === "Idle_Wave") {
      const duration = 2.8;
      returnTimer.current = window.setTimeout(() => {
        next.fadeOut(0.24);
        const idle = actions.Idle_Base;
        if (!idle) return;
        idle.reset().setLoop(LoopRepeat, Infinity).fadeIn(0.3).play();
        currentAction.current = "Idle_Base";
        actionTime.current = 0;
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
      camera={{ position: [0, 0.15, 10.8], fov: 35 }}
      dpr={[1, 1.75]}
      gl={{ antialias: true, alpha: false }}
      shadows
      aria-label="小禾骨骼候选模型动作验收"
    >
      <color attach="background" args={["#18251f"]} />
      <fog attach="fog" args={["#18251f", 9, 16]} />
      <ambientLight intensity={0.55} />
      <directionalLight position={[4, 7, 6]} intensity={1.45} castShadow color="#fff3df" />
      <directionalLight position={[-4, 3, 4]} intensity={0.65} color="#a8e0c1" />
      <pointLight position={[0, 4, -3]} intensity={0.55} color="#d8c7ff" />
      <Suspense fallback={null}>
        <RigModel requestedAction={action} onPlaying={onPlaying} />
        <Environment preset="studio" environmentIntensity={0.22} />
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

useGLTF.preload("/companion/preview/xiaohe-motion-v2.glb");
