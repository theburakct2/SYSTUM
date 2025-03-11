import logging
import sqlite3
import re
from datetime import datetime, timedelta
import pytz
from collections import Counter, defaultdict
from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass, field
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import json

# Bot Configuration
TOKEN = "8065737316:AAG1Y2d5PPI8l8Ct1f_cJZ34LtaaL-K9t6k"
VERSION = "2.0.0"
LAST_UPDATED = "2025-03-11"

     
# Language translations
TRANSLATIONS = {
    'tr': {
        'welcome': """
📊 Trend Analiz Botuna Hoşgeldiniz! (v{})

Kullanılabilir komutlar:
/trend_daily - Günlük trendleri görüntüle
/trend_weekly - Haftalık trendleri görüntüle
/trend_monthly - Aylık trendleri görüntüle
/popularity <kelime> - Belirli bir kelimenin popülerliğini kontrol et
/track <kelime> - Belirli bir kelimeyi takibe al (sadece yöneticiler)
/language - Dil değiştir
/stats - Bot istatistiklerini görüntüle
/help - Yardım menüsünü görüntüle
        """,
        'daily_header': "📊 Günlük Trend Raporu",
        'weekly_header': "📊 Haftalık Trend Raporu",
        'monthly_header': "📊 Aylık Trend Raporu",
        'top_words': "📝 En Çok Kullanılan Kelimeler:",
        'top_hashtags': "#️⃣ En Çok Kullanılan Hashtagler:",
        'times': "kez",
        'no_data': "Bu dönem için veri bulunamadı.",
        'admin_only': "Bu komut sadece yöneticiler için kullanılabilir.",
        'tracking_started': "Takip başladı:",
        'specify_word': "Lütfen bir kelime belirtin.",
        'popularity_stats': "📊 Popülerlik istatistikleri - '{}':",
        'total_uses': "Toplam kullanım:",
        'first_seen': "İlk görülme:",
        'last_seen': "Son görülme:",
        'no_stats': "Bu kelime için istatistik bulunamadı.",
        'stats_header': "📊 Bot İstatistikleri",
        'total_messages': "Toplam İşlenen Mesaj:",
        'total_words': "Toplam Benzersiz Kelime:",
        'total_hashtags': "Toplam Benzersiz Hashtag:",
        'bot_uptime': "Çalışma Süresi:",
        'help_message': "Yardım menüsü için /help yazın.",
        'error_message': "Bir hata oluştu. Lütfen daha sonra tekrar deneyin."
    },
    'en': {
        'welcome': """
📊 Welcome to Trend Analysis Bot! (v{})

Available commands:
/trend_daily - View daily trends
/trend_weekly - View weekly trends
/trend_monthly - View monthly trends
/popularity <word> - Check popularity of a specific word
/track <word> - Track a specific word (admin only)
/language - Change language
/stats - View bot statistics
/help - View help menu
        """,
        'daily_header': "📊 Daily Trend Report",
        'weekly_header': "📊 Weekly Trend Report",
        'monthly_header': "📊 Monthly Trend Report",
        'top_words': "📝 Top Words:",
        'top_hashtags': "#️⃣ Top Hashtags:",
        'times': "times",
        'no_data': "No data found for this period.",
        'admin_only': "This command is only available to administrators.",
        'tracking_started': "Now tracking:",
        'specify_word': "Please specify a word.",
        'popularity_stats': "📊 Popularity stats for '{}':",
        'total_uses': "Total uses:",
        'first_seen': "First seen:",
        'last_seen': "Last seen:",
        'no_stats': "No statistics found for this word.",
        'stats_header': "📊 Bot Statistics",
        'total_messages': "Total Messages Processed:",
        'total_words': "Total Unique Words:",
        'total_hashtags': "Total Unique Hashtags:",
        'bot_uptime': "Uptime:",
        'help_message': "Type /help for help menu.",
        'error_message': "An error occurred. Please try again later."
    }
}

@dataclass
class BotConfig:
    MIN_WORD_LENGTH: int = 3
    MAX_TRENDING_ITEMS: int = 10
    SUDDEN_TREND_THRESHOLD: int = 50
    ISTANBUL_TZ = pytz.timezone('Europe/Istanbul')
    START_TIME: datetime = field(default_factory=lambda: datetime.now(pytz.UTC))
    
    # Genişletilmiş yasaklı kelimeler listesi
    EXCLUDED_WORDS: Set[str] = field(default_factory=lambda: {
        # Türkçe stop words
        "acaba", "ama", "aslında", "az", "bazı", "belki", "biri", "birkaç",
        "birşey", "biz", "bu", "çok", "çünkü", "da", "daha", "de", "defa",
        "diye", "eğer", "en", "gibi", "hem", "hep", "hepsi", "her", "hiç",
        "için", "ile", "ise", "kez", "ki", "kim", "mı", "mu", "mü", "nasıl",
        "ne", "neden", "nerde", "nerede", "nereye", "niçin", "niye", "o", "sanki",
        "şey", "siz", "şu", "tüm", "ve", "veya", "ya", "yani",

        # İngilizce stop words
        "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "has", "he",
        "in", "is", "it", "its", "of", "on", "that", "the", "to", "was", "were",
        "will", "with",

        # Özel karakterler ve sayılar
        "0", "1", "2", "3", "4", "5", "6", "7", "8", "9",
        
        # Yaygın kısaltmalar
        "vs", "vb", "etc", "ie", "eg", "rt", "dm",
        
        # Özel filtreler
        "http", "https", "com", "www", "html", "php", "jpg", "png", "gif",
        "amk", "aq", "mk", "amq", "awk", "awq", "pic", "image", "video",
        
        # Emojiler (regex ile kontrol edilecek)
    })

class TrendBot:
    def __init__(self):
        self.config = BotConfig()
        self.db_path = "trend_bot.db"
        self.init_db()
        
        # Initialize bot
        self.application = Application.builder().token(TOKEN).build()
        self.setup_handlers()
        
        # Initialize stats
        self.message_count = 0
        self.start_time = datetime.now(pytz.UTC)
        self.group_languages = defaultdict(lambda: 'tr')

    def init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            # Create tables with improved schema
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS stats (
                    word TEXT,
                    group_id INTEGER,
                    type TEXT,
                    count INTEGER DEFAULT 0,
                    first_seen TIMESTAMP,
                    last_seen TIMESTAMP,
                    PRIMARY KEY (word, group_id, type)
                );

                CREATE TABLE IF NOT EXISTS group_settings (
                    group_id INTEGER PRIMARY KEY,
                    language TEXT DEFAULT 'tr',
                    timezone TEXT DEFAULT 'Europe/Istanbul',
                    last_report_daily DATE,
                    last_report_weekly DATE,
                    last_report_monthly DATE
                );

                CREATE TABLE IF NOT EXISTS tracked_keywords (
                    group_id INTEGER,
                    keyword TEXT,
                    admin_id INTEGER,
                    added_at TIMESTAMP,
                    PRIMARY KEY (group_id, keyword)
                );

                CREATE TABLE IF NOT EXISTS message_stats (
                    group_id INTEGER,
                    date DATE,
                    message_count INTEGER DEFAULT 0,
                    word_count INTEGER DEFAULT 0,
                    hashtag_count INTEGER DEFAULT 0,
                    PRIMARY KEY (group_id, date)
                );

                CREATE INDEX IF NOT EXISTS idx_stats_group ON stats(group_id);
                CREATE INDEX IF NOT EXISTS idx_stats_word ON stats(word);
                CREATE INDEX IF NOT EXISTS idx_stats_type ON stats(type);
                CREATE INDEX IF NOT EXISTS idx_stats_last_seen ON stats(last_seen);
            """)

    def setup_handlers(self):
        # Base commands
        self.application.add_handler(CommandHandler("start", self.cmd_start))
        self.application.add_handler(CommandHandler("help", self.cmd_help))
        self.application.add_handler(CommandHandler("stats", self.cmd_stats))
        
        # Trend commands
        self.application.add_handler(CommandHandler("trend_daily", self.cmd_trend_daily))
        self.application.add_handler(CommandHandler("trend_weekly", self.cmd_trend_weekly))
        self.application.add_handler(CommandHandler("trend_monthly", self.cmd_trend_monthly))
        
        # Analysis commands
        self.application.add_handler(CommandHandler("popularity", self.cmd_check_popularity))
        self.application.add_handler(CommandHandler("track", self.cmd_track_keyword))
        
        # Settings commands
        self.application.add_handler(CommandHandler("language", self.cmd_language))
        self.application.add_handler(CallbackQueryHandler(self.language_callback, pattern="^lang_"))
        
        # Message handler
        self.application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            self.analyze_message
        ))
        
        # Error handler
        self.application.add_error_handler(self.error_handler)

    async def start(self):
        """Initialize and start the bot"""
        # Setup scheduled reports
        await self.setup_scheduled_reports()
        
        # Start the bot
        await self.application.initialize()
        await self.application.start()
        await self.application.run_polling(allowed_updates=Update.ALL_TYPES)

    async def setup_scheduled_reports(self):
        """Setup scheduled report tasks"""
        
        async def schedule_daily_reports():
            while True:
                try:
                    istanbul_now = datetime.now(self.config.ISTANBUL_TZ)
                    tomorrow = istanbul_now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
                    wait_seconds = (tomorrow - istanbul_now).total_seconds()
                    await asyncio.sleep(wait_seconds)
                    await self.send_scheduled_reports("daily")
                except Exception as e:
                    logging.error(f"Daily report error: {e}")
                    await asyncio.sleep(60)

        async def schedule_weekly_reports():
            while True:
                try:
                    istanbul_now = datetime.now(self.config.ISTANBUL_TZ)
                    days_until_sunday = (6 - istanbul_now.weekday()) % 7
                    next_sunday = istanbul_now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=days_until_sunday)
                    wait_seconds = (next_sunday - istanbul_now).total_seconds()
                    await asyncio.sleep(wait_seconds)
                    await self.send_scheduled_reports("weekly")
                except Exception as e:
                    logging.error(f"Weekly report error: {e}")
                    await asyncio.sleep(60)

        async def schedule_monthly_reports():
            while True:
                try:
                    istanbul_now = datetime.now(self.config.ISTANBUL_TZ)
                    if istanbul_now.day == 1:
                        await self.send_scheduled_reports("monthly")
                    next_check = istanbul_now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
                    wait_seconds = (next_check - istanbul_now).total_seconds()
                    await asyncio.sleep(wait_seconds)
                except Exception as e:
                    logging.error(f"Monthly report error: {e}")
                    await asyncio.sleep(60)

        # Create and store tasks
        self._scheduled_tasks = [
            asyncio.create_task(schedule_daily_reports()),
            asyncio.create_task(schedule_weekly_reports()),
            asyncio.create_task(schedule_monthly_reports())
        ]

    def run(self):
        """Run the bot with proper async handling"""
        try:
            # Set up logging
            logging.basicConfig(
                format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                level=logging.INFO
            )
            
            # Run the bot using asyncio
            asyncio.run(self.start())
            
        except KeyboardInterrupt:
            logging.info("Bot stopped by user")
        except Exception as e:
            logging.error(f"Fatal error: {e}")

    # Command Handlers
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        lang = self.get_group_language(update.effective_chat.id)
        welcome_text = TRANSLATIONS[lang]['welcome'].format(VERSION)
        await update.message.reply_text(welcome_text)

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        lang = self.get_group_language(update.effective_chat.id)
        await update.message.reply_text(TRANSLATIONS[lang]['welcome'].format(VERSION))

    async def cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stats command"""
        lang = self.get_group_language(update.effective_chat.id)
        tr = TRANSLATIONS[lang]
        
        with sqlite3.connect(self.db_path) as conn:
            stats = conn.execute("""
                SELECT COUNT(*) as msg_count,
                       COUNT(DISTINCT word) as word_count,
                       COUNT(DISTINCT CASE WHEN type='hashtag' THEN word END) as hashtag_count
                FROM stats
                WHERE group_id = ?
            """, (update.effective_chat.id,)).fetchone()
            
        uptime = datetime.now(pytz.UTC) - self.start_time
        uptime_str = f"{uptime.days}d {uptime.seconds//3600}h {(uptime.seconds//60)%60}m"
        
        stats_text = f"{tr['stats_header']}\n\n"
        stats_text += f"{tr['total_messages']}: {stats[0]}\n"
        stats_text += f"{tr['total_words']}: {stats[1]}\n"
        stats_text += f"{tr['total_hashtags']}: {stats[2]}\n"
        stats_text += f"{tr['bot_uptime']}: {uptime_str}\n"
        stats_text += f"\nLast Updated: {LAST_UPDATED}"
        
        await update.message.reply_text(stats_text)

    async def analyze_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Analyze incoming messages for trends"""
        if not update.message or not update.message.text:
            return

        self.message_count += 1
        group_id = update.message.chat_id
        text = update.message.text.lower()
        current_time = datetime.now(self.config.ISTANBUL_TZ)

        # Kelime ve hashtag çıkarma işlemi
        words = set(
            word for word in re.findall(r'\b\w+\b', text)
            if len(word) >= self.config.MIN_WORD_LENGTH
            and word not in self.config.EXCLUDED_WORDS
            and not any(c.isdigit() for c in word)
            and not re.match(r'^[0-9\W]+$', word)
        )
        
        hashtags = set(tag.lower() for tag in re.findall(r'#(\w+)', text))

        # Emoji ve özel karakterleri temizle
        words = {word for word in words if not re.match(r'.*[\U0001F300-\U0001F9FF].*', word)}

        with sqlite3.connect(self.db_path) as conn:
            # Kelime istatistiklerini güncelle
            for word in words:
                conn.execute("""
                    INSERT INTO stats (word, group_id, type, count, first_seen, last_seen)
                    VALUES (?, ?, 'word', 1, ?, ?)
                    ON CONFLICT(word, group_id, type) DO UPDATE SET
                        count = count + 1,
                        last_seen = ?
                """, (word, group_id, current_time, current_time, current_time))

            # Hashtag istatistiklerini güncelle
            for tag in hashtags:
                conn.execute("""
                    INSERT INTO stats (word, group_id, type, count, first_seen, last_seen)
                    VALUES (?, ?, 'hashtag', 1, ?, ?)
                    ON CONFLICT(word, group_id, type) DO UPDATE SET
                        count = count + 1,
                        last_seen = ?
                """, (tag, group_id, current_time, current_time, current_time))

            # Günlük mesaj istatistiklerini güncelle
            conn.execute("""
                INSERT INTO message_stats (group_id, date, message_count, word_count, hashtag_count)
                VALUES (?, date(?), 1, ?, ?)
                ON CONFLICT(group_id, date) DO UPDATE SET
                    message_count = message_count + 1,
                    word_count = word_count + ?,
                    hashtag_count = hashtag_count + ?
            """, (group_id, current_time, len(words), len(hashtags), len(words), len(hashtags)))

    async def get_trends(self, group_id: int, period: str) -> str:
        """Get trending topics for the specified period"""
        lang = self.get_group_language(group_id)
        tr = TRANSLATIONS[lang]
        
        current_time = datetime.now(self.config.ISTANBUL_TZ)
        
        if period == "daily":
            start_time = current_time - timedelta(days=1)
            header = tr['daily_header']
        elif period == "weekly":
            start_time = current_time - timedelta(weeks=1)
            header = tr['weekly_header']
        else:  # monthly
            start_time = current_time - timedelta(days=30)
            header = tr['monthly_header']

        with sqlite3.connect(self.db_path) as conn:
            # En çok kullanılan kelimeler
            words = conn.execute("""
                SELECT word, count,
                       (count * 1.0 / (julianday(?) - julianday(first_seen))) as frequency
                FROM stats
                WHERE group_id = ? 
                AND type = 'word'
                AND last_seen >= ?
                ORDER BY count DESC, frequency DESC
                LIMIT ?
            """, (current_time, group_id, start_time, self.config.MAX_TRENDING_ITEMS)).fetchall()

            # En çok kullanılan hashtagler
            hashtags = conn.execute("""
                SELECT word, count,
                       (count * 1.0 / (julianday(?) - julianday(first_seen))) as frequency
                FROM stats
                WHERE group_id = ? 
                AND type = 'hashtag'
                AND last_seen >= ?
                ORDER BY count DESC, frequency DESC
                LIMIT ?
            """, (current_time, group_id, start_time, self.config.MAX_TRENDING_ITEMS)).fetchall()

            # Ani yükselen trendler
            sudden_trends = conn.execute("""
                SELECT word, count,
                       (count * 1.0 / (julianday(?) - julianday(first_seen))) as rate
                FROM stats
                WHERE group_id = ? 
                AND type = 'word'
                AND last_seen >= ?
                AND first_seen < ?
                HAVING rate >= ?
                ORDER BY rate DESC
                LIMIT 5
            """, (current_time, group_id, start_time, current_time, self.config.SUDDEN_TREND_THRESHOLD)).fetchall()

        # Raporu formatla
        report = f"{header}\n"
        report += f"📅 {current_time.strftime('%Y-%m-%d %H:%M')}\n\n"
        
        if words:
            report += f"{tr['top_words']}\n"
            for i, (word, count, _) in enumerate(words, 1):
                report += f"{i}. {word} ({count} {tr['times']})\n"
        
        if hashtags:
            report += f"\n{tr['top_hashtags']}\n"
            for i, (tag, count, _) in enumerate(hashtags, 1):
                report += f"{i}. #{tag} ({count} {tr['times']})\n"
        
        if sudden_trends:
            report += "\n🚀 Hızlı Yükselen Trendler:\n"
            for word, count, rate in sudden_trends:
                report += f"📈 {word} ({count} {tr['times']}) [x{rate:.1f}]\n"

        if not words and not hashtags:
            report += f"\n{tr['no_data']}"

        return report

    async def send_scheduled_reports(self, period: str):
        """Send scheduled reports to all groups"""
        with sqlite3.connect(self.db_path) as conn:
            groups = conn.execute("SELECT DISTINCT group_id FROM stats").fetchall()
            
        for (group_id,) in groups:
            try:
                report = await self.get_trends(group_id, period)
                await self.application.bot.send_message(
                    chat_id=group_id,
                    text=report,
                    parse_mode='HTML'
                )
                
                # Update last report time
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute(f"""
                        UPDATE group_settings 
                        SET last_report_{period} = ?
                        WHERE group_id = ?
                    """, (datetime.now(self.config.ISTANBUL_TZ).date(), group_id))
                    
            except Exception as e:
                logging.error(f"Error sending {period} report to group {group_id}: {e}")

    def get_group_language(self, group_id: int) -> str:
        """Get group's language setting"""
        with sqlite3.connect(self.db_path) as conn:
            result = conn.execute("""
                SELECT language FROM group_settings WHERE group_id = ?
            """, (group_id,)).fetchone()
            
        return result[0] if result else 'tr'

    async def cmd_language(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle language change command"""
        keyboard = [
            [
                InlineKeyboardButton("🇹🇷 Türkçe", callback_data='lang_tr'),
                InlineKeyboardButton("🇬🇧 English", callback_data='lang_en')
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Please select your language / Lütfen dilinizi seçin:",
            reply_markup=reply_markup
        )

    async def language_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle language selection callback"""
        query = update.callback_query
        lang = query.data.split('_')[1]
        group_id = query.message.chat_id
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO group_settings (group_id, language)
                VALUES (?, ?)
            """, (group_id, lang))
        
        response_text = "Dil Türkçe olarak ayarlandı! 🇹🇷" if lang == 'tr' else "Language set to English! 🇬🇧"
        await query.answer()
        await query.edit_message_text(text=response_text)

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors"""
        logging.error(f"Error: {context.error}")
        try:
            if update and update.effective_chat:
                lang = self.get_group_language(update.effective_chat.id)
                await update.effective_message.reply_text(TRANSLATIONS[lang]['error_message'])
        except:
            logging.error("Failed to send error message")

if __name__ == "__main__":
    # Create and run the bot
    bot = TrendBot()
    bot.run()
