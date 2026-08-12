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

# Kıyafet çeşitleri ve her çeşidin adet -> toplam fiyat (€) listesi
PRODUCTS = {
    "leaf": {
        "en": "🍃 Leaf",
        "prices": {5: 50, 10: 100, 15: 130, 25: 190},
    },
    "snow": {
        "en": "❄️ Snow",
        "prices": {0.5: 50, 1: 100, 2: 150, 5: 300},
    },
    "chocolate": {
        "en": "🍫 Chocolate",
        "prices": {5: 50, 10: 100, 15: 130, 25: 190},
    },
}


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
            "🛍 CLOTHING CATALOG\n\n"
            "🍃 Leaf Print T-Shirt\n"
            "❄️ Snow Print Sweatshirt\n"
            "🍫 Chocolate Print Hoodie\n\n"
            "Select one or more products and quantities below.\n"
            "Then press Continue."
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
            "⚠️ Minimum order is 5 pieces.\n"
            "Please enter one of these quantities: 5, 10, 15 or 25."
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
            "🛍 KLEIDUNGSKATALOG\n\n"
            "🍃 T-Shirt mit Blattmotiv\n"
            "❄️ Sweatshirt mit Schneemotiv\n"
            "🍫 Hoodie mit Schokoladenmotiv\n\n"
            "Wähle unten ein oder mehrere Produkte und Mengen aus.\n"
            "Drücke anschließend auf Weiter."
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
            "⚠️ Die Mindestbestellmenge beträgt 5 Stück.\n"
            "Bitte gib eine dieser Mengen ein: 5, 10, 15 oder 25."
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


def cart_lines(lang, cart):
    lines = []
    for product_key, quantity in cart.items():
        product = PRODUCTS[product_key]
        price = product["prices"][quantity]
        lines.append(f"{product[lang]} — {quantity} = {price} €")
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

    selected_title = "✅ Selected:" if lang == "en" else "✅ Ausgewählt:"
    total_label = "Total" if lang == "en" else "Gesamt"
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
            option_row.append(InlineKeyboardButton(
                f"{prefix}{quantity} = {price} €",
                callback_data=f"pick_{product_key}_{quantity}"
            ))
            if len(option_row) == 2:
                keyboard.append(option_row)
                option_row = []
        if option_row:
            keyboard.append(option_row)

    continue_text = "➡️ Continue" if lang == "en" else "➡️ Weiter"
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
    order_lines = "\n".join(cart_lines(lang, cart)) or "-"
    price = cart_total(cart)
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
            f"🛍 Products:\n{order_lines}\n"
            f"💶 Total price: {price} €\n"
            f"📍 Address / Area: {address}\n"
            f"🗺 Location: {location_status}\n\n"
            "🚗 Delivery: FREE\n"
            "💵 Payment: Cash on delivery\n\n"
            "⚠️ Do not make any payment before receiving your product."
        )
    else:
        summary = (
            "🧾 BESTELLÜBERSICHT\n\n"
            f"🛍 Produkte:\n{order_lines}\n"
            f"💶 Gesamtpreis: {price} €\n"
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

    # Katılma isteğiyle açılan geçici özel sohbette Telegram bazen ikinci bir
    # mesajı reddeder. Bu yüzden dil mesajını doğrudan ana menüye çeviriyoruz.
    keyboard = [[
        InlineKeyboardButton(
            TEXTS[lang]["order_button"],
            callback_data="new_order"
        )
    ]]
    keyboard.extend(support_keyboard(lang))

    await query.edit_message_text(
        TEXTS[lang]["welcome"],
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
        await select_language(query, context, "en")
        return


    if data == "lang_de":
        await select_language(query, context, "de")
        return


    lang = get_lang(context)


    # -------------------------
    # YENİ SİPARİŞ
    # -------------------------

    if data == "new_order":
        reset_order(context)

        context.user_data["state"] = "product_selection"
        context.user_data["cart"] = {}

        await query.edit_message_text(
            selection_text(lang, {}),
            reply_markup=InlineKeyboardMarkup(selection_keyboard(lang, {}))
        )
        return


    if data == "selection_info":
        return


    if data.startswith("pick_"):
        _, product_key, quantity_text = data.split("_", 2)
        quantity = int(quantity_text)
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
            warning = (
                "⚠️ Please select at least one product."
                if lang == "en"
                else "⚠️ Bitte wähle mindestens ein Produkt aus."
            )
            await query.edit_message_text(
                f"{selection_text(lang, cart)}\n\n{warning}",
                reply_markup=InlineKeyboardMarkup(selection_keyboard(lang, cart))
            )
            return

        context.user_data["state"] = "address"
        await query.edit_message_text(TEXTS[lang]["address"])
        return


    # -------------------------
    # SİPARİŞİ ONAYLA
    # -------------------------

    if data == "confirm_order":

        cart = context.user_data.get("cart", {})
        order_lines = "\n".join(cart_lines("en", cart)) or "-"
        price = cart_total(cart)
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

    if not ORDER_CHAT_ID:
        raise RuntimeError("ORDER_CHAT_ID bulunamadı!")

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
