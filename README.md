# VOICEVOX読み上げちゃん

## ローカル設定手順
1. VOICEVOXをインストール(HTTP APIが`localhost:50021`で動いている必要がある)。
1. ffmpegをインストール(PATHも通す)[1]。
1. `pip install discord.py`
1. `pip install pynacl`
1. `pass.json`にAPIトークンとユーザーIDを追加（discordで、開発者モードの状態で、ユーザを右クリックすると取得可能）

```
{
  "DISCORD_TOKEN": "ここにBotトークン",
  "TARGET_USER_IDS": [読み上げ対象のユーザID1,読み上げ対象のユーザID1,...]
}
```
`pass.json`はgithubにアップロードしないこと。`DISCORD_TOKEN`が必要なので、使いたい人は連絡必要。

## Bot設定
1. Botをサーバーに招待し、`connect`,`speak`の権限を付与する。

## 使い方

1. VOICEVOXを起動
1. `src/bot.py`を起動（discord上でオンラインになる）
1. VCに先に参加し、`!join`コマンドでbotをVCに参加させる。
1. TARGET_USER_IDSに追加したユーザーが発言すると、自動で読み上げる。

## コマンド一覧

|コマンド|説明|
|-------------|--------------------------------------------------------------|
|`!join`|実行者が参加しているボイスチャンネルにBotが参加する。|
|`!disconnect`|Botを現在のボイスチャンネルから切断する。|
|`!speaker`|対応しているキャラクターの一覧を表示。|
|`!speaker <キャラ名>`|自分の読み上げキャラを変更する（例:!speaker ずんだもん）。|
|`!readme`|実行者を読み上げ対象に登録。|
|`!unreadme`|実行者を読み上げ対象から除外。|
|`!help`|利用可能なコマンド一覧と簡単な説明を表示。|

## その他機能
1. 一定期間(60分)誰も操作しないなら、自動的にオフラインになります。

## エラーハンドリング
### Failed to establish a new connection: [WinError 10061] 対象のコンピューターによって拒否されたため、接続できませんでした。
VOICEVOXのポートが解放されていないことが原因。

## ref
[1] https://32blog.com/programing/ffmpeg-install-guide/