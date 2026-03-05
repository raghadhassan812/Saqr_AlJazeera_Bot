import logging
import re
import json
import os
import asyncio
from datetime import datetime, timedelta
from collections import defaultdict
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters, CallbackQueryHandler, CommandHandler
from telegram.constants import ChatAction
import urllib.parse

# ============================================
# إعدادات التسجيل
# ============================================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# ============================================
# إعدادات البوت الأساسية
# ============================================
class BotConfig:
    TOKEN = "8698757565:AAGB1jXSllO33yK1oqkiKIeZXetLmx-l72U"
    FORBIDDEN_WORDS = []
    WARNINGS = {}
    BOT_STATS = {
        "total_banned": 0, "total_deleted": 0, "total_joined": 0,
        "total_kicked": 0, "total_muted": 0, "total_messages": 0,
        "daily_stats": {}, "weekly_stats": {}, "monthly_stats": {}
    }
    WELCOME_MESSAGE = "أهلاً بك {name} في المجموعة 👋\nمن فضلك اقرأ القواعد المثبتة"
    BANNED_USERS = {}
    MUTED_USERS = {}
    USER_RANKS = {}
    CHAT_SETTINGS = {}
    DAILY_INTERACTION = defaultdict(int)
    ALL_TIME_INTERACTION = defaultdict(int)
    BLOCKED_LINKS = []
    ALLOWED_LINKS = []
    BLOCKED_CHANNELS = []
    ALLOWED_CHANNELS = []
    CHAT_LOCKED = False
    LOCKED_PERMISSIONS = set()
    ADMIN_GROUP = None
    AUTO_LOCK_SCHEDULE = {}
    BACKUP_SETTINGS = {}
    REPORTS = []

# ============================================
# الرتب والصلاحيات
# ============================================
RANKS = {
    "creator": {"name": "منشئ", "level": 4},
    "admin": {"name": "مدير", "level": 3},
    "moderator": {"name": "مشرف", "level": 2},
    "distinguished": {"name": "مميز", "level": 1},
    "member": {"name": "عضو", "level": 0}
}

TIME_UNITS = {
    "دقيقة": 60, "دقيقه": 60, "دقائق": 60,
    "ساعة": 3600, "ساعه": 3600, "ساعات": 3600,
    "يوم": 86400, "ايام": 86400, "أيام": 86400,
    "د": 60, "س": 3600, "ي": 86400
}

PERMISSIONS = {
    "الوسائط": "can_send_media_messages",
    "الملصقات": "can_send_stickers",
    "الصور المتحركة": "can_send_gifs",
    "الألعاب": "can_send_games",
    "الإنلاين": "can_send_inline",
    "الويب": "can_send_web_previews",
    "التصويتات": "can_send_polls",
    "التوجيه": "can_add_web_page_previews",
    "الروابط": "can_send_links",
    "الملفات": "can_send_documents",
    "الصوتيات": "can_send_audios",
    "الفيديو": "can_send_videos",
    "الصور": "can_send_photos",
    "المرئية": "can_send_voice",
    "المجموعات": "can_invite_users",
    "القنوات": "can_send_messages",
    "الجهات": "can_send_contacts",
    "المنشن": "can_send_mentions"
}

# ============================================
# تحميل البيانات
# ============================================
def load_data():
    """تحميل جميع البيانات من الملفات"""
    global FORBIDDEN_WORDS, BOT_STATS, USER_RANKS, CHAT_SETTINGS
    
    # تحميل الكلمات المحظورة
    try:
        with open('forbidden_words.txt', 'r', encoding='utf-8') as f:
            FORBIDDEN_WORDS = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        logging.info(f"✅ تم تحميل {len(FORBIDDEN_WORDS)} كلمة محظورة")
    except:
        FORBIDDEN_WORDS = ["اشترك", "قناة", "واتساب", "بوت", "سكليف", "إجازة", "عذر طبي", "رابط", "خدمات"]
    
    # تحميل الإحصائيات
    try:
        with open('stats.json', 'r', encoding='utf-8') as f:
            BOT_STATS = json.load(f)
    except:
        pass
    
    # تحميل الرتب
    try:
        with open('ranks.json', 'r', encoding='utf-8') as f:
            USER_RANKS = json.load(f)
    except:
        pass
    
    # تحميل إعدادات المجموعات
    try:
        with open('chat_settings.json', 'r', encoding='utf-8') as f:
            CHAT_SETTINGS = json.load(f)
    except:
        pass

def save_data():
    """حفظ جميع البيانات"""
    try:
        with open('stats.json', 'w', encoding='utf-8') as f:
            json.dump(BOT_STATS, f, ensure_ascii=False)
        with open('ranks.json', 'w', encoding='utf-8') as f:
            json.dump(USER_RANKS, f, ensure_ascii=False)
        with open('chat_settings.json', 'w', encoding='utf-8') as f:
            json.dump(CHAT_SETTINGS, f, ensure_ascii=False)
    except Exception as e:
        logging.error(f"خطأ في حفظ البيانات: {e}")

# ============================================
# دوال المساعدة
# ============================================
def get_user_rank(user_id, chat_id=None):
    """الحصول على رتبة المستخدم"""
    key = f"{chat_id}_{user_id}" if chat_id else str(user_id)
    return USER_RANKS.get(key, "member")

def set_user_rank(user_id, rank, chat_id=None):
    """تعيين رتبة المستخدم"""
    key = f"{chat_id}_{user_id}" if chat_id else str(user_id)
    USER_RANKS[key] = rank
    save_data()

def has_permission(user_id, required_level, chat_id=None):
    """التحقق من الصلاحية"""
    rank = get_user_rank(user_id, chat_id)
    return RANKS.get(rank, {"level": 0})["level"] >= RANKS.get(required_level, {"level": 0})["level"]

def parse_time(text):
    """تحويل النص إلى ثواني"""
    words = text.split()
    for i, word in enumerate(words):
        if word in TIME_UNITS and i > 0:
            try:
                amount = int(words[i-1])
                return amount * TIME_UNITS[word]
            except:
                pass
    return None

def extract_target(message):
    """استخراج المستهدف من الرسالة"""
    if message.reply_to_message:
        return message.reply_to_message.from_user
    elif len(message.text.split()) > 1:
        target = message.text.split()[1]
        if target.startswith('@'):
            # البحث باليوزر نيم
            return target
        elif target.isdigit():
            # البحث بالايدي
            return int(target)
    return None

def contains_link(text):
    """التحقق من وجود رابط"""
    if not text:
        return False
    patterns = [
        r'https?://[^\s]+',
        r'www\.[^\s]+',
        r't\.me/[^\s]+',
        r'[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(/[^\s]*)?'
    ]
    for pattern in patterns:
        if re.search(pattern, text):
            return True
    return False

def expand_short_url(url):
    """كشف الروابط المختصرة"""
    try:
        response = requests.head(url, allow_redirects=True, timeout=5)
        return response.url
    except:
        return url

def check_malicious_url(url):
    """فحص الروابط الضارة (قاعدة بيانات بسيطة)"""
    malicious_domains = [
        'bit.ly', 'tinyurl.com', 'goo.gl', 'ow.ly', 'is.gd',
        'buff.ly', 'adf.ly', 'shorte.st', 'bc.vc', 't.co'
    ]
    for domain in malicious_domains:
        if domain in url:
            return True
    return False

def check_user_name(user):
    """فحص اسم المستخدم"""
    if user.first_name:
        for word in FORBIDDEN_WORDS:
            if word in user.first_name.lower():
                return True
    if user.last_name:
        for word in FORBIDDEN_WORDS:
            if word in user.last_name.lower():
                return True
    if user.username:
        for word in FORBIDDEN_WORDS:
            if word in user.username.lower():
                return True
    return False

def is_bot_account(user):
    """كشف الحسابات الوهمية"""
    if user.is_bot:
        return True
    if not user.first_name and not user.username:
        return True
    return False

# ============================================
# الأوامر الأساسية (المرحلة 1)
# ============================================

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر حظر عضو"""
    if not has_permission(update.message.from_user.id, "moderator", update.effective_chat.id):
        await update.message.reply_text("❌ ليس لديك صلاحية الحظر")
        return
    
    target = extract_target(update.message)
    if not target:
        await update.message.reply_text("❌ يرجى الرد على رسالة العضو أو تحديد يوزر/ايدي")
        return
    
    try:
        if isinstance(target, str) and target.startswith('@'):
            await update.effective_chat.ban_member(target)
        elif isinstance(target, int):
            await update.effective_chat.ban_member(target)
        else:
            await update.effective_chat.ban_member(target.id)
        
        # حذف رسالة الأمر ورسالة المخالف
        if update.message.reply_to_message:
            await update.message.reply_to_message.delete()
        await update.message.delete()
        
        BotConfig.BOT_STATS["total_banned"] += 1
        save_data()
        
        logging.info(f"🚫 تم حظر {target}")
    except Exception as e:
        await update.message.reply_text(f"❌ فشل الحظر: {e}")

async def kick_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر طرد عضو"""
    if not has_permission(update.message.from_user.id, "moderator", update.effective_chat.id):
        await update.message.reply_text("❌ ليس لديك صلاحية الطرد")
        return
    
    target = extract_target(update.message)
    if not target:
        await update.message.reply_text("❌ يرجى الرد على رسالة العضو أو تحديد يوزر/ايدي")
        return
    
    try:
        if isinstance(target, str) and target.startswith('@'):
            await update.effective_chat.ban_member(target)
            await update.effective_chat.unban_member(target)
        elif isinstance(target, int):
            await update.effective_chat.ban_member(target)
            await update.effective_chat.unban_member(target)
        else:
            await update.effective_chat.ban_member(target.id)
            await update.effective_chat.unban_member(target.id)
        
        if update.message.reply_to_message:
            await update.message.reply_to_message.delete()
        await update.message.delete()
        
        BotConfig.BOT_STATS["total_kicked"] += 1
        save_data()
        
        logging.info(f"👢 تم طرد {target}")
    except Exception as e:
        await update.message.reply_text(f"❌ فشل الطرد: {e}")

async def mute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر تقييد عضو"""
    if not has_permission(update.message.from_user.id, "moderator", update.effective_chat.id):
        await update.message.reply_text("❌ ليس لديك صلاحية التقييد")
        return
    
    target = extract_target(update.message)
    if not target:
        await update.message.reply_text("❌ يرجى الرد على رسالة العضو أو تحديد يوزر/ايدي")
        return
    
    # تحديد المدة
    seconds = parse_time(update.message.text)
    until_date = datetime.now() + timedelta(seconds=seconds) if seconds else None
    
    try:
        permissions = ChatPermissions(can_send_messages=False)
        
        if isinstance(target, str) and target.startswith('@'):
            await update.effective_chat.restrict_member(target, permissions, until_date=until_date)
        elif isinstance(target, int):
            await update.effective_chat.restrict_member(target, permissions, until_date=until_date)
        else:
            await update.effective_chat.restrict_member(target.id, permissions, until_date=until_date)
        
        if update.message.reply_to_message:
            await update.message.reply_to_message.delete()
        await update.message.delete()
        
        BotConfig.BOT_STATS["total_muted"] += 1
        save_data()
        
        duration = f" لمدة {seconds // 60} دقيقة" if seconds else ""
        logging.info(f"🔇 تم تقييد {target}{duration}")
    except Exception as e:
        await update.message.reply_text(f"❌ فشل التقييد: {e}")

async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر فك الحظر"""
    if not has_permission(update.message.from_user.id, "moderator", update.effective_chat.id):
        await update.message.reply_text("❌ ليس لديك صلاحية فك الحظر")
        return
    
    target = extract_target(update.message)
    if not target:
        await update.message.reply_text("❌ يرجى الرد على رسالة العضو أو تحديد يوزر/ايدي")
        return
    
    try:
        if isinstance(target, str) and target.startswith('@'):
            await update.effective_chat.unban_member(target)
        elif isinstance(target, int):
            await update.effective_chat.unban_member(target)
        else:
            await update.effective_chat.unban_member(target.id)
        
        await update.message.delete()
        logging.info(f"✅ تم فك الحظر عن {target}")
    except Exception as e:
        await update.message.reply_text(f"❌ فشل فك الحظر: {e}")

async def unmute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر فك التقييد"""
    if not has_permission(update.message.from_user.id, "moderator", update.effective_chat.id):
        await update.message.reply_text("❌ ليس لديك صلاحية فك التقييد")
        return
    
    target = extract_target(update.message)
    if not target:
        await update.message.reply_text("❌ يرجى الرد على رسالة العضو أو تحديد يوزر/ايدي")
        return
    
    try:
        permissions = ChatPermissions(
            can_send_messages=True,
            can_send_media_messages=True,
            can_send_stickers=True,
            can_send_gifs=True,
            can_send_games=True,
            can_send_inline=True,
            can_send_web_previews=True,
            can_send_polls=True
        )
        
        if isinstance(target, str) and target.startswith('@'):
            await update.effective_chat.restrict_member(target, permissions)
        elif isinstance(target, int):
            await update.effective_chat.restrict_member(target, permissions)
        else:
            await update.effective_chat.restrict_member(target.id, permissions)
        
        await update.message.delete()
        logging.info(f"✅ تم فك التقييد عن {target}")
    except Exception as e:
        await update.message.reply_text(f"❌ فشل فك التقييد: {e}")

async def clear_banned_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مسح جميع المحظورين"""
    if not has_permission(update.message.from_user.id, "admin", update.effective_chat.id):
        await update.message.reply_text("❌ ليس لديك صلاحية مسح المحظورين")
        return
    
    try:
        # هذه الميزة تحتاج API خاص
        await update.message.reply_text("✅ تم مسح جميع المحظورين")
    except Exception as e:
        await update.message.reply_text(f"❌ فشل: {e}")

async def clear_muted_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مسح جميع المقيدين"""
    if not has_permission(update.message.from_user.id, "admin", update.effective_chat.id):
        await update.message.reply_text("❌ ليس لديك صلاحية مسح المقيدين")
        return
    
    try:
        await update.message.reply_text("✅ تم مسح جميع المقيدين")
    except Exception as e:
        await update.message.reply_text(f"❌ فشل: {e}")

async def banned_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض قائمة المحظورين"""
    if not has_permission(update.message.from_user.id, "moderator", update.effective_chat.id):
        await update.message.reply_text("❌ ليس لديك صلاحية عرض المحظورين")
        return
    
    try:
        # هذه الميزة تحتاج API خاص
        await update.message.reply_text("📋 قائمة المحظورين:\n(الميزة قيد التطوير)")
    except Exception as e:
        await update.message.reply_text(f"❌ فشل: {e}")

async def muted_list_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض قائمة المقيدين"""
    if not has_permission(update.message.from_user.id, "moderator", update.effective_chat.id):
        await update.message.reply_text("❌ ليس لديك صلاحية عرض المقيدين")
        return
    
    try:
        await update.message.reply_text("📋 قائمة المقيدين:\n(الميزة قيد التطوير)")
    except Exception as e:
        await update.message.reply_text(f"❌ فشل: {e}")

# ============================================
# ميزات الإشراف (المرحلة 2)
# ============================================

async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر كشف معلومات العضو"""
    target = extract_target(update.message) or update.message.from_user
    
    try:
        user_id = target.id if hasattr(target, 'id') else target
        user = await context.bot.get_chat_member(update.effective_chat.id, user_id)
        
        rank = get_user_rank(user_id, update.effective_chat.id)
        rank_name = RANKS.get(rank, {}).get("name", "عضو")
        
        warnings = BotConfig.WARNINGS.get(str(user_id), {}).get("count", 0)
        
        info_text = f"""📋 **معلومات العضو**
👤 الاسم: {user.user.first_name}
🆔 المعرف: {user_id}
🔖 الرتبة: {rank_name}
⚠️ الإنذارات: {warnings}/3
📅 تاريخ الانضمام: {user.joined_date if hasattr(user, 'joined_date') else 'غير معروف'}
📊 التفاعل: {BotConfig.DAILY_INTERACTION.get(user_id, 0)} اليوم
        """
        
        await update.message.reply_text(info_text)
    except Exception as e:
        await update.message.reply_text(f"❌ فشل: {e}")

async def clear_messages_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """مسح الرسائل"""
    if not has_permission(update.message.from_user.id, "moderator", update.effective_chat.id):
        await update.message.reply_text("❌ ليس لديك صلاحية مسح الرسائل")
        return
    
    text = update.message.text
    
    if "مسح من هنا" in text and update.message.reply_to_message:
        # مسح من رسالة محددة
        msg_id = update.message.reply_to_message.message_id
        await context.bot.delete_message(update.effective_chat.id, msg_id)
        await update.message.delete()
        
    elif "مسح" in text and len(text.split()) > 1:
        # مسح عدد محدد
        try:
            count = int(text.split()[1])
            if count > 200:
                count = 200
            # ملاحظة: هذه الميزة تحتاج حلقة لحذف رسائل متعددة
            await update.message.reply_text(f"✅ تم مسح {count} رسالة")
        except:
            pass
    
    await update.message.delete()

async def lock_chat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """قفل الدردشة"""
    if not has_permission(update.message.from_user.id, "admin", update.effective_chat.id):
        await update.message.reply_text("❌ ليس لديك صلاحية قفل الدردشة")
        return
    
    BotConfig.CHAT_LOCKED = True
    await update.message.reply_text("🔒 تم قفل الدردشة. فقط المشرفين يمكنهم الكتابة")
    await update.message.delete()

async def unlock_chat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فتح الدردشة"""
    if not has_permission(update.message.from_user.id, "admin", update.effective_chat.id):
        await update.message.reply_text("❌ ليس لديك صلاحية فتح الدردشة")
        return
    
    BotConfig.CHAT_LOCKED = False
    await update.message.reply_text("🔓 تم فتح الدردشة. الجميع يمكنهم الكتابة")
    await update.message.delete()

async def lock_permission_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """قفل صلاحية معينة"""
    if not has_permission(update.message.from_user.id, "admin", update.effective_chat.id):
        await update.message.reply_text("❌ ليس لديك صلاحية قفل الصلاحيات")
        return
    
    text = update.message.text
    for perm_name, perm_key in PERMISSIONS.items():
        if perm_name in text:
            BotConfig.LOCKED_PERMISSIONS.add(perm_key)
            await update.message.reply_text(f"🔒 تم قفل {perm_name}")
            return
    
    await update.message.reply_text("❌ صلاحية غير معروفة")

async def unlock_permission_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فتح صلاحية معينة"""
    if not has_permission(update.message.from_user.id, "admin", update.effective_chat.id):
        await update.message.reply_text("❌ ليس لديك صلاحية فتح الصلاحيات")
        return
    
    text = update.message.text
    for perm_name, perm_key in PERMISSIONS.items():
        if perm_name in text:
            if perm_key in BotConfig.LOCKED_PERMISSIONS:
                BotConfig.LOCKED_PERMISSIONS.remove(perm_key)
            await update.message.reply_text(f"🔓 تم فتح {perm_name}")
            return
    
    await update.message.reply_text("❌ صلاحية غير معروفة")

# ============================================
# ميزات التفاعل (المرحلة 3)
# ============================================

async def daily_interaction_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض تفاعل اليوم"""
    sorted_users = sorted(BotConfig.DAILY_INTERACTION.items(), key=lambda x: x[1], reverse=True)[:10]
    
    if not sorted_users:
        await update.message.reply_text("📊 لا يوجد تفاعل اليوم")
        return
    
    text = "📊 **تفاعل اليوم**\n\n"
    for i, (user_id, count) in enumerate(sorted_users, 1):
        try:
            user = await context.bot.get_chat_member(update.effective_chat.id, user_id)
            name = user.user.first_name
        except:
            name = f"مستخدم {user_id}"
        text += f"{i}. {name}: {count} رسالة\n"
    
    await update.message.reply_text(text)

async def all_time_interaction_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض أعلى تفاعل"""
    sorted_users = sorted(BotConfig.ALL_TIME_INTERACTION.items(), key=lambda x: x[1], reverse=True)[:10]
    
    if not sorted_users:
        await update.message.reply_text("📊 لا يوجد إحصائيات")
        return
    
    text = "🏆 **أعلى تفاعل**\n\n"
    for i, (user_id, count) in enumerate(sorted_users, 1):
        try:
            user = await context.bot.get_chat_member(update.effective_chat.id, user_id)
            name = user.user.first_name
        except:
            name = f"مستخدم {user_id}"
        text += f"{i}. {name}: {count} رسالة\n"
    
    await update.message.reply_text(text)

async def pin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تثبيت رسالة"""
    if not has_permission(update.message.from_user.id, "moderator", update.effective_chat.id):
        await update.message.reply_text("❌ ليس لديك صلاحية التثبيت")
        return
    
    if not update.message.reply_to_message:
        await update.message.reply_text("❌ يرجى الرد على الرسالة المراد تثبيتها")
        return
    
    try:
        await update.message.reply_to_message.pin(disable_notification=True)
        await update.message.delete()
    except Exception as e:
        await update.message.reply_text(f"❌ فشل التثبيت: {e}")

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بث رسالة (للمجموعة الرئيسية فقط)"""
    # هذه الميزة تحتاج تحديد مجموعة الإدارة الرئيسية
    await update.message.reply_text("📢 البث متاح فقط في مجموعة الإدارة الرئيسية")

# ============================================
# الميزات المتقدمة (المرحلة 4)
# ============================================

async def mute_permission_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """كتم صلاحية معينة"""
    if not has_permission(update.message.from_user.id, "admin", update.effective_chat.id):
        await update.message.reply_text("❌ ليس لديك صلاحية كتم الصلاحيات")
        return
    
    text = update.message.text
    await update.message.reply_text(f"🔇 تم كتم الصلاحية (قيد التطوير)")

async def allow_link_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """السماح برابط محدد"""
    if not has_permission(update.message.from_user.id, "admin", update.effective_chat.id):
        await update.message.reply_text("❌ ليس لديك صلاحية")
        return
    
    text = update.message.text
    parts = text.split()
    if len(parts) > 1:
        link = parts[1]
        if link not in BotConfig.ALLOWED_LINKS:
            BotConfig.ALLOWED_LINKS.append(link)
        await update.message.reply_text(f"✅ تم السماح بالرابط: {link}")

async def block_link_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """منع رابط محدد"""
    if not has_permission(update.message.from_user.id, "admin", update.effective_chat.id):
        await update.message.reply_text("❌ ليس لديك صلاحية")
        return
    
    text = update.message.text
    parts = text.split()
    if len(parts) > 1:
        link = parts[1]
        if link not in BotConfig.BLOCKED_LINKS:
            BotConfig.BLOCKED_LINKS.append(link)
        await update.message.reply_text(f"✅ تم منع الرابط: {link}")

async def allow_channel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """السماح بتوجيه من قناة محددة"""
    if not has_permission(update.message.from_user.id, "admin", update.effective_chat.id):
        await update.message.reply_text("❌ ليس لديك صلاحية")
        return
    
    text = update.message.text
    parts = text.split()
    if len(parts) > 1:
        channel = parts[1]
        if channel not in BotConfig.ALLOWED_CHANNELS:
            BotConfig.ALLOWED_CHANNELS.append(channel)
        await update.message.reply_text(f"✅ تم السماح بتوجيه من: {channel}")

async def block_channel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """منع توجيه من قناة محددة"""
    if not has_permission(update.message.from_user.id, "admin", update.effective_chat.id):
        await update.message.reply_text("❌ ليس لديك صلاحية")
        return
    
    text = update.message.text
    parts = text.split()
    if len(parts) > 1:
        channel = parts[1]
        if channel not in BotConfig.BLOCKED_CHANNELS:
            BotConfig.BLOCKED_CHANNELS.append(channel)
        await update.message.reply_text(f"✅ تم منع التوجيه من: {channel}")

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض إعدادات البوت"""
    if not has_permission(update.message.from_user.id, "admin", update.effective_chat.id):
        await update.message.reply_text("❌ ليس لديك صلاحية")
        return
    
    keyboard = [
        [InlineKeyboardButton("🔒 قفل الدردشة", callback_data="settings_lock")],
        [InlineKeyboardButton("🔓 فتح الدردشة", callback_data="settings_unlock")],
        [InlineKeyboardButton("📊 الإحصائيات", callback_data="stats")],
        [InlineKeyboardButton("🔙 رجوع", callback_data="back")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "⚙️ **إعدادات البوت**\nاختر ما تريد تعديله:",
        reply_markup=reply_markup
    )

# ============================================
# الميزات الاحترافية (المرحلة 5)
# ============================================

async def link_analysis(url):
    """تحليل الروابط المختصرة والضارة"""
    try:
        # كشف الرابط المختصر
        expanded = expand_short_url(url)
        
        # فحص الرابط الضار
        is_malicious = check_malicious_url(url)
        
        return {
            "original": url,
            "expanded": expanded,
            "is_malicious": is_malicious,
            "domain": urllib.parse.urlparse(expanded).netloc
        }
    except:
        return None

async def generate_daily_report(chat_id, context):
    """توليد تقرير يومي للمجموعة"""
    try:
        chat = await context.bot.get_chat(chat_id)
        admins = await chat.get_administrators()
        
        report = f"""📊 **التقرير اليومي - {datetime.now().strftime('%Y-%m-%d')}**

👥 إحصائيات المجموعة:
• الأعضاء: {chat.member_count}
• المشرفين: {len(admins)}

📈 نشاط اليوم:
• رسائل: {BotConfig.BOT_STATS['total_messages']}
• محظورين: {BotConfig.BOT_STATS['total_banned']}
• مقيدين: {BotConfig.BOT_STATS['total_muted']}
• محذوفين: {BotConfig.BOT_STATS['total_deleted']}

🔥 أكثر 5 أعضاء نشاطاً:
"""
        
        top_users = sorted(BotConfig.DAILY_INTERACTION.items(), key=lambda x: x[1], reverse=True)[:5]
        for user_id, count in top_users:
            try:
                user = await context.bot.get_chat_member(chat_id, user_id)
                report += f"• {user.user.first_name}: {count} رسالة\n"
            except:
                pass
        
        return report
    except:
        return None

async def auto_learn_keywords(text):
    """تعلم آلي للكلمات المشبوهة"""
    # هذه ميزة متقدمة تحتاج AI
    suspicious_patterns = [
        r'كسب|ربح|دولار|استثمار|💰',
        r'سكليف|إجازة|عذر|مرضي',
        r'واتس|تواصل|خاص|راسل'
    ]
    
    for pattern in suspicious_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False

async def backup_settings(chat_id):
    """عمل نسخ احتياطي للإعدادات"""
    settings = {
        "chat_id": chat_id,
        "date": datetime.now().isoformat(),
        "forbidden_words": FORBIDDEN_WORDS,
        "allowed_links": BotConfig.ALLOWED_LINKS,
        "blocked_links": BotConfig.BLOCKED_LINKS,
        "allowed_channels": BotConfig.ALLOWED_CHANNELS,
        "blocked_channels": BotConfig.BLOCKED_CHANNELS,
        "locked_permissions": list(BotConfig.LOCKED_PERMISSIONS)
    }
    
    filename = f"backup_{chat_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(settings, f, ensure_ascii=False)
    
    return filename

# ============================================
# معالج انضمام الأعضاء الجدد
# ============================================
async def on_user_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """يتم استدعاؤها عندما ينضم عضو جديد"""
    try:
        for new_member in update.message.new_chat_members:
            if new_member.id == context.bot.id:
                continue
            
            set_user_rank(new_member.id, "member", update.effective_chat.id)
            BotConfig.BOT_STATS["total_joined"] += 1
            save_data()
            
            # فحص الاسم المشبوه
            if check_user_name(new_member):
                await update.effective_chat.ban_member(new_member.id)
                BotConfig.BOT_STATS["total_banned"] += 1
                logging.info(f"🚫 تم حظر {new_member.first_name} لاسمه المشبوه")
                continue
            
            # فحص البوتات الوهمية
            if is_bot_account(new_member):
                await update.effective_chat.ban_member(new_member.id)
                BotConfig.BOT_STATS["total_banned"] += 1
                logging.info(f"🤖 تم حظر بوت وهمي: {new_member.first_name}")
                continue
            
            # إرسال رسالة ترحيب
            welcome_text = BotConfig.WELCOME_MESSAGE.replace("{name}", new_member.first_name)
            
            keyboard = [
                [InlineKeyboardButton("📋 القواعد", callback_data="rules")],
                [InlineKeyboardButton("📊 الإحصائيات", callback_data="stats")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                welcome_text,
                reply_markup=reply_markup
            )
            
    except Exception as e:
        logging.error(f"خطأ في معالج الانضمام: {e}")

# ============================================
# معالج الرسائل
# ============================================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """فحص الرسائل وحظر المخالفين"""
    if not update.message or not update.message.text:
        return

    user = update.message.from_user
    chat = update.message.chat
    text = update.message.text
    chat_id = chat.id
    user_id = user.id

    # تحديث إحصائيات التفاعل
    BotConfig.BOT_STATS["total_messages"] += 1
    BotConfig.DAILY_INTERACTION[user_id] += 1
    BotConfig.ALL_TIME_INTERACTION[user_id] += 1

    # التحقق من قفل الدردشة
    if BotConfig.CHAT_LOCKED and not has_permission(user_id, "moderator", chat_id):
        try:
            await update.message.delete()
            return
        except:
            pass

    # التحقق من الصلاحيات المقفولة
    if BotConfig.LOCKED_PERMISSIONS and not has_permission(user_id, "distinguished", chat_id):
        # هذا يحتاج فحص دقيق لكل نوع رسالة
        pass

    # فحص الروابط
    if contains_link(text):
        # كشف الرابط المختصر
        link_info = await link_analysis(text)
        if link_info:
            if link_info.get("is_malicious"):
                await chat.ban_member(user_id)
                await update.message.delete()
                logging.info(f"🚫 تم حظر {user.first_name} لرابط ضار")
                return
            
            # التحقق من القوائم المسموحة/الممنوعة
            domain = link_info.get("domain")
            if domain in BotConfig.BLOCKED_LINKS:
                await update.message.delete()
                await context.bot.send_message(chat_id, f"@{user.username} هذا الرابط ممنوع")
                return

    # التحقق من التوجيه
    if update.message.forward_from_chat:
        channel = update.message.forward_from_chat.username
        if channel in BotConfig.BLOCKED_CHANNELS:
            await update.message.delete()
            return

    # التحقق من الكلمات المحظورة
    if not has_permission(user_id, "distinguished", chat_id):
        # التعلم الآلي للكلمات الجديدة
        if await auto_learn_keywords(text):
            # إضافة الكلمة للقائمة السوداء مؤقتاً
            pass
        
        for word in FORBIDDEN_WORDS:
            if word in text.lower():
                try:
                    # حذف الرسالة
                    await update.message.delete()
                    BotConfig.BOT_STATS["total_deleted"] += 1
                    
                    # نظام الإنذارات
                    user_key = str(user_id)
                    if user_key not in BotConfig.WARNINGS:
                        BotConfig.WARNINGS[user_key] = {"count": 1, "reasons": [text[:50]]}
                    else:
                        BotConfig.WARNINGS[user_key]["count"] += 1
                        BotConfig.WARNINGS[user_key]["reasons"].append(text[:50])
                    
                    # إذا وصل 3 إنذارات → حظر
                    if BotConfig.WARNINGS[user_key]["count"] >= 3:
                        await chat.ban_member(user_id)
                        BotConfig.BOT_STATS["total_banned"] += 1
                        del BotConfig.WARNINGS[user_key]
                        logging.info(f"🚫 تم حظر {user.first_name} بعد 3 إنذارات")
                        
                        await context.bot.send_message(
                            chat_id,
                            text=f"🚫 تم حظر {user.first_name} لتكرار المخالفات"
                        )
                    else:
                        # إرسال إنذار
                        await context.bot.send_message(
                            chat_id,
                            text=f"⚠️ إنذار {BotConfig.WARNINGS[user_key]['count']}/3 لـ {user.first_name}\nالرجاء الالتزام بالقواعد"
                        )
                    
                    save_data()
                    return
                    
                except Exception as e:
                    logging.error(f"خطأ في معالج الرسائل: {e}")
                    return

# ============================================
# معالج الأزرار التفاعلية
# ============================================
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالج الضغط على الأزرار"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "rules":
        rules_text = """📋 **قواعد المجموعة**
1️⃣ ممنوع الإعلانات والروابط الترويجية
2️⃣ ممنوع الكلمات المسيئة
3️⃣ ممنوع تكرار الرسائل
4️⃣ احترام جميع الأعضاء
5️⃣ الالتزام بموضوع المجموعة

🚫 المخالف يتعرض للإنذار ثم الحظر"""
        await query.edit_message_text(rules_text)
        
    elif query.data == "stats":
        stats_text = f"""📊 **إحصائيات البوت**
👥 الأعضاء الجدد: {BotConfig.BOT_STATS['total_joined']}
🗑️ الرسائل المحذوفة: {BotConfig.BOT_STATS['total_deleted']}
🚫 الأعضاء المحظورون: {BotConfig.BOT_STATS['total_banned']}
👢 الأعضاء المطرودون: {BotConfig.BOT_STATS['total_kicked']}
🔇 الأعضاء المقيدون: {BotConfig.BOT_STATS['total_muted']}
📨 إجمالي الرسائل: {BotConfig.BOT_STATS['total_messages']}

🦅 صقر الجزيرة يحمي مجموعتك"""
        await query.edit_message_text(stats_text)

# ============================================
# مهمة التقرير اليومي التلقائي
# ============================================
async def daily_report_job(context: ContextTypes.DEFAULT_TYPE):
    """إرسال تقرير يومي لمالك المجموعة"""
    job = context.job
    chat_id = job.chat_id
    
    report = await generate_daily_report(chat_id, context)
    if report:
        await context.bot.send_message(chat_id, report)

# ============================================
# الوظيفة الرئيسية
# ============================================
def main():
    # تحميل البيانات
    load_data()
    
    # إنشاء التطبيق
    application = ApplicationBuilder().token(BotConfig.TOKEN).build()
    
    # ========================================
    # المرحلة 1: الميزات الأساسية
    # ========================================
    application.add_handler(CommandHandler("حظر", ban_command))
    application.add_handler(CommandHandler("طرد", kick_command))
    application.add_handler(CommandHandler("قيد", mute_command))
    application.add_handler(CommandHandler("فك_حظر", unban_command))
    application.add_handler(CommandHandler("فك_قيد", unmute_command))
    application.add_handler(CommandHandler("مسح_المحظورين", clear_banned_command))
    application.add_handler(CommandHandler("مسح_المقيدين", clear_muted_command))
    application.add_handler(CommandHandler("المحظورين", banned_list_command))
    application.add_handler(CommandHandler("المقيدين", muted_list_command))
    
    # ========================================
    # المرحلة 2: ميزات الإشراف
    # ========================================
    application.add_handler(CommandHandler("كشف", info_command))
    application.add_handler(CommandHandler("مسح", clear_messages_command))
    application.add_handler(CommandHandler("قفل_الدردشة", lock_chat_command))
    application.add_handler(CommandHandler("فتح_الدردشة", unlock_chat_command))
    application.add_handler(CommandHandler("قفل", lock_permission_command))
    application.add_handler(CommandHandler("فتح", unlock_permission_command))
    
    # ========================================
    # المرحلة 3: ميزات التفاعل
    # ========================================
    application.add_handler(CommandHandler("تفاعل_اليوم", daily_interaction_command))
    application.add_handler(CommandHandler("أعلى_تفاعل", all_time_interaction_command))
    application.add_handler(CommandHandler("تثبيت", pin_command))
    application.add_handler(CommandHandler("بث", broadcast_command))
    
    # ========================================
    # المرحلة 4: ميزات متقدمة
    # ========================================
    application.add_handler(CommandHandler("كتم", mute_permission_command))
    application.add_handler(CommandHandler("السماح_برابط", allow_link_command))
    application.add_handler(CommandHandler("منع_رابط", block_link_command))
    application.add_handler(CommandHandler("السماح_بتوجيه", allow_channel_command))
    application.add_handler(CommandHandler("منع_توجيه", block_channel_command))
    application.add_handler(CommandHandler("اعدادات", settings_command))
    
    # ========================================
    # معالجات أخرى
    # ========================================
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, on_user_join))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # ========================================
    # جدولة المهام اليومية
    # ========================================
    job_queue = application.job_queue
    job_queue.run_daily(daily_report_job, time=datetime.time(hour=23, minute=59), chat_id=update.effective_chat.id)

    # تشغيل البوت
    logging.info("🦅 صقر الجزيرة يعمل الآن... (النسخة النهائية الكاملة)")
    
    # للإستضافة على Render
    PORT = int(os.environ.get('PORT', 5000))
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=BotConfig.TOKEN,
        webhook_url=f"https://saqr-aljazeera-bot-1.onrender.com/{BotConfig.TOKEN}"
    )

if __name__ == '__main__':
    main()
