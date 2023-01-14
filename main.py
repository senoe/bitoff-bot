import os
import time
from datetime import datetime
from threading import Thread

import httpx
from dotenv import load_dotenv
from pytz import timezone
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler
from telegram_bot_pagination import InlineKeyboardPaginator

from bitoff import Bitoff

load_dotenv()


class Paginator(InlineKeyboardPaginator):
    current_page_label = '· {} ·'


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    await update.message.reply_markdown_v2("⚡️*Bitoff Bot* \- an unofficial bitoff\.io bot"
                                           "\n*Profile • General Information*"
                                           f"\nUser: `@{update.effective_user.username} ({update.effective_user.id})`"
                                           f"\nLinked account: `none`")


def track_offers():
    global recorded_offers
    print("Order tracking started.")
    while True:
        data = bitoff.get_offer_list()
        offer_count = data["shops"][0]["count"]

        recorded_offer_count = len(recorded_offers)
        if recorded_offer_count != offer_count:
            print(f"New offers discovered! {recorded_offer_count} -> {offer_count}")
            previous_offers = recorded_offers
            recorded_offers = data["list"]

            if data["pagination"]["lastPage"] != 1:
                for page in range(2, data["pagination"]["lastPage"] + 1):
                    data = bitoff.get_offer_list(page)
                    recorded_offers.extend(data["list"])

            if len(previous_offers) == 0:
                print(f"Synced existing orders ({len(recorded_offers)}).")
            else:
                # Find new offers
                new_offers = [o for o in recorded_offers if o not in previous_offers]
                for offer in new_offers:
                    print(f"New offer discovered! {offer['order_id']}")
                    data = bitoff.get_offer(offer["order_id"])
                    if not data:
                        continue

                    amount_key = "usdt_amount" if offer["currency"] == "usdt" else "bitcoin_rate"
                    if offer["as_shopper_username"]:
                        shopper = f"`{offer['as_shopper_username']}` \(`{offer['username']}`\)"
                    else:
                        shopper = f"`{offer['username']}`"

                    uk = data['source'] == "united kingdom"
                    message = f"🆕 Offer: *Amazon{'․co․uk' if uk else '․com'}* | `{offer['order_id']}`\n"
                    message += f"• 🛍 Shopper: {shopper}\n"
                    message += f"• 💰 Amount: `{round(offer[amount_key], 8)} {data['currency'].upper()}`\n"
                    if data["currency"] == "btc":
                        message += f"• 📈 Applied Rate: `{data['applied']}`\n"
                    message += f"• 🚚 Fast Release: `{'Yes' if data['fast_release'] else 'No'}`\n"
                    message += f"• 🏷 Price: `${data['total_usd']:.2f}`\n"
                    message += f"• ✂️ Discount: `{data['off']}%`\n"
                    message += f"• 📦 Ship to: `{data['shipping']}`\n"
                    message += f"• 🛒 Products \(*{len(data['products'])}*\):\n"
                    for product in data["products"]:
                        if uk:
                            message += f"[\[view\]]({product['url']}) £{product['origin_price']}: *{product['count']}x* `{product['_id']}`\n"
                        else:
                            title = product["title"]
                            if len(title) > 30:
                                title = (title[:30] + "...").replace("-...", "...").replace(" ...", "...")
                            price = f"{product['price']:.2f}".replace(".", "\.")
                            message += f"[\[view\]](https://amazon.com/dp/{product['id']}) ${price}: *{product['count']}x* `{title}`\n"

                    message = message.replace("-", "\-").replace("|", "\|").replace("!", "\!").replace("_", "\_")
                    httpx.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", params={"parse_mode": "MarkdownV2", "chat_id": tracker_channel_id, "text": message})

        time.sleep(20)


async def get_offer_list_response(page: int = 1):
    data = bitoff.get_offer_list(page)
    offer_count = data["shops"][0]["count"]

    response = "⚡️*Bitoff Bot* - an unofficial bitoff.io bot\n\n"
    response += f"*Earner offers*:\n"

    count = data["pagination"]["current"]
    if count != 1:
        count *= data["pagination"]["perPage"] + 1

    for offer in data["list"]:
        amount_key = "usdt_amount" if offer["currency"] == "usdt" else "bitcoin_rate"
        count_info = f"{'` `' if count < 10 else ''}{count}"
        currency_info = f"{round(offer[amount_key], 8)} {offer['currency'].upper()}"
        discount = f"{'` `' if offer['off'] < 10 else ''}`{offer['off']}%`"
        fast_release = "≡" if offer['fast_release'] else ""

        if offer["as_shopper_username"]:
            shopper = offer["as_shopper_username"]
        else:
            shopper = offer["username"]

        response += f"{count_info}. {discount} 🇺🇸 *${offer['price']:.2f}* `{offer['order_id']}` {fast_release}{currency_info} • {shopper}\n"
        count += 1

    response += f"\n*Offer statistics*:\n"
    response += f"• Total: `{offer_count}` offers\n"
    response += f"• Amazon․com: `{data['shops'][1]['count']}` offers\n"
    response += f"• Amazon․co․uk: `{data['shops'][2]['count']}` offers\n"

    response += "\n*Fast release* offers are indicated by the `≡` symbol."
    response += "\nThe fiat amount represents the *price* of the item(s)."

    date = datetime.now(timezone("America/Los_Angeles"))
    current_time = date.strftime("%Y-%m-%d %H:%M:%S")

    response += f"\nDisplaying page `{data['pagination']['current']}` of `{data['pagination']['lastPage']}`. Last updated @ `{current_time}`"

    response = response \
        .replace(".", "\.").replace("-", "\-").replace("|", "\|").replace("(", "\(").replace(")", "\)") \
        .replace("[", "\[").replace("]", "\]").replace("!", "\!").replace("_", "\_")

    paginator = Paginator(
        page_count=data["pagination"]["lastPage"],
        data_pattern="offers#{page}",
        current_page=page
    )

    return paginator.markup, response


async def offers_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = await update.message.reply_text(text="⌛ Please wait...")
    markup, response = await get_offer_list_response()
    await message.edit_text(text=response, reply_markup=markup, parse_mode=ParseMode.MARKDOWN_V2)


async def offers_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    page = int(query.data.split('#')[1])
    markup, response = await get_offer_list_response(page)
    await query.edit_message_text(text=response, reply_markup=markup, parse_mode=ParseMode.MARKDOWN_V2)
    await query.answer()


if __name__ == "__main__":
    recorded_offers = []
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    tracker_channel_id = os.environ.get("TELEGRAM_TRACKER_CHANNEL_ID")
    bitoff = Bitoff()
    Thread(target=track_offers).start()
    app = ApplicationBuilder().token(bot_token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("offers", offers_command))
    app.add_handler(CallbackQueryHandler(offers_callback, pattern="^offers#"))
    app.run_polling(drop_pending_updates=True)
