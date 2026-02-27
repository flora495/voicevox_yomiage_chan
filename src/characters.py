from __future__ import annotations

from typing import Literal, TypedDict, Dict, List
from pathlib import Path
import json

import requests
from aivoice_python import AIVoiceTTsControl, HostStatus  # [web:312]

Engine = Literal["voicevox", "aivoice"]


class CharacterInfo(TypedDict):
    engine: Engine
    speaker_id: str          # VOICEVOX: 数値IDをstr化, A.I.VOICE: キャラ名そのもの
    allowed_user_ids: list[int]


# ===== VOICEVOX: /speakers から動的に ID 解決 =====
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "settings" / "config.json"
with CONFIG_PATH.open("r", encoding="utf-8") as f:
    CONFIG: dict = json.load(f)

VOICEVOX_HOST = CONFIG["voicevox"]["HOST"]
VOICEVOX_PORT = CONFIG["voicevox"]["PORT"]
_voicevox_session = requests.Session()


def _voicevox_fetch_speakers():
    url = f"http://{VOICEVOX_HOST}:{VOICEVOX_PORT}/speakers"
    r = _voicevox_session.get(url)
    r.raise_for_status()
    return r.json()


def _voicevox_build_name_to_id_map() -> dict[str, int]:
    data = _voicevox_fetch_speakers()
    mapping: dict[str, int] = {}

    preferred_style_names = ["ノーマル", "normal", "ふつう"]

    for speaker in data:
        name = speaker["name"]
        styles = speaker["styles"]

        chosen_id = None
        for pref in preferred_style_names:
            for style in styles:
                if pref in style["name"]:
                    chosen_id = style["id"]
                    break
            if chosen_id is not None:
                break

        if chosen_id is None and styles:
            chosen_id = styles[0]["id"]

        if chosen_id is not None:
            mapping[name] = chosen_id

    return mapping


# ===== A.I.VOICE: 利用可能なプリセット名一覧（バリデーション用・任意） =====

def _aivoice_get_voice_preset_names() -> list[str]:
    tts = AIVoiceTTsControl()
    host_names = tts.get_available_host_names()
    if not host_names:
        return []

    tts.initialize(host_names[0])
    if tts.status == HostStatus.NotRunning:
        tts.start_host()
    tts.connect()

    names = list(tts.voice_preset_names)  # or voice_names[web:312]
    tts.disconnect()
    return names


# ===== JSON 読み込み & CHARACTER_MAP 構築 =====

CONF_PATH = Path("settings") / "characters_config.json"


def _load_raw_config():
    with CONF_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def _build_character_map() -> tuple[dict[str, CharacterInfo], str]:
    conf = _load_raw_config()
    raw_chars: dict[str, dict] = conf.get("characters", {})
    default_name: str = conf.get("default_character", "")

    char_map: dict[str, CharacterInfo] = {}

    # VOICEVOX name -> id
    try:
        vv_name_to_id = _voicevox_build_name_to_id_map()
    except Exception as e:
        print("[WARN] VOICEVOX speakers の取得に失敗しました:", e)
        vv_name_to_id = {}

    # A.I.VOICE のプリセット名一覧（存在チェック用・任意）
    try:
        aivoice_presets = set(_aivoice_get_voice_preset_names())
    except Exception as e:
        print("[WARN] A.I.VOICE voice_preset_names の取得に失敗しました:", e)
        aivoice_presets = set()

    for name, info in raw_chars.items():
        engine: Engine = info["engine"]
        allowed: list[int] = info.get("allowed_user_ids", [])

        if engine == "voicevox":
            sid = vv_name_to_id.get(name)
            if sid is None:
                print(f"[WARN] VOICEVOX speaker '{name}' not found in /speakers")
                continue
            char_map[name] = {
                "engine": "voicevox",
                "speaker_id": str(sid),
                "allowed_user_ids": allowed,
            }

        elif engine == "aivoice":
            # A.I.VOICE はキャラ名＝speaker_id として扱う
            speaker_id = name
            if aivoice_presets and speaker_id not in aivoice_presets:
                print(f"[WARN] A.I.VOICE preset '{speaker_id}' not found in voice_preset_names")
            char_map[name] = {
                "engine": "aivoice",
                "speaker_id": speaker_id,
                "allowed_user_ids": allowed,
            }

        else:
            print(f"[WARN] Unknown engine '{engine}' for character '{name}'")
            continue

    # デフォルトキャラ補正
    if default_name not in char_map and char_map:
        fallback = next(iter(char_map.keys()))
        print(
            f"[WARN] default_character '{default_name}' not in CHARACTER_MAP. "
            f"Fallback to '{fallback}'."
        )
        default_name = fallback

    return char_map, default_name


CHARACTER_MAP, DEFAULT_CHARACTER_NAME = _build_character_map()
