import os
import sys
import urllib.request
import json
import ssl

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header():
    print("==========================================================")
    print("🚀  SMM Автоматизатор — Панель настройки 'НейроСофт Гейминг'")
    print("==========================================================")
    print("Этот скрипт поможет вам настроить ключи доступа в файле .env")
    print("и сразу проверит подключение к API.\n")

def test_telegram(token, channel_id):
    print("⏳ Проверка подключения к Telegram API...")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": channel_id,
        "text": "🛠️ <b>Тестовое сообщение от SMM-автоматизатора!</b>\n\nЕсли вы видите это, значит настройки бота и ID канала верны.",
        "parse_mode": "HTML"
    }
    
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    try:
        req = urllib.request.Request(
            url, 
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'}
        )
        resp = urllib.request.urlopen(req, timeout=10, context=ctx)
        res_data = json.loads(resp.read().decode('utf-8'))
        if res_data.get("ok"):
            print("✅ Подключение к Telegram успешно! Сообщение отправлено.")
            return True
        else:
            print(f"❌ Ошибка Telegram API: {res_data.get('description')}")
            return False
    except Exception as e:
        print(f"❌ Ошибка подключения к Telegram: {e}")
        return False

def test_gemini(api_key):
    print("⏳ Проверка подключения к Gemini API...")
    
    # We can test by calling listModels or generating a tiny response via direct REST API
    # directly using REST is easier and doesn't require importing google-generativeai at setup time
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": "Hello, respond with OK"}]}]
    }
    
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        resp = urllib.request.urlopen(req, timeout=12, context=ctx)
        res_data = json.loads(resp.read().decode('utf-8'))
        
        # Check if we got content back
        candidates = res_data.get("candidates", [])
        if candidates:
            print("✅ Подключение к Gemini API успешно!")
            return True
        else:
            print(f"❌ Ошибка: Неверный формат ответа от Gemini: {res_data}")
            return False
    except Exception as e:
        print(f"❌ Ошибка подключения к Gemini API: {e}")
        print("Подсказка: проверьте правильность ключа и отсутствие блокировок IP.")
        return False

def main():
    clear_screen()
    print_header()
    
    # Check if .env already exists
    env_exists = os.path.exists(".env")
    if env_exists:
        confirm = input("⚠️ Файл .env уже существует. Перезаписать его? (y/n): ").strip().lower()
        if confirm != 'y':
            print("Настройка отменена.")
            sys.exit(0)
            
    # Input variables
    gemini_key = input("🔑 Введите ваш GEMINI_API_KEY: ").strip().strip("'\"")
    while not gemini_key:
        gemini_key = input("❌ Ключ не может быть пустым. Введите GEMINI_API_KEY: ").strip().strip("'\"")
        
    bot_token = input("🤖 Введите токен Telegram-бота (TELEGRAM_BOT_TOKEN): ").strip().strip("'\"")
    while not bot_token:
        bot_token = input("❌ Токен не может быть пустым. Введите токен бота: ").strip().strip("'\"")
        
    channel_id = input("📢 Введите ID канала или username (TELEGRAM_CHANNEL_ID): ").strip().strip("'\"")
    while not channel_id:
        channel_id = input("❌ ID канала не может быть пустым. Введите ID канала: ").strip().strip("'\"")
        
    theme = input("🎨 Выберите тему оформления (default / dracula / cyberpunk) [default]: ").strip().lower()
    if not theme:
        theme = "default"
        
    print("\n----------------------------------------------------------")
    print("🔬 Тестирование конфигурации")
    print("----------------------------------------------------------")
    
    telegram_ok = test_telegram(bot_token, channel_id)
    gemini_ok = test_gemini(gemini_key)
    
    if not telegram_ok or not gemini_ok:
        proceed = input("\n⚠️ Проверка завершилась с ошибками. Все равно записать файл .env? (y/n): ").strip().lower()
        if proceed != 'y':
            print("Настройка завершена без сохранения.")
            sys.exit(0)
            
    # Write .env file
    try:
        with open(".env", "w", encoding="utf-8") as f:
            f.write("# SMM Automator Configuration\n")
            f.write(f"GEMINI_API_KEY='{gemini_key}'\n")
            f.write(f"TELEGRAM_BOT_TOKEN='{bot_token}'\n")
            f.write(f"TELEGRAM_CHANNEL_ID='{channel_id}'\n")
            f.write(f"BRANDING_THEME='{theme}'\n")
            f.write("DATABASE_URL=''\n")
            f.write("SQLITE_DB_PATH='smm_database.db'\n")
        print("\n🎉 Конфигурация успешно сохранена в файл .env!")
        print("Теперь вы можете запустить проект командой: python -m smm_engine.main")
    except Exception as e:
        print(f"❌ Ошибка записи файла .env: {e}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nНастройка прервана пользователем.")
        sys.exit(0)
