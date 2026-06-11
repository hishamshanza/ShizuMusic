"""
config.py — All environment variables in one place.
Copy sample.env → .env and fill in your values.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── Required ──────────────────────────────────────────────────────────────────
API_ID          = int(os.environ["34437217"])
API_HASH        = os.environ["e3d23047f69ea38cef9eec0fc1d1f94a"]
BOT_TOKEN       = os.environ["8318780474:AAGKxt-XS5xRpIGkE2r_EtocWdcghgVth-U"]
STRING_SESSION  = os.environ["BQINeGEAMoZwao15Q7VfcQq8pGpJ_K11hgNUnyqfWgawxRsFPTsQ6UqvYLqA7TBTn35-n1zDy8Qb3SPC4jAz1rRiwXt5TpjEcwE-G5Gp9dhW9piwZMh4pSQfhmmjq4pLr5R3MLGENuGjyxK-cvzSONmLlKB4eL3LLa1Y41qXoayiXbdngeeX-CdouCPgzohSi9g56xP-4ajboj8XhDH6Zf2cFdIx7xyZztsxyC5eB1eZ8OmZYWHX0t1RN27HvLRicZ0sdVPtPrwXf1sxq-ZISPUe-FvD1a7OjbtBhQBPkOIG2EOTd3YCx1Es42H-uI3QDRq-wLb2s_sqK9zkg9FZMAjglr0QewAAAAHv1oQ6AQ"]
MONGO_DB_URL    = os.environ["mongodb+srv://hishammon:hishammon@cluster0.2g7bqyf.mongodb.net/?appName=Cluster0"]
OWNER_ID        = int(os.environ["8908717915"])

# ── Optional ──────────────────────────────────────────────────────────────────
BOT_NAME         = os.getenv("BOT_NAME", "ꜱᴋɪʟʟ x ꜰɪꜰᴀ ꜱᴛʀᴇᴀᴍ")
BOT_LINK         = os.getenv("BOT_LINK", "http://t.me/Skill_x_fifa_stream_bot")
UPDATES_CHANNEL  = os.getenv("UPDATES_CHANNEL", "https://t.me/skillxfifaworld")
SUPPORT_GROUP    = os.getenv("SUPPORT_GROUP", "https://t.me/skillxfifaworld")
LOGGER_ID        = int(os.getenv("LOGGER_ID", "0"))
PING_IMG_URL     = os.getenv("PING_IMG_URL", "https://files.catbox.moe/ddzvc0.jpg",)
SESSION_NAME     = os.getenv("SESSION_NAME", "ShizuMusic")
PORT             = int(os.getenv("PORT", 10000))

#── Start ───────────────────────────────────────────────────────────────────────
START_ANIMATIONS = [
    "https://telegra.ph/file/1a3c152717eb9d2e94dc2.mp4",
    "https://graph.org/file/ba7699c28dab379b518ca.mp4",
    "https://graph.org/file/83ebf52e8bbf138620de7.mp4",
    "https://graph.org/file/82fd67aa56eb1b299e08d.mp4",
    "https://graph.org/file/318eac81e3d4667edcb77.mp4",
    "https://graph.org/file/7c1aa59649fbf3ab422da.mp4",
    "https://graph.org/file/2a7f857f31b32766ac6fc.mp4",
]

# ── Limits ────────────────────────────────────────────────────────────────────
MAX_DURATION_SECONDS = 6000   # 30 minutes
QUEUE_LIMIT          = 20
COOLDOWN             = 10     # seconds between /play per chat
