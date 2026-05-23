# --------------------------------------------------------------------------------
#  ShizuMusic © 2026
#  Developed by Bad Munda ❤️
#
#  Unauthorized copying, editing, re-uploading or removing credits
#  from this source code is strictly prohibited.
# --------------------------------------------------------------------------------

"""
/autoplay <query>  — Start autoplay
/end               — Stop autoplay + playback
"""

import asyncio

from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message

from ShizuMusic import bot
from ShizuMusic.core.autoplay import (
    get_autoplay_query,
    is_autoplay,
    start_autoplay,
    stop_autoplay,
)
import KHANA KI MAA KI CHUT
from ShizuMusic.core.call import leave_vc
from ShizuMusic.core.player import play_song
from ShizuMusic.core.queue import peek_current, queue_size
from ShizuMusic.utils.formatters import short
from ShizuMusic.utils.permissions import is_user_authorized


# ─────────────────────────────────────────────
# /autoplay
# ─────────────────────────────────────────────
@bot.on_message(
    filters.group
    & filters.regex(r"^/autoplay(?:@\w+)?(?:\s+(?P<q>.+))?$")
)
async def autoplay_cmd(_, message: Message) -> None:

    chat_id = message.chat.id
    user = message.from_user

    # Admin check
    if not await is_user_authorized(message):
        await message.reply(
            "<b>❍ ᴀᴅᴍɪɴ ᴏɴʟʏ</b>\n"
            "<b>❍ ᴏɴʟʏ ɢʀᴏᴜᴘ ᴀᴅᴍɪɴꜱ ᴄᴀɴ ᴜꜱᴇ /autoplay</b>",
            parse_mode=ParseMode.HTML,
        )
        return

    match = message.matches[0]
    query = (match.group("q") or "").strip()

    # No query provided
    if not query:
        current_q = get_autoplay_query(chat_id)

        if is_autoplay(chat_id) and current_q:
            await message.reply(
                f"<b>❍ ᴀᴜᴛᴏᴘʟᴀʏ ɪꜱ ᴀʟʀᴇᴀᴅʏ ʀᴜɴɴɪɴɢ</b>\n"
                f"<b>❍ Qᴜᴇʀʏ :</b> <code>{current_q}</code>\n"
                f"<b>❍ ᴜꜱᴇ /end ᴛᴏ ꜱᴛᴏᴘ ᴀᴜᴛᴏᴘʟᴀʏ ꜰɪʀꜱᴛ</b>",
                parse_mode=ParseMode.HTML,
            )
        else:
            await message.reply(
                "<b>❍ ᴜꜱᴀɢᴇ :</b> <code>/autoplay sidhu moose wala</code>\n"
                "<b>❍ ᴛʜɪꜱ ᴡɪʟʟ ᴄᴏɴᴛɪɴᴜᴏᴜꜱʟʏ ᴘʟᴀʏ ꜱᴏɴɢꜱ ᴀᴜᴛᴏᴍᴀᴛɪᴄᴀʟʟʏ</b>",
                parse_mode=ParseMode.HTML,
            )
        return

    # Initial status message
    pm = await message.reply(
        f"<b>🔁 ꜱᴇᴛᴛɪɴɢ ᴜᴘ ᴀᴜᴛᴏᴘʟᴀʏ...</b>\n"
        f"<b>❍ Qᴜᴇʀʏ :</b> <code>{query}</code>",
        parse_mode=ParseMode.HTML,
    )

    req = user.first_name if user else "AutoPlay"
    req_id = user.id if user else 0

    was_playing = queue_size(chat_id) > 0

    # Start autoplay engine
    count = await start_autoplay(chat_id, query, req, req_id)

    # Failed
    if count == 0:
        stop_autoplay(chat_id)

        await pm.edit_text(
            "<b>❍ ᴀᴜᴛᴏᴘʟᴀʏ ꜰᴀɪʟᴇᴅ</b>\n"
            "<b>❍ ɴᴏ ꜱᴏɴɢꜱ ᴡᴇʀᴇ ꜰᴏᴜɴᴅ, ᴘʟᴇᴀꜱᴇ ᴛʀʏ ᴀɢᴀɪɴ</b>",
            parse_mode=ParseMode.HTML,
        )
        return

    first = peek_current(chat_id)

    # Success message
    await pm.edit_text(
        f"<b>🔁 ᴀᴜᴛᴏᴘʟᴀʏ ꜱᴛᴀʀᴛᴇᴅ</b>\n"
        f"<b>❍ Qᴜᴇʀʏ :</b> <code>{query}</code>\n"
        f"<b>❍ {count} ꜱᴏɴɢꜱ ᴀᴅᴅᴇᴅ ᴛᴏ Qᴜᴇᴜᴇ</b>\n"
        f"<b>❍ ᴜꜱᴇ /end ᴛᴏ ꜱᴛᴏᴘ ᴀᴜᴛᴏᴘʟᴀʏ</b>",
        parse_mode=ParseMode.HTML,
    )

    # Start playback if nothing is currently playing
    if not was_playing and first:
        dm = await bot.send_message(
            chat_id,
            f"<b>❍ ɴᴏᴡ ᴘʟᴀʏɪɴɢ :</b> <code>{short(first['title'])}</code>",
            parse_mode=ParseMode.HTML,
        )

        await play_song(chat_id, dm, first)

    # Delete command message
    try:
        await message.delete()
    except Exception:
        pass


# ─────────────────────────────────────────────
# /end — Stop autoplay + playback
# ─────────────────────────────────────────────
@bot.on_message(filters.group & filters.command("end"))
async def end_cmd(_, message: Message) -> None:

    chat_id = message.chat.id

    # Admin check
    if not await is_user_authorized(message):
        await message.reply(
            "<b>❍ ᴀᴅᴍɪɴ ᴏɴʟʏ</b>",
            parse_mode=ParseMode.HTML,
        )
        return

    was_autoplay = is_autoplay(chat_id)

    # Stop autoplay + leave VC
    stop_autoplay(chat_id)
    await leave_vc(chat_id)

    # Response messages
    if was_autoplay:
        await message.reply(
            "<b>🔁 ᴀᴜᴛᴏᴘʟᴀʏ ꜱᴛᴏᴘᴘᴇᴅ</b>\n"
            "<b>❍ ᴘʟᴀʏʙᴀᴄᴋ ʜᴀꜱ ʙᴇᴇɴ ꜱᴛᴏᴘᴘᴇᴅ ✓</b>\n"
            "<b>❍ Qᴜᴇᴜᴇ ʜᴀꜱ ʙᴇᴇɴ ᴄʟᴇᴀʀᴇᴅ ✓</b>",
            parse_mode=ParseMode.HTML,
        )
    else:
        await message.reply(
            "<b>❍ ᴘʟᴀʏʙᴀᴄᴋ ʜᴀꜱ ʙᴇᴇɴ ꜱᴛᴏᴘᴘᴇᴅ</b>\n"
            "<b>❍ Qᴜᴇᴜᴇ ʜᴀꜱ ʙᴇᴇɴ ᴄʟᴇᴀʀᴇᴅ</b>",
            parse_mode=ParseMode.HTML,
        )
