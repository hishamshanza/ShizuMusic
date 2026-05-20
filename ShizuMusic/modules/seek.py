# --------------------------------------------------------------------------------
#  ShizuMusic © 2026
#  Developed by Bad Munda ❤️
#
#  Unauthorized copying, editing, re-uploading or removing credits
#  from this source code is strictly prohibited.
# --------------------------------------------------------------------------------

"""
/seek <seconds>      — Jump forward N seconds in the current song
/seekback <seconds>  — Jump backward N seconds in the current song

Examples:
  /seek 1       → forward 1 second
  /seek 120     → forward 120 seconds (2 minutes)
  /seekback 30  → back 30 seconds
"""

import asyncio
import time

from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from ShizuMusic import bot, call_py, LOGGER
from ShizuMusic.core.queue import peek_current
from ShizuMusic.utils.formatters import fmt_time, parse_dur, progress_bar, short
from ShizuMusic.utils.youtube import resolve_stream


# ── Per-chat seek position tracker ───────────────────────────────────────────
# Stores: { chat_id: { "start_ts": float, "offset": int } }
# start_ts = time.time() when current song started playing from offset
# offset   = seconds into the song where playback started
_seek_state: dict[int, dict] = {}


def set_seek_state(chat_id: int, offset: int) -> None:
    """Call this whenever a song starts or seek happens."""
    _seek_state[chat_id] = {
        "start_ts": time.time(),
        "offset": offset,
    }


def get_current_position(chat_id: int) -> int:
    """Return estimated current playback position in seconds."""
    state = _seek_state.get(chat_id)
    if not state:
        return 0
    elapsed = int(time.time() - state["start_ts"])
    return state["offset"] + elapsed


def clear_seek_state(chat_id: int) -> None:
    _seek_state.pop(chat_id, None)


# ── Internal: re-stream from a given position ─────────────────────────────────
async def _seek_to(chat_id: int, target_sec: int, message: Message) -> None:
    """
    Re-stream the current song from target_sec onwards.
    Uses pytgcalls ChangeStream with ffmpeg audio options.
    """
    from pytgcalls.types import AudioQuality, MediaStream

    song = peek_current(chat_id)
    if not song:
        await message.reply(
            "<b>❍ Nothing is playing right now.</b>",
            parse_mode=ParseMode.HTML,
        )
        return

    total_sec = parse_dur(song.get("duration", "0:00"))

    # Clamp target between 0 and (total - 1)
    target_sec = max(0, min(target_sec, total_sec - 1))

    pm = await message.reply(
        f"<b>❍ Seeking to</b> <code>{fmt_time(target_sec)}</code><b>...</b>",
        parse_mode=ParseMode.HTML,
    )

    try:
        media_path = await resolve_stream(song["url"])
    except Exception as e:
        await pm.edit_text(
            f"<b>❍ Seek failed — could not resolve stream.</b>\n<code>{e}</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    try:
        from pytgcalls.types import MediaStream as MS

        # Build ffmpeg options to start from target_sec
        ffmpeg_opts = {
            "headers": None,
            "before_options": f"-ss {target_sec}",
        }

        await call_py.change_stream(
            chat_id,
            MS(
                media_path,
                audio_parameters=AudioQuality.HIGH,
                video_flags=MS.Flags.IGNORE,
                ffmpeg_parameters=f"-ss {target_sec}",
            ),
        )
    except Exception as e:
        # Fallback: try plain play() if change_stream not supported
        try:
            from pytgcalls.types import MediaStream as MS
            await call_py.play(
                chat_id,
                MS(
                    media_path,
                    audio_parameters=AudioQuality.HIGH,
                    video_flags=MS.Flags.IGNORE,
                    ffmpeg_parameters=f"-ss {target_sec}",
                ),
            )
        except Exception as e2:
            await pm.edit_text(
                f"<b>❍ Seek failed.</b>\n<code>{e2}</code>",
                parse_mode=ParseMode.HTML,
            )
            return

    # Update seek state so progress bar stays accurate
    set_seek_state(chat_id, target_sec)

    # Build updated now-playing message
    caption = (
        "<blockquote>"
        "<b>🎧 Sʜɪᴢᴜ Mᴜsɪᴄ</b>\n\n"
        f"<b>❍ Title :</b> {short(song['title'])}\n"
        f"<b>❍ Duration :</b> {song.get('duration', '?')}\n"
        f"<b>❍ By :</b> {song['requester']}\n"
        f"<b>❍ Seeked to :</b> <code>{fmt_time(target_sec)}</code>"
        "</blockquote>"
    )
    btns = [
        InlineKeyboardButton("▷",   callback_data="resume"),
        InlineKeyboardButton("II",  callback_data="pause"),
        InlineKeyboardButton("‣‣I", callback_data="skip"),
        InlineKeyboardButton("▢",   callback_data="stop"),
    ]
    bar = progress_bar(target_sec, total_sec)
    kb  = InlineKeyboardMarkup([
        [InlineKeyboardButton(bar, callback_data="noop")],
        btns,
    ])

    await pm.edit_text(caption, reply_markup=kb, parse_mode=ParseMode.HTML)


# ── /seek command ─────────────────────────────────────────────────────────────
@bot.on_message(
    filters.group
    & filters.regex(r"^/seek(?:@\w+)?\s+(?P<sec>\d+)$")
)
async def seek_cmd(_, message: Message) -> None:
    """
    /seek <seconds>
    Jump forward by N seconds from current position.
    """
    chat_id = message.chat.id

    song = peek_current(chat_id)
    if not song:
        await message.reply(
            "<b>❍ No song is currently playing.</b>",
            parse_mode=ParseMode.HTML,
        )
        return

    sec = int(message.matches[0].group("sec"))
    if sec < 1:
        await message.reply(
            "<b>❍ Please provide a number of seconds greater than 0.</b>\n"
            "<b>❍ Usage :</b> <code>/seek 30</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    current_pos = get_current_position(chat_id)
    target      = current_pos + sec
    total_sec   = parse_dur(song.get("duration", "0:00"))

    if current_pos >= total_sec - 1:
        await message.reply(
            "<b>❍ Song is almost finished. Cannot seek forward.</b>",
            parse_mode=ParseMode.HTML,
        )
        return

    if target >= total_sec:
        await message.reply(
            f"<b>❍ Cannot seek that far forward.</b>\n"
            f"<b>❍ Current position :</b> <code>{fmt_time(current_pos)}</code>\n"
            f"<b>❍ Song duration :</b> <code>{fmt_time(total_sec)}</code>\n"
            f"<b>❍ Max forward :</b> <code>{fmt_time(total_sec - current_pos - 1)} seconds</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    try:
        await message.delete()
    except Exception:
        pass

    await _seek_to(chat_id, target, message)


# ── /seekback command ─────────────────────────────────────────────────────────
@bot.on_message(
    filters.group
    & filters.regex(r"^/seekback(?:@\w+)?\s+(?P<sec>\d+)$")
)
async def seekback_cmd(_, message: Message) -> None:
    """
    /seekback <seconds>
    Jump backward by N seconds from current position.
    """
    chat_id = message.chat.id

    song = peek_current(chat_id)
    if not song:
        await message.reply(
            "<b>❍ No song is currently playing.</b>",
            parse_mode=ParseMode.HTML,
        )
        return

    sec = int(message.matches[0].group("sec"))
    if sec < 1:
        await message.reply(
            "<b>❍ Please provide a number of seconds greater than 0.</b>\n"
            "<b>❍ Usage :</b> <code>/seekback 30</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    current_pos = get_current_position(chat_id)
    target      = current_pos - sec

    if target < 0:
        target = 0  # clamp to start

    try:
        await message.delete()
    except Exception:
        pass

    await _seek_to(chat_id, target, message)


# ── /seek with no args — show usage ──────────────────────────────────────────
@bot.on_message(
    filters.group
    & filters.regex(r"^/seek(?:@\w+)?$")
)
async def seek_usage(_, message: Message) -> None:
    chat_id = message.chat.id
    song    = peek_current(chat_id)

    if song:
        pos       = get_current_position(chat_id)
        total_sec = parse_dur(song.get("duration", "0:00"))
        await message.reply(
            f"<b>❍ Current position :</b> <code>{fmt_time(pos)}</code> / <code>{fmt_time(total_sec)}</code>\n\n"
            f"<b>❍ Usage :</b>\n"
            f"<code>/seek 30</code>     → forward 30 seconds\n"
            f"<code>/seekback 30</code> → backward 30 seconds\n"
            f"<code>/seek 120</code>    → forward 2 minutes",
            parse_mode=ParseMode.HTML,
        )
    else:
        await message.reply(
            "<b>❍ Usage :</b>\n"
            "<code>/seek 30</code>     → forward 30 seconds\n"
            "<code>/seekback 30</code> → backward 30 seconds\n"
            "<code>/seek 120</code>    → forward 2 minutes",
            parse_mode=ParseMode.HTML,
      )
