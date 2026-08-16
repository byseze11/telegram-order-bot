import os
import sqlite3
from datetime import datetime, timezone
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ForceReply,
    ReplyKeyboardMarkup,
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
MENU_IMAGE_PATH = os.getenv(
    "MENU_IMAGE_PATH",
    os.path.join(os.path.dirname(__file__), "assets", "menu.png"),
)

# BUNLARI SONRA BİRLİKTE AYARLAYACAĞIZ
# Siparişlerin geleceği özel Telegram grubunun ID'si
ORDER_CHAT_ID = os.getenv("ORDER_CHAT_ID")

# Katılma isteği geldiğinde özelden karşılanacak PinkPanther grubu
PINKPANTHER_GROUP_ID = int(
    os.getenv("PINKPANTHER_GROUP_ID", "-1004472680906")
)

# Canlı destek için Telegram kullanıcı adın
# @ işareti OLMADAN yazılacak. Örnek: PinkPantherSupport
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

# Ürün çeşitleri ve seçim -> toplam fiyat (€) listesi
PRODUCTS = {
    "leaf": {
        "en": "🍀 Leaf",
        "de": "🍀 Blatt",
        "tr": "🍀 Yaprak",
        "es": "🍀 Hoja",
        "it": "🍀 Foglia",
        "ru": "🍀 Лист",
        "pl": "🍀 Liść",
        "fr": "🍀 Feuille",
        "grams_per_unit": 5,
        "prices": {1: 50, 2: 100, 3: 130, 5: 190},
    },
    "chocolate": {
        "en": "🍫 Chocolate",
        "de": "🍫 Schokolade",
        "tr": "🍫 Çikolata",
        "es": "🍫 Chocolate",
        "it": "🍫 Cioccolato",
        "ru": "🍫 Шоколад",
        "pl": "🍫 Czekolada",
        "fr": "🍫 Chocolat",
        "grams_per_unit": 5,
        "prices": {1: 50, 2: 100, 3: 130, 5: 190},
    },
    "snow": {
        "en": "❄️ Snow",
        "de": "❄️ Schnee",
        "tr": "❄️ Kar",
        "es": "❄️ Nieve",
        "it": "❄️ Neve",
        "ru": "❄️ Снег",
        "pl": "❄️ Śnieg",
        "fr": "❄️ Neige",
        "unit": "g",
        "prices": {0.5: 50, 1: 100, 3: 225},
    },
}


# =========================================================
# METİNLER
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
        reasons.append(f"{row['reentry_count']} yeniden giriş")
    username = (row["username"] or "").lower()
    matches = [word for word in VENDOR_KEYWORDS if word in username]
    if matches:
        score += VENDOR_USERNAME_POINTS
        reasons.append("kullanıcı adı: " + ", ".join(matches))
    joined = parse_time(row["first_joined_at"])
    age_days = (utc_now() - joined).days if joined else 0
    if not row["has_ordered"] and age_days >= VENDOR_INACTIVE_DAYS:
        score += VENDOR_INACTIVE_POINTS
        reasons.append(f"{age_days} gündür sipariş yok")
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
    username = f"@{row['username']}" if row["username"] else "Kullanıcı adı yok"
    stay_seconds = row["total_stay_seconds"]
    if row["is_member"] and row["last_joined_at"]:
        stay_seconds += max(
            0, int((utc_now() - parse_time(row["last_joined_at"])).total_seconds())
        )
    await context.bot.send_message(
        chat_id=VENDOR_ALERT_CHAT_ID,
        text=(
            "⚠️ Potansiyel Satıcı\n\n"
            f"👤 {row['full_name'] or '-'}\n"
            f"📱 {username}\n"
            f"🆔 {row['user_id']}\n"
            f"📊 Puan: {score}/{VENDOR_SCORE_THRESHOLD}\n"
            f"🔁 Gir-çık / yeniden giriş: {row['reentry_count']}\n"
            f"⏱ Grupta toplam süre: {stay_seconds // 86400} gün\n"
            f"🗓 İlk girişten beri: {age_days} gün\n"
            f"🛒 Sipariş: Hayır\n"
            f"🔎 Nedenler: {', '.join(reasons) or '-'}"
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
            print("Satıcı adayı kontrol hatası:", user_id, error)


TEXTS = {
    "en": {
        "language_selected": "🇬🇧 English selected.",

        "welcome": (
            "⚠️ IMPORTANT – PLEASE READ CAREFULLY\n\n"
            "🐾 Welcome to GreenPantherBot\n\n"
            "Hello! I’m GreenPantherBot. I’m here to help you place your order "
            "quickly and easily.\n\n"
            "💵 Cash payment only.\n"
            "✅ No payment is required before you receive your product.\n"
            "🤝 In-person handover is available.\n"
            "🚗 Driver delivery is FREE.\n"
            "📍 You can share your location directly through Telegram.\n"
            "🆘 If you have any questions or problems, you can continue your "
            "order through Live Support.\n\n"
            "Please choose an option below:"
        ),

        "order_button": "🛍 Place an Order",
        "support_button": "🆘 Live Support",

        "product": (
            "🛍 PRODUCT CATALOG\n\n"
            "🍀 Leaf\n"
            "🍫 Chocolate\n"
            "❄️ Snow\n\n"
            "Select one or more products and quantities below.\n"
            "Then press Continue."
        ),

        "brand_prompt": (
            "✍️ Please type the brand/name of your selected product.\n\n"
            "Send it as a normal text message; there is no button for this step."
        ),

        "quantity": (
            "🔢 How many would you like to order?\n\n"
            "Minimum order: 5 pieces\n\n"
            "5 pieces = 50 €\n"
            "10 pieces = 100 €\n"
            "15 pieces = 130 €\n"
            "25 pieces = 190 €\n\n"
            "Please enter one of these quantities: 5, 10, 15 or 25."
        ),

        "address": (
            "📍 DELIVERY INFORMATION\n\n"
            "Please send your full delivery address and postal code together.\n\n"
            "Example:\n"
            "Musterstraße 12, 12345 Berlin\n\n"
            "ℹ️ NOTE:\n"
            "If you don’t know your full address or postal code, enter the area "
            "or district you know. On the next step, use the 📍 Share Location "
            "button to send your exact delivery point.\n\n"
            "If you need help, you can continue through 🆘 Live Support."
        ),

        "share_location": "📍 Share Location",
        "skip_location": "➡️ Continue Without Location",

        "location_question": (
            "📍 Use the Share Location button to send your exact delivery point.\n\n"
            "If you do not know the full address, sending your location is the easiest option.\n\n"
            "You can also continue without sharing your location."
        ),

        "location_received": "✅ Location received.",

        "confirm": "✅ Confirm Order",
        "change": "✏️ Change Information",
        "cancel": "❌ Cancel Order",

        "cancelled": (
            "❌ Your order has been cancelled.\n\n"
            "You can start again anytime with /start."
        ),

        "success": (
            "✅ YOUR ORDER HAS BEEN RECEIVED SUCCESSFULLY.\n\n"
            "Thank you for your order. You will be contacted regarding the delivery.\n\n"
            "🚗 Delivery: FREE\n"
            "💵 Payment: Cash on delivery\n\n"
            "⚠️ Please do not make any payment before receiving your product."
        ),

        "support_not_ready": (
            "🆘 Live Support is currently being configured.\n"
            "Please try again shortly."
        ),

        "restart": "🔄 Please enter the product name or product code again.",

        "invalid_quantity": (
            "⚠️ Minimum order is 5 pieces.\n"
            "Please enter one of these quantities: 5, 10, 15 or 25."
        ),
    },

    "de": {
        "language_selected": "🇩🇪 Deutsch ausgewählt.",

        "welcome": (
            "⚠️ WICHTIG – BITTE SORGFÄLTIG LESEN\n\n"
            "🐾 Willkommen beim GreenPantherBot\n\n"
            "Hallo! Ich bin der GreenPantherBot. Ich bin hier, um dir dabei zu helfen, "
            "deine Bestellung schnell und einfach aufzugeben.\n\n"
            "💵 Nur Barzahlung.\n"
            "✅ Du musst nichts bezahlen, bevor du dein Produkt erhalten hast.\n"
            "🤝 Eine persönliche Übergabe ist möglich.\n"
            "🚗 Die Lieferung durch unseren Fahrer ist KOSTENLOS.\n"
            "📍 Deinen Standort kannst du direkt über Telegram senden.\n"
            "🆘 Falls du Fragen oder Probleme hast, kannst du deine Bestellung "
            "über den Live-Support fortsetzen.\n\n"
            "Bitte wähle unten eine Option:"
        ),

        "order_button": "🛍 Bestellung aufgeben",
        "support_button": "🆘 Live-Support",

        "product": (
            "🛍 PRODUKTKATALOG\n\n"
            "🍀 Blatt\n"
            "🍫 Schokolade\n"
            "❄️ Schnee\n\n"
            "Wähle unten ein oder mehrere Produkte und Mengen aus.\n"
            "Drücke anschließend auf Weiter."
        ),

        "brand_prompt": (
            "✍️ Bitte schreibe die Marke/den Namen des ausgewählten Produkts.\n\n"
            "Sende sie als normale Textnachricht; für diesen Schritt gibt es keine Schaltfläche."
        ),

        "quantity": (
            "🔢 Wie viele Stück möchtest du bestellen?\n\n"
            "Mindestbestellmenge: 5 Stück\n\n"
            "5 Stück = 50 €\n"
            "10 Stück = 100 €\n"
            "15 Stück = 130 €\n"
            "25 Stück = 190 €\n\n"
            "Bitte gib eine dieser Mengen ein: 5, 10, 15 oder 25."
        ),

        "address": (
            "📍 LIEFERINFORMATIONEN\n\n"
            "Bitte sende deine vollständige Lieferadresse und Postleitzahl zusammen.\n\n"
            "Beispiel:\n"
            "Musterstraße 12, 12345 Berlin\n\n"
            "ℹ️ HINWEIS:\n"
            "Wenn du deine vollständige Adresse oder Postleitzahl nicht kennst, "
            "gib den bekannten Stadtteil ein. Tippe im nächsten Schritt auf "
            "📍 Standort senden, um den genauen Lieferort zu teilen.\n\n"
            "Falls du Hilfe benötigst, kannst du über den 🆘 Live-Support fortfahren."
        ),

        "share_location": "📍 Standort senden",
        "skip_location": "➡️ Ohne Standort fortfahren",

        "location_question": (
            "📍 Tippe auf Standort senden, um den genauen Lieferort zu teilen.\n\n"
            "Wenn du die vollständige Adresse nicht kennst, ist das Senden des Standorts am einfachsten.\n\n"
            "Du kannst auch ohne Standort fortfahren."
        ),

        "location_received": "✅ Standort erhalten.",

        "confirm": "✅ Bestellung bestätigen",
        "change": "✏️ Angaben ändern",
        "cancel": "❌ Bestellung stornieren",

        "cancelled": (
            "❌ Deine Bestellung wurde storniert.\n\n"
            "Du kannst jederzeit mit /start neu beginnen."
        ),

        "success": (
            "✅ DEINE BESTELLUNG WURDE ERFOLGREICH AUFGENOMMEN.\n\n"
            "Vielen Dank für deine Bestellung. Wir werden dich bezüglich der "
            "Lieferung kontaktieren.\n\n"
            "🚗 Lieferung: KOSTENLOS\n"
            "💵 Zahlung: Barzahlung bei Übergabe\n\n"
            "⚠️ Bitte bezahle nichts, bevor du dein Produkt erhalten hast."
        ),

        "support_not_ready": (
            "🆘 Der Live-Support wird derzeit eingerichtet.\n"
            "Bitte versuche es später erneut."
        ),

        "restart": "🔄 Bitte gib den Produktnamen oder Produktcode erneut ein.",

        "invalid_quantity": (
            "⚠️ Die Mindestbestellmenge beträgt 5 Stück.\n"
            "Bitte gib eine dieser Mengen ein: 5, 10, 15 oder 25."
        ),
    }
}


# Ek dil çevirileri
TEXTS.update({
    "tr": {
        "language_selected": "🇹🇷 Türkçe seçildi.",
        "welcome": (
            "⚠️ ÖNEMLİ – LÜTFEN DİKKATLİCE OKUYUN\n\n"
            "🐾 GreenPantherBot'a hoş geldiniz\n\n"
            "Siparişinizi hızlı ve kolayca oluşturmanıza yardımcı olacağım.\n\n"
            "💵 Yalnızca nakit ödeme.\n✅ Ürünü teslim almadan ödeme yapmayın.\n"
            "🚗 Kurye teslimatı ÜCRETSİZDİR.\n📍 Konumunuzu Telegram üzerinden paylaşabilirsiniz.\n\n"
            "Lütfen aşağıdan bir seçenek belirleyin:"
        ),
        "order_button": "🛍 Sipariş Ver",
        "support_button": "🆘 Canlı Destek",
        "product": (
            "🛍 ÜRÜN KATALOĞU\n\n"
            "🍀 Yaprak\n"
            "🍫 Çikolata\n"
            "❄️ Kar\n\n"
            "Bir veya daha fazla ürün ve miktar seçin. Sonra Devam'a basın."
        ),
        "brand_prompt": "✍️ Seçtiğiniz ürünün markasını/adını normal mesaj olarak yazın.",
        "quantity": "🔢 Lütfen miktarı seçin.",
        "address": (
            "📍 TESLİMAT BİLGİLERİ\n\nTam adresinizi ve posta kodunuzu birlikte yazın.\n\n"
            "Örnek: Musterstraße 12, 12345 Berlin\n\n"
            "Tam adresinizi bilmiyorsanız bildiğiniz bölgeyi yazın. Sonraki adımda "
            "📍 Konum Gönder butonuna basarak kesin konumunuzu paylaşabilirsiniz."
        ),
        "share_location": "📍 Konum Gönder",
        "skip_location": "➡️ Siparişe Devam Et",
        "location_question": (
            "📍 Teslimat noktasını doğru bulabilmemiz için konumunuzu gönderebilirsiniz.\n\n"
            "Tam adresinizi bilmiyorsanız 📍 Konum Gönder butonuna basın.\n\n"
            "Konum paylaşmak istemiyorsanız ➡️ Siparişe Devam Et seçeneğini kullanın."
        ),
        "location_received": "✅ Konum alındı.",
        "location_skipped": "➡️ Konum paylaşılmadan siparişe devam ediliyor.",
        "confirm": "✅ Siparişi Onayla",
        "change": "✏️ Bilgileri Değiştir",
        "cancel": "❌ Siparişi İptal Et",
        "cancelled": "❌ Siparişiniz iptal edildi.\n\n/start ile yeniden başlayabilirsiniz.",
        "success": "✅ SİPARİŞİNİZ ALINDI.\n\nTeslimat için sizinle iletişime geçilecektir.\n\n🚗 Teslimat: ÜCRETSİZ\n💵 Ödeme: Teslimatta nakit",
        "support_not_ready": "🆘 Canlı destek hazırlanıyor. Lütfen daha sonra tekrar deneyin.",
        "restart": "🔄 Lütfen ürün adını veya kodunu tekrar girin.",
        "invalid_quantity": "⚠️ Lütfen geçerli bir miktar seçin.",
    },
    "es": {
        "language_selected": "🇪🇸 Español seleccionado.",
        "welcome": (
            "⚠️ IMPORTANTE – LEE ATENTAMENTE\n\n🐾 Bienvenido a GreenPantherBot\n\n"
            "Te ayudaré a realizar tu pedido de forma rápida y sencilla.\n\n"
            "💵 Solo pago en efectivo.\n✅ No pagues antes de recibir el producto.\n"
            "🚗 La entrega es GRATIS.\n📍 Puedes compartir tu ubicación por Telegram.\n\n"
            "Elige una opción:"
        ),
        "order_button": "🛍 Hacer un pedido",
        "support_button": "🆘 Soporte en vivo",
        "product": (
            "🛍 CATÁLOGO DE PRODUCTOS\n\n"
            "🍀 Hoja\n🍫 Chocolate\n❄️ Nieve\n\n"
            "Selecciona productos y cantidades. Luego pulsa Continuar."
        ),
        "brand_prompt": "✍️ Escribe la marca o el nombre del producto seleccionado como mensaje normal.",
        "quantity": "🔢 Selecciona una cantidad.",
        "address": "📍 DATOS DE ENTREGA\n\nEscribe tu dirección completa y código postal.\n\nEjemplo: Musterstraße 12, 12345 Berlin\n\nSi no conoces la dirección completa, escribe la zona que conozcas. En el siguiente paso, pulsa 📍 Compartir ubicación para enviar el punto exacto.",
        "share_location": "📍 Compartir ubicación",
        "skip_location": "➡️ Continuar sin ubicación",
        "location_question": "📍 Pulsa Compartir ubicación para enviar el punto exacto. Si no conoces la dirección completa, esta es la opción más sencilla. También puedes continuar sin compartirla.",
        "location_received": "✅ Ubicación recibida.",
        "confirm": "✅ Confirmar pedido",
        "change": "✏️ Cambiar información",
        "cancel": "❌ Cancelar pedido",
        "cancelled": "❌ Tu pedido ha sido cancelado.\n\nPuedes empezar de nuevo con /start.",
        "success": "✅ PEDIDO RECIBIDO.\n\nNos pondremos en contacto contigo para la entrega.\n\n🚗 Entrega: GRATIS\n💵 Pago: En efectivo al recibir",
        "support_not_ready": "🆘 El soporte se está configurando. Inténtalo más tarde.",
        "restart": "🔄 Introduce de nuevo el nombre o código del producto.",
        "invalid_quantity": "⚠️ Selecciona una cantidad válida.",
    },
    "it": {
        "language_selected": "🇮🇹 Italiano selezionato.",
        "welcome": (
            "⚠️ IMPORTANTE – LEGGI ATTENTAMENTE\n\n🐾 Benvenuto nel GreenPantherBot\n\n"
            "Ti aiuterò a effettuare l'ordine in modo semplice e veloce.\n\n"
            "💵 Solo pagamento in contanti.\n✅ Non pagare prima di ricevere il prodotto.\n"
            "🚗 Consegna GRATUITA.\n📍 Puoi condividere la posizione tramite Telegram.\n\nScegli un'opzione:"
        ),
        "order_button": "🛍 Effettua un ordine",
        "support_button": "🆘 Assistenza",
        "product": (
            "🛍 CATALOGO PRODOTTI\n\n"
            "🍀 Foglia\n🍫 Cioccolato\n❄️ Neve\n\n"
            "Seleziona prodotti e quantità, poi premi Continua."
        ),
        "brand_prompt": "✍️ Scrivi la marca o il nome del prodotto scelto come messaggio normale.",
        "quantity": "🔢 Seleziona una quantità.",
        "address": "📍 DATI DI CONSEGNA\n\nScrivi indirizzo completo e codice postale.\n\nEsempio: Musterstraße 12, 12345 Berlin\n\nSe non conosci l'indirizzo completo, scrivi la zona che conosci. Nel passaggio successivo, premi 📍 Condividi posizione per inviare il punto esatto.",
        "share_location": "📍 Condividi posizione",
        "skip_location": "➡️ Continua senza posizione",
        "location_question": "📍 Premi Condividi posizione per inviare il punto esatto. Se non conosci l'indirizzo completo, questa è l'opzione più semplice. Puoi anche continuare senza condividerla.",
        "location_received": "✅ Posizione ricevuta.",
        "confirm": "✅ Conferma ordine",
        "change": "✏️ Modifica dati",
        "cancel": "❌ Annulla ordine",
        "cancelled": "❌ Il tuo ordine è stato annullato.\n\nPuoi ricominciare con /start.",
        "success": "✅ ORDINE RICEVUTO.\n\nTi contatteremo per la consegna.\n\n🚗 Consegna: GRATUITA\n💵 Pagamento: Contanti alla consegna",
        "support_not_ready": "🆘 L'assistenza è in fase di configurazione. Riprova più tardi.",
        "restart": "🔄 Inserisci nuovamente nome o codice del prodotto.",
        "invalid_quantity": "⚠️ Seleziona una quantità valida.",
    },
    "ru": {
        "language_selected": "🇷🇺 Выбран русский язык.",
        "welcome": (
            "⚠️ ВАЖНО – ПРОЧИТАЙТЕ ВНИМАТЕЛЬНО\n\n🐾 Добро пожаловать в GreenPantherBot\n\n"
            "Я помогу быстро и легко оформить заказ.\n\n💵 Только наличные.\n"
            "✅ Не платите до получения товара.\n🚗 Доставка БЕСПЛАТНАЯ.\n"
            "📍 Вы можете отправить геолокацию через Telegram.\n\nВыберите действие:"
        ),
        "order_button": "🛍 Сделать заказ",
        "support_button": "🆘 Поддержка",
        "product": (
            "🛍 КАТАЛОГ ТОВАРОВ\n\n"
            "🍀 Лист\n🍫 Шоколад\n❄️ Снег\n\n"
            "Выберите товары и количество, затем нажмите Продолжить."
        ),
        "brand_prompt": "✍️ Напишите марку или название выбранного товара обычным сообщением.",
        "quantity": "🔢 Выберите количество.",
        "address": "📍 ДАННЫЕ ДЛЯ ДОСТАВКИ\n\nНапишите полный адрес и почтовый индекс.\n\nПример: Musterstraße 12, 12345 Berlin\n\nЕсли вы не знаете полный адрес, укажите известный район. На следующем шаге нажмите 📍 Отправить геолокацию, чтобы передать точную точку.",
        "share_location": "📍 Отправить геолокацию",
        "skip_location": "➡️ Продолжить без геолокации",
        "location_question": "📍 Нажмите Отправить геолокацию, чтобы передать точную точку доставки. Если вы не знаете полный адрес, это самый простой вариант. Можно продолжить без геолокации.",
        "location_received": "✅ Геолокация получена.",
        "confirm": "✅ Подтвердить заказ",
        "change": "✏️ Изменить данные",
        "cancel": "❌ Отменить заказ",
        "cancelled": "❌ Заказ отменён.\n\nНачать заново: /start.",
        "success": "✅ ЗАКАЗ ПРИНЯТ.\n\nМы свяжемся с вами по поводу доставки.\n\n🚗 Доставка: БЕСПЛАТНО\n💵 Оплата: Наличными при получении",
        "support_not_ready": "🆘 Поддержка настраивается. Попробуйте позже.",
        "restart": "🔄 Введите название или код товара ещё раз.",
        "invalid_quantity": "⚠️ Выберите допустимое количество.",
    },
    "pl": {
        "language_selected": "🇵🇱 Wybrano język polski.",
        "welcome": (
            "⚠️ WAŻNE – PRZECZYTAJ UWAŻNIE\n\n🐾 Witamy w GreenPantherBot\n\n"
            "Pomogę Ci szybko i łatwo złożyć zamówienie.\n\n💵 Tylko płatność gotówką.\n"
            "✅ Nie płać przed otrzymaniem produktu.\n🚗 Dostawa jest BEZPŁATNA.\n"
            "📍 Możesz udostępnić lokalizację przez Telegram.\n\nWybierz opcję:"
        ),
        "order_button": "🛍 Złóż zamówienie",
        "support_button": "🆘 Pomoc na żywo",
        "product": (
            "🛍 KATALOG PRODUKTÓW\n\n"
            "🍀 Liść\n🍫 Czekolada\n❄️ Śnieg\n\n"
            "Wybierz produkty i ilości, a następnie naciśnij Dalej."
        ),
        "brand_prompt": "✍️ Wpisz markę lub nazwę wybranego produktu jako zwykłą wiadomość.",
        "quantity": "🔢 Wybierz ilość.",
        "address": "📍 DANE DOSTAWY\n\nWpisz pełny adres i kod pocztowy.\n\nPrzykład: Musterstraße 12, 12345 Berlin\n\nJeśli nie znasz pełnego adresu, wpisz znaną dzielnicę. W następnym kroku naciśnij 📍 Udostępnij lokalizację, aby wysłać dokładny punkt.",
        "share_location": "📍 Udostępnij lokalizację",
        "skip_location": "➡️ Kontynuuj bez lokalizacji",
        "location_question": "📍 Naciśnij Udostępnij lokalizację, aby wysłać dokładny punkt dostawy. Jeśli nie znasz pełnego adresu, jest to najprostsza opcja. Możesz też kontynuować bez lokalizacji.",
        "location_received": "✅ Otrzymano lokalizację.",
        "confirm": "✅ Potwierdź zamówienie",
        "change": "✏️ Zmień dane",
        "cancel": "❌ Anuluj zamówienie",
        "cancelled": "❌ Zamówienie zostało anulowane.\n\nMożesz zacząć ponownie przez /start.",
        "success": "✅ ZAMÓWIENIE PRZYJĘTE.\n\nSkontaktujemy się w sprawie dostawy.\n\n🚗 Dostawa: BEZPŁATNA\n💵 Płatność: Gotówką przy odbiorze",
        "support_not_ready": "🆘 Pomoc jest konfigurowana. Spróbuj później.",
        "restart": "🔄 Wpisz ponownie nazwę lub kod produktu.",
        "invalid_quantity": "⚠️ Wybierz prawidłową ilość.",
    },
    "fr": {
        "language_selected": "🇫🇷 Français sélectionné.",
        "welcome": (
            "⚠️ IMPORTANT – LISEZ ATTENTIVEMENT\n\n🐾 Bienvenue sur GreenPantherBot\n\n"
            "Je vais vous aider à passer votre commande rapidement et facilement.\n\n"
            "💵 Paiement en espèces uniquement.\n✅ Ne payez pas avant de recevoir le produit.\n"
            "🚗 Livraison GRATUITE.\n📍 Vous pouvez partager votre position via Telegram.\n\nChoisissez une option :"
        ),
        "order_button": "🛍 Passer une commande",
        "support_button": "🆘 Assistance en direct",
        "product": (
            "🛍 CATALOGUE DE PRODUITS\n\n"
            "🍀 Feuille\n🍫 Chocolat\n❄️ Neige\n\n"
            "Sélectionnez les produits et quantités, puis appuyez sur Continuer."
        ),
        "brand_prompt": "✍️ Écrivez la marque ou le nom du produit choisi dans un message normal.",
        "quantity": "🔢 Sélectionnez une quantité.",
        "address": "📍 INFORMATIONS DE LIVRAISON\n\nÉcrivez votre adresse complète et votre code postal.\n\nExemple : Musterstraße 12, 12345 Berlin\n\nSi vous ne connaissez pas l'adresse complète, indiquez le quartier connu. À l'étape suivante, appuyez sur 📍 Partager la position pour envoyer le point exact.",
        "share_location": "📍 Partager la position",
        "skip_location": "➡️ Continuer sans position",
        "location_question": "📍 Appuyez sur Partager la position pour envoyer le point de livraison exact. Si vous ne connaissez pas l'adresse complète, c'est l'option la plus simple. Vous pouvez aussi continuer sans partager la position.",
        "location_received": "✅ Position reçue.",
        "confirm": "✅ Confirmer la commande",
        "change": "✏️ Modifier les informations",
        "cancel": "❌ Annuler la commande",
        "cancelled": "❌ Votre commande a été annulée.\n\nVous pouvez recommencer avec /start.",
        "success": "✅ COMMANDE REÇUE.\n\nNous vous contacterons pour la livraison.\n\n🚗 Livraison : GRATUITE\n💵 Paiement : En espèces à la livraison",
        "support_not_ready": "🆘 L'assistance est en cours de configuration. Réessayez plus tard.",
        "restart": "🔄 Saisissez à nouveau le nom ou le code du produit.",
        "invalid_quantity": "⚠️ Sélectionnez une quantité valide.",
    },
})


LANGUAGE_OPTIONS = (
    ("en", "🇬🇧 English"), ("de", "🇩🇪 Deutsch"),
    ("tr", "🇹🇷 Türkçe"), ("es", "🇪🇸 Español"),
    ("it", "🇮🇹 Italiano"), ("ru", "🇷🇺 Русский"),
    ("pl", "🇵🇱 Polski"), ("fr", "🇫🇷 Français"),
)

ADMIN_LANGUAGE_NAMES = {
    "en": "İngilizce", "de": "Almanca", "tr": "Türkçe", "es": "İspanyolca",
    "it": "İtalyanca", "ru": "Rusça", "pl": "Lehçe", "fr": "Fransızca",
}

UI_TEXT = {
    "en": {"selected": "Selected", "total": "Total", "continue": "Continue", "brand": "Brand", "brand_ok": "Brand", "received": "Received", "not_shared": "Not shared", "empty": "Please select at least one product.", "summary": "ORDER SUMMARY", "products": "Products", "total_price": "Total price", "address": "Address / Area", "location": "Location", "delivery": "Delivery: FREE", "payment": "Payment: Cash on delivery", "warning": "Do not make any payment before receiving your product."},
    "de": {"selected": "Ausgewählt", "total": "Gesamt", "continue": "Weiter", "brand": "Marke", "brand_ok": "Marke", "received": "Erhalten", "not_shared": "Nicht gesendet", "empty": "Bitte wähle mindestens ein Produkt aus.", "summary": "BESTELLÜBERSICHT", "products": "Produkte", "total_price": "Gesamtpreis", "address": "Adresse / Gebiet", "location": "Standort", "delivery": "Lieferung: KOSTENLOS", "payment": "Zahlung: Barzahlung bei Übergabe", "warning": "Bitte bezahle nichts, bevor du dein Produkt erhalten hast."},
    "tr": {"selected": "Seçilenler", "total": "Toplam", "continue": "Devam", "brand": "Marka", "brand_ok": "Marka", "received": "Alındı", "not_shared": "Paylaşılmadı", "empty": "Lütfen en az bir ürün seçin.", "summary": "SİPARİŞ ÖZETİ", "products": "Ürünler", "total_price": "Toplam fiyat", "address": "Adres / Bölge", "location": "Konum", "delivery": "Teslimat: ÜCRETSİZ", "payment": "Ödeme: Teslimatta nakit", "warning": "Ürününüzü teslim almadan ödeme yapmayın."},
    "es": {"selected": "Seleccionado", "total": "Total", "continue": "Continuar", "brand": "Marca", "brand_ok": "Marca", "received": "Recibida", "not_shared": "No compartida", "empty": "Selecciona al menos un producto.", "summary": "RESUMEN DEL PEDIDO", "products": "Productos", "total_price": "Precio total", "address": "Dirección / Zona", "location": "Ubicación", "delivery": "Entrega: GRATIS", "payment": "Pago: En efectivo al recibir", "warning": "No pagues antes de recibir el producto."},
    "it": {"selected": "Selezionato", "total": "Totale", "continue": "Continua", "brand": "Marca", "brand_ok": "Marca", "received": "Ricevuta", "not_shared": "Non condivisa", "empty": "Seleziona almeno un prodotto.", "summary": "RIEPILOGO ORDINE", "products": "Prodotti", "total_price": "Prezzo totale", "address": "Indirizzo / Zona", "location": "Posizione", "delivery": "Consegna: GRATUITA", "payment": "Pagamento: Contanti alla consegna", "warning": "Non pagare prima di ricevere il prodotto."},
    "ru": {"selected": "Выбрано", "total": "Итого", "continue": "Продолжить", "brand": "Марка", "brand_ok": "Марка", "received": "Получена", "not_shared": "Не отправлена", "empty": "Выберите хотя бы один товар.", "summary": "СВОДКА ЗАКАЗА", "products": "Товары", "total_price": "Итоговая цена", "address": "Адрес / Район", "location": "Геолокация", "delivery": "Доставка: БЕСПЛАТНО", "payment": "Оплата: Наличными при получении", "warning": "Не платите до получения товара."},
    "pl": {"selected": "Wybrano", "total": "Razem", "continue": "Dalej", "brand": "Marka", "brand_ok": "Marka", "received": "Otrzymana", "not_shared": "Nieudostępniona", "empty": "Wybierz co najmniej jeden produkt.", "summary": "PODSUMOWANIE ZAMÓWIENIA", "products": "Produkty", "total_price": "Cena łączna", "address": "Adres / Rejon", "location": "Lokalizacja", "delivery": "Dostawa: BEZPŁATNA", "payment": "Płatność: Gotówką przy odbiorze", "warning": "Nie płać przed otrzymaniem produktu."},
    "fr": {"selected": "Sélectionné", "total": "Total", "continue": "Continuer", "brand": "Marque", "brand_ok": "Marque", "received": "Reçue", "not_shared": "Non partagée", "empty": "Sélectionnez au moins un produit.", "summary": "RÉSUMÉ DE LA COMMANDE", "products": "Produits", "total_price": "Prix total", "address": "Adresse / Quartier", "location": "Position", "delivery": "Livraison : GRATUITE", "payment": "Paiement : En espèces à la livraison", "warning": "Ne payez pas avant de recevoir le produit."},
}


# =========================================================
# YARDIMCI FONKSİYONLAR
# =========================================================

def get_lang(context):
    lang = context.user_data.get("lang", "en")
    return lang if lang in TEXTS else "en"


def reset_order(context):
    lang = context.user_data.get("lang")

    context.user_data.clear()

    if lang:
        context.user_data["lang"] = lang


def support_keyboard(lang):
    buttons = []

    if SUPPORT_USERNAME:
        buttons.append([
            InlineKeyboardButton(
                TEXTS[lang]["support_button"],
                url=f"https://t.me/{SUPPORT_USERNAME}"
            )
        ])

    return buttons


def language_keyboard():
    return [
        [
            InlineKeyboardButton(label, callback_data=f"lang_{code}")
            for code, label in LANGUAGE_OPTIONS[index:index + 2]
        ]
        for index in range(0, len(LANGUAGE_OPTIONS), 2)
    ]


def quantity_text(lang, product, quantity):
    if product.get("grams_per_unit"):
        grams = quantity * product["grams_per_unit"]
        return f"{quantity}x ({grams} g)"

    unit = product.get("unit", "g")
    return f"{quantity} {unit}"


def cart_lines(lang, cart, brand=None):
    lines = []
    for product_key, quantity in cart.items():
        product = PRODUCTS[product_key]
        price = product["prices"][quantity]
        amount = quantity_text(lang, product, quantity)
        lines.append(f"{product[lang]} — {amount} = {price} €")

    if brand and cart:
        brand_label = UI_TEXT[lang]["brand"]
        lines.append(f"🏷️ {brand_label}: {brand}")
    return lines


def cart_total(cart):
    return sum(
        PRODUCTS[product_key]["prices"][quantity]
        for product_key, quantity in cart.items()
    )


def selection_text(lang, cart):
    text = TEXTS[lang]["product"]
    if not cart:
        return text

    selected_title = f"✅ {UI_TEXT[lang]['selected']}:"
    total_label = UI_TEXT[lang]["total"]
    return (
        f"{text}\n\n{selected_title}\n"
        + "\n".join(cart_lines(lang, cart))
        + f"\n\n💶 {total_label}: {cart_total(cart)} €"
    )


def selection_keyboard(lang, cart):
    keyboard = []
    for product_key, product in PRODUCTS.items():
        keyboard.append([
            InlineKeyboardButton(product[lang], callback_data="selection_info")
        ])
        option_row = []
        for quantity, price in product["prices"].items():
            selected = cart.get(product_key) == quantity
            prefix = "✅ " if selected else ""
            amount = quantity_text(lang, product, quantity)
            option_row.append(InlineKeyboardButton(
                f"{prefix}{amount} = {price} €",
                callback_data=f"pick_{product_key}_{quantity}"
            ))
            if len(option_row) == 2:
                keyboard.append(option_row)
                option_row = []
        if option_row:
            keyboard.append(option_row)

    continue_text = f"➡️ {UI_TEXT[lang]['continue']}"
    keyboard.append([
        InlineKeyboardButton(continue_text, callback_data="cart_continue")
    ])
    return keyboard


async def show_main_menu(message, context):
    lang = get_lang(context)

    keyboard = [
        [
            InlineKeyboardButton(
                TEXTS[lang]["order_button"],
                callback_data="new_order"
            )
        ]
    ]

    keyboard.extend(support_keyboard(lang))

    await message.reply_text(
        TEXTS[lang]["welcome"],
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def show_summary(update, context):
    lang = get_lang(context)

    cart = context.user_data.get("cart", {})
    order_lines = "\n".join(
        cart_lines(lang, cart, context.user_data.get("brand"))
    ) or "-"
    price = cart_total(cart)
    address = context.user_data.get("address", "-")

    latitude = context.user_data.get("latitude")
    longitude = context.user_data.get("longitude")

    ui = UI_TEXT[lang]
    location_status = (
        f"✅ {ui['received']}" if latitude and longitude
        else f"➖ {ui['not_shared']}"
    )
    summary = (
        f"🧾 {ui['summary']}\n\n"
        f"🛍 {ui['products']}:\n{order_lines}\n"
        f"💶 {ui['total_price']}: {price} €\n"
        f"📍 {ui['address']}: {address}\n"
        f"🗺 {ui['location']}: {location_status}\n\n"
        f"🚗 {ui['delivery']}\n"
        f"💵 {ui['payment']}\n\n"
        f"⚠️ {ui['warning']}"
    )

    keyboard = [
        [
            InlineKeyboardButton(
                TEXTS[lang]["confirm"],
                callback_data="confirm_order"
            )
        ],
        [
            InlineKeyboardButton(
                TEXTS[lang]["change"],
                callback_data="change_order"
            )
        ],
        [
            InlineKeyboardButton(
                TEXTS[lang]["cancel"],
                callback_data="cancel_order"
            )
        ]
    ]

    await update.effective_message.reply_text(
        summary,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    context.user_data["state"] = "summary"


# =========================================================
# /START
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    keyboard = [
        [
            InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"),
            InlineKeyboardButton("🇩🇪 Deutsch", callback_data="lang_de"),
        ]
    ]

    keyboard = language_keyboard()

    await update.message.reply_text(
        "🌍 Choose your language / Sprache auswählen",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def join_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    request = update.chat_join_request

    if request is None or request.chat.id != PINKPANTHER_GROUP_ID:
        return

    keyboard = [
        [
            InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"),
            InlineKeyboardButton("🇩🇪 Deutsch", callback_data="lang_de"),
        ]
    ]

    keyboard = language_keyboard()

    try:
        # Telegram bu özel sohbet kimliğini katılma isteğiyle birlikte verir.
        # Böylece kullanıcı daha önce /start yazmamış olsa da mesaj gönderilebilir.
        await context.bot.send_message(
            chat_id=request.user_chat_id,
            text="🌍 Choose your language / Sprache auswählen",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    except Exception as error:
        print("Katılma isteğine özel mesaj gönderilemedi:", error)

    # Özel mesaj başarısız olsa bile katılım onayı ayrıca çalışır.
    try:
        await context.bot.approve_chat_join_request(
            chat_id=request.chat.id,
            user_id=request.from_user.id
        )
    except Exception as error:
        print("Katılma isteği otomatik onaylanamadı:", error)


async def select_language(query, context, lang):
    context.user_data.clear()
    context.user_data["lang"] = lang

    await query.edit_message_text(TEXTS[lang]["language_selected"])

    await show_main_menu(query.message, context)



# =========================================================
# BUTONLAR
# =========================================================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data


    # -------------------------
    # DİL SEÇİMİ
    # -------------------------

    if data.startswith("lang_"):
        selected_lang = data.removeprefix("lang_")
        if selected_lang in TEXTS:
            await select_language(query, context, selected_lang)
        return


    lang = get_lang(context)


    # -------------------------
    # YENİ SİPARİŞ
    # -------------------------

    if data == "new_order":
        reset_order(context)

        context.user_data["state"] = "product_selection"
        context.user_data["cart"] = {}

        try:
            with open(MENU_IMAGE_PATH, "rb") as menu_image:
                await context.bot.send_photo(
                    chat_id=query.message.chat.id,
                    photo=menu_image,
                )
        except Exception as error:
            print("Menü resmi gönderilemedi:", error)

        await query.message.reply_text(
            selection_text(lang, {}),
            reply_markup=InlineKeyboardMarkup(selection_keyboard(lang, {}))
        )
        return


    if data == "selection_info":
        return


    if data.startswith("pick_"):
        _, product_key, quantity_text = data.split("_", 2)
        quantity = float(quantity_text) if "." in quantity_text else int(quantity_text)
        if (
            product_key not in PRODUCTS
            or quantity not in PRODUCTS[product_key]["prices"]
        ):
            return

        cart = context.user_data.setdefault("cart", {})
        cart[product_key] = quantity

        await query.edit_message_text(
            selection_text(lang, cart),
            reply_markup=InlineKeyboardMarkup(selection_keyboard(lang, cart))
        )
        return


    if data == "cart_continue":
        cart = context.user_data.get("cart", {})
        if not cart:
            warning = f"⚠️ {UI_TEXT[lang]['empty']}"
            await query.edit_message_text(
                f"{selection_text(lang, cart)}\n\n{warning}",
                reply_markup=InlineKeyboardMarkup(selection_keyboard(lang, cart))
            )
            return

        context.user_data["state"] = "brand_entry"
        await query.edit_message_reply_markup(reply_markup=None)
        user_mention = query.from_user.mention_html()
        await query.message.reply_text(
            f"{user_mention}\n{TEXTS[lang]['brand_prompt']}",
            parse_mode="HTML",
            reply_markup=ForceReply(
                selective=True,
                input_field_placeholder=UI_TEXT[lang]["brand"],
            ),
        )
        return


    # -------------------------
    # SİPARİŞİ ONAYLA
    # -------------------------

    if data == "confirm_order":

        cart = context.user_data.get("cart", {})
        order_lines = "\n".join(
            cart_lines("en", cart, context.user_data.get("brand"))
        ) or "-"
        price = cart_total(cart)
        address = context.user_data.get("address", "-")

        latitude = context.user_data.get("latitude")
        longitude = context.user_data.get("longitude")

        user = query.from_user

        # Keep seller detection separate from the existing order state machine.
        record_order(user)

        username = f"@{user.username}" if user.username else "No username"

        customer_name = user.full_name or "Unknown"

        if latitude and longitude:
            maps_link = f"https://maps.google.com/?q={latitude},{longitude}"
            location_text = f"✅ {latitude}, {longitude}\n{maps_link}"
        else:
            location_text = "❌ Konum gönderilmedi"

        admin_message = (
            "🚨 YENİ SİPARİŞ 🚨\n\n"
            f"👤 Müşteri: {customer_name}\n"
            f"📱 Telegram: {username}\n"
            f"🆔 Kullanıcı ID: {user.id}\n"
            f"🌍 Dil: {ADMIN_LANGUAGE_NAMES.get(lang, lang)}\n\n"
            f"🛍 Ürünler:\n{order_lines}\n"
            f"💶 Toplam fiyat: {price} €\n"
            f"🏠 Adres / Bölge: {address}\n\n"
            f"📍 Konum:\n{location_text}\n\n"
            "🚗 Teslimat: Ücretsiz\n"
            "💵 Ödeme: Teslimatta nakit"
        )

        if ORDER_CHAT_ID:
            try:
                await context.bot.send_message(
                    chat_id=ORDER_CHAT_ID,
                    text=admin_message,
                    disable_web_page_preview=True
                )

                if latitude and longitude:
                    await context.bot.send_location(
                        chat_id=ORDER_CHAT_ID,
                        latitude=latitude,
                        longitude=longitude
                    )

            except Exception as e:
                print("Sipariş grubuna gönderme hatası:", e)

        else:
            print("ORDER_CHAT_ID ayarlanmamış.")
            print(admin_message)

        await query.edit_message_reply_markup(reply_markup=None)

        await query.message.reply_text(
            TEXTS[lang]["success"],
            reply_markup=ReplyKeyboardRemove()
        )

        reset_order(context)

        return


    # -------------------------
    # BİLGİLERİ DEĞİŞTİR
    # -------------------------

    if data == "change_order":
        reset_order(context)

        context.user_data["state"] = "product_selection"
        context.user_data["cart"] = {}

        await query.edit_message_text(
            selection_text(lang, {}),
            reply_markup=InlineKeyboardMarkup(selection_keyboard(lang, {}))
        )

        return


    # -------------------------
    # SİPARİŞİ İPTAL ET
    # -------------------------

    if data == "cancel_order":
        await query.edit_message_reply_markup(reply_markup=None)

        await query.message.reply_text(
            TEXTS[lang]["cancelled"],
            reply_markup=ReplyKeyboardRemove()
        )

        reset_order(context)

        return


    # -------------------------
    # KONUM OLMADAN DEVAM
    # -------------------------

    if data == "skip_location":
        await query.edit_message_reply_markup(reply_markup=None)

        await show_summary(update, context)

        return


# =========================================================
# YAZILI MESAJLAR
# =========================================================

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get("state")

    if not state:
        return

    lang = get_lang(context)

    text = update.message.text.strip()

    if state == "location":
        if text == TEXTS[lang]["skip_location"]:
            await update.message.reply_text(
                TEXTS[lang].get(
                    "location_skipped",
                    TEXTS[lang]["skip_location"],
                ),
                reply_markup=ReplyKeyboardRemove(),
            )
            await show_summary(update, context)
        return


    # -------------------------
    # MARKA (YAZILI MESAJ)
    # -------------------------

    if state == "brand_entry":
        context.user_data["brand"] = text
        context.user_data["state"] = "address"

        brand_label = UI_TEXT[lang]["brand_ok"]
        await update.message.reply_text(
            f"✅ {brand_label}: {text}\n\n{TEXTS[lang]['address']}",
            reply_markup=ForceReply(
                selective=True,
                input_field_placeholder=UI_TEXT[lang]["address"],
            ),
        )
        return


    # -------------------------
    # ADRES / BÖLGE
    # -------------------------

    if state == "address":

        context.user_data["address"] = text
        context.user_data["state"] = "location"

        location_keyboard = ReplyKeyboardMarkup(
            [
                [
                    KeyboardButton(
                        TEXTS[lang]["share_location"],
                        request_location=True,
                    )
                ],
                [KeyboardButton(TEXTS[lang]["skip_location"])],
            ],
            resize_keyboard=True,
            one_time_keyboard=True,
        )

        await update.message.reply_text(
            TEXTS[lang]["location_question"],
            reply_markup=location_keyboard,
        )

        return


# =========================================================
# KONUM MESAJI
# =========================================================
async def show_id(update, context):
    await update.message.reply_text(f"Bu grubun ID'si: {update.effective_chat.id}")
async def location_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    state = context.user_data.get("state")

    if state != "location":
        return

    lang = get_lang(context)

    location = update.message.location

    context.user_data["latitude"] = location.latitude
    context.user_data["longitude"] = location.longitude

    await update.message.reply_text(
        TEXTS[lang]["location_received"],
        reply_markup=ReplyKeyboardRemove()
    )

    await show_summary(update, context)


# =========================================================
# ANA PROGRAM
# =========================================================

def main():

    if not TOKEN:
        raise RuntimeError("BOT_TOKEN bulunamadı!")

    if not ORDER_CHAT_ID:
        raise RuntimeError("ORDER_CHAT_ID bulunamadı!")

    if not VENDOR_ALERT_CHAT_ID:
        print(
            "VENDOR_ALERT_CHAT_ID ayarlanmamış: üye kayıtları ve puanlama "
            "çalışır, ancak satıcı uyarısı hiçbir gruba gönderilmez."
        )

    init_vendor_db()
    app = Application.builder().token(TOKEN).build()

    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        ChatJoinRequestHandler(
            join_request,
            chat_id=PINKPANTHER_GROUP_ID
        )
    )

    app.add_handler(
        ChatMemberHandler(chat_member_update, ChatMemberHandler.CHAT_MEMBER)
    )

    if app.job_queue:
        app.job_queue.run_repeating(
            scan_vendor_candidates,
            interval=VENDOR_SCAN_INTERVAL,
            first=10,
            name="vendor-candidate-scan",
        )

    app.add_handler(
        CallbackQueryHandler(button_handler)
    )

    app.add_handler(
        MessageHandler(
            filters.LOCATION,
            location_handler
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            text_handler
        )
    )

    print("GreenPantherBot çalışıyor...")
    app.add_handler(CommandHandler("id", show_id))
    app.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()
