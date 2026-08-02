from unittest.mock import AsyncMock, patch

import pytest

from smm_engine.main import main


@pytest.mark.asyncio
async def test_production_cli_exits_before_pipeline_when_database_is_missing(
    monkeypatch,
    caplog,
):
    marker = "must-not-be-logged"
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("GEMINI_API_KEY", marker)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", marker)
    monkeypatch.setenv("TELEGRAM_CHANNEL_ID", marker)
    monkeypatch.setenv("TELEGRAM_ADMIN_CHAT_ID", "123456789")
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with patch("smm_engine.main.SMMPipeline") as pipeline_class:
        with pytest.raises(SystemExit) as exc_info:
            await main()

    assert exc_info.value.code == 1
    pipeline_class.assert_not_called()
    assert "DATABASE_URL" in caplog.text
    assert marker not in caplog.text


@pytest.mark.asyncio
async def test_development_cli_keeps_local_dry_run(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")

    with patch(
        "smm_engine.main.check_required_env",
        return_value=["GEMINI_API_KEY"],
    ), patch("smm_engine.main.SMMPipeline") as pipeline_class:
        pipeline_class.return_value.run = AsyncMock(return_value={"processed": 0})

        await main()

    pipeline_class.assert_called_once_with()
    pipeline_class.return_value.run.assert_awaited_once_with()
