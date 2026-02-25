# tts_aivoice.py
from typing import Dict, List
import tempfile
from pathlib import Path
from abstract_tts_client import AbstractTTSClient
from aivoice_python import AIVoiceTTsControl,HostStatus

class AIVoiceClient(AbstractTTSClient):
    def __init__(self):
        self._ctl = AIVoiceTTsControl()
        
          # 1. 利用可能なホスト名の先頭を使う
        host_names = self._ctl.get_available_host_names()
        if not host_names:
            raise RuntimeError("利用可能な A.I.VOICE ホストが見つかりません。")
        host_name = host_names[0]

        # 2. 初期化
        self._ctl.initialize(host_name)

        # 3. A.I.VOICE Editor が起動していなければ起動
        if self._ctl.status == HostStatus.NotRunning:
            self._ctl.start_host()

        # 4. エディタに接続
        self._ctl.connect()

    def list_speakers(self, names: List[str] | None = None) -> Dict[str, str]:
        # README にあるプロパティ/メソッドで一覧を取得
        # 例: ctl.voice_names が ["Aoi","Akane",...] みたいなリストならそれを採用
        all_names = self._ctl.voice_names  # 実際の API 名に合わせて
        result: Dict[str, str] = {}

        if names is None:
            for n in all_names:
                # A.I.VOICE 側は「名前 = ID」として扱ってしまってよい
                result[n] = n
        else:
            for n in names:
                if n in all_names:
                    result[n] = n

        return result


    def synth_to_wav_bytes(self, text: str, speaker_id: str) -> bytes:
        print("voice_names:", list(self._ctl.voice_names))
        print("voice_preset_names:", list(self._ctl.voice_preset_names))

        self._ctl.current_voice_preset_name = speaker_id
        self._ctl.text = text

        debug_dir = Path("debug_wav")
        debug_dir.mkdir(exist_ok=True)
        tmp_path = debug_dir / "aivoice_last.wav"

        # 1回だけ保存
        print(f"[AIVoice TTS] saving wav to: {tmp_path}")
        self._ctl.save_audio_to_file(str(tmp_path))

        # 実際に存在するかチェック
        if not tmp_path.exists():
            print(f"[AIVoice TTS] ERROR: file not found after save: {tmp_path}")
            return b""

        data = tmp_path.read_bytes()
        # デバッグ中は消さない方が確認しやすいのでコメントアウト
        # tmp_path.unlink(missing_ok=True)
        return data

'''
    def synth_to_wav_bytes(self, text: str, speaker_id: str) -> bytes:
        self._ctl.current_voice_preset_name = speaker_id  # 実際のプロパティ名に合わせて
        self._ctl.text = text

        # 一時ファイルを作成
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            tmp_path = Path(tmp.name)
            

        # A.I.VOICE エディタに WAV を書かせる
        self._ctl.save_audio_to_file(str(tmp_path))

        # Python 側で読み戻す
        data = tmp_path.read_bytes()
        tmp_path.unlink(missing_ok=True)
        return data
'''

    