"""Check whether a GLB satisfies the Xiaohe technical delivery contract.

This cannot judge artistic quality. The side-by-side visual review in
ASSET_ACCEPTANCE.md is a separate, mandatory release gate.
"""

from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path


REQUIRED_ACTIONS = {"Idle_Base", "Idle_Wave", "Talk", "Sitting_Idle", "Sitting_Talk"}
REQUIRED_BONES = {
    "Head", "spine_02", "upperarm_l", "lowerarm_l", "hand_l",
    "upperarm_r", "lowerarm_r", "hand_r", "thigh_l", "calf_l",
    "thigh_r", "calf_r",
}
REQUIRED_FACE_STATES = {
    "blink": {"blink", "eye_blink"},
    "smile": {"smile", "happy"},
    "concern": {"concern", "sad", "worried"},
    "viseme_a": {"viseme_a", "mouth_a", "a"},
    "viseme_i": {"viseme_i", "mouth_i", "i"},
    "viseme_u": {"viseme_u", "mouth_u", "u"},
    "viseme_e": {"viseme_e", "mouth_e", "e"},
    "viseme_o": {"viseme_o", "mouth_o", "o"},
}
MAX_BYTES = 12 * 1024 * 1024


def read_glb(path: Path) -> dict:
    with path.open("rb") as asset:
        magic, version, total_length = struct.unpack("<4sII", asset.read(12))
        if magic != b"glTF" or version != 2 or total_length != path.stat().st_size:
            raise ValueError("not a valid glTF 2.0 binary")
        json_length, chunk_type = struct.unpack("<I4s", asset.read(8))
        if chunk_type != b"JSON":
            raise ValueError("GLB first chunk is not JSON")
        return json.loads(asset.read(json_length))


def inspect(path: Path) -> tuple[dict, list[str]]:
    gltf = read_glb(path)
    nodes = gltf.get("nodes", [])
    joints = {
        nodes[index].get("name", "")
        for skin in gltf.get("skins", [])
        for index in skin.get("joints", [])
        if index < len(nodes)
    }
    actions = {animation.get("name", "") for animation in gltf.get("animations", [])}
    morph_names = {
        name.lower()
        for mesh in gltf.get("meshes", [])
        for name in mesh.get("extras", {}).get("targetNames", [])
    }
    missing_face_states = sorted(
        label for label, aliases in REQUIRED_FACE_STATES.items()
        if not aliases.intersection(morph_names)
    )
    report = {
        "file": str(path),
        "size_mib": round(path.stat().st_size / 1024 / 1024, 2),
        "joint_count": len(joints),
        "missing_bones": sorted(REQUIRED_BONES - joints),
        "animations": sorted(actions),
        "missing_animations": sorted(REQUIRED_ACTIONS - actions),
        "morph_targets": sorted(morph_names),
        "missing_face_states": missing_face_states,
    }
    failures = []
    if path.stat().st_size > MAX_BYTES:
        failures.append("GLB exceeds 12 MiB")
    if report["missing_bones"]:
        failures.append("required skeleton bones are missing")
    if report["missing_animations"]:
        failures.append("required action clips are missing")
    if missing_face_states:
        failures.append("blink, expressions or speech mouth shapes are missing")
    return report, failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("glb", type=Path)
    args = parser.parse_args()
    try:
        report, failures = inspect(args.glb)
    except (OSError, ValueError, json.JSONDecodeError, struct.error) as exc:
        parser.error(str(exc))
    print(json.dumps({**report, "technical_pass": not failures, "failures": failures}, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
