import asyncio
import logging
import random
import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# 🔧 Настройки
BOT_TOKEN = "8367673850:AAHOU-v8zuOnlWR2AKMYOyquFWFBygxPADA"
CHECK_INTERVAL = 10  # интервал проверки в минутах

# 📋 Словарь: {user_id: {"url": str, "known_ads": set}}
user_data = {}

# ⚙️ Настройка логов
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# 🕵️‍♂️ Заголовки для имитации браузера
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/129.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
}


# 🧩 Парсер объявлений
def parse_avito_ads(url):
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code == 429:
            logger.warning("❌ Avito вернул ошибку 429 (Too Many Requests) — временная блокировка.")
            return "429"
        if response.status_code != 200:
            logger.warning(f"⚠️ Ошибка {response.status_code} при загрузке страницы.")
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        ads = soup.find_all("div", {"data-marker": "item"})

        results = []
        for ad in ads:
            link_tag = ad.find("a", {"itemprop": "url"})
            if link_tag and "href" in link_tag.attrs:
                href = link_tag["href"]
                if not href.startswith("http"):
                    href = "https://www.avito.ru" + href
                results.append(href)

        return results
    except Exception as e:
        logger.error(f"Ошибка при парсинге: {e}")
        return []


# 🧠 Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет 👋 Я бот для отслеживания объявлений на Avito.\n\n"
        "Отправь мне ссылку на поиск, например:\n"
        "https://www.avito.ru/moskva/avtomobili/bmw-ASgBAgICAUTgtg3klyg\n\n"
        "Я буду присылать новые объявления, которые появятся по этому запросу 🚗"
    )


# 📥 Получение ссылки от пользователя
async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    url = update.message.text.strip()

    if not url.startswith("https://www.avito.ru/"):
        await update.message.reply_text("⚠️ Это не похоже на ссылку с Avito. Пришли корректную ссылку.")
        return

    ads = parse_avito_ads(url)
    if ads == "429":
        await update.message.reply_text(
            "❌ Avito временно ограничил доступ. Подожди 5–10 минут и попробуй снова."
        )
        return

    user_data[user_id] = {"url": url, "known_ads": set(ads)}
    await update.message.reply_text(
        f"✅ Отслеживаю объявления по ссылке:\n{url}\n\nВсего найдено: {len(ads)}"
    )


# 🔁 Проверка обновлений
async def check_avito_ads(context: ContextTypes.DEFAULT_TYPE):
    logger.info("🔍 Проверка новых объявлений...")
    for user_id, data in user_data.items():
        url = data["url"]
        known_ads = data["known_ads"]

        await asyncio.sleep(random.randint(3, 10))  # небольшая задержка
        new_ads = parse_avito_ads(url)

        if new_ads == "429":
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text="⚠️ Avito временно ограничил запросы. Проверка приостановлена на 10 минут.",
                )
            except Exception as e:
                logger.error(f"Ошибка при отправке уведомления 429: {e}")
            continue

        if not new_ads:
            continue

        new_items = [ad for ad in new_ads if ad not in known_ads]
        if new_items:
            data["known_ads"].update(new_items)
            for ad in new_items:
                try:
                    await context.bot.send_message(chat_id=user_id, text=f"🆕 Новое объявление:\n{ad}")
                except Exception as e:
                    logger.error(f"Не удалось отправить сообщение пользователю {user_id}: {e}")


# 🚀 Основная функция
async def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))

    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_avito_ads, "interval", minutes=CHECK_INTERVAL, args=[app])
    scheduler.start()

    logger.info("Бот запущен ✅")
    await app.run_polling()


if __name__ == "__main__":
    import nest_asyncio

    nest_asyncio.apply()
    asyncio.get_event_loop().run_until_complete(main())

