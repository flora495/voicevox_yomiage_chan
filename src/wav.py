# wav.py
import json
from pathlib import Path

import requests

HOST = "localhost"
PORT = 50021


def tts_to_wav(text: str, out_path: Path, speaker_id: int) -> Path:
    """
    VOICEVOXに text を渡して、speaker_id の声で WAV を out_path に保存する。
    """
    # 1. クエリ生成
    q = requests.post(
        f"http://{HOST}:{PORT}/audio_query",
        params={"text": text, "speaker": speaker_id},
    )
    q.raise_for_status()
    query = q.json()

    # 2. 合成してwav取得
    s = requests.post(
        f"http://{HOST}:{PORT}/synthesis",
        params={"speaker": speaker_id},
        data=json.dumps(query),
    )
    s.raise_for_status()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("wb") as f:
        f.write(s.content)
    return out_path

