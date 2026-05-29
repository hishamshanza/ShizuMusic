# --------------------------------------------------------------------------------
#  ShizuMusic © 2026
#  Developed by Bad Munda ❤️
#
#  Unauthorized copying, editing, re-uploading or removing credits
#  from this source code is strictly prohibited.
# --------------------------------------------------------------------------------

import asyncio
import logging

from pyrogram import filters
from pyrogram.enums import ParseMode
from pyrogram.errors import (
    ChatAdminRequired,
    ChatWriteForbidden,
    FloodWait,
    PeerIdInvalid,
    UserIsBlocked,
)
from pyrogram.types import Message

import config
from ShizuMusic import bot
from ShizuMusic.utils.db import (
    get_broadcast_chats,
    get_broadcast_count,
    remove_broadcast_chat,
)

logger = logging.getLogger(__name__)

# ── Broadcast lock — prevents two broadcasts running at once ──────────────────
_IS_BROADCASTING = False
_broadcast_lock  = asyncio.Lock()

# ── Flags ─────────────────────────────────────────────────────────────────────
#
#  /broadcast or /gcast — reply to a message, OR provide text directly
#
#  Flags (add after command or in the text):
#   -pin       → pin in groups silently (no notification)
#   -pinloud   → pin in groups with notification
#   -nogroup   → skip all groups, send to users only
#   -user      → also send to private users
#
#  Examples:
#   /broadcast -pin            (reply to msg — pin silently)
#   /broadcast -user           (reply to msg — groups + users)
#   /broadcast -nogroup -user  (reply to msg — users only)
#   /broadcast Hello everyone  (text — groups)
#   /gcast -pin -user          (reply — groups pinned + users)
#
# ─────────────────────────────────────────────────────────────────────────────


@bot.on_message(
    filters.command(["broadcast", "gcast"])
    & filters.user(config.OWNER_ID)
)
async def broadcast_cmd(_, message: Message) -> None:

    global _IS_BROADCASTING

    async with _broadcast_lock:
        if _IS_BROADCASTING:
            await message.reply(
                "<b>❍ A broadcast is already running.</b>\n"
                "<b>❍ Please wait for it to finish.</b>",
                parse_mode=ParseMode.HTML,
            )
            return

        _IS_BROADCASTING = True

    try:
        await _run_broadcast(message)
    finally:
        _IS_BROADCASTING = False


async def _run_broadcast(message: Message) -> None:

    # ── Parse raw args (everything after /broadcast or /gcast) ───────────────
    raw = message.text or ""
    try:
        raw_args = raw.split(None, 1)[1].strip()
    except IndexError:
        raw_args = ""

    # ── Extract flags ─────────────────────────────────────────────────────────
    flag_pin      = "-pin"      in raw_args
    flag_pinloud  = "-pinloud"  in raw_args
    flag_nogroup  = "-nogroup"  in raw_args
    flag_user     = "-user"     in raw_args

    # Clean flags from text
    clean_text = raw_args
    for flag in ("-pinloud", "-nogroup", "-user", "-pin"):
        clean_text = clean_text.replace(flag, "").strip()

    # ── Determine broadcast content ───────────────────────────────────────────
    if message.reply_to_message:
        broadcast_msg  = message.reply_to_message
        broadcast_type = "reply"
    elif clean_text:
        broadcast_msg  = clean_text
        broadcast_type = "text"
    else:
        await message.reply(
            "<b>❍ Reply to a message</b> <b>or provide text.</b>\n\n"
            "<b>❍ Flags:</b>\n"
            "<code>-pin</code>      → pin silently in groups\n"
            "<code>-pinloud</code>  → pin with notification\n"
            "<code>-nogroup</code>  → skip groups\n"
            "<code>-user</code>     → also send to users",
            parse_mode=ParseMode.HTML,
        )
        return

    # ── Load data ─────────────────────────────────────────────────────────────
    all_docs = get_broadcast_chats()
    counts   = get_broadcast_count()

    groups  = [d for d in all_docs if d.get("type") == "group"]
    private = [d for d in all_docs if d.get("type") == "private"]

    # ── Starting message ──────────────────────────────────────────────────────
    targets = 0
    if not flag_nogroup:
        targets += len(groups)
    if flag_user:
        targets += len(private)

    if targets == 0:
        await message.reply(
            "<b>❍ No targets found in broadcast list.</b>\n"
            "<b>❍ Add users/groups first.</b>",
            parse_mode=ParseMode.HTML,
        )
        return

    pm = await message.reply(
        f"<b>❍ Broadcast Started</b>\n\n"
        f"<b>❍ Total    :</b> <code>{counts['total']}</code>\n"
        f"<b>❍ Groups   :</b> <code>{len(groups)}</code>\n"
        f"<b>❍ Users    :</b> <code>{len(private)}</code>\n"
        f"<b>❍ Targets  :</b> <code>{targets}</code>\n\n"
        f"<b>❍ Flags    :</b> "
        f"{'pin ' if flag_pin else ''}"
        f"{'pinloud ' if flag_pinloud else ''}"
        f"{'nogroup ' if flag_nogroup else ''}"
        f"{'user ' if flag_user else ''}"
        f"<code>{'none' if not any([flag_pin, flag_pinloud, flag_nogroup, flag_user]) else ''}</code>",
        parse_mode=ParseMode.HTML,
    )

    success_g = 0
    success_u = 0
    pinned    = 0
    failed    = 0

    # ── Broadcast to groups ───────────────────────────────────────────────────
    if not flag_nogroup:
        for doc in groups:
            cid = int(doc["chat_id"])
            try:
                if broadcast_type == "reply":
                    sent = await bot.forward_messages(cid, broadcast_msg.chat.id, broadcast_msg.id)
                else:
                    sent = await bot.send_message(cid, broadcast_msg, parse_mode=ParseMode.HTML)

                success_g += 1

                # Pin logic
                if flag_pin or flag_pinloud:
                    try:
                        await bot.pin_chat_message(
                            cid,
                            sent.id,
                            disable_notification=flag_pin,  # silent if -pin, loud if -pinloud
                        )
                        pinned += 1
                    except ChatAdminRequired:
                        pass
                    except Exception:
                        pass

            except FloodWait as e:
                wait = int(e.value)
                if wait > 200:
                    failed += 1
                    continue
                await asyncio.sleep(wait)
                try:
                    if broadcast_type == "reply":
                        await bot.forward_messages(cid, broadcast_msg.chat.id, broadcast_msg.id)
                    else:
                        await bot.send_message(cid, broadcast_msg, parse_mode=ParseMode.HTML)
                    success_g += 1
                except Exception:
                    failed += 1

            except (UserIsBlocked, ChatWriteForbidden, PeerIdInvalid):
                remove_broadcast_chat(cid)
                failed += 1

            except Exception:
                failed += 1

            await asyncio.sleep(0.4)

    # ── Broadcast to users ────────────────────────────────────────────────────
    if flag_user:
        for doc in private:
            uid = int(doc["chat_id"])
            try:
                if broadcast_type == "reply":
                    await bot.forward_messages(uid, broadcast_msg.chat.id, broadcast_msg.id)
                else:
                    await bot.send_message(uid, broadcast_msg, parse_mode=ParseMode.HTML)
                success_u += 1

            except FloodWait as e:
                wait = int(e.value)
                if wait > 200:
                    failed += 1
                    continue
                await asyncio.sleep(wait)
                try:
                    if broadcast_type == "reply":
                        await bot.forward_messages(uid, broadcast_msg.chat.id, broadcast_msg.id)
                    else:
                        await bot.send_message(uid, broadcast_msg, parse_mode=ParseMode.HTML)
                    success_u += 1
                except Exception:
                    failed += 1

            except (UserIsBlocked, PeerIdInvalid):
                remove_broadcast_chat(uid)
                failed += 1

            except Exception:
                failed += 1

            await asyncio.sleep(0.4)

    # ── Final result ──────────────────────────────────────────────────────────
    await pm.edit_text(
        "<b>❍ Broadcast Completed ✅</b>\n\n"
        f"<b>❍ Groups  :</b> <code>{success_g}</code>\n"
        f"<b>❍ Users   :</b> <code>{success_u}</code>\n"
        f"<b>❍ Pinned  :</b> <code>{pinned}</code>\n"
        f"<b>❍ Failed  :</b> <code>{failed}</code>",
        parse_mode=ParseMode.HTML,
    )
