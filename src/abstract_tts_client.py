# tts_base.py
from abc import ABC, abstractmethod
from typing import Dict, List


class AbstractTTSClient(ABC):
    """
    TTSClientの抽象クラス。新しいエンジン（例えばA.I.Voice2）に対応したい場合は、以下のメソッドが実装できれば可能です。
    """
    
    def __init__(self,config):
        self.config=config
        
    @abstractmethod
    def list_speakers(self, names: List[str] | None = None) -> Dict[str, str]:
        """キャラ名 -> 内部ID (文字列) のマップを返す。names が指定されていれば、その中だけ絞る。"""
        pass

    @abstractmethod
    def synth_to_wav_bytes(self, text: str, speaker_id: str) -> bytes:
        """text を speaker_id の声で読み上げた WAV データ(bytes)を返す。"""
        pass
