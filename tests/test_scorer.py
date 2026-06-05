import pytest
from unittest.mock import MagicMock, patch
from smm_engine.scrapers.base import NewsItem
from smm_engine.analyzers.scorer import NewsScorer

@pytest.mark.asyncio
async def test_news_scorer_with_mock():
    # Setup mock for generative AI model
    mock_model = MagicMock()
    mock_response = MagicMock()
    # Fake Gemini JSON output
    mock_response.text = '{"relevance": 25, "freshness": 15, "virality": 18, "uniqueness": 10, "quality": 12, "total": 80, "reason": "Test reason"}'
    mock_model.generate_content.return_value = mock_response
    
    item = NewsItem(
        source="test",
        source_id="123",
        title="Mocked AI Breakthrough",
        url="https://example.com/ai"
    )
    
    with patch("google.generativeai.GenerativeModel", return_value=mock_model), \
         patch("smm_engine.analyzers.scorer.GEMINI_API_KEY", "dummy_key"):
        scorer = NewsScorer()
        scorer.enabled = True # force enabled
        
        result = await scorer.score_item(item)
        
        assert result["total"] == 80
        assert result["relevance"] == 25
        assert result["reason"] == "Test reason"
        mock_model.generate_content.assert_called_once()
