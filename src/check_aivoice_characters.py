from aivoice_python import AIVoiceTTsControl, HostStatus

tts = AIVoiceTTsControl()
host_name = tts.get_available_host_names()[0]
tts.initialize(host_name)
if tts.status == HostStatus.NotRunning:
    tts.start_host()
tts.connect()

print("voice_names:", list(tts.voice_names))
print("voice_preset_names:", list(tts.voice_preset_names))

tts.disconnect()
