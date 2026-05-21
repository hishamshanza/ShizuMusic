# --------------------------------------------------------------------------------
#  ShizuMusic © 2026
#  Developed by Bad Munda ❤️
#
#  Unauthorized copying, editing, re-uploading or removing credits
#  from this source code is strictly prohibited.
# --------------------------------------------------------------------------------

"""
/speed <0.5 – 2.0>   — Change playback speed  (e.g. /speed 1.5)
/bass  <1 – 20>      — Boost bass             (e.g. /bass 8)
/bassoff             — Remove bass boost
/speedreset          — Reset speed to normal (1.0)
/effects             — Show current speed & bass settings
"""

import asyncio
import os
import subprocess

from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message

from ShizuMusic import LOGGER, bot, call_py
from ShizuMusic.core.queue import peek_current
from ShizuMusic.utils.formatters import short


# ── Per-chat effect state ─────────────────────────────────────────────────────
# { chat_id: { "speed": float, "bass": int } }
_effects: dict[int, dict] = {}

SPEED_DEFAULT = 1.0
BASS_DEFAULT  = 0


def get_effects(chat_id: int) -> dict:
    return _effects.get(chat_id, {"speed": SPEED_DEFAULT, "bass": BASS_DEFAULT})


def set_effects(chat_id: int, speed: float = None, bass: int = None) -> dict:
    cur = _effects.setdefault(chat_id, {"speed": SPEED_DEFAULT, "bass": BASS_DEFAULT})
    if speed is not None:
        cur["speed"] = speed
    if bass is not None:
        cur["bass"] = bass
    return cur


def clear_effects(chat_id: int) -> None:
    _effects.pop(chat_id, None)


# ── ffmpeg filter builder ──────────────────────────────────────────────────────

def _build_filters(speed: float, bass: int) -> str:
    """
    Build ffmpeg -af filter string.
    speed  : atempo (0.5–2.0). Values outside this range chain multiple atempo.
    bass   : bass boost via equalizer, gain in dB (0 = off).
    """
    filters_parts = []

    # Bass boost: low-shelf EQ at 80 Hz
    if bass and bass > 0:
        gain = min(bass, 20)  # cap at 20 dB
        filters_parts.append(f"equalizer=f=80:t=h:width=200:g={gain}")

    # Speed — atempo accepts only 0.5–2.0 per filter, chain if needed
    if speed and speed != 1.0:
        speed = round(max(0.25, min(speed, 4.0)), 2)
        if 0.5 <= speed <= 2.0:
            filters_parts.append(f"atempo={speed}")
        elif speed < 0.5:
            # e.g. 0.25 → atempo=0.5,atempo=0.5
            filters_parts.append("atempo=0.5,atempo=0.5")
        else:
            # e.g. 3.0 → atempo=2.0,atempo=1.5
            remaining = speed
            chain = []
            while remaining > 2.0:
                chain.append("atempo=2.0")
                remaining /= 2.0
            chain.append(f"atempo={round(remaining, 2)}")
            filters_parts.append(",".join(chain))

    return ",".join(filters_parts) if filters_parts else None


# ── Apply effects: process file with ffmpeg, then change_stream ───────────────

async def _apply_and_stream(chat_id: int, message: Message) -> None:
    """
    1. Get current song's local file
    2. Run ffmpeg with current effects
    3. Stream the processed file via change_stream / play
    """
    from ShizuMusic.utils.youtube import resolve_stream
    from pytgcalls.types import AudioQuality, MediaStream

    song = peek_current(chat_id)
    if not song:
        await message.reply(
            "<b>❍ No song is currently playing.</b>",
            parse_mode=ParseMode.HTML,
        )
        return

    state = get_effects(chat_id)
    speed = state["speed"]
    bass  = state["bass"]

    pm = await message.reply(
        "<b>❍ Applying effects, please wait...</b>",
        parse_mode=ParseMode.HTML,
    )

    try:
        src_path = await resolve_stream(song["url"])
    except Exception as e:
        await pm.edit_text(
            f"<b>❍ Failed to resolve stream.</b>\n<code>{e}</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    af_str = _build_filters(speed, bass)

    # If no effects, stream original
    if not af_str:
        processed_path = src_path
    else:
        # Create processed file in downloads/effects/
        os.makedirs("downloads/effects", exist_ok=True)
        video_id = os.path.splitext(os.path.basename(src_path))[0]
        out_name = f"{video_id}_s{str(speed).replace('.','')}_b{bass}.mp3"
        processed_path = os.path.join("downloads/effects", out_name)

        # Use cached processed file if it exists
        if not (os.path.exists(processed_path) and os.path.getsize(processed_path) > 0):
            cmd = [
                "ffmpeg", "-y",
                "-i", src_path,
                "-af", af_str,
                "-vn",
                "-acodec", "libmp3lame",
                "-b:a", "192k",
                processed_path,
            ]
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                await asyncio.wait_for(proc.communicate(), timeout=120)
                if proc.returncode != 0 or not os.path.exists(processed_path):
                    raise Exception("ffmpeg processing failed")
            except asyncio.TimeoutError:
                await pm.edit_text(
                    "<b>❍ Effect processing timed out. Try a shorter song.</b>",
                    parse_mode=ParseMode.HTML,
                )
                return
            except Exception as e:
                await pm.edit_text(
                    f"<b>❍ ffmpeg error:</b> <code>{e}</code>",
                    parse_mode=ParseMode.HTML,
                )
                return

    # Stream the processed file
    try:
        await call_py.change_stream(
            chat_id,
            MediaStream(
                processed_path,
                audio_parameters=AudioQuality.HIGH,
                video_flags=MediaStream.Flags.IGNORE,
            ),
        )
    except Exception:
        try:
            await call_py.play(
                chat_id,
                MediaStream(
                    processed_path,
                    audio_parameters=AudioQuality.HIGH,
                    video_flags=MediaStream.Flags.IGNORE,
                ),
            )
        except Exception as e2:
            await pm.edit_text(
                f"<b>❍ Playback failed:</b> <code>{e2}</code>",
                parse_mode=ParseMode.HTML,
            )
            return

    # Reset seek state to 0 after effect change
    try:
        from ShizuMusic.modules.seek import set_seek_state
        set_seek_state(chat_id, 0)
    except Exception:
        pass

    # Build status message
    speed_label = f"{speed}x" if speed != SPEED_DEFAULT else "Normal (1.0x)"
    bass_label  = f"{bass} dB boost" if bass > 0 else "Off"

    await pm.edit_text(
        f"<b>❍ Effects Applied ✓</b>\n\n"
        f"<b>❍ Song    :</b> {short(song['title'])}\n"
        f"<b>❍ Speed   :</b> <code>{speed_label}</code>\n"
        f"<b>❍ Bass    :</b> <code>{bass_label}</code>",
        parse_mode=ParseMode.HTML,
    )


# ── /speed command ─────────────────────────────────────────────────────────────

@bot.on_message(
    filters.group
    & filters.regex(r"^/speed(?:@\w+)?\s+(?P<val>[\d.]+)$")
)
async def speed_cmd(_, message: Message) -> None:
    """
    /speed 0.5   → 0.5x (slow)
    /speed 1.0   → normal
    /speed 1.5   → 1.5x faster
    /speed 2.0   → 2x fastest
    """
    chat_id = message.chat.id
    try:
        val = float(message.matches[0].group("val"))
    except ValueError:
        await message.reply(
            "<b>❍ Invalid value.</b> Use a number like <code>/speed 1.5</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    if not (0.25 <= val <= 4.0):
        await message.reply(
            "<b>❍ Speed must be between</b> <code>0.25</code> <b>and</b> <code>4.0</code>\n\n"
            "<b>❍ Examples :</b>\n"
            "<code>/speed 0.5</code>  → slow\n"
            "<code>/speed 1.0</code>  → normal\n"
            "<code>/speed 1.5</code>  → fast\n"
            "<code>/speed 2.0</code>  → very fast",
            parse_mode=ParseMode.HTML,
        )
        return

    set_effects(chat_id, speed=val)

    try:
        await message.delete()
    except Exception:
        pass

    await _apply_and_stream(chat_id, message)


# ── /speedreset command ────────────────────────────────────────────────────────

@bot.on_message(
    filters.group
    & filters.regex(r"^/speedreset(?:@\w+)?$")
)
async def speedreset_cmd(_, message: Message) -> None:
    """Reset speed to 1.0x (normal)."""
    chat_id = message.chat.id
    set_effects(chat_id, speed=SPEED_DEFAULT)

    try:
        await message.delete()
    except Exception:
        pass

    await _apply_and_stream(chat_id, message)


# ── /bass command ──────────────────────────────────────────────────────────────

@bot.on_message(
    filters.group
    & filters.regex(r"^/bass(?:@\w+)?\s+(?P<val>\d+)$")
)
async def bass_cmd(_, message: Message) -> None:
    """
    /bass 5    → mild bass boost
    /bass 10   → medium bass boost
    /bass 20   → heavy bass boost (max)
    """
    chat_id = message.chat.id
    try:
        val = int(message.matches[0].group("val"))
    except ValueError:
        await message.reply(
            "<b>❍ Invalid value.</b> Use a number like <code>/bass 10</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    if not (1 <= val <= 20):
        await message.reply(
            "<b>❍ Bass boost must be between</b> <code>1</code> <b>and</b> <code>20</code>\n\n"
            "<b>❍ Examples :</b>\n"
            "<code>/bass 5</code>   → mild\n"
            "<code>/bass 10</code>  → medium\n"
            "<code>/bass 15</code>  → strong\n"
            "<code>/bass 20</code>  → maximum",
            parse_mode=ParseMode.HTML,
        )
        return

    set_effects(chat_id, bass=val)

    try:
        await message.delete()
    except Exception:
        pass

    await _apply_and_stream(chat_id, message)


# ── /bassoff command ───────────────────────────────────────────────────────────

@bot.on_message(
    filters.group
    & filters.regex(r"^/bassoff(?:@\w+)?$")
)
async def bassoff_cmd(_, message: Message) -> None:
    """Remove bass boost — back to flat EQ."""
    chat_id = message.chat.id
    set_effects(chat_id, bass=BASS_DEFAULT)

    try:
        await message.delete()
    except Exception:
        pass

    await _apply_and_stream(chat_id, message)


# ── /effects command ───────────────────────────────────────────────────────────

@bot.on_message(
    filters.group
    & filters.regex(r"^/effects(?:@\w+)?$")
)
async def effects_status_cmd(_, message: Message) -> None:
    """Show current speed and bass settings for this chat."""
    chat_id = message.chat.id
    state   = get_effects(chat_id)
    speed   = state["speed"]
    bass    = state["bass"]

    speed_label = f"{speed}x" if speed != SPEED_DEFAULT else "Normal (1.0x)"
    bass_label  = f"{bass} dB boost" if bass > 0 else "Off"

    song       = peek_current(chat_id)
    song_label = short(song["title"]) if song else "Nothing playing"

    await message.reply(
        f"<b>❍ Current Effects — {message.chat.title}</b>\n\n"
        f"<b>❍ Now Playing :</b> {song_label}\n"
        f"<b>❍ Speed       :</b> <code>{speed_label}</code>\n"
        f"<b>❍ Bass Boost  :</b> <code>{bass_label}</code>\n\n"
        "<b>❍ Commands :</b>\n"
        "<code>/speed 1.5</code>    → set speed\n"
        "<code>/speedreset</code>   → back to normal speed\n"
        "<code>/bass 10</code>      → set bass boost (1–20)\n"
        "<code>/bassoff</code>      → remove bass boost",
        parse_mode=ParseMode.HTML,
)
