# 🚀 SMM Автоматизатор — "НейроСофт Гейминг"

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111.0+-green.svg?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Gemini](https://img.shields.io/badge/Gemini_API-Lite_Enabled-orange.svg?style=for-the-badge&logo=google&logoColor=white)](https://ai.google.dev)
[![License](https://img.shields.io/badge/License-MIT-purple.svg?style=for-the-badge)](LICENSE)

Полностью автономный ИИ-редактор и автопубликатор для Telegram-каналов гик, IT и гейминг тематики. Проект собирает новости из популярных источников, оценивает их актуальность, адаптирует контент под ваш стиль с помощью ИИ, автоматически очищает текст от раздражающих ИИ-штампов (ИИ-слопа) по 30 уникальным правилам и мгновенно публикует в ваш канал с красивой сгенерированной обложкой.

---

## 🔥 Ключевые фичи

1. **Многоканальный сбор (Scraping)**: Парсинг HackerNews (Algolia Search), Dev.to, Steam News, GamersNexus (RSS) и GitHub Trending.
2. **Умное ранжирование (AI Scorer)**: Автоматическая оценка новостей от 0 до 100 баллов на основе соответствия тематике, свежести, вирусности и качества.
3. **Очистка от ИИ-клише (Pass 2: Humanizer)**: Уникальный текстовый фильтр, исправляющий 30 признаков "роботизированного" текста (*"следует отметить"*, *"в современную эпоху..."*, *"delve"*, избыточный пассивный залог и т.д.).
4. **Умное форматирование в Telegram**: Автоматическое создание красивых жирных заголовков, выделений и раскрывающихся (collapsible) цитат (`<blockquote expandable>`), которые гарантированно парсятся и не ломают отправку.
5. **Динамические плагины-парсеры**: Модульная архитектура! Вы можете расширить функционал, просто добавив новый парсер в папку `plugins/scrapers/`.
6. **Кастомизируемые темы оформления**: Настройки цветов, водяных знаков и стилей для автогенератора обложек вынесены в YAML-темы (`themes/default.yaml`).
7. **Панель модерации & Управление через Bot**: Веб-интерфейс FastAPI и Telegram-бот для согласования постов в один клик.
8. **Адаптация под лимиты API**: Умный клиент Gemini с экспоненциальной задержкой (RPM) и автоматическим переключением (fallback) на альтернативные бесплатные модели при исчерпании суточной квоты.

---

## 🚀 Быстрый запуск в 1 клик

Вы можете мгновенно развернуть SMM Автоматизатор на платформе Render:

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)

*(Вам нужно будет указать переменные окружения `GEMINI_API_KEY`, `TELEGRAM_BOT_TOKEN` и `TELEGRAM_CHANNEL_ID` в панели управления Render).*

---

## 💻 Локальная установка для новичков

### Шаг 1: Клонирование и установка зависимостей
```bash
git clone https://github.com/UmarUsmomi/SMM-chik.git
cd SMM-chik
pip install -r requirements.txt
```

### Шаг 2: Настройка конфигурации
Создайте файл `.env` в корневой папке проекта:
```ini
GEMINI_API_KEY="ваш_ключ_gemini_api"
TELEGRAM_BOT_TOKEN="токен_вашего_телеграм_бота"
TELEGRAM_CHANNEL_ID="-100xxxxxxxxx" # ID вашего канала
```
> 💡 **Как получить ключи?**
> - **Gemini API Key**: Получите бесплатно в [Google AI Studio](https://aistudio.google.com/).
> - **Telegram Bot Token**: Создайте бота через `@BotFather` в Telegram.
> - **Telegram Channel ID**: Добавьте созданного бота в администраторы вашего канала и перешлите любой пост из канала боту `@ShowJsonBot` или узнайте ID через веб-клиент.

### Шаг 3: Запуск проекта
Запустите веб-сервер и панель управления:
```bash
uvicorn bot.app:app --host 0.0.0.0 --port 10000
```
Откройте браузер по адресу: `http://localhost:10000` для просмотра дашборда управления.

---

## 🧩 Модульная архитектура (Как вносить свой вклад)

### 1. Создание плагина-парсера (Scrapers)
Все новые парсеры автоматически импортируются из папки `plugins/scrapers/`. Для создания собственного парсера напишите простой файл:

`plugins/scrapers/my_cool_source.py`:
```python
from smm_engine.scrapers.base import BaseScraper, NewsItem

class MyCoolScraper(BaseScraper):
    async def scrape(self):
        # Напишите вашу логику сбора данных (например, httpx.get)
        # Верните список объектов NewsItem
        return [
            NewsItem(
                source="my_cool_source",
                source_id="unique_id_123",
                title="Супер новость из нового источника!",
                url="https://example.com/news",
                raw_data={"tags": ["it", "future"]}
            )
        ]
```
Включить или настроить его можно в `config/sources.yaml`:
```yaml
sources:
  my_cool_source:
    enabled: true
    limit: 5
```

### 2. Изменение темы оформления обложек
Все цвета и стили генерируемых обложек для постов настраиваются в файле `themes/default.yaml`. Пример настройки:
```yaml
colors:
  background_fallback: [13, 15, 20, 255] # RGBA цвет заливки
  brand_accent: [217, 4, 41, 255] # Основной акцентный цвет (HEX-красный)
  text_primary: [255, 255, 255, 255]

watermark:
  text_parts:
    - text: "/ игры "
      color_type: "primary"
    - text: "⚡"
      color_type: "accent"
```

---

## 🧪 Запуск тестов
Чтобы убедиться, что все функции работают стабильно, запустите:
```bash
python -m pytest
```

---

## 📄 Лицензия
Проект распространяется под свободной лицензией MIT. Будем рады вашим Pull Request и звездам ⭐️ на GitHub!
