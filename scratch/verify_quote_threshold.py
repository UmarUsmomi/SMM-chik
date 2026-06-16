import asyncio
from unittest.mock import patch, AsyncMock
from smm_engine.content.adapter import ContentAdapter
from smm_engine.scrapers.base import NewsItem

async def verify_thresholds():
    adapter = ContentAdapter()
    
    # We will test lengths 499, 500, 501
    lengths = [499, 500, 501]
    
    print("=== Verifying Boundary Values for Quote Threshold ===")
    for length in lengths:
        content_str = "A" * length
        item = NewsItem(
            source="test_source",
            source_id=f"test_{length}",
            title=f"Title {length}",
            url=f"http://example.com/{length}",
            raw_data={"content": content_str}
        )
        
        # We need to test under two conditions for random.random(): 0.50 (allowed if long) and 0.70 (forbidden always)
        for rand_val in [0.50, 0.70]:
            with patch("smm_engine.content.adapter.generate_content_with_retry", new_callable=AsyncMock) as mock_generate, \
                 patch("smm_engine.content.adapter.parse_json_robust") as mock_parse, \
                 patch("random.random", return_value=rand_val):
                
                mock_generate.return_value = "{}"
                mock_parse.return_value = {"title": "Test Title", "body": "Test Body"}
                
                await adapter._adapt_pass(item)
                
                prompt = mock_generate.call_args[0][0]
                
                # Determine what should happen
                # is_long = length > 500. So length 499 and 500 are not long.
                # length 501 is long.
                # if is_long and rand_val < 0.60: blockquotes allowed
                # else: blockquotes forbidden
                is_long = length > 500
                should_allow = is_long and (rand_val < 0.60)
                
                has_allow_instr = "Если в новости есть яркая прямая цитата" in prompt
                has_forbid_instr = "КАТЕГОРИЧЕСКИ ЗАПРЕЩАЕТСЯ использовать тег <blockquote>" in prompt
                
                print(f"Length: {length}, Random: {rand_val:.2f} -> Should Allow: {should_allow}")
                print(f"  Has Allow Instruction: {has_allow_instr}")
                print(f"  Has Forbid Instruction: {has_forbid_instr}")
                
                if should_allow:
                    assert has_allow_instr and not has_forbid_instr, "Failed: should have allowed blockquote"
                else:
                    assert has_forbid_instr and not has_allow_instr, "Failed: should have forbidden blockquote"
                print("  STATUS: PASS")
    print("=====================================================")

if __name__ == "__main__":
    asyncio.run(verify_thresholds())
