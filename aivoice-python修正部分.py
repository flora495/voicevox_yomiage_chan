    @property
    def status(self) -> HostStatus:
        """ホストプログラムのステータスを取得します。"""
        # NOTE: raw_status may be an int, a .NET Enum, or a string ("Idle", "AI.Talk.Editor.Api.HostStatus.Idle", etc.)
        raw_status = self.tts_control.Status
        
        # 数値の場合はそのまま変換
        try:
            code=int(raw_status)
            return HostStatus(code)
        except (ValueError, TypeError):
            #数値でなければ次
            pass
        
        # raw_statusが<class 'AI.Talk.Editor.Api.HostStatus'>だった場合に備えてstrに変換
        raw_status = str(raw_status)
        # フルネームだった場合に備えて末尾だけ取り出す
        raw_status = raw_status.split(".")[-1]
        
        status_mapping = {
            "NotRunning": HostStatus.NotRunning,
            "NotConnected": HostStatus.NotConnected,
            "Idle": HostStatus.Idle,
            "Busy": HostStatus.Busy
        }
        return status_mapping.get(raw_status, HostStatus.NotConnected)
        
