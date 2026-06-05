import pytest
from unittest.mock import MagicMock, patch
from smm_engine.content.humanizer import TextHumanizer

@pytest.mark.asyncio
async def test_text_humanizer_with_mock():
    mock_model = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Это чистый текст без признаков ИИ."
    mock_model.generate_content.return_value = mock_response
    
    with patch("google.generativeai.GenerativeModel", return_value=mock_model), \
         patch("smm_engine.content.humanizer.GEMINI_API_KEY", "dummy_key"):
        humanizer = TextHumanizer()
        humanizer.enabled = True
        
        result = await humanizer.humanize("В мире, где технологии развиваются, следует отметить этот инструмент.")
        
        assert result == "Это чистый текст без признаков ИИ."
        mock_model.generate_content.assert_called_once()
