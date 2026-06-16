import asyncio
import logging
from smm_engine.publishers.telegram_pub import TelegramPublisher

logging.basicConfig(level=logging.INFO)

async def main():
    pub = TelegramPublisher()
    
    title = "🚀 CUDA НА AMD: МИР СОШЕЛ С УМА"
    text = """Кажется, мы дожили до момента, когда проприетарные технологии NVIDIA перестали быть «вещью в себе». Энтузиасты наконец-то запустили CUDA на картах AMD. Да, вы не ослышались: код, который годами был заперт в экосистеме «зеленых», теперь работает на железе Radeon.

<blockquote expandable>
Проект называется <b>ZLUDA</b>. Это не просто эмулятор, а слой трансляции, который позволяет запускать приложения с поддержкой CUDA на видеокартах AMD практически без потери производительности.
</blockquote>

Раньше для работы с нейросетями или тяжелым рендерингом выбор был очевиден — только NVIDIA. Теперь этот барьер рушится. 

Что это значит для нас? 
<ul>
<li>Больше не нужно переплачивать за видеокарты с шильдиком GeForce, если вам нужны специфические библиотеки.</li>
<li>AMD получает шанс отвоевать долю рынка в профессиональном сегменте.</li>
<li>Разработчики получают свободу выбора железа.</li>
</ul>

Конечно, это не официальная поддержка от AMD или NVIDIA, и проект пока находится в стадии активной разработки. Но сам факт того, что это стало возможным, меняет правила игры. Похоже, монополия CUDA начинает трещать по швам.

Теперь можно запускать CUDA-код прямо на AMD GPU без правок и костылей, как на родном железе. Это серьезный удар по монополии NVIDIA: владельцы «красных» карт наконец-то могут выдохнуть, а Хуангу пора напрячься. Готовы сменить лагерь или всё ещё верите в магию CUDA-ядер?

#ml #ai #ии #нейросети"""

    formatted_title = f"<b>{pub._escape_html(title)}</b>"
    formatted_text = pub._format_markdown_to_html(text)
    caption = f"{formatted_title}\n\n{formatted_text}"
    
    print(f"Original caption length: {len(caption)}")
    
    if len(caption) > 1024:
        max_text_len = 1024 - len(formatted_title) - 10
        print(f"max_text_len: {max_text_len}")
        if max_text_len > 50:
            truncated_text = formatted_text[:max_text_len]
            print(f"Truncated text before split length: {len(truncated_text)}")
            split_parts = truncated_text.rsplit('\n', 1)
            print(f"Split parts count: {len(split_parts)}")
            formatted_text = split_parts[0] + "..."
        else:
            formatted_text = formatted_text[:100] + "..."
        caption = f"{formatted_title}\n\n{formatted_text}"
        
    print(f"Truncated caption length: {len(caption)}")
    print("Truncated caption:")
    print(caption)

if __name__ == "__main__":
    asyncio.run(main())
