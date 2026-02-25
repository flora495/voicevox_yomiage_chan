# bot.py

#################################################################
#　　　　　　　　　　 ∧＿∧
#　　　　　 ∧＿∧ 　（´<_｀ ）　 Welcome to My Coding Space!
#　　　　 （ ´_ゝ`）　/　 ⌒i
#　　　　／　　　＼　 　  |　|
#　　　 /　　 /￣￣￣￣/　　|
#　 ＿_(__ﾆつ/　    ＿/ .| .|＿＿＿＿
#　 　　　＼/＿＿＿＿/　（u　⊃
#################################################################

import json
import asyncio
import time
from collections import defaultdict
from pathlib import Path
from io import BytesIO

import discord
from discord.ext import commands

from wav import tts_to_wav_bytes, get_voicevox_speakers

# ===== パス・設定ファイル読み込み =====
COMMAND_PREFIX = "!"

PROJECT_ROOT = Path(__file__).resolve().parent.parent

TOKEN_PATH = PROJECT_ROOT / "settings" / "token.json"
USER_PREFS_PATH = PROJECT_ROOT / "settings" / "user_preferences.json"

# token.json からトークンを読む
with TOKEN_PATH.open("r", encoding="utf-8") as f:
    token_conf = json.load(f)
DISCORD_TOKEN = token_conf["DISCORD_TOKEN"]

# user_prefs.json からユーザー設定を読む（なければデフォルト）
if USER_PREFS_PATH.exists():
    with USER_PREFS_PATH.open("r", encoding="utf-8") as f:
        user_prefs = json.load(f)
else:
    user_prefs = {}

TARGET_USER_IDS = set(user_prefs.get("TARGET_USER_IDS", []))          # 読み上げ対象
AUTOJOIN_USER_IDS = set(user_prefs.get("AUTOJOIN_USER_IDS", []))      # 自動入室対象
user_speakers_name: dict[str, str] = user_prefs.get("USER_SPEAKERS", {})  # user_id(str) -> キャラ名


def save_user_prefs():
    """user_prefs.json に現在の設定を書き戻す。"""
    data = {
        "TARGET_USER_IDS": list(TARGET_USER_IDS),
        "AUTOJOIN_USER_IDS": list(AUTOJOIN_USER_IDS),
        "USER_SPEAKERS": user_speakers_name,
    }
    USER_PREFS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with USER_PREFS_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

#対象キャラクターを以下に登録する
VOICEVOX_SPEAKERS=get_voicevox_speakers(["ずんだもん","四国めたん","春日部つむぎ","東北きりたん","東北ずん子","中国うさぎ","あんこもん"])

# デフォルトキャラ
DEFAULT_SPEAKER_NAME = "ずんだもん"
DEFAULT_SPEAKER_ID = VOICEVOX_SPEAKERS[DEFAULT_SPEAKER_NAME]

# ギルドごとの現在話者ID・名前（サーバーのデフォルトキャラ）
guild_speakers_id: dict[int, int] = defaultdict(lambda: DEFAULT_SPEAKER_ID)
guild_speakers_name: dict[int, str] = defaultdict(lambda: DEFAULT_SPEAKER_NAME)

# ffmpeg オプション
FFMPEG_OPTIONS = {
    "before_options": "-loglevel panic",
    "options": "-vn",
}

# ===== 非アクティブ監視用 =====
VC_IDLE_TIMEOUT = 30 * 60  # 30分（どのVCにも入っていない状態が続いたら invisible）

last_activity = time.time()
last_in_vc_time = time.time()  # 最後にどこかのVCにいた時刻


def touch_activity():
    global last_activity
    last_activity = time.time()


def touch_in_vc():
    """ボイスチャットに入った / まだ入っているときに呼ぶ。"""
    global last_in_vc_time
    last_in_vc_time = time.time()


# ===== 文分割ヘルパ =====

def split_into_sentences(text: str) -> list[str]:
    """
    簡易な文分割: 記号で区切る。
    区切り記号も文末に残す。
    """
    seps = "。！？!?、,．."
    sentences = []
    buf = ""

    for ch in text:
        buf += ch
        if ch in seps:
            s = buf.strip()
            if s:
                sentences.append(s)
            buf = ""

    tail = buf.strip()
    if tail:
        sentences.append(tail)

    return sentences


# ===== 再生キュー =====
# (guild_id, wav_bytes, message_id, sentence_index)
play_queue: asyncio.Queue[tuple[int, bytes, int, int]] = asyncio.Queue()


async def player_task():
    """キューから音声を取り出して順番に再生するタスク。"""
    await bot.wait_until_ready()
    while not bot.is_closed():
        guild_id, wav_bytes, msg_id, idx = await play_queue.get()

        guild = bot.get_guild(guild_id)
        if guild is None:
            continue
        vc = guild.voice_client
        if vc is None or not vc.is_connected():
            continue

        # 前の再生が終わるのを待つ
        while vc.is_playing() or vc.is_paused():
            await asyncio.sleep(0.1)

        wav_buf = BytesIO(wav_bytes)
        source = discord.FFmpegPCMAudio(
            wav_buf,
            pipe=True,
            **FFMPEG_OPTIONS,
        )
        vc.play(source)

        # 再生終了を待つ
        while vc.is_playing():
            await asyncio.sleep(0.1)


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
    uid_str = str(user_id)
    if uid_str in user_speakers_name:
        return user_speakers_name[uid_str]
    return get_guild_speaker_name(guild_id)


async def inactivity_watcher():
    """
    Bot がどのVCにも入っていない状態が 30分 続いたら、ステータスを invisible にする。
    プログラムは終了しない。
    """
    await bot.wait_until_ready()
    while not bot.is_closed():
        now = time.time()

        # Bot がどこかのVCにいるか
        in_any_vc = any(vc.is_connected() for vc in bot.voice_clients)

        if in_any_vc:
            # VC にいる間は「最後にVCにいた時刻」を更新 & ステータスをオンラインに戻す
            touch_in_vc()
            try:
                await bot.change_presence(status=discord.Status.online)
            except Exception as e:
                print("change_presence (online) error:", e)
        else:
            # どのVCにもいない状態が続いているか
            if now - last_in_vc_time > VC_IDLE_TIMEOUT:
                try:
                    await bot.change_presence(status=discord.Status.invisible)
                    print("No VC for 30 minutes. Changed presence to invisible.")
                except Exception as e:
                    print("change_presence (invisible) error:", e)
                # invisible にしたあともループは続けておく

        await asyncio.sleep(60)


# ===== イベント・コマンド =====

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    bot.loop.create_task(inactivity_watcher())
    bot.loop.create_task(player_task())


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

    touch_in_vc()  # VC に入ったので更新

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

    if name is None:
        lines = ["利用可能なキャラ一覧:"]
        for char_name, sid in VOICEVOX_SPEAKERS.items():
            lines.append(f"- {char_name}（ID: {sid}）")
        lines.append("キャラ変更の例↓")
        lines.append(f"- {COMMAND_PREFIX}speaker ずんだもん")
        await ctx.send("\n".join(lines))
        return

    name = name.strip()

    if name not in VOICEVOX_SPEAKERS:
        valid = ", ".join(VOICEVOX_SPEAKERS.keys())
        await ctx.send(f"知らないキャラです。使える名前: {valid}")
        return

    uid_str = str(ctx.author.id)
    user_speakers_name[uid_str] = name
    save_user_prefs()

    speaker_id = VOICEVOX_SPEAKERS[name]
    await ctx.send(
        f"{ctx.author.display_name} さんの読み上げキャラを「{name}」（ID: {speaker_id}）に変更しました。"
    )


@bot.command()
async def readme(ctx: commands.Context):
    """自分を読み上げ対象に登録"""
    touch_activity()

    uid = ctx.author.id
    if uid in TARGET_USER_IDS:
        await ctx.send(f"{ctx.author.display_name} さんは既に読み上げ対象です。")
        return

    TARGET_USER_IDS.add(uid)
    save_user_prefs()

    await ctx.send(f"{ctx.author.display_name} さんを読み上げ対象に追加しました。")


@bot.command()
async def unreadme(ctx: commands.Context):
    """自分を読み上げ対象から外す"""
    touch_activity()

    uid = ctx.author.id
    if uid not in TARGET_USER_IDS:
        await ctx.send(f"{ctx.author.display_name} さんは元々読み上げ対象ではありません。")
        return

    TARGET_USER_IDS.remove(uid)
    save_user_prefs()

    await ctx.send(f"{ctx.author.display_name} さんを読み上げ対象から削除しました。")


@bot.command()
async def autojoin_on(ctx: commands.Context):
    """
    自分を自動入室対象に登録。
    例: !autojoin_on
    """
    touch_activity()

    target = ctx.author
    uid = target.id

    if uid in AUTOJOIN_USER_IDS:
        await ctx.send(f"{target.display_name} さんは既に自動入室対象です。")
        return

    AUTOJOIN_USER_IDS.add(uid)
    save_user_prefs()

    await ctx.send(f"{target.display_name} さんを自動入室対象に追加しました。")


@bot.command()
async def autojoin_off(ctx: commands.Context):
    """
    自分を自動入室対象から解除。
    例: !autojoin_off
    """
    touch_activity()

    target = ctx.author
    uid = target.id

    if uid not in AUTOJOIN_USER_IDS:
        await ctx.send(f"{target.display_name} さんは自動入室対象ではありません。")
        return

    AUTOJOIN_USER_IDS.remove(uid)
    save_user_prefs()

    await ctx.send(f"{target.display_name} さんを自動入室対象から削除しました。")


@bot.event
async def on_message(message: discord.Message):
    global last_activity

    # 計測開始（テキスト受信→合成完了まで）
    start = time.perf_counter()

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

    # 必要なら長さ制限（全体）
    if len(text) > 100:
        text = text[:100] + " 以下略"

    # 文に分割
    sentences = split_into_sentences(text)
    if not sentences:
        return

    char_name = get_effective_speaker_name(message.guild.id, message.author.id)
    speaker_id = VOICEVOX_SPEAKERS.get(char_name, DEFAULT_SPEAKER_ID)

    # 文ごとに並列で合成
    tasks = []
    for idx, sent in enumerate(sentences):
        task = asyncio.to_thread(tts_to_wav_bytes, sent, speaker_id)
        tasks.append((idx, task))

    results: list[tuple[int, bytes]] = []
    for idx, task in tasks:
        try:
            wav_bytes = await task
        except Exception as e:
            print(f"VOICEVOXエラー (sentence {idx}):", e)
            continue
        results.append((idx, wav_bytes))

    if not results:
        return

    # 文の順番で並べ替えてキューに積む
    results.sort(key=lambda x: x[0])

    for idx, wav_bytes in results:
        await play_queue.put((message.guild.id, wav_bytes, message.id, idx))

    end = time.perf_counter()
    elapsed = end - start
    print(
        f"[TTS queued-sent] guild={message.guild.id} user={message.author.id} "
        f"len={len(message.content)} chars "
        f"sentences={len(sentences)} synth_elapsed_total={elapsed:.3f} sec"
    )


@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    """
    1) 人間が全員抜けてBotだけになったら、自動でVCから切断する。
    2) 特定ユーザーがVCに入ったら自動で入室する。
    """

    # ===== 2) 特定ユーザー自動入室 =====
    # before.channel が None / after.channel が not None のとき「VCに入った」
    if before.channel is None and after.channel is not None:
        if member.id in AUTOJOIN_USER_IDS:
            voice_client = member.guild.voice_client
            if voice_client is None or not voice_client.is_connected():
                try:
                    await after.channel.connect()
                    touch_in_vc()
                    print(
                        f"Auto-joined VC '{after.channel.name}' in guild {member.guild.id} "
                        f"for user {member.id}"
                    )
                except Exception as e:
                    print("Auto-join error:", e)

    # ===== 1) 人間が全員抜けてBotだけになったら、自動でVCから切断 =====
    voice_client = member.guild.voice_client
    if voice_client is None or voice_client.channel is None:
        return

    channel = voice_client.channel

    if before.channel is not channel and after.channel is not channel:
        return

    members = channel.members
    humans = [m for m in members if not m.bot]

    if len(humans) == 0:
        await voice_client.disconnect()
        print(f"Auto-disconnected from VC in guild {member.guild.id} because no humans left.")


# ===== エントリポイント =====

if __name__ == "__main__":
    if not DISCORD_TOKEN:
        raise RuntimeError("settings/token.json の DISCORD_TOKEN が空です。")
    bot.run(DISCORD_TOKEN)
