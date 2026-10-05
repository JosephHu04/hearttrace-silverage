"use client";

import { Suspense, useEffect, useMemo, useRef, useState, type RefObject } from "react";
import { Canvas, createPortal, useFrame } from "@react-three/fiber";
import { ContactShadows, Environment, useAnimations, useGLTF } from "@react-three/drei";
import { Group, MathUtils, Mesh, Object3D } from "three";

export type MascotKind = "moss" | "cloud";
export type MascotMood = "idle" | "hello" | "listen" | "happy" | "wink" | "curious" | "talk" | "think" | "alert" | "offline";
export const MASCOT_SKIN_STORAGE_KEY = "hearttrace.elder.mascot-kind";

const SOURCES: Record<MascotKind, string> = {
  moss: "/companion/mascots/moss-jelly-cc0.glb",
  cloud: "/companion/mascots/cloud-jelly-cc0.glb"
};
const SPARKLES: [number, number, number][] = [
  [-0.19, 0.23, 0.035], [0.19, 0.19, 0.035],
  [-0.16, 0.06, 0.075], [0.17, 0.08, 0.075]
];

function pulse(time: number, center: number, width: number): number {
  const distance = Math.abs(time - center) / width;
  return distance >= 1 ? 0 : 0.5 + 0.5 * Math.cos(Math.PI * distance);
}

function Model({ kind, mood, trigger, reducedMotion, mouthLevelRef, onInteract }: {
  kind: MascotKind; mood: MascotMood; trigger: number; reducedMotion: boolean; mouthLevelRef?: RefObject<number>; onInteract?: () => void;
}) {
  const root = useRef<Group>(null);
  const sparkleGroup = useRef<Group>(null);
  const speechMouth = useRef<Mesh>(null);
  const openMouth = useRef(false);
  const mouthOpening = useRef(0);
  const elapsed = useRef(0);
  const actionTime = useRef(0);
  const { scene, animations } = useGLTF(SOURCES[kind]);
  // useGLTF caches its scene; each visible mascot needs independent face nodes.
  const modelScene = useMemo(() => scene.clone(true), [scene]);
  const { actions } = useAnimations(animations, modelScene);
  const features = useMemo(() => {
    const find = (name: string) => modelScene.getObjectByName(name) as Object3D | undefined;
    const eyes = [find("eye-left"), find("eye-right")];
    const brows = [find("brow-left"), find("brow-right")];
    const cheeks = [find("blush-left"), find("blush-right")];
    const ears = [find("ear-left"), find("ear-right")];
    const crown = find("crown");
    const mouth = find("mouth");
    return {
      eyes, brows, cheeks, ears, crown, mouth,
      eyeScales: eyes.map((eye) => eye?.scale.clone()),
      eyePositions: eyes.map((eye) => eye?.position.clone()),
      browPositions: brows.map((brow) => brow?.position.clone()),
      browRotations: brows.map((brow) => brow?.rotation.z ?? 0),
      cheekScales: cheeks.map((cheek) => cheek?.scale.clone()),
      earRotations: ears.map((ear) => ear?.rotation.z ?? 0),
      crownRotation: crown?.rotation.z ?? 0,
      mouthPosition: mouth?.position.clone(),
      mouthScale: mouth?.scale.clone(),
      mouthRotation: mouth?.rotation.z ?? 0
    };
  }, [modelScene]);

  useEffect(() => {
    const bob = actions.bob;
    if (!reducedMotion) {
      bob?.reset().fadeIn(0.35).play();
      if (bob) bob.timeScale = 0.38;
    }
    return () => { bob?.stop(); };
  }, [actions, reducedMotion]);
  useEffect(() => { actionTime.current = 0; }, [mood, trigger]);

  useFrame((state, delta) => {
    if (!root.current) return;
    const dt = Math.min(delta, 0.05);
    elapsed.current += dt;
    actionTime.current += dt;
    const t = elapsed.current;
    const a = actionTime.current;
    const motion = reducedMotion ? 0 : 1;
    const breathing = Math.sin(t * (mood === "listen" ? 1.3 : 1.75)) * motion;
    const idleCycle = t % 13.4;
    const idlePeek = mood === "idle" ? pulse(idleCycle, 4.0, 1.3) * motion : 0;
    const idlePerk = mood === "idle" ? pulse(idleCycle, 9.2, 0.85) * motion : 0;
    const helloDip = mood === "hello" ? pulse(a, 0.25, 0.22) * motion : 0;
    const helloRise = mood === "hello" ? pulse(a, 0.72, 0.43) * motion : 0;
    const happyHop = mood === "happy" ? (pulse(a, 0.6, 0.34) + pulse(a, 1.32, 0.37)) * motion : 0;
    const happyLand = mood === "happy" ? (pulse(a, 0.94, 0.2) + pulse(a, 1.7, 0.24)) * motion : 0;
    const wink = mood === "wink" ? pulse(a, 0.58, 0.32) : 0;
    const curious = mood === "curious" ? Math.min(1, a / 0.42) : 0;
    const listen = mood === "listen" ? 1 : 0;
    const thinking = mood === "think" ? 1 : 0;
    const talking = mood === "talk" ? 1 : 0;
    const alert = mood === "alert" ? 1 : 0;
    const offline = mood === "offline";

    root.current.position.y = MathUtils.damp(root.current.position.y,
      (happyHop * 0.23 + helloRise * 0.11 - helloDip * 0.038 + idlePerk * 0.022 + breathing * 0.012) * motion, 8, dt);
    root.current.position.z = MathUtils.damp(root.current.position.z,
      (helloRise * 0.06 + listen * 0.035 + curious * 0.035) * motion, 5, dt);
    root.current.rotation.x = MathUtils.damp(root.current.rotation.x,
      (-listen * 0.095 + helloDip * 0.08 - helloRise * 0.07 + talking * Math.sin(t * 3.4) * 0.023 + Math.sin(t * 0.8) * 0.009 * motion), 5, dt);
    root.current.rotation.y = MathUtils.damp(root.current.rotation.y,
      (Math.sin(t * 0.45) * 0.055 + idlePeek * 0.19 + wink * 0.12 - curious * 0.08 - thinking * 0.09 + alert * Math.sin(t * 6) * 0.025) * motion, 4, dt);
    root.current.rotation.z = MathUtils.damp(root.current.rotation.z,
      (listen * 0.085 + curious * 0.16 + thinking * -0.075 + wink * -0.09 + helloRise * -0.11 + Math.sin(t * 0.9) * 0.014 + idlePerk * -0.08) * motion, 6, dt);
    const scale = offline ? 4.02 : 4.15;
    root.current.scale.set(
      scale * (1 + happyLand * 0.055 - happyHop * 0.03 + breathing * 0.007),
      scale * (1 - happyLand * 0.075 + happyHop * 0.045 + breathing * 0.012),
      scale * (1 + happyLand * 0.035 - happyHop * 0.025)
    );

    const blinkPhase = t % 7.7;
    const blink = Math.max(pulse(blinkPhase, 2.3, 0.09), pulse(blinkPhase, 2.51, 0.07) * 0.75, pulse(blinkPhase, 6.45, 0.11));
    features.eyes.forEach((eye, index) => {
      const baseScale = features.eyeScales[index];
      const basePosition = features.eyePositions[index];
      if (!eye || !baseScale || !basePosition) return;
      const smileEye = mood === "happy" ? 0.46 : mood === "hello" ? helloRise * 0.19 : mood === "wink" ? 0.12 : 0;
      const closed = Math.max(blink * 0.9, index === 0 ? wink * 0.94 : 0, smileEye);
      eye.scale.x = MathUtils.damp(eye.scale.x, baseScale.x * (mood === "happy" ? 1.13 : 1), 10, dt);
      eye.scale.y = MathUtils.damp(eye.scale.y, baseScale.y * (1 - closed), 20, dt);
      eye.rotation.z = MathUtils.damp(eye.rotation.z, mood === "happy" ? (index === 0 ? -0.13 : 0.13) : 0, 8, dt);
      const pointerX = MathUtils.clamp(state.pointer.x, -1, 1) * 0.006;
      const pointerY = MathUtils.clamp(state.pointer.y, -1, 1) * 0.004;
      eye.position.x = MathUtils.damp(eye.position.x, basePosition.x + pointerX + idlePeek * 0.004 + curious * 0.004, 6, dt);
      eye.position.y = MathUtils.damp(eye.position.y, basePosition.y + pointerY + (mood === "happy" ? 0.003 : 0) + thinking * 0.004, 6, dt);
    });
    features.brows.forEach((brow, index) => {
      const basePosition = features.browPositions[index];
      if (!brow || !basePosition) return;
      const lift = mood === "happy" ? 0.012 : mood === "hello" ? helloRise * 0.009 : mood === "curious" ? (index === 0 ? 0.016 : -0.003) : alert ? 0.012 : thinking ? (index === 0 ? 0.007 : 0.003) : listen ? -0.004 : idlePerk * 0.004;
      brow.position.y = MathUtils.damp(brow.position.y, basePosition.y + lift, 7, dt);
      const tilt = mood === "happy" ? (index === 0 ? 0.1 : -0.1) : mood === "curious" ? (index === 0 ? -0.2 : 0.07) : thinking ? (index === 0 ? -0.12 : 0.06) : listen ? (index === 0 ? 0.08 : -0.08) : 0;
      brow.rotation.z = MathUtils.damp(brow.rotation.z, features.browRotations[index] + tilt, 7, dt);
    });
    features.cheeks.forEach((cheek, index) => {
      const base = features.cheekScales[index];
      if (!cheek || !base) return;
      const warmth = mood === "happy" ? 1.38 : mood === "hello" || mood === "wink" ? 1.2 : 1;
      cheek.scale.x = MathUtils.damp(cheek.scale.x, base.x * warmth, 7, dt);
      cheek.scale.y = MathUtils.damp(cheek.scale.y, base.y * warmth, 7, dt);
    });
    features.ears.forEach((ear, index) => {
      if (!ear) return;
      const direction = index === 0 ? 1 : -1;
      const reaction = mood === "happy" ? (happyHop + happyLand * 0.45) * 0.24 : mood === "hello" ? helloRise * 0.29 : mood === "wink" ? wink * 0.25 : mood === "curious" ? curious * 0.1 : listen ? 0.075 : idlePerk * 0.14;
      ear.rotation.z = MathUtils.damp(ear.rotation.z,
        features.earRotations[index] + direction * (Math.sin(t * 1.2 + index * 0.7) * 0.035 * motion + reaction * motion), 9, dt);
    });
    if (features.crown) {
      features.crown.rotation.z = MathUtils.damp(features.crown.rotation.z,
        features.crownRotation + (Math.sin(t * 1.1) * 0.03 + helloRise * 0.08 - curious * 0.055 + happyHop * 0.08) * motion, 7, dt);
    }
    const speaking = mood === "talk"
      ? MathUtils.clamp(mouthLevelRef ? mouthLevelRef.current : Math.abs(Math.sin(t * 6.8)), 0, 1)
      : 0;
    mouthOpening.current = MathUtils.damp(mouthOpening.current, speaking, 12, dt);
    if (openMouth.current) {
      if (mouthOpening.current < 0.11) openMouth.current = false;
    } else if (mouthOpening.current > 0.22) openMouth.current = true;
    if (features.mouth && features.mouthScale && features.mouthPosition) {
      const smile = mood === "happy" ? 1.28 : mood === "hello" || mood === "wink" ? 1.12 : listen ? 0.93 : thinking ? 0.87 : 1 + idlePerk * 0.05;
      features.mouth.visible = !openMouth.current;
      features.mouth.scale.x = MathUtils.damp(features.mouth.scale.x, features.mouthScale.x * smile, 9, dt);
      features.mouth.scale.y = MathUtils.damp(features.mouth.scale.y, features.mouthScale.y * (1 + (mood === "happy" ? 0.2 : 0)), 11, dt);
      features.mouth.position.y = MathUtils.damp(features.mouth.position.y, features.mouthPosition.y + (mood === "happy" ? 0.003 : 0), 7, dt);
      features.mouth.rotation.z = MathUtils.damp(features.mouth.rotation.z, features.mouthRotation + wink * 0.1, 7, dt);
    }
    if (speechMouth.current && features.mouth) {
      // The open-mouth shape must follow the GLB body's animation. A separate
      // root-level mesh drifted below the smile and remained visible at rest.
      speechMouth.current.position.set(features.mouth.position.x, features.mouth.position.y + 0.004, features.mouth.position.z + 0.008);
      speechMouth.current.visible = openMouth.current;
      speechMouth.current.scale.x = MathUtils.damp(speechMouth.current.scale.x, 0.004 + mouthOpening.current * 0.014, 14, dt);
      speechMouth.current.scale.y = MathUtils.damp(speechMouth.current.scale.y, 0.002 + mouthOpening.current * 0.011, 14, dt);
    }
    if (sparkleGroup.current) {
      const strength = (mood === "happy" ? Math.max(happyHop, happyLand * 0.8) : mood === "hello" ? helloRise : mood === "wink" ? wink : 0) * motion;
      sparkleGroup.current.children.forEach((star, index) => {
        star.scale.setScalar(strength * (index % 2 === 0 ? 1 : 0.7));
        star.rotation.z += dt * 1.2 * motion;
        star.position.y = SPARKLES[index][1] + strength * (0.02 + index * 0.008);
      });
    }
  });

  return <group ref={root}>
    <primitive object={modelScene} onClick={onInteract ? (event: { stopPropagation: () => void }) => { event.stopPropagation(); onInteract(); } : undefined} />
    {features.mouthPosition && features.mouth?.parent && createPortal(<mesh ref={speechMouth} visible={false} position={[features.mouthPosition.x, features.mouthPosition.y + 0.004, features.mouthPosition.z + 0.008]} scale={[0.004, 0.002, 0.003]}>
      <sphereGeometry args={[1, 20, 12]} />
      <meshStandardMaterial color="#382d39" roughness={0.8} />
    </mesh>, features.mouth.parent)}
    <group ref={sparkleGroup}>
      {SPARKLES.map((position, index) => <mesh key={index} position={position} scale={0}>
        <octahedronGeometry args={[0.014, 0]} />
        <meshStandardMaterial color={kind === "moss" ? "#fff3a8" : "#c9dcff"} emissive={kind === "moss" ? "#f8ce7a" : "#b6cfff"} emissiveIntensity={0.8} roughness={0.3} />
      </mesh>)}
    </group>
  </group>;
}

export function Mascot3D({ kind = "moss", mood = "idle", trigger = 0, transparent = false, lobby = false, mouthLevelRef, onInteract }: {
  kind?: MascotKind; mood?: MascotMood; trigger?: number; transparent?: boolean; lobby?: boolean; mouthLevelRef?: RefObject<number>; onInteract?: () => void;
}) {
  const [reducedMotion, setReducedMotion] = useState(false);
  useEffect(() => {
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const update = () => setReducedMotion(query.matches);
    update();
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);
  return (
    <Canvas camera={{ position: [0, 1.4, lobby ? 4.2 : 2.85], fov: 34 }} dpr={[1, 1.5]} gl={{ antialias: true, alpha: true }} aria-label="会眨眼和回应的三维精灵">
      {!transparent && <color attach="background" args={["#eff5ee"]} />}
      <ambientLight intensity={0.62} />
      <directionalLight position={[-3, 5, 4]} intensity={1.28} color="#fff8e8" />
      <directionalLight position={[3, 2, -2]} intensity={0.68} color="#d5f4ec" />
      <Suspense fallback={null}>
        <Environment preset="studio" environmentIntensity={0.18} />
        <group position={[0, -0.5, 0]}>
          <Model key={kind} kind={kind} mood={mood} trigger={trigger} reducedMotion={reducedMotion} mouthLevelRef={mouthLevelRef} onInteract={onInteract} />
          <ContactShadows position={[0, -0.015, 0]} opacity={0.23} blur={2.9} scale={3} far={1.8} />
        </group>
      </Suspense>
    </Canvas>
  );
}

useGLTF.preload(SOURCES.moss);
useGLTF.preload(SOURCES.cloud);
