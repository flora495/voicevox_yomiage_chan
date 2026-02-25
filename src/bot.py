#################################################################
#                        ∧＿∧
#            ∧＿∧      （´<_｀ ）   Welcome to My Coding Space!
#          （ ´_ゝ`）  /　  ⌒i
#         ／         ＼       |  |
#        /        /￣￣￣￣/   |
#   ＿_(__ﾆつ /      ＿/  | .|＿＿＿＿
#          ＼/＿＿＿＿/   （u  ⊃
#################################################################

import json
import asyncio
import time
from collections import defaultdict
from pathlib import Path
from io import BytesIO
from typing import Dict
import re
import unicodedata
import discord
from discord.ext import commands

# ==== 追加: エンジン・キャラ定義 ====
from characters import CHARACTER_MAP, DEFAULT_CHARACTER_NAME  # キャラ名→{engine,speaker_id}
from tts_voicevox import VoicevoxClient
from tts_aivoice import AIVoiceClient


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

# user_id(str) -> キャラ名
user_speakers_name: Dict[str, str] = user_prefs.get("USER_SPEAKERS", {})


# ==== TTS クライアントを初期化 ====
voicevox_client = VoicevoxClient()
aivoice_client = AIVoiceClient()

# ギルドごとの現在キャラ名（サーバーのデフォルトキャラ）
guild_speakers_name: Dict[int, str] = defaultdict(lambda: DEFAULT_CHARACTER_NAME)


# ffmpeg オプション
FFMPEG_OPTIONS = {
    "before_options": "-loglevel panic",
    "options": "-vn",
}

# ===== 非アクティブ監視用 =====
IDLE_TIMEOUT = 30 * 60  # 30分
last_work_time = time.time()  # 最後に「仕事」した時刻


def normalize_char_name(name: str) -> str:
    if name is None:
        return ""
    s = unicodedata.normalize("NFKC", name)
    s = re.sub(r"\s+", "", s)
    return s


# 起動時に正規化キーのマップも作る
NORMALIZED_CHARACTER_MAP = {normalize_char_name(name): name for name in CHARACTER_MAP.keys()}


def save_user_preferences():
    """user_preferences.json に現在の設定を書き戻す。"""
    data = {
        "TARGET_USER_IDS": list(TARGET_USER_IDS),
        "AUTOJOIN_USER_IDS": list(AUTOJOIN_USER_IDS),
        "USER_SPEAKERS": user_speakers_name,
    }
    USER_PREFS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with USER_PREFS_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def touch_work():
    """Bot が何か仕事をしたときに呼ぶ。"""
    global last_work_time
    last_work_time = time.time()


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


def get_effective_character_name(guild_id: int, user_id: int) -> str:
    uid_str = str(user_id)
    if uid_str in user_speakers_name:
        return user_speakers_name[uid_str]
    return get_guild_speaker_name(guild_id)


async def inactivity_watcher():
    """
    最後に「仕事」(VC入室 or コマンド/メッセージ処理)をしてから
    一定時間(IDLE_TIMEOUT)が経過したら、ステータスを invisible に。
    仕事中は online。
    """
    await bot.wait_until_ready()
    while not bot.is_closed():
        now = time.time()
        dt = now - last_work_time

        if dt <= IDLE_TIMEOUT:
            try:
                await bot.change_presence(status=discord.Status.online)
            except Exception as e:
                print("change_presence (online) error:", e)
        else:
            try:
                await bot.change_presence(status=discord.Status.invisible)
            except Exception as e:
                print("change_presence (invisible) error:", e)

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
    touch_work()

    if ctx.author.voice is None:
        await ctx.send("ボイスチャンネルに参加してから実行してね。")
        return

    channel = ctx.author.voice.channel
    if ctx.voice_client is None:
        await channel.connect()
    else:
        await ctx.voice_client.move_to(channel)

    char_name = get_effective_character_name(ctx.guild.id, ctx.author.id)
    bot_name = bot.user.display_name if bot.user else "読み上げBot"
    await ctx.send(f"{bot_name}（{char_name}）が「{channel.name}」に接続しました。")


@bot.command()
async def disconnect(ctx: commands.Context):
    """VCから切断"""
    touch_work()

    if ctx.voice_client is not None:
        await ctx.voice_client.disconnect()
        await ctx.send("切断しました。")


@bot.command()
async def speaker(ctx: commands.Context, *, name: str | None = None):
    touch_work()

    # 共通の一覧整形ロジック
    def build_character_list_header(prefix: str) -> str:
        lines = [prefix]
        for char_name, info in CHARACTER_MAP.items():
            allowed = info.get("allowed_user_ids") or []
            if not allowed:
                scope = "誰でも利用可"
            else:
                scope = f"許可ユーザーのみ ({len(allowed)}人)"
            lines.append(f"- {char_name} [{info['engine']}] ({scope})")
        return "\n".join(lines)

    # name 未指定なら一覧表示
    if name is None:
        msg = build_character_list_header("利用可能なキャラ一覧:")
        await ctx.send(msg)
        return

    # 入力を正規化して照合
    normalized = normalize_char_name(name)
    original_name = NORMALIZED_CHARACTER_MAP.get(normalized)

    if original_name is None:
        # 不明なキャラ名 → 一覧付きエラーメッセージ
        msg = build_character_list_header("知らないキャラです。\n利用可能なキャラ一覧:")
        await ctx.send(msg)
        return

    info = CHARACTER_MAP[original_name]
    allowed_ids = info.get("allowed_user_ids") or []
    if allowed_ids and ctx.author.id not in allowed_ids:
        await ctx.send(
            f"「{original_name}」は利用可能なユーザーが制限されています。"
            "このキャラはあなたのアカウントでは使用できません。"
        )
        return

    uid_str = str(ctx.author.id)
    user_speakers_name[uid_str] = original_name
    save_user_preferences()

    await ctx.send(
        f"{ctx.author.display_name} さんの読み上げキャラを「{original_name}」に変更しました。"
    )
    

@bot.command()
async def readme(ctx: commands.Context):
    """自分を読み上げ対象に登録"""
    touch_work()

    uid = ctx.author.id
    if uid in TARGET_USER_IDS:
        await ctx.send(f"{ctx.author.display_name} さんは既に読み上げ対象です。")
        return

    TARGET_USER_IDS.add(uid)
    save_user_preferences()

    await ctx.send(f"{ctx.author.display_name} さんを読み上げ対象に追加しました。")


@bot.command()
async def unreadme(ctx: commands.Context):
    """自分を読み上げ対象から外す"""
    touch_work()

    uid = ctx.author.id
    if uid not in TARGET_USER_IDS:
        await ctx.send(f"{ctx.author.display_name} さんは元々読み上げ対象ではありません。")
        return

    TARGET_USER_IDS.remove(uid)
    save_user_preferences()

    await ctx.send(f"{ctx.author.display_name} さんを読み上げ対象から削除しました。")


@bot.command()
async def autojoin_on(ctx: commands.Context):
    """
    自分を自動入室対象に登録。
    例: !autojoin_on
    """
    touch_work()

    target = ctx.author
    uid = target.id

    if uid in AUTOJOIN_USER_IDS:
        await ctx.send(f"{target.display_name} さんは既に自動入室対象です。")
        return

    AUTOJOIN_USER_IDS.add(uid)
    save_user_preferences()

    await ctx.send(f"{target.display_name} さんを自動入室対象に追加しました。")


@bot.command()
async def autojoin_off(ctx: commands.Context):
    """
    自分を自動入室対象から解除。
    例: !autojoin_off
    """
    touch_work()

    target = ctx.author
    uid = target.id

    if uid not in AUTOJOIN_USER_IDS:
        await ctx.send(f"{target.display_name} さんは自動入室対象ではありません。")
        return

    AUTOJOIN_USER_IDS.remove(uid)
    save_user_preferences()

    await ctx.send(f"{target.display_name} さんを自動入室対象から削除しました。")


@bot.event
async def on_message(message: discord.Message):
    global last_work_time

    start = time.perf_counter()

    # Bot自身やDMは無視
    if message.author.bot or message.guild is None:
        return

    # コマンドは読み上げ対象外
    if message.content.startswith(COMMAND_PREFIX):
        touch_work()
        await bot.process_commands(message)
        return

    # 特定ユーザ以外は読まない
    if message.author.id not in TARGET_USER_IDS:
        await bot.process_commands(message)
        return

    # ここまで来たら「読み上げ対象のメッセージ」
    touch_work()
    await bot.process_commands(message)

    vc = message.guild.voice_client
    if vc is None or not vc.is_connected():
        return  # VCにいないときは読み上げない

    text = message.content.strip()
    if not text:
        return

    if len(text) > 100:
        text = text[:100] + " 以下略"

    sentences = split_into_sentences(text)
    if not sentences:
        return

    # ==== ここから: キャラ名 → エンジン＆speaker_id 解決 ====
    char_name = get_effective_character_name(message.guild.id, message.author.id)
    info = CHARACTER_MAP.get(char_name)

    if info is None:
        # 未定義キャラの場合はデフォルトにフォールバック
        info = CHARACTER_MAP[DEFAULT_CHARACTER_NAME]

    engine = info["engine"]
    speaker_id = info["speaker_id"]

    def synth_one(sent: str) -> bytes:
        if engine == "voicevox":
            return voicevox_client.synth_to_wav_bytes(sent, speaker_id)
        elif engine == "aivoice":
            return aivoice_client.synth_to_wav_bytes(sent, speaker_id)
        else:
            raise ValueError(f"Unknown TTS engine: {engine}")

    # 文ごとに並列で合成
    tasks = []
    for idx, sent in enumerate(sentences):
        task = asyncio.to_thread(synth_one, sent)
        tasks.append((idx, task))

    results: list[tuple[int, bytes]] = []
    for idx, task in tasks:
        try:
            wav_bytes = await task
        except Exception as e:
            print(f"TTSエラー (sentence {idx}, engine={engine}):", e)
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
        f"sentences={len(sentences)} synth_elapsed_total={elapsed:.3f} sec "
        f"engine={engine} char={char_name}"
    )


@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    """
    1) 人間が全員抜けてBotだけになったら、自動でVCから切断する。
    2) 特定ユーザーがVCに入ったら自動で入室する。
    """

    # ===== 2) 特定ユーザー自動入室 =====
    if before.channel is None and after.channel is not None:
        if member.id in AUTOJOIN_USER_IDS:
            voice_client = member.guild.voice_client
            if voice_client is None or not voice_client.is_connected():
                try:
                    await after.channel.connect()
                    touch_work()
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
