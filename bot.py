import os
import sqlite3
from datetime import datetime, timezone
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    Application,
    ChatMemberHandler,
    ChatJoinRequestHandler,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# =========================================================
# AYARLAR
# =========================================================

TOKEN = os.getenv("BOT_TOKEN")

# BUNLARI SONRA BΔ°RLΔ°KTE AYARLAYACAΔIZ
# SipariΕlerin geleceΔi Γ¶zel Telegram grubunun ID'si
ORDER_CHAT_ID = os.getenv("ORDER_CHAT_ID")

# KatΔ±lma isteΔi geldiΔinde Γ¶zelden karΕΔ±lanacak PinkPanther grubu
PINKPANTHER_GROUP_ID = int(
    os.getenv("PINKPANTHER_GROUP_ID", "-1004472680906")
)

# CanlΔ± destek iΓ§in Telegram kullanΔ±cΔ± adΔ±n
# @ iΕareti OLMADAN yazΔ±lacak. Γ–rnek: PinkPantherSupport
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "")

# Seller alerts always use their own group; they never fall back to the order group.
VENDOR_ALERT_CHAT_ID = os.getenv(
    "VENDOR_ALERT_CHAT_ID", "-1004348363207"
)
VENDOR_DB_PATH = os.getenv("VENDOR_DB_PATH", "vendor_detection.db")
VENDOR_SCORE_THRESHOLD = int(os.getenv("VENDOR_SCORE_THRESHOLD", "5"))
VENDOR_REENTRY_POINTS = int(os.getenv("VENDOR_REENTRY_POINTS", "2"))
VENDOR_INACTIVE_DAYS = int(os.getenv("VENDOR_INACTIVE_DAYS", "7"))
VENDOR_INACTIVE_POINTS = int(os.getenv("VENDOR_INACTIVE_POINTS", "3"))
VENDOR_USERNAME_POINTS = int(os.getenv("VENDOR_USERNAME_POINTS", "2"))
VENDOR_SCAN_INTERVAL = int(os.getenv("VENDOR_SCAN_INTERVAL", "3600"))
VENDOR_KEYWORDS = tuple(
    item.strip().lower()
    for item in os.getenv(
        "VENDOR_KEYWORDS",
        "cannabis,weed,hash,hashish,marijuana,420,thc,plug,vendor,shop,store,"
        "seller,wholesale,toptan,coke",
    ).split(",")
    if item.strip()
)

# ΓrΓΌn Γ§eΕitleri ve seΓ§im -> toplam fiyat (β‚¬) listesi
PRODUCTS = {
    "leaf": {
        "en": "π€ Leaf",
        "de": "π€ Blatt",
        "tr": "π€ Yaprak",
        "es": "π€ Hoja",
        "it": "π€ Foglia",
        "ru": "π€ Π›ΠΈΡΡ‚",
        "pl": "π€ LiΕ›Δ‡",
        "fr": "π€ Feuille",
        "grams_per_unit": 5,
        "prices": {1: 50, 2: 100, 3: 130, 5: 190},
    },
    "chocolate": {
        "en": "π« Chocolate",
        "de": "π« Schokolade",
        "tr": "π« Γ‡ikolata",
        "es": "π« Chocolate",
        "it": "π« Cioccolato",
        "ru": "π« Π¨ΠΎΠΊΠΎΠ»Π°Π΄",
        "pl": "π« Czekolada",
        "fr": "π« Chocolat",
        "grams_per_unit": 5,
        "prices": {1: 50, 2: 100, 3: 130, 5: 190},
    },
    "snow": {
        "en": "β„οΈ Snow",
        "de": "β„οΈ Schnee",
        "tr": "β„οΈ Kar",
        "es": "β„οΈ Nieve",
        "it": "β„οΈ Neve",
        "ru": "β„οΈ Π΅Π½ΠµΠ³",
        "pl": "β„οΈ Εnieg",
        "fr": "β„οΈ Neige",
        "unit": "g",
        "prices": {0.5: 50, 1: 100, 3: 225},
    },
}


# =========================================================
# METΔ°NLER
# =========================================================

def db_connection():
    connection = sqlite3.connect(VENDOR_DB_PATH, timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


def init_vendor_db():
    with db_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS member_activity (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT NOT NULL DEFAULT '',
                first_joined_at TEXT,
                last_joined_at TEXT,
                last_left_at TEXT,
                is_member INTEGER NOT NULL DEFAULT 0,
                join_count INTEGER NOT NULL DEFAULT 0,
                reentry_count INTEGER NOT NULL DEFAULT 0,
                total_stay_seconds INTEGER NOT NULL DEFAULT 0,
                has_ordered INTEGER NOT NULL DEFAULT 0,
                first_ordered_at TEXT,
                last_ordered_at TEXT,
                order_count INTEGER NOT NULL DEFAULT 0,
                candidate_notified INTEGER NOT NULL DEFAULT 0,
                last_score INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            )
            """
        )


def utc_now():
    return datetime.now(timezone.utc)


def parse_time(value):
    return datetime.fromisoformat(value) if value else None


def record_member_join(user):
    now = utc_now().isoformat()
    with db_connection() as connection:
        row = connection.execute(
            "SELECT is_member FROM member_activity WHERE user_id = ?", (user.id,)
        ).fetchone()
        if row is None:
            connection.execute(
                """INSERT INTO member_activity
                   (user_id, username, full_name, first_joined_at, last_joined_at,
                    is_member, join_count, updated_at)
                   VALUES (?, ?, ?, ?, ?, 1, 1, ?)""",
                (user.id, user.username, user.full_name or "", now, now, now),
            )
        elif not row["is_member"]:
            connection.execute(
                """UPDATE member_activity
                   SET username = ?, full_name = ?, last_joined_at = ?, is_member = 1,
                       join_count = join_count + 1, reentry_count = reentry_count + 1,
                       updated_at = ? WHERE user_id = ?""",
                (user.username, user.full_name or "", now, now, user.id),
            )


def record_member_leave(user):
    now_dt = utc_now()
    now = now_dt.isoformat()
    with db_connection() as connection:
        row = connection.execute(
            "SELECT last_joined_at, is_member FROM member_activity WHERE user_id = ?",
            (user.id,),
        ).fetchone()
        if row is None:
            connection.execute(
                """INSERT INTO member_activity
                   (user_id, username, full_name, last_left_at, updated_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (user.id, user.username, user.full_name or "", now, now),
            )
        elif row["is_member"]:
            joined = parse_time(row["last_joined_at"])
            stay = max(0, int((now_dt - joined).total_seconds())) if joined else 0
            connection.execute(
                """UPDATE member_activity SET username = ?, full_name = ?,
                   last_left_at = ?, is_member = 0,
                   total_stay_seconds = total_stay_seconds + ?, updated_at = ?
                   WHERE user_id = ?""",
                (user.username, user.full_name or "", now, stay, now, user.id),
            )


def record_order(user):
    now = utc_now().isoformat()
    with db_connection() as connection:
        connection.execute(
            """INSERT INTO member_activity
               (user_id, username, full_name, has_ordered, first_ordered_at,
                last_ordered_at, order_count, updated_at)
               VALUES (?, ?, ?, 1, ?, ?, 1, ?)
               ON CONFLICT(user_id) DO UPDATE SET username = excluded.username,
                   full_name = excluded.full_name, has_ordered = 1,
                   first_ordered_at = COALESCE(member_activity.first_ordered_at, excluded.first_ordered_at),
                   last_ordered_at = excluded.last_ordered_at,
                   order_count = member_activity.order_count + 1,
                   candidate_notified = 0, updated_at = excluded.updated_at""",
            (user.id, user.username, user.full_name or "", now, now, now),
        )


def vendor_score(row):
    score = row["reentry_count"] * VENDOR_REENTRY_POINTS
    reasons = []
    if row["reentry_count"]:
        reasons.append(f"{row['reentry_count']} yeniden giriΕ")
    username = (row["username"] or "").lower()
    matches = [word for word in VENDOR_KEYWORDS if word in username]
    if matches:
        score += VENDOR_USERNAME_POINTS
        reasons.append("kullanΔ±cΔ± adΔ±: " + ", ".join(matches))
    joined = parse_time(row["first_joined_at"])
    age_days = (utc_now() - joined).days if joined else 0
    if not row["has_ordered"] and age_days >= VENDOR_INACTIVE_DAYS:
        score += VENDOR_INACTIVE_POINTS
        reasons.append(f"{age_days} gΓΌndΓΌr sipariΕ yok")
    return score, reasons, age_days


async def evaluate_vendor_candidate(context, user_id):
    with db_connection() as connection:
        row = connection.execute(
            "SELECT * FROM member_activity WHERE user_id = ?", (user_id,)
        ).fetchone()
        if row is None:
            return
        score, reasons, age_days = vendor_score(row)
        should_notify = (
            score >= VENDOR_SCORE_THRESHOLD
            and not row["candidate_notified"]
            and not row["has_ordered"]
        )
        connection.execute(
            "UPDATE member_activity SET last_score = ?, updated_at = ? WHERE user_id = ?",
            (score, utc_now().isoformat(), user_id),
        )
    if not should_notify or not VENDOR_ALERT_CHAT_ID:
        return
    username = f"@{row['username']}" if row["username"] else "KullanΔ±cΔ± adΔ± yok"
    stay_seconds = row["total_stay_seconds"]
    if row["is_member"] and row["last_joined_at"]:
        stay_seconds += max(
            0, int((utc_now() - parse_time(row["last_joined_at"])).total_seconds())
        )
    await context.bot.send_message(
        chat_id=VENDOR_ALERT_CHAT_ID,
        text=(
            "β οΈ Potansiyel SatΔ±cΔ±\n\n"
            f"π‘¤ {row['full_name'] or '-'}\n"
            f"π“± {username}\n"
            f"π†” {row['user_id']}\n"
            f"π“ Puan: {score}/{VENDOR_SCORE_THRESHOLD}\n"
            f"π” Gir-Γ§Δ±k / yeniden giriΕ: {row['reentry_count']}\n"
            f"β± Grupta toplam sΓΌre: {stay_seconds // 86400} gΓΌn\n"
            f"π—“ Δ°lk giriΕten beri: {age_days} gΓΌn\n"
            f"π›’ SipariΕ: HayΔ±r\n"
            f"π” Nedenler: {', '.join(reasons) or '-'}"
        ),
    )
    with db_connection() as connection:
        connection.execute(
            "UPDATE member_activity SET candidate_notified = 1 WHERE user_id = ?",
            (user_id,),
        )


def is_active_member(chat_member):
    if chat_member.status in ("member", "administrator", "creator"):
        return True
    return chat_member.status == "restricted" and bool(chat_member.is_member)


async def chat_member_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    change = update.chat_member
    if change is None or change.chat.id != PINKPANTHER_GROUP_ID:
        return
    old_member = is_active_member(change.old_chat_member)
    new_member = is_active_member(change.new_chat_member)
    user = change.new_chat_member.user
    if user.is_bot:
        return
    if not old_member and new_member:
        record_member_join(user)
        await evaluate_vendor_candidate(context, user.id)
    elif old_member and not new_member:
        record_member_leave(user)
        await evaluate_vendor_candidate(context, user.id)


async def scan_vendor_candidates(context: ContextTypes.DEFAULT_TYPE):
    with db_connection() as connection:
        user_ids = [
            row["user_id"]
            for row in connection.execute(
                "SELECT user_id FROM member_activity "
                "WHERE has_ordered = 0 AND candidate_notified = 0"
            )
        ]
    for user_id in user_ids:
        try:
            await evaluate_vendor_candidate(context, user_id)
        except Exception as error:
            print("SatΔ±cΔ± adayΔ± kontrol hatasΔ±:", user_id, error)


TEXTS = {
    "en": {
        "language_selected": "π‡¬π‡§ English selected.",

        "welcome": (
            "β οΈ IMPORTANT β€“ PLEASE READ CAREFULLY\n\n"
            "πΎ Welcome to PinkPanther Bot\n\n"
            "Hello! Iβ€™m PinkPanther Bot. Iβ€™m here to help you place your order "
            "quickly and easily.\n\n"
            "π’µ Cash payment only.\n"
            "β… No payment is required before you receive your product.\n"
            "π¤ In-person handover is available.\n"
            "π— Driver delivery is FREE.\n"
            "π“ You can share your location directly through Telegram.\n"
            "π† If you have any questions or problems, you can continue your "
            "order through Live Support.\n\n"
            "Please choose an option below:"
        ),

        "order_button": "π› Place an Order",
        "support_button": "π† Live Support",

        "product": (
            "π› PRODUCT CATALOG\n\n"
            "π€ Leaf\n"
            "π« Chocolate\n"
            "β„οΈ Snow\n\n"
            "Select one or more products and quantities below.\n"
            "Then press Continue."
        ),

        "brand_prompt": (
            "βοΈ Please type the brand/name of your selected product.\n\n"
            "Send it as a normal text message; there is no button for this step."
        ),

        "quantity": (
            "π”Ά How many would you like to order?\n\n"
            "Minimum order: 5 pieces\n\n"
            "5 pieces = 50 β‚¬\n"
            "10 pieces = 100 β‚¬\n"
            "15 pieces = 130 β‚¬\n"
            "25 pieces = 190 β‚¬\n\n"
            "Please enter one of these quantities: 5, 10, 15 or 25."
        ),

        "address": (
            "π“ DELIVERY INFORMATION\n\n"
            "Please send your full delivery address and postal code together.\n\n"
            "Example:\n"
            "MusterstraΓe 12, 12345 Berlin\n\n"
            "β„ΉοΈ NOTE:\n"
            "If you donβ€™t know your full address or postal code, simply enter "
            "the area or district you are in.\n\n"
            "You can also share your exact location directly through Telegram "
            "using the π“ Share Location button.\n\n"
            "If you need help, you can continue through π† Live Support."
        ),

        "share_location": "π“ Share Location",
        "skip_location": "β΅οΈ Continue Without Location",

        "location_question": (
            "π“ If you want, you can now share your exact location.\n\n"
            "This helps us find the delivery point more easily.\n\n"
            "You can also continue without sharing your location."
        ),

        "location_received": "β… Location received.",

        "confirm": "β… Confirm Order",
        "change": "βοΈ Change Information",
        "cancel": "β Cancel Order",

        "cancelled": (
            "β Your order has been cancelled.\n\n"
            "You can start again anytime with /start."
        ),

        "success": (
            "β… YOUR ORDER HAS BEEN RECEIVED SUCCESSFULLY.\n\n"
            "Thank you for your order. You will be contacted regarding the delivery.\n\n"
            "π— Delivery: FREE\n"
            "π’µ Payment: Cash on delivery\n\n"
            "β οΈ Please do not make any payment before recσ;¶‰ΛkΊwµηUαΠ΅±…Ή°ΑΙ½‘ΥΠ°ΕΥ…ΉΡ¥Ρδ¤(€€€€€€€€€€€½ΑΡ¥½Ή}Ι½άΉ…ΑΑ•Ή΅%Ή±¥Ή•-•ε‰½…Ι‘	ΥΡΡ½Έ (€€€€€€€€€€€€€€€‰νΑΙ•™¥αυν…µ½ΥΉΡτ€τνΑΙ¥•τƒ
°°(€€€€€€€€€€€€€€€…±±‰…­}‘…Ρ„υ‰Α¥­}νΑΙ½‘ΥΡ}­•ευ}νΕΥ…ΉΡ¥Ρετ(€€€€€€€€€€€€¤¤(€€€€€€€€€€€¥±•Έ΅½ΑΡ¥½Ή}Ι½ά¤€ττ€Θθ(€€€€€€€€€€€€€€€­•ε‰½…ΙΉ…ΑΑ•Ή΅½ΑΡ¥½Ή}Ι½ά¤(€€€€€€€€€€€€€€€½ΑΡ¥½Ή}Ι½ά€τmt(€€€€€€€¥½ΑΡ¥½Ή}Ι½άθ(€€€€€€€€€€€­•ε‰½…ΙΉ…ΑΑ•Ή΅½ΑΡ¥½Ή}Ι½ά¤((€€€½ΉΡ¥ΉΥ•}Ρ•αΠ€τ‹z‡Ύβ<νU%}QaQm±…Ήul½ΉΡ¥ΉΥ”uτ(€€€­•ε‰½…ΙΉ…ΑΑ•Ή΅l(€€€€€€€%Ή±¥Ή•-•ε‰½…Ι‘	ΥΡΡ½Έ΅½ΉΡ¥ΉΥ•}Ρ•αΠ°…±±‰…­}‘…Ρ„τ‰…ΙΡ}½ΉΡ¥ΉΥ”¤(€€€t¤(€€€Ι•ΡΥΙΈ­•ε‰½…Ι(4(4)…ΝεΉ‘•Ν΅½έ}µ…¥Ή}µ•ΉΤ΅µ•ΝΝ…”°½ΉΡ•αΠ¤θ4(€€€±…Ή€τ•Ρ}±…Ή΅½ΉΡ•αΠ¤4(4(€€€­•ε‰½…Ι€τl4(€€€€€€€l4(€€€€€€€€€€€%Ή±¥Ή•-•ε‰½…Ι‘	ΥΡΡ½Έ 4(€€€€€€€€€€€€€€€QaQMm±…Ήul‰½Ι‘•Ι}‰ΥΡΡ½Έ‰t°4(€€€€€€€€€€€€€€€…±±‰…­}‘…Ρ„τ‰Ή•έ}½Ι‘•Θ4(€€€€€€€€€€€€¤4(€€€€€€€t4(€€€t4(4(€€€­•ε‰½…ΙΉ•αΡ•Ή΅ΝΥΑΑ½ΙΡ}­•ε‰½…Ι΅±…Ή¤¤4(4(€€€…έ…¥Πµ•ΝΝ…”ΉΙ•Α±ε}Ρ•αΠ 4(€€€€€€€QaQMm±…Ήul‰έ•±½µ”‰t°4(€€€€€€€Ι•Α±ε}µ…Ι­Υΐυ%Ή±¥Ή•-•ε‰½…Ι‘5…Ι­Υΐ΅­•ε‰½…Ι¤4(€€€€¤4(4(4)…ΝεΉ‘•Ν΅½έ}ΝΥµµ…Ιδ΅ΥΑ‘…Ρ”°½ΉΡ•αΠ¤θ(€€€±…Ή€τ•Ρ}±…Ή΅½ΉΡ•αΠ¤((€€€…ΙΠ€τ½ΉΡ•αΠΉΥΝ•Ι}‘…Ρ„Ή•Π ‰…ΙΠ°ντ¤(€€€½Ι‘•Ι}±¥Ή•Μ€τ€‰qΈΉ©½¥Έ (€€€€€€€…ΙΡ}±¥Ή•Μ΅±…Ή°…ΙΠ°½ΉΡ•αΠΉΥΝ•Ι}‘…Ρ„Ή•Π ‰‰Ι…Ή¤¤(€€€€¤½Θ€΄(€€€ΑΙ¥”€τ…ΙΡ}Ρ½Ρ…°΅…ΙΠ¤(€€€…‘‘Ι•ΝΜ€τ½ΉΡ•αΠΉΥΝ•Ι}‘…Ρ„Ή•Π ‰…‘‘Ι•ΝΜ°€΄¤4(4(€€€±…Ρ¥ΡΥ‘”€τ½ΉΡ•αΠΉΥΝ•Ι}‘…Ρ„Ή•Π ‰±…Ρ¥ΡΥ‘”¤4(€€€±½Ή¥ΡΥ‘”€τ½ΉΡ•αΠΉΥΝ•Ι}‘…Ρ„Ή•Π ‰±½Ή¥ΡΥ‘”¤4(4(€€€Υ¤€τU%}QaQm±…Ήt(€€€±½…Ρ¥½Ή}ΝΡ…ΡΥΜ€τ€ (€€€€€€€‹rνΥ¥lΙ••¥Ω•uτ¥±…Ρ¥ΡΥ‘”…Ή±½Ή¥ΡΥ‘”(€€€€€€€•±Ν”‹zXνΥ¥lΉ½Ρ}Ν΅…Ι•uτ(€€€€¤(€€€ΝΥµµ…Ιδ€τ€ (€€€€€€€‹Β~ψνΥ¥lΝΥµµ…ΙδuυqΉqΈ(€€€€€€€‹Β~n4νΥ¥lΑΙ½‘ΥΡΜuτιqΉν½Ι‘•Ι}±¥Ή•ΝυqΈ(€€€€€€€‹Β~JΨνΥ¥lΡ½Ρ…±}ΑΙ¥”uτθνΑΙ¥•τƒ
±qΈ(€€€€€€€‹Β~N4νΥ¥l…‘‘Ι•ΝΜuτθν…‘‘Ι•ΝΝυqΈ(€€€€€€€‹Β~^θνΥ¥l±½…Ρ¥½Έuτθν±½…Ρ¥½Ή}ΝΡ…ΡΥΝυqΉqΈ(€€€€€€€‹Β~j\νΥ¥l‘•±¥Ω•ΙδuυqΈ(€€€€€€€‹Β~JΤνΥ¥lΑ…εµ•ΉΠuυqΉqΈ(€€€€€€€‹jƒΎβ<νΥ¥lέ…ΙΉ¥Ήuτ(€€€€¤(4(€€€­•ε‰½…Ι€τl4(€€€€€€€l4(€€€€€€€€€€€%Ή±¥Ή•-•ε‰½…Ι‘	ΥΡΡ½Έ 4(€€€€€€€€€€€€€€€QaQMm±…Ήul‰½Ή™¥Ι΄‰t°4(€€€€€€€€€€€€€€€…±±‰…­}‘…Ρ„τ‰½Ή™¥Ιµ}½Ι‘•Θ4(€€€€€€€€€€€€¤4(€€€€€€€t°4(€€€€€€€l4(€€€€€€€€€€€%Ή±¥Ή•-•ε‰½…Ι‘	ΥΡΡ½Έ 4(€€€€€€€€€€€€€€€QaQMm±…Ήul‰΅…Ή”‰t°4(€€€€€€€€€€€€€€€…±±‰…­}‘…Ρ„τ‰΅…Ή•}½Ι‘•Θ4(€€€€€€€€€€€€¤4(€€€€€€€t°4(€€€€€€€l4(€€€€€€€€€€€%Ή±¥Ή•-•ε‰½…Ι‘	ΥΡΡ½Έ 4(€€€€€€€€€€€€€€€QaQMm±…Ήul‰…Ή•°‰t°4(€€€€€€€€€€€€€€€…±±‰…­}‘…Ρ„τ‰…Ή•±}½Ι‘•Θ4(€€€€€€€€€€€€¤4(€€€€€€€t4(€€€t4(4(€€€…έ…¥ΠΥΑ‘…Ρ”Ή•™™•Ρ¥Ω•}µ•ΝΝ…”ΉΙ•Α±ε}Ρ•αΠ 4(€€€€€€€ΝΥµµ…Ιδ°4(€€€€€€€Ι•Α±ε}µ…Ι­Υΐυ%Ή±¥Ή•-•ε‰½…Ι‘5…Ι­Υΐ΅­•ε‰½…Ι¤4(€€€€¤4(4(€€€½ΉΡ•αΠΉΥΝ•Ι}‘…Ρ…l‰ΝΡ…Ρ”‰t€τ€‰ΝΥµµ…Ιδ4(4(4(€τττττττττττττττττττττττττττττττττττττττττττττττττττττττττ4(€½MQIP4(€τττττττττττττττττττττττττττττττττττττττττττττττττττττττττ4(4)…ΝεΉ‘•ΝΡ…ΙΠ΅ΥΑ‘…Ρ”θUΑ‘…Ρ”°½ΉΡ•αΠθ½ΉΡ•αΡQεΑ•ΜΉU1Q}QeA¤θ(€€€½ΉΡ•αΠΉΥΝ•Ι}‘…Ρ„Ή±•…Θ ¤4(4(€€€­•ε‰½…Ι€τl4(€€€€€€€l4(€€€€€€€€€€€%Ή±¥Ή•-•ε‰½…Ι‘	ΥΡΡ½Έ ‹Β~³Β~Ή±¥Ν °…±±‰…­}‘…Ρ„τ‰±…Ή}•Έ¤°4(€€€€€€€€€€€%Ή±¥Ή•-•ε‰½…Ι‘	ΥΡΡ½Έ ‹Β~§Β~¨•ΥΡΝ °…±±‰…­}‘…Ρ„τ‰±…Ή}‘”¤°4(€€€€€€€t4(€€€t4(4(€€€­•ε‰½…Ι€τ±…ΉΥ…•}­•ε‰½…Ι ¤((€€€…έ…¥ΠΥΑ‘…Ρ”Ήµ•ΝΝ…”ΉΙ•Α±ε}Ρ•αΠ (€€€€€€€€‹Β~24΅½½Ν”ε½ΥΘ±…ΉΥ…”€ΌMΑΙ…΅”…ΥΝί‘΅±•Έ°(€€€€€€€Ι•Α±ε}µ…Ι­Υΐυ%Ή±¥Ή•-•ε‰½…Ι‘5…Ι­Υΐ΅­•ε‰½…Ι¤(€€€€¤(()…ΝεΉ‘•©½¥Ή}Ι•ΕΥ•ΝΠ΅ΥΑ‘…Ρ”θUΑ‘…Ρ”°½ΉΡ•αΠθ½ΉΡ•αΡQεΑ•ΜΉU1Q}QeA¤θ(€€€Ι•ΕΥ•ΝΠ€τΥΑ‘…Ρ”Ή΅…Ρ}©½¥Ή}Ι•ΕΥ•ΝΠ((€€€¥Ι•ΕΥ•ΝΠ¥Μ9½Ή”½ΘΙ•ΕΥ•ΝΠΉ΅…ΠΉ¥€„τA%9-A9Q!I}I=UA}%θ(€€€€€€€Ι•ΡΥΙΈ((€€€­•ε‰½…Ι€τl(€€€€€€€l(€€€€€€€€€€€%Ή±¥Ή•-•ε‰½…Ι‘	ΥΡΡ½Έ ‹Β~³Β~Ή±¥Ν °…±±‰…­}‘…Ρ„τ‰±…Ή}•Έ¤°(€€€€€€€€€€€%Ή±¥Ή•-•ε‰½…Ι‘	ΥΡΡ½Έ ‹Β~§Β~¨•ΥΡΝ °…±±‰…­}‘…Ρ„τ‰±…Ή}‘”¤°(€€€€€€€t(€€€t((€€€­•ε‰½…Ι€τ±…ΉΥ…•}­•ε‰½…Ι ¤((€€€ΡΙδθ(€€€€€€€€Q•±•Ι…΄‰ΤƒΩι•°Ν½΅‰•Π­¥µ±§}¥Ή¤­…ΣΕ±µ„¥ΝΡ—}¥ε±”‰¥Ι±¥­Ρ”Ω•Ι¥ΘΈ(€€€€€€€€Ωε±•”­Υ±±…»ΕΔ‘…΅„ƒΩΉ”€½ΝΡ…ΙΠε…ιµ…·Η|½±Ν„‘„µ•Ν…¨ΩΉ‘•Ι¥±•‰¥±¥ΘΈ(€€€€€€€…έ…¥Π½ΉΡ•αΠΉ‰½ΠΉΝ•Ή‘}µ•ΝΝ…” (€€€€€€€€€€€΅…Ρ}¥υΙ•ΕΥ•ΝΠΉΥΝ•Ι}΅…Ρ}¥°(€€€€€€€€€€€Ρ•αΠτ‹Β~24΅½½Ν”ε½ΥΘ±…ΉΥ…”€ΌMΑΙ…΅”…ΥΝί‘΅±•Έ°(€€€€€€€€€€€Ι•Α±ε}µ…Ι­Υΐυ%Ή±¥Ή•-•ε‰½…Ι‘5…Ι­Υΐ΅­•ε‰½…Ι¤(€€€€€€€€¤(€€€•α•ΑΠα•ΑΡ¥½Έ…Μ•ΙΙ½Θθ(€€€€€€€ΑΙ¥ΉΠ ‰-…ΣΕ±µ„¥ΝΡ—}¥Ή”ƒΩι•°µ•Ν…¨ΩΉ‘•Ι¥±•µ•‘¤θ°•ΙΙ½Θ¤((€€€€ƒYι•°µ•Ν…¨‰‡}…ΛΕΟΕθ½±Ν„‰¥±”­…ΣΕ³Ε΄½Ή…ηΔ…εΛΕ„ƒ…³ΗΕΘΈ(€€€ΡΙδθ(€€€€€€€…έ…¥Π½ΉΡ•αΠΉ‰½ΠΉ…ΑΑΙ½Ω•}΅…Ρ}©½¥Ή}Ι•ΕΥ•ΝΠ (€€€€€€€€€€€΅…Ρ}¥υΙ•ΕΥ•ΝΠΉ΅…ΠΉ¥°(€€€€€€€€€€€ΥΝ•Ι}¥υΙ•ΕΥ•ΝΠΉ™Ι½µ}ΥΝ•ΘΉ¥(€€€€€€€€¤(€€€•α•ΑΠα•ΑΡ¥½Έ…Μ•ΙΙ½Θθ(€€€€€€€ΑΙ¥ΉΠ ‰-…ΣΕ±µ„¥ΝΡ—}¤½Ρ½µ…Ρ¥¬½Ή…ε±…Ή…µ…“Δθ°•ΙΙ½Θ¤(()…ΝεΉ‘•Ν•±•Ρ}±…ΉΥ…”΅ΕΥ•Ιδ°½ΉΡ•αΠ°±…Ή¤θ(€€€½ΉΡ•αΠΉΥΝ•Ι}‘…Ρ„Ή±•…Θ ¤(€€€½ΉΡ•αΠΉΥΝ•Ι}‘…Ρ…l‰±…Ή‰t€τ±…Ή((€€€€-…ΣΕ±µ„¥ΝΡ—}¥ε±”‡Ε±…Έ—¥¤ƒΩι•°Ν½΅‰•ΡΡ”Q•±•Ι…΄‰…ι•Έ¥­¥Ή¤‰¥Θ(€€€€µ•Ν…«ΔΙ•‘‘•‘•ΘΈ	Τηρι‘•Έ‘¥°µ•Ν…«Ε»Δ‘Ώ}ΙΥ‘…Έ…Ή„µ•»ρε”ƒ•Ω¥Ι¥ε½ΙΥθΈ(€€€­•ε‰½…Ι€τml(€€€€€€€%Ή±¥Ή•-•ε‰½…Ι‘	ΥΡΡ½Έ (€€€€€€€€€€€QaQMm±…Ήul‰½Ι‘•Ι}‰ΥΡΡ½Έ‰t°(€€€€€€€€€€€…±±‰…­}‘…Ρ„τ‰Ή•έ}½Ι‘•Θ(€€€€€€€€¤(€€€ut(€€€­•ε‰½…ΙΉ•αΡ•Ή΅ΝΥΑΑ½ΙΡ}­•ε‰½…Ι΅±…Ή¤¤((€€€…έ…¥ΠΕΥ•ΙδΉ•‘¥Ρ}µ•ΝΝ…•}Ρ•αΠ (€€€€€€€QaQMm±…Ήul‰έ•±½µ”‰t°(€€€€€€€Ι•Α±ε}µ…Ι­Υΐυ%Ή±¥Ή•-•ε‰½…Ι‘5…Ι­Υΐ΅­•ε‰½…Ι¤(€€€€¤((4(4(€τττττττττττττττττττττττττττττττττττττττττττττττττττττττττ4(	UQ=91H4(€τττττττττττττττττττττττττττττττττττττττττττττττττττττττττ4(4)…ΝεΉ‘•‰ΥΡΡ½Ή}΅…Ή‘±•Θ΅ΥΑ‘…Ρ”θUΑ‘…Ρ”°½ΉΡ•αΠθ½ΉΡ•αΡQεΑ•ΜΉU1Q}QeA¤θ4(€€€ΕΥ•Ιδ€τΥΑ‘…Ρ”Ή…±±‰…­}ΕΥ•Ιδ4(€€€…έ…¥ΠΕΥ•ΙδΉ…ΉΝέ•Θ ¤4(4(€€€‘…Ρ„€τΕΥ•ΙδΉ‘…Ρ„4(4(4(€€€€€΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄4(€€€€Α0MΑ7ΐ4(€€€€€΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄4(4(€€€¥‘…Ρ„ΉΝΡ…ΙΡΝέ¥Ρ  ‰±…Ή|¤θ(€€€€€€€Ν•±•Ρ•‘}±…Ή€τ‘…Ρ„ΉΙ•µ½Ω•ΑΙ•™¥ΰ ‰±…Ή|¤(€€€€€€€¥Ν•±•Ρ•‘}±…Ή¥ΈQaQLθ(€€€€€€€€€€€…έ…¥ΠΝ•±•Ρ}±…ΉΥ…”΅ΕΥ•Ιδ°½ΉΡ•αΠ°Ν•±•Ρ•‘}±…Ή¤(€€€€€€€Ι•ΡΥΙΈ(4(4(€€€±…Ή€τ•Ρ}±…Ή΅½ΉΡ•αΠ¤4(4(4(€€€€€΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄4(€€€€e;ΐOΑAKΓx4(€€€€€΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄4(4(€€€¥‘…Ρ„€ττ€‰Ή•έ}½Ι‘•Θθ(€€€€€€€Ι•Ν•Ρ}½Ι‘•Θ΅½ΉΡ•αΠ¤((€€€€€€€½ΉΡ•αΠΉΥΝ•Ι}‘…Ρ…l‰ΝΡ…Ρ”‰t€τ€‰ΑΙ½‘ΥΡ}Ν•±•Ρ¥½Έ(€€€€€€€½ΉΡ•αΠΉΥΝ•Ι}‘…Ρ…l‰…ΙΠ‰t€τντ((€€€€€€€…έ…¥ΠΕΥ•ΙδΉ•‘¥Ρ}µ•ΝΝ…•}Ρ•αΠ (€€€€€€€€€€€Ν•±•Ρ¥½Ή}Ρ•αΠ΅±…Ή°ντ¤°(€€€€€€€€€€€Ι•Α±ε}µ…Ι­Υΐυ%Ή±¥Ή•-•ε‰½…Ι‘5…Ι­Υΐ΅Ν•±•Ρ¥½Ή}­•ε‰½…Ι΅±…Ή°ντ¤¤(€€€€€€€€¤(€€€€€€€Ι•ΡΥΙΈ(((€€€¥‘…Ρ„€ττ€‰Ν•±•Ρ¥½Ή}¥Ή™Όθ(€€€€€€€Ι•ΡΥΙΈ(((€€€¥‘…Ρ„ΉΝΡ…ΙΡΝέ¥Ρ  ‰Α¥­|¤θ(€€€€€€€|°ΑΙ½‘ΥΡ}­•δ°ΕΥ…ΉΡ¥Ρε}Ρ•αΠ€τ‘…Ρ„ΉΝΑ±¥Π ‰|°€Θ¤(€€€€€€€ΕΥ…ΉΡ¥Ρδ€τ™±½…Π΅ΕΥ…ΉΡ¥Ρε}Ρ•αΠ¤¥€Έ¥ΈΕΥ…ΉΡ¥Ρε}Ρ•αΠ•±Ν”¥ΉΠ΅ΕΥ…ΉΡ¥Ρε}Ρ•αΠ¤(€€€€€€€¥€ (€€€€€€€€€€€ΑΙ½‘ΥΡ}­•δΉ½Π¥ΈAI=UQL(€€€€€€€€€€€½ΘΕΥ…ΉΡ¥ΡδΉ½Π¥ΈAI=UQMmΑΙ½‘ΥΡ}­•εul‰ΑΙ¥•Μ‰t(€€€€€€€€¤θ(€€€€€€€€€€€Ι•ΡΥΙΈ((€€€€€€€…ΙΠ€τ½ΉΡ•αΠΉΥΝ•Ι}‘…Ρ„ΉΝ•Ρ‘•™…Υ±Π ‰…ΙΠ°ντ¤(€€€€€€€…ΙΡmΑΙ½‘ΥΡ}­•εt€τΕΥ…ΉΡ¥Ρδ((€€€€€€€…έ…¥ΠΕΥ•ΙδΉ•‘¥Ρ}µ•ΝΝ…•}Ρ•αΠ (€€€€€€€€€€€Ν•±•Ρ¥½Ή}Ρ•αΠ΅±…Ή°…ΙΠ¤°(€€€€€€€€€€€Ι•Α±ε}µ…Ι­Υΐυ%Ή±¥Ή•-•ε‰½…Ι‘5…Ι­Υΐ΅Ν•±•Ρ¥½Ή}­•ε‰½…Ι΅±…Ή°…ΙΠ¤¤(€€€€€€€€¤(€€€€€€€Ι•ΡΥΙΈ(((€€€¥‘…Ρ„€ττ€‰…ΙΡ}½ΉΡ¥ΉΥ”θ(€€€€€€€…ΙΠ€τ½ΉΡ•αΠΉΥΝ•Ι}‘…Ρ„Ή•Π ‰…ΙΠ°ντ¤(€€€€€€€¥Ή½Π…ΙΠθ(€€€€€€€€€€€έ…ΙΉ¥Ή€τ‹jƒΎβ<νU%}QaQm±…Ήul•µΑΡδuτ(€€€€€€€€€€€…έ…¥ΠΕΥ•ΙδΉ•‘¥Ρ}µ•ΝΝ…•}Ρ•αΠ (€€€€€€€€€€€€€€€‰νΝ•±•Ρ¥½Ή}Ρ•αΠ΅±…Ή°…ΙΠ¥υqΉqΉνέ…ΙΉ¥Ήτ°(€€€€€€€€€€€€€€€Ι•Α±ε}µ…Ι­Υΐυ%Ή±¥Ή•-•ε‰½…Ι‘5…Ι­Υΐ΅Ν•±•Ρ¥½Ή}­•ε‰½…Ι΅±…Ή°…ΙΠ¤¤(€€€€€€€€€€€€¤(€€€€€€€€€€€Ι•ΡΥΙΈ((€€€€€€€½ΉΡ•αΠΉΥΝ•Ι}‘…Ρ…l‰ΝΡ…Ρ”‰t€τ€‰‰Ι…Ή‘}•ΉΡΙδ(€€€€€€€…έ…¥ΠΕΥ•ΙδΉ•‘¥Ρ}µ•ΝΝ…•}Ρ•αΠ΅QaQMm±…Ήul‰‰Ι…Ή‘}ΑΙ½µΑΠ‰t¤(€€€€€€€Ι•ΡΥΙΈ(4(4(€€€€€΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄4(€€€€OΑAKΓ{ΐ=9e14(€€€€€΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄4(4(€€€¥‘…Ρ„€ττ€‰½Ή™¥Ιµ}½Ι‘•Θθ4(4(€€€€€€€…ΙΠ€τ½ΉΡ•αΠΉΥΝ•Ι}‘…Ρ„Ή•Π ‰…ΙΠ°ντ¤(€€€€€€€½Ι‘•Ι}±¥Ή•Μ€τ€‰qΈΉ©½¥Έ (€€€€€€€€€€€…ΙΡ}±¥Ή•Μ ‰•Έ°…ΙΠ°½ΉΡ•αΠΉΥΝ•Ι}‘…Ρ„Ή•Π ‰‰Ι…Ή¤¤(€€€€€€€€¤½Θ€΄(€€€€€€€ΑΙ¥”€τ…ΙΡ}Ρ½Ρ…°΅…ΙΠ¤(€€€€€€€…‘‘Ι•ΝΜ€τ½ΉΡ•αΠΉΥΝ•Ι}‘…Ρ„Ή•Π ‰…‘‘Ι•ΝΜ°€΄¤4(4(€€€€€€€±…Ρ¥ΡΥ‘”€τ½ΉΡ•αΠΉΥΝ•Ι}‘…Ρ„Ή•Π ‰±…Ρ¥ΡΥ‘”¤4(€€€€€€€±½Ή¥ΡΥ‘”€τ½ΉΡ•αΠΉΥΝ•Ι}‘…Ρ„Ή•Π ‰±½Ή¥ΡΥ‘”¤4(4(€€€€€€€ΥΝ•Θ€τΕΥ•ΙδΉ™Ι½µ}ΥΝ•Θ((€€€€€€€€-••ΐΝ•±±•Θ‘•Ρ•Ρ¥½ΈΝ•Α…Ι…Ρ”™Ι½΄Ρ΅”•α¥ΝΡ¥Ή½Ι‘•ΘΝΡ…Ρ”µ…΅¥Ή”Έ(€€€€€€€Ι•½Ι‘}½Ι‘•Θ΅ΥΝ•Θ¤(4(€€€€€€€ΥΝ•ΙΉ…µ”€τ‰νΥΝ•ΘΉΥΝ•ΙΉ…µ•τ¥ΥΝ•ΘΉΥΝ•ΙΉ…µ”•±Ν”€‰9ΌΥΝ•ΙΉ…µ”4(4(€€€€€€€ΥΝΡ½µ•Ι}Ή…µ”€τΥΝ•ΘΉ™Υ±±}Ή…µ”½Θ€‰UΉ­Ή½έΈ4(4(€€€€€€€¥±…Ρ¥ΡΥ‘”…Ή±½Ή¥ΡΥ‘”θ4(€€€€€€€€€€€µ…ΑΝ}±¥Ή¬€τ‰΅ΡΡΑΜθΌ½µ…ΑΜΉ½½±”Ή½΄ΌύΔυν±…Ρ¥ΡΥ‘•τ±ν±½Ή¥ΡΥ‘•τ4(€€€€€€€€€€€±½…Ρ¥½Ή}Ρ•αΠ€τ‹rν±…Ρ¥ΡΥ‘•τ°ν±½Ή¥ΡΥ‘•υqΉνµ…ΑΝ}±¥Ή­τ4(€€€€€€€•±Ν”θ4(€€€€€€€€€€€±½…Ρ¥½Ή}Ρ•αΠ€τ€‹v0-½ΉΥ΄ΩΉ‘•Ι¥±µ•‘¤4(4(€€€€€€€…‘µ¥Ή}µ•ΝΝ…”€τ€ 4(€€€€€€€€€€€€‹Β~j e;ΐOΑAKΓxƒΒ~j΅qΉqΈ4(€€€€€€€€€€€‹Β~F7σ}Ρ•Ι¤θνΥΝΡ½µ•Ι}Ή…µ•υqΈ4(€€€€€€€€€€€‹Β~NΔQ•±•Ι…΄θνΥΝ•ΙΉ…µ•υqΈ4(€€€€€€€€€€€‹Β~P-Υ±±…»ΕΔ%θνΥΝ•ΘΉ¥‘υqΈ4(€€€€€€€€€€€‹Β~24¥°θν5%9}19U}95LΉ•Π΅±…Ή°±…Ή¥υqΉqΈ(€€€€€€€€€€€‹Β~n4ƒqΛρΉ±•ΘιqΉν½Ι‘•Ι}±¥Ή•ΝυqΈ(€€€€€€€€€€€‹Β~JΨQ½Α±…΄™¥ε…ΠθνΑΙ¥•τƒ
±qΈ(€€€€€€€€€€€‹Β~>€‘Ι•Μ€ΌΩ±”θν…‘‘Ι•ΝΝυqΉqΈ4(€€€€€€€€€€€‹Β~N4-½ΉΥ΄ιqΉν±½…Ρ¥½Ή}Ρ•αΡυqΉqΈ4(€€€€€€€€€€€€‹Β~j\Q•Ν±¥µ…ΠθƒqΙ•ΡΝ¥ιqΈ4(€€€€€€€€€€€€‹Β~JΤƒY‘•µ”θQ•Ν±¥µ…ΡΡ„Ή…­¥Π4(€€€€€€€€¤4(4(€€€€€€€¥=II}!Q}%θ4(€€€€€€€€€€€ΡΙδθ4(€€€€€€€€€€€€€€€…έ…¥Π½ΉΡ•αΠΉ‰½ΠΉΝ•Ή‘}µ•ΝΝ…” 4(€€€€€€€€€€€€€€€€€€€΅…Ρ}¥υ=II}!Q}%°4(€€€€€€€€€€€€€€€€€€€Ρ•αΠυ…‘µ¥Ή}µ•ΝΝ…”°4(€€€€€€€€€€€€€€€€€€€‘¥Ν…‰±•}έ•‰}Α…•}ΑΙ•Ω¥•άυQΙΥ”4(€€€€€€€€€€€€€€€€¤4(4(€€€€€€€€€€€€€€€¥±…Ρ¥ΡΥ‘”…Ή±½Ή¥ΡΥ‘”θ4(€€€€€€€€€€€€€€€€€€€…έ…¥Π½ΉΡ•αΠΉ‰½ΠΉΝ•Ή‘}±½…Ρ¥½Έ 4(€€€€€€€€€€€€€€€€€€€€€€€΅…Ρ}¥υ=II}!Q}%°4(€€€€€€€€€€€€€€€€€€€€€€€±…Ρ¥ΡΥ‘”υ±…Ρ¥ΡΥ‘”°4(€€€€€€€€€€€€€€€€€€€€€€€±½Ή¥ΡΥ‘”υ±½Ή¥ΡΥ‘”4(€€€€€€€€€€€€€€€€€€€€¤4(4(€€€€€€€€€€€•α•ΑΠα•ΑΡ¥½Έ…Μ”θ4(€€€€€€€€€€€€€€€ΑΙ¥ΉΠ ‰M¥Α…Ι§|ΙΥ‰ΥΉ„ΩΉ‘•Ιµ”΅…Ρ…ΟΔθ°”¤4(4(€€€€€€€•±Ν”θ4(€€€€€€€€€€€ΑΙ¥ΉΠ ‰=II}!Q}%…ε…Ι±…Ήµ…·Η|Έ¤4(€€€€€€€€€€€ΑΙ¥ΉΠ΅…‘µ¥Ή}µ•ΝΝ…”¤4(4(€€€€€€€…έ…¥ΠΕΥ•ΙδΉ•‘¥Ρ}µ•ΝΝ…•}Ι•Α±ε}µ…Ι­Υΐ΅Ι•Α±ε}µ…Ι­Υΐυ9½Ή”¤4(4(€€€€€€€…έ…¥ΠΕΥ•ΙδΉµ•ΝΝ…”ΉΙ•Α±ε}Ρ•αΠ 4(€€€€€€€€€€€QaQMm±…Ήul‰ΝΥ•ΝΜ‰t°4(€€€€€€€€€€€Ι•Α±ε}µ…Ι­ΥΐυI•Α±ε-•ε‰½…Ι‘I•µ½Ω” ¤4(€€€€€€€€¤4(4(€€€€€€€Ι•Ν•Ρ}½Ι‘•Θ΅½ΉΡ•αΠ¤4(4(€€€€€€€Ι•ΡΥΙΈ4(4(4(€€€€€΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄4(€€€€Α1Α1Kΐ{ΓySΑH4(€€€€€΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄4(4(€€€¥‘…Ρ„€ττ€‰΅…Ή•}½Ι‘•Θθ(€€€€€€€Ι•Ν•Ρ}½Ι‘•Θ΅½ΉΡ•αΠ¤((€€€€€€€½ΉΡ•αΠΉΥΝ•Ι}‘…Ρ…l‰ΝΡ…Ρ”‰t€τ€‰ΑΙ½‘ΥΡ}Ν•±•Ρ¥½Έ(€€€€€€€½ΉΡ•αΠΉΥΝ•Ι}‘…Ρ…l‰…ΙΠ‰t€τντ((€€€€€€€…έ…¥ΠΕΥ•ΙδΉ•‘¥Ρ}µ•ΝΝ…•}Ρ•αΠ (€€€€€€€€€€€Ν•±•Ρ¥½Ή}Ρ•αΠ΅±…Ή°ντ¤°(€€€€€€€€€€€Ι•Α±ε}µ…Ι­Υΐυ%Ή±¥Ή•-•ε‰½…Ι‘5…Ι­Υΐ΅Ν•±•Ρ¥½Ή}­•ε‰½…Ι΅±…Ή°ντ¤¤(€€€€€€€€¤(4(€€€€€€€Ι•ΡΥΙΈ4(4(4(€€€€€΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄4(€€€€OΑAKΓ{ΐƒΑAQ0P4(€€€€€΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄4(4(€€€¥‘…Ρ„€ττ€‰…Ή•±}½Ι‘•Θθ4(€€€€€€€…έ…¥ΠΕΥ•ΙδΉ•‘¥Ρ}µ•ΝΝ…•}Ι•Α±ε}µ…Ι­Υΐ΅Ι•Α±ε}µ…Ι­Υΐυ9½Ή”¤4(4(€€€€€€€…έ…¥ΠΕΥ•ΙδΉµ•ΝΝ…”ΉΙ•Α±ε}Ρ•αΠ 4(€€€€€€€€€€€QaQMm±…Ήul‰…Ή•±±•‰t°4(€€€€€€€€€€€Ι•Α±ε}µ…Ι­ΥΐυI•Α±ε-•ε‰½…Ι‘I•µ½Ω” ¤4(€€€€€€€€¤4(4(€€€€€€€Ι•Ν•Ρ}½Ι‘•Θ΅½ΉΡ•αΠ¤4(4(€€€€€€€Ι•ΡΥΙΈ4(4(4(€€€€€΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄4(€€€€-=9U4=158Y44(€€€€€΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄4(4(€€€¥‘…Ρ„€ττ€‰Ν­¥Α}±½…Ρ¥½Έθ4(€€€€€€€…έ…¥ΠΕΥ•ΙδΉ•‘¥Ρ}µ•ΝΝ…•}Ι•Α±ε}µ…Ι­Υΐ΅Ι•Α±ε}µ…Ι­Υΐυ9½Ή”¤4(4(€€€€€€€…έ…¥ΠΝ΅½έ}ΝΥµµ…Ιδ΅ΥΑ‘…Ρ”°½ΉΡ•αΠ¤4(4(€€€€€€€Ι•ΡΥΙΈ4(4(4(€τττττττττττττττττττττττττττττττττττττττττττττττττττττττττ4(ei%1$5M)1H4(€τττττττττττττττττττττττττττττττττττττττττττττττττττττττττ4(4)…ΝεΉ‘•Ρ•αΡ}΅…Ή‘±•Θ΅ΥΑ‘…Ρ”θUΑ‘…Ρ”°½ΉΡ•αΠθ½ΉΡ•αΡQεΑ•ΜΉU1Q}QeA¤θ4(€€€ΝΡ…Ρ”€τ½ΉΡ•αΠΉΥΝ•Ι}‘…Ρ„Ή•Π ‰ΝΡ…Ρ”¤4(4(€€€¥Ή½ΠΝΡ…Ρ”θ4(€€€€€€€Ι•ΡΥΙΈ4(4(€€€±…Ή€τ•Ρ}±…Ή΅½ΉΡ•αΠ¤4(4(€€€Ρ•αΠ€τΥΑ‘…Ρ”Ήµ•ΝΝ…”ΉΡ•αΠΉΝΡΙ¥ΐ ¤(((€€€€€΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄(€€€€5I-€΅ei%1$5M(¤(€€€€€΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄((€€€¥ΝΡ…Ρ”€ττ€‰‰Ι…Ή‘}•ΉΡΙδθ(€€€€€€€½ΉΡ•αΠΉΥΝ•Ι}‘…Ρ…l‰‰Ι…Ή‰t€τΡ•αΠ(€€€€€€€½ΉΡ•αΠΉΥΝ•Ι}‘…Ρ…l‰ΝΡ…Ρ”‰t€τ€‰…‘‘Ι•ΝΜ((€€€€€€€‰Ι…Ή‘}±…‰•°€τU%}QaQm±…Ήul‰‰Ι…Ή‘}½¬‰t(€€€€€€€…έ…¥ΠΥΑ‘…Ρ”Ήµ•ΝΝ…”ΉΙ•Α±ε}Ρ•αΠ (€€€€€€€€€€€‹rν‰Ι…Ή‘}±…‰•±τθνΡ•αΡυqΉqΉνQaQMm±…Ήul…‘‘Ι•ΝΜuτ(€€€€€€€€¤(€€€€€€€Ι•ΡΥΙΈ(4(4(€€€€€΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄4(€€€€IL€ΌY14(€€€€€΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄΄4(4(€€€¥ΝΡ…Ρ”€ττ€‰…‘‘Ι•ΝΜθ((€€€€€€€½ΉΡ•αΠΉΥΝ•Ι}‘…Ρ…l‰…‘‘Ι•ΝΜ‰t€τΡ•αΠ(€€€€€€€½ΉΡ•αΠΉΥΝ•Ι}‘…Ρ…l‰ΝΡ…Ρ”‰t€τ€‰±½…Ρ¥½Έ((€€€€€€€Ν­¥Α}­•ε‰½…Ι€τl(€€€€€€€€€€€l4(€€€€€€€€€€€€€€€%Ή±¥Ή•-•ε‰½…Ι‘	ΥΡΡ½Έ 4(€€€€€€€€€€€€€€€€€€€QaQMm±…Ήul‰Ν­¥Α}±½…Ρ¥½Έ‰t°4(€€€€€€€€€€€€€€€€€€€…±±‰…­}‘…Ρ„τ‰Ν­¥Α}±½…Ρ¥½Έ4(€€€€€€€€€€€€€€€€¤4(€€€€€€€€€€€t4(€€€€€€€t4(4(€€€€€€€Ν­¥Α}­•ε‰½…ΙΉ•αΡ•Ή΅ΝΥΑΑ½ΙΡ}­•ε‰½…Ι΅±…Ή¤¤((€€€€€€€…έ…¥ΠΥΑ‘…Ρ”Ήµ•ΝΝ…”ΉΙ•Α±ε}Ρ•αΠ (€€€€€€€€€€€QaQMm±…Ήul‰±½…Ρ¥½Ή}ΕΥ•ΝΡ¥½Έ‰t°(€€€€€€€€€€€Ι•Α±ε}µ…Ι­Υΐυ%Ή±¥Ή•-•ε‰½…Ι‘5…Ι­Υΐ΅Ν­¥Α}­•ε‰½…Ι¤(€€€€€€€€¤(4(€€€€€€€Ι•ΡΥΙΈ4(4(4(€τττττττττττττττττττττττττττττττττττττττττττττττττττττττττ4(-=9U45M)$4(€τττττττττττττττττττττττττττττττττττττττττττττττττττττττττ4)…ΝεΉ‘•Ν΅½έ}¥΅ΥΑ‘…Ρ”°½ΉΡ•αΠ¤θ4(€€€…έ…¥ΠΥΑ‘…Ρ”Ήµ•ΝΝ…”ΉΙ•Α±ε}Ρ•αΠ΅‰	ΤΙΥ‰ΥΈ%Ν¤θνΥΑ‘…Ρ”Ή•™™•Ρ¥Ω•}΅…ΠΉ¥‘τ¤4)…ΝεΉ‘•±½…Ρ¥½Ή}΅…Ή‘±•Θ 4(€€€ΥΑ‘…Ρ”θUΑ‘…Ρ”°4(€€€½ΉΡ•αΠθ½ΉΡ•αΡQεΑ•ΜΉU1Q}QeA4(¤θ4(4(€€€ΝΡ…Ρ”€τ½ΉΡ•αΠΉΥΝ•Ι}‘…Ρ„Ή•Π ‰ΝΡ…Ρ”¤4(4(€€€¥ΝΡ…Ρ”€„τ€‰±½…Ρ¥½Έθ4(€€€€€€€Ι•ΡΥΙΈ4(4(€€€±…Ή€τ•Ρ}±…Ή΅½ΉΡ•αΠ¤4(4(€€€±½…Ρ¥½Έ€τΥΑ‘…Ρ”Ήµ•ΝΝ…”Ή±½…Ρ¥½Έ4(4(€€€½ΉΡ•αΠΉΥΝ•Ι}‘…Ρ…l‰±…Ρ¥ΡΥ‘”‰t€τ±½…Ρ¥½ΈΉ±…Ρ¥ΡΥ‘”4(€€€½ΉΡ•αΠΉΥΝ•Ι}‘…Ρ…l‰±½Ή¥ΡΥ‘”‰t€τ±½…Ρ¥½ΈΉ±½Ή¥ΡΥ‘”4(4(€€€…έ…¥ΠΥΑ‘…Ρ”Ήµ•ΝΝ…”ΉΙ•Α±ε}Ρ•αΠ 4(€€€€€€€QaQMm±…Ήul‰±½…Ρ¥½Ή}Ι••¥Ω•‰t°4(€€€€€€€Ι•Α±ε}µ…Ι­ΥΐυI•Α±ε-•ε‰½…Ι‘I•µ½Ω” ¤4(€€€€¤4(4(€€€…έ…¥ΠΝ΅½έ}ΝΥµµ…Ιδ΅ΥΑ‘…Ρ”°½ΉΡ•αΠ¤4(4(4(€τττττττττττττττττττττττττττττττττττττττττττττττττττττττττ4(9AI=I44(€τττττττττττττττττττττττττττττττττττττττττττττττττττττττττ4(4)‘•µ…¥Έ ¤θ(4(€€€¥Ή½ΠQ=-8θ(€€€€€€€Ι…¥Ν”IΥΉΡ¥µ•ΙΙ½Θ ‰	=Q}Q=-8‰Υ±ΥΉ…µ…“Δ„¤((€€€¥Ή½Π=II}!Q}%θ(€€€€€€€Ι…¥Ν”IΥΉΡ¥µ•ΙΙ½Θ ‰=II}!Q}%‰Υ±ΥΉ…µ…“Δ„¤((€€€¥Ή½ΠY9=I}1IQ}!Q}%θ(€€€€€€€ΑΙ¥ΉΠ (€€€€€€€€€€€€‰Y9=I}1IQ}!Q}%…ε…Ι±…Ήµ…·Η|θƒρε”­…ηΕΡ±…ΛΔΩ”ΑΥ…Ή±…µ„€(€€€€€€€€€€€€‹…³ΗΕΘ°…Ή…¬Ν…ΣΕΔΥε…ΛΕΟΔ΅§‰¥ΘΙΥ‰„ΩΉ‘•Ι¥±µ•θΈ(€€€€€€€€¤(4(€€€¥Ή¥Ρ}Ω•Ή‘½Ι}‘ ¤(€€€…Αΐ€τΑΑ±¥…Ρ¥½ΈΉ‰Υ¥±‘•Θ ¤ΉΡ½­•Έ΅Q=-8¤Ή‰Υ¥± ¤(4(€€€…ΑΐΉ…‘‘}΅…Ή‘±•Θ (€€€€€€€½µµ…Ή‘!…Ή‘±•Θ ‰ΝΡ…ΙΠ°ΝΡ…ΙΠ¤(€€€€¤((€€€…ΑΐΉ…‘‘}΅…Ή‘±•Θ (€€€€€€€΅…Ρ)½¥ΉI•ΕΥ•ΝΡ!…Ή‘±•Θ (€€€€€€€€€€€©½¥Ή}Ι•ΕΥ•ΝΠ°(€€€€€€€€€€€΅…Ρ}¥υA%9-A9Q!I}I=UA}%(€€€€€€€€¤(€€€€¤((€€€…ΑΐΉ…‘‘}΅…Ή‘±•Θ (€€€€€€€΅…Ρ5•µ‰•Ι!…Ή‘±•Θ΅΅…Ρ}µ•µ‰•Ι}ΥΑ‘…Ρ”°΅…Ρ5•µ‰•Ι!…Ή‘±•ΘΉ!Q}55	H¤(€€€€¤((€€€¥…ΑΐΉ©½‰}ΕΥ•Υ”θ(€€€€€€€…ΑΐΉ©½‰}ΕΥ•Υ”ΉΙΥΉ}Ι•Α•…Ρ¥Ή (€€€€€€€€€€€Ν…Ή}Ω•Ή‘½Ι}…Ή‘¥‘…Ρ•Μ°(€€€€€€€€€€€¥ΉΡ•ΙΩ…°υY9=I}M9}%9QIY0°(€€€€€€€€€€€™¥ΙΝΠτΔΐ°(€€€€€€€€€€€Ή…µ”τ‰Ω•Ή‘½Θµ…Ή‘¥‘…Ρ”µΝ…Έ°(€€€€€€€€¤(4(€€€…ΑΐΉ…‘‘}΅…Ή‘±•Θ 4(€€€€€€€…±±‰…­EΥ•Ιε!…Ή‘±•Θ΅‰ΥΡΡ½Ή}΅…Ή‘±•Θ¤4(€€€€¤4(4(€€€…ΑΐΉ…‘‘}΅…Ή‘±•Θ 4(€€€€€€€5•ΝΝ…•!…Ή‘±•Θ 4(€€€€€€€€€€€™¥±Ρ•ΙΜΉ1=Q%=8°4(€€€€€€€€€€€±½…Ρ¥½Ή}΅…Ή‘±•Θ4(€€€€€€€€¤4(€€€€¤4(4(€€€…ΑΐΉ…‘‘}΅…Ή‘±•Θ 4(€€€€€€€5•ΝΝ…•!…Ή‘±•Θ 4(€€€€€€€€€€€™¥±Ρ•ΙΜΉQaP€ω™¥±Ρ•ΙΜΉ=559°4(€€€€€€€€€€€Ρ•αΡ}΅…Ή‘±•Θ4(€€€€€€€€¤4(€€€€¤4(4(€€€ΑΙ¥ΉΠ ‰A¥Ή­A…ΉΡ΅•Θ	½Πƒ…³ΗΕε½ΘΈΈΈ¤4(€€€…ΑΐΉ…‘‘}΅…Ή‘±•Θ΅½µµ…Ή‘!…Ή‘±•Θ ‰¥°Ν΅½έ}¥¤¤4(€€€…ΑΐΉΙΥΉ}Α½±±¥Ή 4(€€€€€€€…±±½έ•‘}ΥΑ‘…Ρ•ΜυUΑ‘…Ρ”Ή11}QeAL4(€€€€¤4(4(4)¥}}Ή…µ•}|€ττ€‰}}µ…¥Ή}|θ4(€€€µ…¥Έ ¤4(