# --------------------------------------------------------------------------------
#  ShizuMusic © 2026
#  Developed by Bad Munda ❤️
#
#  Unauthorized copying, editing, re-uploading or removing credits
#  from this source code is strictly prohibited.
# --------------------------------------------------------------------------------

from pyrogram import filters
from pyrogram.handlers import MessageHandler
from pyrogram.types import Message

from ShizuMusic import bot


async def _block_middleware(_, message: Message) -> None:
    """
    Global middleware — runs at group=-1, before every other handler.
    Silently stops blocked groups / users from reaching any plugin.
    """
    try:
        # Import from utils.db directly — no circular dependency
        from ShizuMusic.utils.db import is_group_blocked, is_user_blocked_db
    except ImportError:
        return

    chat_id = message.chat.id      if message.chat      else None
    user_id = message.from_user.id if message.from_user else None

    if chat_id and is_group_blocked(chat_id):
        message.stop_propagation()
        return

    if user_id and is_user_blocked_db(user_id):
        message.stop_propagation()
        return


def register_block_middleware() -> None:
    """
    Register the global block middleware.
    Call once in __main__.py BEFORE plugins are loaded.

    Usage:
        from ShizuMusic.utils.decorators import register_block_middleware
        register_block_middleware()
    """
    bot.add_handler(
        MessageHandler(
            _block_middleware,
            filters=filters.all,
        ),
        group=-1,
    )
    
