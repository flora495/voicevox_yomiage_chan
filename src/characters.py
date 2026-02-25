# characters.py
from __future__ import annotations

from typing import Literal, TypedDict, Dict, List

# VOICEVOX 用
import json
import requests

# A.I.VOICE 用
from aivoice_python import AIVoiceTTsControl, HostStatus  # [web:312]


Engine = Literal["voicevox", "aivoice"]


class CharacterInfo(TypedDict):
    engine: Engine
    speaker_id: str  # VOICEVOXは数値IDを文字列化, A.I.VOICEはプリセット名など


# ===== 1. VOICEVOX の話者IDを動的取得 =====

VOICEVOX_HOST = "localhost"
VOICEVOX_PORT = 50021
_voicevox_session = requests.Session()


def _voicevox_fetch_speakers():
    url = f"http://{VOICEVOX_HOST}:{VOICEVOX_PORT}/speakers"
    r = _voicevox_session.get(url)
    r.raise_for_status()
    return r.json()


def _voicevox_build_name_to_id_map() -> Dict[str, int]:
    """
    VOICEVOXの /speakers 結果から、
    「キャラ名（スタイル名省略） -> ノーマル系スタイルのid」
    のマップを作る。
    （元の wav.py と同じロジック）
    """
    data = _voicevox_fetch_speakers()
    mapping: Dict[str, int] = {}

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


# ===== 2. A.I.VOICE のボイス名を取得 =====

def _aivoice_get_voice_names() -> List[str]:
    """
    A.I.VOICE Editor から利用可能なボイス名リストを取得する。
    （aivoice-python の README に基づく）[web:312]
    """
    tts = AIVoiceTTsControl()
    host_names = tts.get_available_host_names()
    if not host_names:
        return []

    tts.initialize(host_names[0])

    if tts.status == HostStatus.NotRunning:
        tts.start_host()

    tts.connect()
    voices = list(tts.voice_names)  # プリセット名とは別に必要なら voice_preset_names も使える[web:312]
    tts.disconnect()
    return voices


# ===== 3. キャラクタ定義（キャラ名だけ固定、IDは起動時に埋める） =====

# ここに「Botで使いたいキャラ名」を並べる。
# VOICEVOX用キャラ
VOICEVOX_CHARACTER_NAMES = [
    "ずんだもん",
    "四国めたん",
    "春日部つむぎ",
    "東北きりたん",
    "東北ずん子",
    "中国うさぎ",
    "あんこもん",
]

# A.I.VOICE用キャラ（実際の環境で存在する名前に合わせて調整）
AIVOICE_CHARACTER_NAMES = [
    "紲星 あかり"
]


# Bot全体のデフォルトキャラ
DEFAULT_CHARACTER_NAME = "ずんだもん"


def _build_character_map() -> Dict[str, CharacterInfo]:
    char_map: Dict[str, CharacterInfo] = {}

    # --- VOICEVOX 側 ---
    try:
        vv_name_to_id = _voicevox_build_name_to_id_map()
    except Exception as e:
        print("[WARN] VOICEVOX speakers の取得に失敗しました:", e)
        vv_name_to_id = {}

    for name in VOICEVOX_CHARACTER_NAMES:
        sid = vv_name_to_id.get(name)
        if sid is None:
            print(f"[WARN] VOICEVOX speaker '{name}' not found in /speakers")
            continue
        char_map[name] = {
            "engine": "voicevox",
            "speaker_id": str(sid),
        }

    # --- A.I.VOICE 側 ---
    try:
        available_voices = set(_aivoice_get_voice_names())
    except Exception as e:
        print("[WARN] A.I.VOICE voice_names の取得に失敗しました:", e)
        available_voices = set()

    for name in AIVOICE_CHARACTER_NAMES:
        if name not in available_voices:
            print(f"[WARN] A.I.VOICE voice '{name}' not found in voice_names")
            continue
        # A.I.VOICE 側は「名前 = speaker_id」として扱う
        char_map[name] = {
            "engine": "aivoice",
            "speaker_id": name,
        }

    # デフォルトキャラがマップに無ければ、適当に一つ目をデフォルト扱いにする
    if DEFAULT_CHARACTER_NAME not in char_map and char_map:
        any_name = next(iter(char_map.keys()))
        print(
            f"[WARN] DEFAULT_CHARACTER_NAME '{DEFAULT_CHARACTER_NAME}' not in CHARACTER_MAP. "
            f"Fallback to '{any_name}'."
        )

    return char_map


# 起動時に一度だけ構築
CHARACTER_MAP: Dict[str, CharacterInfo] = _build_character_map()
