from smm_engine.publishers.telegram_pub import TelegramPublisher

pub = TelegramPublisher()

test_text = """Хочешь вернуть атмосферу старых кассет на свой современный экран? Есть простой способ превратить картинку в настоящий VHS-вайб.

<blockquote expandable>
Этот эффект добавляет те самые помехи, искажения и характерные цвета, которые мы помним по видеомагнитофонам из 90-х.
</blockquote>

<b>Как это работает:</b>

Вместо сложных настроек используй готовые шейдеры или фильтры. Они накладывают на изображение «шум», легкое дрожание и цветовые сдвиги, имитируя сигнал с магнитной ленты.

Это отличный способ стилизовать стрим, видео или просто добавить ностальгии в рабочий процесс. Никакого профессионального софта — достаточно пары кликов, чтобы картинка «поплыла» в стиле старого доброго аналогового ТВ.

Забудь про стерильный 4K, пришло время ностальгического глитча. Библиотека ntsc-rs на Rust добавляет в проект аутентичные помехи, цветовые сдвиги и «мыло» старых телевизоров. Отличный способ передать атмосферу 90-х, не выжигая глаза идеальной картинкой. Готов променять четкость на ламповый шум кассеты?"""

title = "📺 VIBE CHECK: ТВОЙ МОНИТОР ТЕПЕРЬ В VHS-СТИЛЕ"

formatted_title = f"<b>{pub._escape_html(title)}</b>"
formatted_text = pub._format_markdown_to_html(test_text)
caption = f"{formatted_title}\n\n{formatted_text}"

print("=== FORMATTED TEXT ===")
print(formatted_text)
print("=" * 40)

max_caption_len = 1024 - 20
max_raw_text_len = max_caption_len - len(formatted_title) - 2

print(f"Original len: {len(caption)}")
print(f"Max caption len: {max_caption_len}")
print(f"Max raw text len: {max_raw_text_len}")

if len(caption) > max_caption_len:
    truncated_text = pub._truncate_html(formatted_text, max_raw_text_len)
    caption_trunc = f"{formatted_title}\n\n{truncated_text}"
    print("=== TRUNCATED TEXT ===")
    print(truncated_text)
    print("=" * 40)
    print(f"Truncated len: {len(caption_trunc)}")
else:
    print("No truncation needed.")
