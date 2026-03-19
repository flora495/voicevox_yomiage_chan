# VOICEVOX読み上げちゃん

## Discord BotのAPI tokenを取得
1. Discord Developer Portalにアクセスし、新規アプリケーションを作成。
1. 権限とかはいい感じに付与。
1. API tokenを生成してメモ。


## サーバー設定手順
1. VOICEVOXをインストール(HTTP APIが`localhost:50021`で動いている必要がある)。
1. (必要なら)A.I.Voice Editorをインストール。
1. ffmpegをインストール(PATHも通す)[1]。
1. `pip install discord.py`
1. `pip install pynacl`
1. `pip install davey`
1. `pip install aivoice-python`
1. `token.json`にDiscordのAPIトークンを追加。`token.json`は絶対にgithubにアップロードしないこと。
1. その他の設定ファイルも[設定ファイル詳細](#設定ファイル詳細)を参照して作成。


## Discord上の設定
1. Botをサーバーに招待し、`connect`,`speak`の権限を付与する。

## 起動方法

1. VOICEVOXを起動。
1. (必要なら)A.I.VOICE Editorを起動。
1. `src/bot.py`を起動。

## 設定ファイル詳細
### `token.json`
```
{
  "DISCORD_TOKEN": "ここにBotのトークン文字列"
}
```
API TOKEN保持ファイル。Githubにアップロードしないこと。
### `user_preferences.json`
```
{
  "TARGET_USER_IDS": [
    111111111111111111,
    222222222222222222
  ],
  "AUTOJOIN_USER_IDS": [
    111111111111111111
  ],
  "USER_SPEAKERS": {
    "111111111111111111": "ずんだもん",
    "222222222222222222": "紲星 あかり"
  }
}
```
ユーザーごとの設定を保持する。主に読み上げ対象かどうか、AUTOJOIN対象かどうか、どのキャラクターが設定されているか。
### `characters_config.json`
```
{
  "characters": {
    "ずんだもん": {
      "engine": "voicevox",
      "allowed_user_ids": []
    },
    "四国めたん": {
      "engine": "voicevox",
      "allowed_user_ids": []
    },
    "紲星 あかり": {
      "engine": "aivoice",
      "allowed_user_ids": [
        111111111111111111
      ]
    }
  },
  "default_character": "ずんだもん"
}

```
読み上げのキャラクターの属性。`"allowed_user_ids"`が空でないキャラクターはそこで指定されたユーザIDを持つユーザのみが`!speaker`で設定できます。必要であれば手動で変更すること。
<br>
また、新しいキャラクターを追加する際はここに追加するだけで可能です。

### `config.json`
```
{
  "bot": {
    "IDLE_TIMEOUT": discord上でinvisibleになる時間。nullなら起動中常にオンライン,
    "PLAYER_POLL_INTERVAL": 複数文章の処理中に、文章キューを確認する頻度,
    "PRESENCE_CHECK_INTERVAL": inactivity_watcherの確認頻度,
    "SENTENCE_SEPARATORS": 区切り文字,
    "NORMAL_SPEED_CHAR_LIMIT":これ以上長い文章の場合、後半を倍速でしゃべる,
    "TRUNCATE_CHAR_LIMIT":これ以上長い文章の場合は、略する,
    "URL_SKIP":URLが入力されたときに、略すかどうか,
    "AUTOJOIN_MESSAGE": autojoinでbotが入室したときに、入室メッセージを出すかどうか
  },
  "voicevox": {
    "HOST": "localhost",
    "PORT": 50021,
    "DEFAULT_SPEED_SCALE":通常時の喋るスピード,
    "FAST_SPEED_SCALE":倍速時の喋るスピード,
  },
  "aivoice": {
    "DEFAULT_SPEED_SCALE":通常時の喋るスピード,
    "FAST_SPEED_SCALE":倍速時の喋るスピード,
    "MiddlePause": aivoice apiのパラメタ,
    "LongPause": aivoice apiのパラメタ,
    "SentencePause": aivoice apiのパラメタ
  }
}

```


## その他の機能とか
1. どこのボイスチャットにも入っていない状態が一定時間続くとbotのdiscord上でのステータスが自動でinvisibleになる。invisibleなだけで実際はオンラインなので、コマンドには反応します。
1. A.I.Voiceの登録済みキャラクター一覧を確認したい場合`check_aivoice_characters.py`を実行せよ。
1. URLは省略して読む。

## エラーリスト
1. `Failed to establish a new connection: [WinError 10061] 対象のコンピューターによって拒否されたため、接続できませんでした。`
　VOICEVOXのポートが解放されていないことが原因、起動すれば勝手に解放する。
1. ~~`aivoice-python`の`AIVoiceTTsControl.status()`にバグがありました。修正した関数を`aivoice-python修正部分.py`に書きました。`status`が常に`HostStatus.NotConnected`になるというもので、これだとaivoiceがしゃべるたびに再接続することになりますが、レスポンスタイムはあんまり変わらなかったので、そこまで気にしなくてもよいかも。気になるなら修正ファイルを取り込む。~~ aivoice-python v0.1.6で修正されました。

## ref
[1] https://32blog.com/programing/ffmpeg-install-guide/