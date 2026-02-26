# tts_aivoice.py
from typing import Dict, List
from pathlib import Path
from abstract_tts_client import AbstractTTSClient
from aivoice_python import AIVoiceTTsControl, HostStatus
import tempfile
import json


class AIVoiceClient(AbstractTTSClient):
    def __init__(self, config):
        super().__init__(config)
        self._ctl = AIVoiceTTsControl()

        # 利用可能なホスト名の先頭を使う
        host_names = self._ctl.get_available_host_names()
        if not host_names:
            raise RuntimeError("利用可能な A.I.VOICE ホストが見つかりません。")
        host_name = host_names[0]

        # 初期化
        self._ctl.initialize(host_name)

        # 最初の接続（Editor が起動していなければ失敗→ログだけ出す）
        try:
            self._ensure_connected()
        except RuntimeError as e:
            # ここでは落とさず、あとで synth 時にも同じエラーを返す想定
            print(e)

        # パラメータの初期値を変更
        for key in ["MiddlePause", "LongPause", "SentencePause"]:
            if key in self.config:
                self._set_params(key, self.config[key])

    def _ensure_connected(self):
        """
        A.I.VOICE Editor が起動しており、接続されていることを保証する。
        A.I.VOICE Editorへの接続は10分何もしないと自動で切断される仕様、切断されたらしゃべるときに自動で再接続します。
        """
        status = self._ctl.status

        # Editor 自体が起動していない
        if status == HostStatus.NotRunning:
            msg = "A.I.VOICE Editor が起動していません。Editor を起動してから再度お試しください。"
            print(msg)
            # 呼び出し側で扱いやすいよう RuntimeError にする
            raise RuntimeError(msg)
        try:
            # NotRunning 以外で Connected でなければ connect
            if status == HostStatus.NotConnected:
                # 接続が切れていたら再接続
                print("A.I.VOICE Editorへの再接続")
                self._ctl.connect()
        except Exception as e:
            msg = f"A.I.VOICE Editor への接続に失敗しました: {e}"
            print(msg)
            raise RuntimeError(msg)

    def list_speakers(self, names: List[str] | None = None) -> Dict[str, str]:
        all_names = self._ctl.voice_names  # 実際の aivoice_python の API に合わせる
        result: Dict[str, str] = {}

        if names is None:
            for n in all_names:
                result[n] = n
        else:
            for n in names:
                if n in all_names:
                    result[n] = n

        return result

    def _set_params(self, key: str, value: float) -> None:
        """
        parameterの変更するやつ
        """
        mc = json.loads(self._ctl.master_control)
        mc[key] = value
        self._ctl.master_control = json.dumps(mc)

    def synth_to_wav_bytes(
        self,
        text: str,
        speaker_id: str,
        speed_scale: float | None = None,
    ) -> bytes:
        """speaker_id はプリセット名（または voice_names の要素）を想定。"""
        # ★ 発話のたびに接続確認
        self._ensure_connected()

        # プリセットとテキストを設定
        self._ctl.current_voice_preset_name = speaker_id
        self._ctl.text = text

        # 速度スケール指定があれば、A.I.VOICE のパラメータに反映
        if speed_scale is not None:
            try:
                self._set_params("Speed", speed_scale)
            except Exception as e:
                print("A.I.VOICE の速度パラメータ設定に失敗しました:", e)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            tmp_path = Path(tmp.name)

        self._ctl.save_audio_to_file(str(tmp_path))

        data = tmp_path.read_bytes()
        tmp_path.unlink(missing_ok=True)

        return data
