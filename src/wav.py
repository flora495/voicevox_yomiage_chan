# wav.py
import json
from pathlib import Path
import requests

HOST = "localhost"
PORT = 50021

session = requests.Session()


def get_voicevox_speakers(speakers):
    # VOICEVOXの話者IDを /speakers から動的に取得
    speaker_map = build_speaker_name_to_id_map()

    # 使いたいキャラだけピックアップ
    voicevox_speakers = {}

    def add_speaker_if_available(char_name: str):
        sid = speaker_map.get(char_name)
        if sid is not None:
            voicevox_speakers[char_name] = sid
        else:
            print(f"[WARN] VOICEVOX speaker '{char_name}' not found in /speakers")

    # 既存 + 追加したいキャラ
    for name in speakers:
        add_speaker_if_available(name)

    return voicevox_speakers

def fetch_speakers():
    """VOICEVOXエンジンから話者一覧を取得して返す。"""
    url = f"http://{HOST}:{PORT}/speakers"
    r = session.get(url)
    r.raise_for_status()
    return r.json()


def build_speaker_name_to_id_map() -> dict[str, int]:
    """
    VOICEVOXの /speakers 結果から、
    「キャラ名（スタイル名省略） -> ノーマル系スタイルのid」
    のマップを作る。
    """
    data = fetch_speakers()
    mapping: dict[str, int] = {}

    # 「どのスタイルをノーマル扱いにするか」の優先順
    # （環境によってスタイル名が微妙に違う可能性があるので、含まれていたら採用する方式）
    preferred_style_names = ["ノーマル", "normal", "ふつう"]

    for speaker in data:
        name = speaker["name"]              # 例: "ずんだもん"
        styles = speaker["styles"]          # 各スタイル: {"name": "...", "id": ...}

        # 優先スタイルを探す
        chosen_id = None
        for pref in preferred_style_names:
            for style in styles:
                if pref in style["name"]:
                    chosen_id = style["id"]
                    break
            if chosen_id is not None:
                break

        # 見つからなければ、最初のスタイルを採用
        if chosen_id is None and styles:
            chosen_id = styles[0]["id"]

        if chosen_id is not None:
            mapping[name] = chosen_id

    return mapping


def tts_to_wav(text: str, out_path: Path, speaker_id: int) -> Path:
    q = session.post(
        f"http://{HOST}:{PORT}/audio_query",
        params={"text": text, "speaker": speaker_id},
    )
    q.raise_for_status()
    query = q.json()
    query["speedScale"] = 1.1
    query["prePhonemeLength"] = 0.0
    query["postPhonemeLength"] = 0.0

    s = session.post(
        f"http://{HOST}:{PORT}/synthesis",
        params={"speaker": speaker_id},
        data=json.dumps(query),
    )
    s.raise_for_status()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("wb") as f:
        f.write(s.content)
    return out_path


def tts_to_wav_bytes(text: str, speaker_id: int) -> bytes:
    q = session.post(
        f"http://{HOST}:{PORT}/audio_query",
        params={"text": text, "speaker": speaker_id},
    )
    q.raise_for_status()
    query = q.json()
    query["speedScale"] = 1.1
    query["prePhonemeLength"] = 0.0
    query["postPhonemeLength"] = 0.0

    s = session.post(
        f"http://{HOST}:{PORT}/synthesis",
        params={"speaker": speaker_id},
        data=json.dumps(query),
    )
    s.raise_for_status()
    return s.content
