# bot.py
import json
import asyncio
import time
from collections import defaultdict
from pathlib import Path

import discord
from discord.ext import commands

from wav import tts_to_wav

# ===== パス・設定ファイル読み込み =====

COMMAND_PREFIX = "!"

# このファイル: .../voicevox_yomiage_chan/src/bot.py
# プロジェクトルート: .../voicevox_yomiage_chan
PROJECT_ROOT = Path(__file__).resolve().parent.parent

PASS_PATH = PROJECT_ROOT / "settings" / "pass.json"
USER_SPEAKERS_PATH = PROJECT_ROOT / "settings" / "user_speakers.json"

with PASS_PATH.open("r", encoding="utf-8") as f:
    pass_conf = json.load(f)

DISCORD_TOKEN = pass_conf["DISCORD_TOKEN"]
TARGET_USER_IDS = set(pass_conf.get("TARGET_USER_IDS", []))

# VOICEVOXの話者一覧（IDはあなたの環境に合わせて調整してください）
VOICEVOX_SPEAKERS = {
    "ずんだもん": 3,
    "四国めたん": 2,
    "春日部つむぎ": 8,
    "東北きりたん": 10,  # 仮ID。実環境に合わせて変えてください
}

DEFAULT_SPEAKER_NAME = "ずんだもん"
DEFAULT_SPEAKER_ID = VOICEVOX_SPEAKERS[DEFAULT_SPEAKER_NAME]

# ギルドごとの現在話者ID・名前（サーバーのデフォルトキャラ）
guild_speakers_id: dict[int, int] = defaultdict(lambda: DEFAULT_SPEAKER_ID)
guild_speakers_name: dict[int, str] = defaultdict(lambda: DEFAULT_SPEAKER_NAME)

# ユーザごとのキャラ設定（user_id(str) -> キャラ名）
if USER_SPEAKERS_PATH.exists():
    with USER_SPEAKERS_PATH.open("r", encoding="utf-8") as f:
        user_speakers_name: dict[str, str] = json.load(f)
else:
    user_speakers_name: dict[str, str] = {}

# 一時wav保存先（プロジェクトルート基準）
AUDIO_DIR = PROJECT_ROOT / "audio_cache"

# ffmpeg オプション（PATHにffmpegが通っている前提）
FFMPEG_OPTIONS = {
    "before_options": "-loglevel panic",
    "options": "-vn",
}

# ===== 非アクティブ監視用 =====

INACTIVE_TIMEOUT = 60 * 60  # 60*60秒=60分
last_activity = time.time()


def touch_activity():
    global last_activity
    last_activity = time.time()


# ===== Discord Bot 初期化 =====

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)

# ===== ヘルパ =====

def get_guild_speaker_name(guild_id: int) -> str:
    return guild_speakers_name[guild_id]


def get_guild_speaker_id(guild_id: int) -> int:
    return guild_speakers_id[guild_id]


def get_effective_speaker_name(guild_id: int, user_id: int) -> str:
    """
    ユーザ専用キャラがあればそれを優先し、
    なければサーバー共通のデフォルトキャラを返す。
    """
    uid_str = str(user_id)
    if uid_str in user_speakers_name:
        return user_speakers_name[uid_str]
    return get_guild_speaker_name(guild_id)


async def inactivity_watcher():
    await bot.wait_until_ready()
    while not bot.is_closed():
        now = time.time()
        if now - last_activity > INACTIVE_TIMEOUT:
            print("Inactivity timeout reached. Shutting down bot.")
            await bot.close()
            break
        await asyncio.sleep(60)

# ===== イベント・コマンド =====

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    bot.loop.create_task(inactivity_watcher())


@bot.command()
async def join(ctx: commands.Context):
    """呼び出した人のVCに参加"""
    touch_activity()

    if ctx.author.voice is None:
        await ctx.send("ボイスチャンネルに参加してから実行してね。")
        return

    channel = ctx.author.voice.channel
    if ctx.voice_client is None:
        await channel.connect()
    else:
        await ctx.voice_client.move_to(channel)

    # join を呼んだ人のキャラ名（なければサーバーデフォルト）
    char_name = get_effective_speaker_name(ctx.guild.id, ctx.author.id)
    bot_name = bot.user.display_name if bot.user else "読み上げBot"
    await ctx.send(f"{bot_name}（{char_name}）が「{channel.name}」に接続しました。")


@bot.command()
async def disconnect(ctx: commands.Context):
    """VCから切断"""
    touch_activity()

    if ctx.voice_client is not None:
        await ctx.voice_client.disconnect()
        await ctx.send("切断しました。")


@bot.command()
async def speaker(ctx: commands.Context, name: str | None = None):
    """
    自分のキャラ変更コマンド。単体ならキャラ一覧を表示。
    例: !speaker ずんだもん
        !speaker   （キャラ一覧を表示）
    """
    touch_activity()

    # 引数なし → 一覧表示
    if name is None:
        lines = ["利用可能なキャラ一覧:"]
        for char_name, sid in VOICEVOX_SPEAKERS.items():
            lines.append(f"- {char_name}（ID: {sid}）")

        # 使い方サンプルを追記
        lines.append("キャラ変更の例↓")
        lines.append(f"- {COMMAND_PREFIX}speaker ずんだもん")

        await ctx.send("\n".join(lines))
        return


    # ここからは変更処理
    name = name.strip()

    if name not in VOICEVOX_SPEAKERS:
        valid = ", ".join(VOICEVOX_SPEAKERS.keys())
        await ctx.send(f"知らないキャラです。使える名前: {valid}")
        return

    uid_str = str(ctx.author.id)
    user_speakers_name[uid_str] = name

    USER_SPEAKERS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with USER_SPEAKERS_PATH.open("w", encoding="utf-8") as f:
        json.dump(user_speakers_name, f, ensure_ascii=False, indent=2)

    speaker_id = VOICEVOX_SPEAKERS[name]
    await ctx.send(
        f"{ctx.author.display_name} さんの読み上げキャラを「{name}」（ID: {speaker_id}）に変更しました。"
    )



@bot.command()
async def readme(ctx: commands.Context):
    """
    自分を読み上げ対象に登録:
    例: !readme
    """
    uid = ctx.author.id
    if uid in TARGET_USER_IDS:
        await ctx.send(f"{ctx.author.display_name} さんは既に読み上げ対象です。")
        return

    TARGET_USER_IDS.add(uid)

    # pass.json へ反映
    pass_conf["TARGET_USER_IDS"] = list(TARGET_USER_IDS)
    with PASS_PATH.open("w", encoding="utf-8") as f:
        json.dump(pass_conf, f, ensure_ascii=False, indent=2)

    await ctx.send(f"{ctx.author.display_name} さんを読み上げ対象に追加しました。")


@bot.command()
async def unreadme(ctx: commands.Context):
    """
    自分を読み上げ対象から外す:
    例: !unreadme
    """
    uid = ctx.author.id
    if uid not in TARGET_USER_IDS:
        await ctx.send(f"{ctx.author.display_name} さんは元々読み上げ対象ではありません。")
        return

    TARGET_USER_IDS.remove(uid)

    pass_conf["TARGET_USER_IDS"] = list(TARGET_USER_IDS)
    with PASS_PATH.open("w", encoding="utf-8") as f:
        json.dump(pass_conf, f, ensure_ascii=False, indent=2)

    await ctx.send(f"{ctx.author.display_name} さんを読み上げ対象から削除しました。")



@bot.event
async def on_message(message: discord.Message):
    global last_activity

    # Bot自身やDMは無視
    if message.author.bot or message.guild is None:
        return

    # コマンドは読み上げ対象外
    if message.content.startswith(COMMAND_PREFIX):
        touch_activity()
        await bot.process_commands(message)
        return

    # 特定ユーザ以外は読まない
    if message.author.id not in TARGET_USER_IDS:
        await bot.process_commands(message)
        return


    # ここまで来たら「読み上げ対象のメッセージ」
    touch_activity()
    await bot.process_commands(message)

    vc = message.guild.voice_client
    if vc is None or not vc.is_connected():
        return  # VCにいないときは読み上げない

    text = message.content.strip()
    if not text:
        return

    # 必要なら長さ制限
    if len(text) > 100:
        text = text[:100] + " 以下略"

    # ユーザ専用キャラ or サーバーデフォルト
    char_name = get_effective_speaker_name(message.guild.id, message.author.id)
    speaker_id = VOICEVOX_SPEAKERS.get(char_name, DEFAULT_SPEAKER_ID)

    # 音声合成 → 一時wav
    wav_path = AUDIO_DIR / f"{message.id}.wav"
    try:
        tts_to_wav(text, wav_path, speaker_id)
    except Exception as e:
        print("VOICEVOXエラー:", e)
        return

    # 再生キュー制御（前の再生が終わるまで待つ）
    while vc.is_playing() or vc.is_paused():
        await asyncio.sleep(0.1)

    # ffmpegで再生
    source = discord.FFmpegPCMAudio(str(wav_path), **FFMPEG_OPTIONS)
    vc.play(source)

    # 再生終了を待って削除
    while vc.is_playing():
        await asyncio.sleep(0.1)
    try:
        wav_path.unlink()
    except FileNotFoundError:
        pass


@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    """
    人間が全員抜けてBotだけになったら、自動でVCから切断する。
    """
    # BotがそのギルドでVCに接続しているか確認
    voice_client = member.guild.voice_client
    if voice_client is None or voice_client.channel is None:
        return

    channel = voice_client.channel

    # 対象のVCにメンバーが変化したイベントでなければ無視
    if before.channel is not channel and after.channel is not channel:
        return

    # 今そのVCにいるメンバーを取得
    members = channel.members

    # Bot以外の人間がいるかチェック
    humans = [m for m in members if not m.bot]

    # 人間が0人 → Botだけ → 切断
    if len(humans) == 0:
        await voice_client.disconnect()


# ===== エントリポイント =====

if __name__ == "__main__":
    if not DISCORD_TOKEN:
        raise RuntimeError("settings/pass.json の DISCORD_TOKEN が空です。")
    bot.run(DISCORD_TOKEN)
