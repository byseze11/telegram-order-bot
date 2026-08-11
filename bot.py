import os
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    Application,
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

# BUNLARI SONRA BİRLİKTE AYARLAYACAĞIZ
# Siparişlerin geleceği özel Telegram grubunun ID'si
ORDER_CHAT_ID = os.getenv("ORDER_CHAT_ID")

# Canlı destek için Telegram kullanıcı adın
# @ işareti OLMADAN yazılacak. Örnek: PinkPantherSupport
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "")


# =========================================================
# METİNLER
# =========================================================

TEXTS = {
    "en": {
        "language_selected": "🇬🇧 English selected.",

        "welcome": (
            "⚠️ IMPORTANT – PLEASE READ CAREFULLY\n\n"
            "🐾 Welcome to PinkPanther Bot\n\n"
            "Hello! I’m PinkPanther Bot. I’m here to help you place your order "
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
            "🛍 Please enter the product name or product code.\n\n"
            "Example: PP-104"
        ),

        "quantity": (
            "🔢 How many would you like to order?\n\n"
            "Please enter the quantity."
        ),

        "address": (
            "📍 DELIVERY INFORMATION\n\n"
            "Please send your full delivery address and postal code together.\n\n"
            "Example:\n"
            "Musterstraße 12, 12345 Berlin\n\n"
            "ℹ️ NOTE:\n"
            "If you don’t know your full address or postal code, simply enter "
            "the area or district you are in.\n\n"
            "You can also share your exact location directly through Telegram "
            "using the 📍 Share Location button.\n\n"
            "If you need help, you can continue through 🆘 Live Support."
        ),

        "share_location": "📍 Share Location",
        "skip_location": "➡️ Continue Without Location",

        "location_question": (
            "📍 If you want, you can now share your exact location.\n\n"
            "This helps us find the delivery point more easily.\n\n"
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
            "⚠️ Please enter a valid quantity.\n"
            "Example: 1"
        ),
    },

    "de": {
        "language_selected": "🇩🇪 Deutsch ausgewählt.",

        "welcome": (
            "⚠️ WICHTIG – BITTE SORGFÄLTIG LESEN\n\n"
            "🐾 Willkommen beim PinkPanther Bot\n\n"
            "Hallo! Ich bin der PinkPanther Bot. Ich bin hier, um dir dabei zu helfen, "
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
            "🛍 Bitte gib den Produktnamen oder den Produktcode ein.\n\n"
            "Beispiel: PP-104"
        ),

        "quantity": (
            "🔢 Wie viele Stück möchtest du bestellen?\n\n"
            "Bitte gib die gewünschte Menge ein."
        ),

        "address": (
            "📍 LIEFERINFORMATIONEN\n\n"
            "Bitte sende deine vollständige Lieferadresse und Postleitzahl zusammen.\n\n"
            "Beispiel:\n"
            "Musterstraße 12, 12345 Berlin\n\n"
            "ℹ️ HINWEIS:\n"
            "Wenn du deine vollständige Adresse oder Postleitzahl nicht kennst, "
            "gib einfach den Stadtteil oder die Gegend an, in der du dich befindest.\n\n"
            "Du kannst deinen genauen Standort auch direkt über Telegram mit der "
            "Schaltfläche 📍 Standort senden teilen.\n\n"
            "Falls du Hilfe benötigst, kannst du über den 🆘 Live-Support fortfahren."
        ),

        "share_location": "📍 Standort senden",
        "skip_location": "➡️ Ohne Standort fortfahren",

        "location_question": (
            "📍 Wenn du möchtest, kannst du jetzt deinen genauen Standort senden.\n\n"
            "So können wir den Lieferort leichter finden.\n\n"
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
            "⚠️ Bitte gib eine gültige Menge ein.\n"
            "Beispiel: 1"
        ),
    }
}


# =========================================================
# YARDIMCI FONKSİYONLAR
# =========================================================

def get_lang(context):
    return context.user_data.get("lang", "en")


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

    product = context.user_data.get("product", "-")
    quantity = context.user_data.get("quantity", "-")
    address = context.user_data.get("address", "-")

    latitude = context.user_data.get("latitude")
    longitude = context.user_data.get("longitude")

    if latitude and longitude:
        location_status = "✅ Received" if lang == "en" else "✅ Erhalten"
    else:
        location_status = "➖ Not shared" if lang == "en" else "➖ Nicht gesendet"

    if lang == "en":
        summary = (
            "🧾 ORDER SUMMARY\n\n"
            f"🛍 Product: {product}\n"
            f"🔢 Quantity: {quantity}\n"
            f"📍 Address / Area: {address}\n"
            f"🗺 Location: {location_status}\n\n"
            "🚗 Delivery: FREE\n"
            "💵 Payment: Cash on delivery\n\n"
            "⚠️ Do not make any payment before receiving your product."
        )
    else:
        summary = (
            "🧾 BESTELLÜBERSICHT\n\n"
            f"🛍 Produkt: {product}\n"
            f"🔢 Menge: {quantity}\n"
            f"📍 Adresse / Gebiet: {address}\n"
            f"🗺 Standort: {location_status}\n\n"
            "🚗 Lieferung: KOSTENLOS\n"
            "💵 Zahlung: Barzahlung bei Übergabe\n\n"
            "⚠️ Bitte bezahle nichts, bevor du dein Produkt erhalten hast."
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

    await update.message.reply_text(
        "🌍 Choose your language / Sprache auswählen",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


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

    if data == "lang_en":
        context.user_data.clear()
        context.user_data["lang"] = "en"

        await query.edit_message_text("🇬🇧 English selected.")
        await show_main_menu(query.message, context)
        return


    if data == "lang_de":
        context.user_data.clear()
        context.user_data["lang"] = "de"

        await query.edit_message_text("🇩🇪 Deutsch ausgewählt.")
        await show_main_menu(query.message, context)
        return


    lang = get_lang(context)


    # -------------------------
    # YENİ SİPARİŞ
    # -------------------------

    if data == "new_order":
        reset_order(context)

        context.user_data["state"] = "product"

        await query.message.reply_text(
            TEXTS[lang]["product"],
            reply_markup=ReplyKeyboardRemove()
        )
        return


    # -------------------------
    # SİPARİŞİ ONAYLA
    # -------------------------

    if data == "confirm_order":

        product = context.user_data.get("product", "-")
        quantity = context.user_data.get("quantity", "-")
        address = context.user_data.get("address", "-")

        latitude = context.user_data.get("latitude")
        longitude = context.user_data.get("longitude")

        user = query.from_user

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
            f"🌍 Dil: {'İngilizce' if lang == 'en' else 'Almanca'}\n\n"
            f"🛍 Ürün: {product}\n"
            f"🔢 Miktar: {quantity}\n"
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

        context.user_data["state"] = "product"

        await query.message.reply_text(
            TEXTS[lang]["restart"],
            reply_markup=ReplyKeyboardRemove()
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


    # -------------------------
    # ÜRÜN
    # -------------------------

    if state == "product":

        context.user_data["product"] = text
        context.user_data["state"] = "quantity"

        await update.message.reply_text(
            TEXTS[lang]["quantity"]
        )

        return


    # -------------------------
    # MİKTAR
    # -------------------------

    if state == "quantity":

        clean_quantity = text.replace(" ", "")

        if not clean_quantity.isdigit():
            await update.message.reply_text(
                TEXTS[lang]["invalid_quantity"]
            )
            return

        quantity = int(clean_quantity)

        if quantity <= 0:
            await update.message.reply_text(
                TEXTS[lang]["invalid_quantity"]
            )
            return

        context.user_data["quantity"] = quantity
        context.user_data["state"] = "address"

        support_buttons = support_keyboard(lang)

        if support_buttons:
            await update.message.reply_text(
                TEXTS[lang]["address"],
                reply_markup=InlineKeyboardMarkup(support_buttons)
            )
        else:
            await update.message.reply_text(
                TEXTS[lang]["address"]
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
                        request_location=True
                    )
                ]
            ],
            resize_keyboard=True,
            one_time_keyboard=True
        )

        await update.message.reply_text(
            TEXTS[lang]["location_question"],
            reply_markup=location_keyboard
        )

        skip_keyboard = [
            [
                InlineKeyboardButton(
                    TEXTS[lang]["skip_location"],
                    callback_data="skip_location"
                )
            ]
        ]

        skip_keyboard.extend(support_keyboard(lang))

        await update.message.reply_text(
            "👇",
            reply_markup=InlineKeyboardMarkup(skip_keyboard)
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

    app = Application.builder().token(TOKEN).build()

    app.add_handler(
        CommandHandler("start", start)
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

    print("PinkPanther Bot çalışıyor...")
app.add_handler(CommandHandler("id", show_id))
    app.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()
