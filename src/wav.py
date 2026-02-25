# wav.py
import json
from pathlib import Path

import requests

HOST = "localhost"
PORT = 50021

# ① セッションをグローバルに 1 個だけ作る
session = requests.Session()


def tts_to_wav(text: str, out_path: Path, speaker_id: int) -> Path:
    """
    VOICEVOXに text を渡して、speaker_id の声で WAV を out_path に保存する。
    """

    # 1. クエリ生成（session を使う）
    q = session.post(
        f"http://{HOST}:{PORT}/audio_query",
        params={"text": text, "speaker": speaker_id},
    )
    q.raise_for_status()
    query = q.json()

    # ② クエリに軽量化パラメータを追加
    # 話速を少し早く（例: 1.1倍）、前後の無音を削る
    query["speedScale"] = 1.1          # 1.0 が標準、1.1〜1.2 くらいで様子見
    query["prePhonemeLength"] = 0.0    # 発話前の無音
    query["postPhonemeLength"] = 0.0   # 発話後の無音

    # 2. 合成してwav取得（こちらも session を使う）
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
