import time
from pathlib import Path

from aivoice_python import AIVoiceTTsControl, HostStatus


def main():
    # 1. コントローラ作成（デフォルトインストールパス）
    tts = AIVoiceTTsControl()

    # 2. 利用可能なホスト名の先頭を使う
    host_names = tts.get_available_host_names()
    if not host_names:
        raise RuntimeError("利用可能な A.I.VOICE ホストが見つかりません。")
    host_name = host_names[0]
    print(f"Host: {host_name}")

    # 3. 初期化
    tts.initialize(host_name)

    # 4. A.I.VOICE Editor が起動していなければ起動
    if tts.status == HostStatus.NotRunning:
        print("A.I.VOICE Editor を起動します...")
        tts.start_host()

    # 5. エディタに接続
    print("エディタに接続します...")
    tts.connect()
    print(f"バージョン: {tts.version}")

    # 6. 利用可能なボイス一覧を表示
    voices = tts.voice_names
    print("利用可能なボイス:")
    for i, v in enumerate(voices):
        print(f"  [{i}] {v}")

    # 7. 使うボイスを決める（ここでは先頭のボイス）
    if voices:
        tts.current_voice_preset_name = voices[0]
        print(f"使用ボイス: {tts.current_voice_preset_name}")
    else:
        print("ボイスが見つかりません。")
        return

    # 8. 読み上げるテキストを設定
    tts.text = "これはwav出力のテストです。変な音が乗っていないかを確認してください。"

    # 9. WAV ファイルとして保存
    out_path = Path("output.wav").resolve()
    print(f"WAVファイルに出力します: {out_path}")
    tts.save_audio_to_file(str(out_path))

    # 10. 再生時間を取得して、実際に再生もしてみる（任意）
    play_time_ms = tts.get_play_time()
    print(f"再生時間: {play_time_ms / 1000:.2f} 秒")
    tts.play()
    time.sleep((play_time_ms + 500) / 1000)

    # 11. 切断
    tts.disconnect()
    print("完了しました。")


if __name__ == "__main__":
    main()

