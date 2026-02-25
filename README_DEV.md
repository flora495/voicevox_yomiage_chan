# VOICEVOX読み上げちゃん

## ローカル設定手順
1. VOICEVOXをインストール(HTTP APIが`localhost:50021`で動いている必要がある)。
1. ffmpegをインストール(PATHも通す)[1]。
1. `pip install discord.py`
1. `pip install pynacl`
1. `pip install aivoice-python`
1. `token.json`にDiscordのAPIトークンを追加。

```
{
  "DISCORD_TOKEN": "ここにBotトークン"
}
```
`token.json`は絶対にgithubにアップロードしないこと。

## Discord上の設定
1. Botをサーバーに招待し、`connect`,`speak`の権限を付与する。

## 起動方法

1. VOICEVOXを起動。
1. A.I.VOICE Editorを起動。
1. `src/bot.py`を起動。

## 設定ファイル詳細
### `token.json`
API TOKEN保持ファイル。Githubにアップロードしないこと。
### `user_preferences.json`
ユーザーごとの設定を保持する。主に読み上げ対象かどうか、AUTOJOIN対象かどうか、どのキャラクターが設定されているか。
### `characters_config.json`
読み上げのキャラクターの属性。`"allowed_user_ids"`が空でないキャラクターはそこで指定されたユーザIDを持つユーザのみが`!speaker`で設定できます。必要であれば手動で変更すること。
<br>
また、新しいキャラクターを追加する際はここに追加するだけで良い。


## その他の機能とか
1. どこのボイスチャットにも入っていない状態が一定時間続くとbotのdiscord上でのステータスが自動でinvisibleになる。invisibleなだけで実際はオンラインなので、コマンドには反応します。
1. A.I.Voiceの登録済みキャラクター一覧を確認したい場合`check_aivoice_characters.py`を実行せよ。

## エラーリスト
1. `Failed to establish a new connection: [WinError 10061] 対象のコンピューターによって拒否されたため、接続できませんでした。`
　VOICEVOXのポートが解放されていないことが原因、起動すれば勝手に解放する。

## ref
[1] https://32blog.com/programing/ffmpeg-install-guide/