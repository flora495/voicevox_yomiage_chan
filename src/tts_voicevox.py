# tts_voicevox.py
from __future__ import annotations
import json
import requests

from abstract_tts_client import AbstractTTSClient

session = requests.Session()

class VoicevoxClient(AbstractTTSClient):
    def _fetch_speakers(self):
        url = f"http://{self.config["HOST"]}:{self.config["PORT"]}/speakers"
        r = session.get(url)
        r.raise_for_status()
        return r.json()

    def _build_name_to_id_map(self) -> dict[str, int]:
        data = self._fetch_speakers()
        mapping: dict[str, int] = {}
        preferred_style_names = ["ノーマル", "normal", "ふつう"]

        for sp in data:
            name = sp["name"]
            styles = sp["styles"]
            chosen_id = None

            for pref in preferred_style_names:
                for st in styles:
                    if pref in st["name"]:
                        chosen_id = st["id"]
                        break
                if chosen_id is not None:
                    break

            if chosen_id is None and styles:
                chosen_id = styles[0]["id"]

            if chosen_id is not None:
                mapping[name] = chosen_id

        return mapping

    def list_speakers(self, names: list[str] | None = None) -> dict[str, str]:
        all_map = self._build_name_to_id_map()
        if names is None:
            return {k: str(v) for k, v in all_map.items()}
        result: dict[str, str] = {}
        for n in names:
            if n in all_map:
                result[n] = str(all_map[n])
        return result

    def synth_to_wav_bytes(self, text: str, speaker_id: str, speed_scale: float) -> bytes:
        sid = int(speaker_id)
        q = session.post(
            f"http://{self.config["HOST"]}:{self.config["PORT"]}/audio_query",
            params={"text": text, "speaker": sid},
        )
        q.raise_for_status()
        query = q.json()
        query["speedScale"] = speed_scale

        s = session.post(
            f"http://{self.config["HOST"]}:{self.config["PORT"]}/synthesis",
            params={"speaker": sid},
            data=json.dumps(query),
        )
        s.raise_for_status()
        return s.content
