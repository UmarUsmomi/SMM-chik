# Project Context

This folder contains the metadata and orchestrator files for the SMM bot modernization task.

## Key Files to Modernize:
- `smm_engine/media/image_handler.py`: HUD graphics, watermark, fonts, Cyberpunk card.
- `smm_engine/media/video_generator.py` and `smm_engine/publishers/telegram_pub.py`: update `fetch_background` calls to `generate_ai_background`.
- `smm_engine/content/adapter.py`: blockquote implementation.
- `bot/app.py`: scheduler check using db settings.
- `smm_engine/storage/database.py` and potentially others: sqlite3 datetime adapter and `google.generativeai` warning fixes.

## Working Directories:
- Orchestrator: `d:\SMM\.agents\orchestrator_modernization`
- Subagents: to be spawned under `.agents/` prefix.
