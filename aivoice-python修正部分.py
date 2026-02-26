@property
def status(self) -> HostStatus:
    """ホストプログラムのステータスを取得します。"""
    raw_status = self.tts_control.Status
    
    # C#のEnumから文字列が返ってくる場合の対応
    if isinstance(raw_status, str):
        status_mapping = {
            "NotRunning": HostStatus.NotRunning,
            "NotConnected": HostStatus.NotConnected,
            "Idle": HostStatus.Idle,
            "Busy": HostStatus.Busy
        }
        return status_mapping.get(raw_status, HostStatus.NotConnected)
    
    # int/<class 'AI.Talk.Editor.Api.HostStatus'>の場合はintで変換
    try:
        return HostStatus(int(raw_status))
    except ValueError:
        return HostStatus.NotConnected
