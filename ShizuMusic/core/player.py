# --------------------------------------------------------------------------------
#  ShizuMusic © 2026
#  Developed by Bad Munda ❤️
#
#  Unauthorized copying, editing, re-uploading or removing credits
#  from this source code is strictly prohibited.
# --------------------------------------------------------------------------------

import asyncio
import random
import time

from pyrogram.enums import ParseMode
from pyrogram.raw.functions.phone import CreateGroupCall
from pyrogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from pytgcalls.types import (
    AudioQuality,
    MediaStream,
    VideoQuality,
)

import config

from ShizuMusic import (
    LOGGER,
    assistant,
    bot,
    call_py,
)

from ShizuMusic.core.queue import (
    remove_from_queue,
)

from ShizuMusic.utils.formatters import (
    parse_dur,
    progress_bar,
    short,
)

from ShizuMusic.utils.youtube import (
    resolve_stream,
)


# ─────────────────────────────────────────────
# PROGRESS UPDATER
# ─────────────────────────────────────────────

async def _update_progress(
    chat_id: int,
    msg: Message,
    start_t: float,
    total: float,
    caption: str,
) -> None:

    btns = [
        InlineKeyboardButton(
            "▷",
            callback_data="resume",
        ),
        InlineKeyboardButton(
            "II",
            callback_data="pause",
        ),
        InlineKeyboardButton(
            "‣‣I",
            callback_data="skip",
        ),
        InlineKeyboardButton(
            "▢",
            callback_data="stop",
        ),
    ]

    while True:

        elapsed = min(
            time.time() - start_t,
            total,
        )

        bar = progress_bar(
            elapsed,
            total,
        )

        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        bar,
                        callback_data="noop",
                    )
                ],
                btns,
            ]
        )

        try:

            await bot.edit_message_caption(
                chat_id,
                msg.id,
                caption=caption,
                reply_markup=kb,
            )

        except Exception as e:

            if "MESSAGE_NOT_MODIFIED" not in str(e):
                break

        if elapsed >= total:
            break

        await asyncio.sleep(18)


# ─────────────────────────────────────────────
# AUTO START VC
# ─────────────────────────────────────────────

async def _ensure_vc(chat_id: int) -> bool:

    try:

        chat_id = int(chat_id)

        chat = await assistant.get_chat(chat_id)

        await assistant.invoke(
            CreateGroupCall(
                peer=await assistant.resolve_peer(chat.id),
                random_id=random.randint(
                    10000,
                    99999,
                ),
            )
        )

        LOGGER.info(
            f"[VC] Created in {chat_id}"
        )

        await asyncio.sleep(2)

        return True

    except Exception as e:

        err = str(e).lower()

        # already active
        if (
            "already" in err
            or "groupcall_already_started" in err
        ):

            return True

        # admin rights missing
        if (
            "chat_admin_required" in err
            or "admin" in err
        ):

            await bot.send_message(
                chat_id,
                "<b>❍ ᴠᴄ ꜱᴛᴀʀᴛ ᴘᴇʀᴍɪssɪᴏɴ ᴍɪssɪɴɢ</b>\n\n"
                "<b>❍ ɢɪᴠᴇ ᴀssɪsᴛᴀɴᴛ :</b>\n"
                "• <code>Manage Video Chats</code>\n"
                "• <code>Admin Rights</code>",
                parse_mode=ParseMode.HTML,
            )

            return False

        LOGGER.error(f"[VC ERROR] {e}")

        await bot.send_message(
            chat_id,
            "<b>❍ ᴠᴄ ꜱᴛᴀʀᴛ ғᴀɪʟᴇᴅ</b>\n"
            f"<code>{e}</code>",
            parse_mode=ParseMode.HTML,
        )

        return False


# ─────────────────────────────────────────────
# MAIN PLAY FUNCTION
# ─────────────────────────────────────────────

async def play_song(
    chat_id: int,
    message: Message,
    song: dict,
) -> None:

    chat_id = int(chat_id)

    url = song.get("url")

    if not url:
        return

    loading_text = (
        f"<b>❍ ʟᴏᴀᴅɪɴɢ :</b> "
        f"{short(song['title'])}"
    )

    try:

        await message.edit(
            loading_text,
            parse_mode=ParseMode.HTML,
        )

    except Exception:

        message = await bot.send_message(
            chat_id,
            loading_text,
            parse_mode=ParseMode.HTML,
        )

    # ─────────────────────────────────────────
    # RESOLVE STREAM
    # ─────────────────────────────────────────

    try:

        media_path = await resolve_stream(url)

    except Exception as e:

        try:
            remove_from_queue(chat_id, 0)
        except Exception:
            pass

        await bot.send_message(
            chat_id,
            f"<b>❍ ᴅᴏᴡɴʟᴏᴀᴅ ғᴀɪʟᴇᴅ</b>\n\n"
            f"<code>{e}</code>",
            parse_mode=ParseMode.HTML,
        )

        return

    is_video = song.get("video", False)

    # ─────────────────────────────────────────
    # AUTO EFFECTS
    # ─────────────────────────────────────────

    if not is_video:

        try:

            from ShizuMusic.modules.effects import (
                maybe_apply_effects,
            )

            media_path = await maybe_apply_effects(
                chat_id,
                media_path,
            )

        except Exception as fx_err:

            LOGGER.warning(
                f"[Effects] Skipped: {fx_err}"
            )

    # ─────────────────────────────────────────
    # PLAY STREAM
    # ─────────────────────────────────────────

    played = False

    for attempt in range(2):

        try:

            if is_video:

                await call_py.play(
                    chat_id,
                    MediaStream(
                        media_path,
                        audio_parameters=AudioQuality.HIGH,
                        video_parameters=VideoQuality.HD_720p,
                    ),
                )

            else:

                await call_py.play(
                    chat_id,
                    MediaStream(
                        media_path,
                        audio_parameters=AudioQuality.HIGH,
                        video_flags=MediaStream.Flags.IGNORE,
                    ),
                )

            played = True

            break

        except Exception as e:

            err = str(e).lower()

            vc_missing = any(
                x in err
                for x in (
                    "groupcallnotfound",
                    "not_in_group_call",
                    "groupcall_forbidden",
                    "not in group call",
                    "no active group call",
                )
            )

            # auto create vc
            if vc_missing and attempt == 0:

                LOGGER.info(
                    f"[VC] Creating VC in {chat_id}"
                )

                ok = await _ensure_vc(chat_id)

                if ok:
                    continue

                try:
                    remove_from_queue(chat_id, 0)
                except Exception:
                    pass

                return

            # admin permission error
            if (
                "chat_admin_required" in err
                or "admin" in err
            ):

                try:
                    remove_from_queue(chat_id, 0)
                except Exception:
                    pass

                await bot.send_message(
                    chat_id,
                    "<b>❍ ᴠᴄ ꜱᴛᴀʀᴛ ᴘᴇʀᴍɪssɪᴏɴ ᴍɪssɪɴɢ</b>\n\n"
                    "<b>❍ ᴘʟᴇᴀsᴇ ɢɪᴠᴇ :</b>\n"
                    "• <code>Manage Video Chats</code>\n"
                    "• <code>Admin Rights</code>\n\n"
                    "<b>❍ ᴀssɪsᴛᴀɴᴛ ᴍᴜsᴛ ʙᴇ ᴀᴅᴍɪɴ</b>",
                    parse_mode=ParseMode.HTML,
                )

                LOGGER.error(f"[ADMIN ERROR] {e}")

                return

            # generic error
            try:
                remove_from_queue(chat_id, 0)
            except Exception:
                pass

            await bot.send_message(
                chat_id,
                "<b>❍ ᴘʟᴀʏʙᴀᴄᴋ ғᴀɪʟᴇᴅ</b>\n\n"
                f"<code>{e}</code>",
                parse_mode=ParseMode.HTML,
            )

            LOGGER.error(f"[PLAY ERROR] {e}")

            return

    if not played:
        return

    # ─────────────────────────────────────────
    # RESET SEEK
    # ─────────────────────────────────────────

    try:

        from ShizuMusic.modules.seek import (
            set_seek_state,
        )

        set_seek_state(chat_id, 0)

    except Exception:
        pass

    # ─────────────────────────────────────────
    # DATABASE TRACKING
    # ─────────────────────────────────────────

    try:

        from ShizuMusic.database import (
            add_served_chat,
            add_served_user,
            increment_play_count,
        )

        add_served_chat(chat_id)

        requester_id = song.get(
            "requester_id"
        )

        if requester_id:
            add_served_user(requester_id)

        increment_play_count(chat_id)

    except Exception as db_err:

        LOGGER.warning(
            f"[DB ERROR] {db_err}"
        )

    # ─────────────────────────────────────────
    # NOW PLAYING UI
    # ─────────────────────────────────────────

    total = parse_dur(
        song.get("duration", "0:00")
    )

    caption = (
        "<blockquote>"
        "<b>🎧 Sʜɪᴢᴜ Mᴜsɪᴄ</b>\n\n"
        f"<b>❍ ᴛɪᴛʟᴇ :</b> "
        f"{short(song['title'])}\n"
        f"<b>❍ ᴅᴜʀ :</b> "
        f"{song.get('duration', '?')}\n"
        f"<b>❍ ʙʏ :</b> "
        f"{song['requester']}"
        "</blockquote>"
    )

    btns = [
        InlineKeyboardButton(
            "▷",
            callback_data="resume",
        ),
        InlineKeyboardButton(
            "II",
            callback_data="pause",
        ),
        InlineKeyboardButton(
            "‣‣I",
            callback_data="skip",
        ),
        InlineKeyboardButton(
            "▢",
            callback_data="stop",
        ),
    ]

    bar = progress_bar(
        0,
        total,
    )

    kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    bar,
                    callback_data="noop",
                )
            ],
            btns,
        ]
    )

    thumb = song.get("thumbnail")

    try:

        pmsg = await message.reply_photo(
            photo=thumb,
            caption=caption,
            reply_markup=kb,
            parse_mode=ParseMode.HTML,
        )

    except Exception:

        pmsg = await bot.send_message(
            chat_id,
            caption,
            reply_markup=kb,
            parse_mode=ParseMode.HTML,
        )

    try:
        await message.delete()
    except Exception:
        pass

    asyncio.create_task(
        _update_progress(
            chat_id,
            pmsg,
            time.time(),
            total,
            caption,
        )
    )

    # ─────────────────────────────────────────
    # LOGGER
    # ─────────────────────────────────────────

    if config.LOGGER_ID:

        asyncio.create_task(
            bot.send_message(
                config.LOGGER_ID,
                "<b>#ɴᴏᴡᴘʟᴀʏɪɴɢ</b>\n"
                f"• <b>ᴛɪᴛʟᴇ :</b> "
                f"{song.get('title')}\n"
                f"• <b>ᴅᴜʀ :</b> "
                f"{song.get('duration')}\n"
                f"• <b>ʙʏ :</b> "
                f"{song.get('requester')}",
                parse_mode=ParseMode.HTML,
            )
    )
