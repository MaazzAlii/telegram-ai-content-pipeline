import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "scripts"))

from process_ai_content import validate_ai_response
from fetch_feeds import is_on_topic

def run_tests():
    # Test 1: Valid AI response
    valid_json = '{"headline": "OpenAI Releases GPT-5 with Advanced Autonomous Capabilities", "hook": "A massive leap in agentic capabilities.", "body": "OpenAI has officially announced their newest frontier model featuring deep reasoning and tool use capabilities designed specifically for enterprise workflows and multi-agent coordination systems.", "why_it_matters": "Changes agent development.", "key_points": ["Enhanced reasoning", "Native tool integration"], "source_url": "https://openai.com/news", "category": "AI News", "hashtags": ["#AI", "##OpenAI", "Tech"]}'
    valid, err, post, _ = validate_ai_response(valid_json, 'Fallback', 'https://openai.com', 'AI_NEWS')
    assert valid is True, f'Valid JSON failed: {err}'
    assert "##" not in post, f"Hashtag ## not cleaned: {post}"
    print("Test 1 (Valid Response & Hashtag auto-clean): PASS")

    # Test 2: Invalid JSON
    invalid_json = 'This is raw text not json'
    valid, err, _, _ = validate_ai_response(invalid_json, 'Fallback', 'https://openai.com', 'AI_NEWS')
    assert valid is False and 'JSON Parse' in err, f'Invalid JSON passed: {err}'
    print("Test 2 (JSON Parse Error): PASS")

    # Test 3: Short body (< 100 chars)
    short_json = '{"headline": "Short News Title", "body": "Too short", "source_url": "https://test.com", "category": "AI News"}'
    valid, err, _, _ = validate_ai_response(short_json, 'Fallback', 'https://test.com', 'AI_NEWS')
    assert valid is False and 'Minimum Length' in err, f'Short body passed: {err}'
    print("Test 3 (Short Length < 100): PASS")

    # Test 4: Refusal phrase
    refusal_json = '{"headline": "AI Summary", "body": "I cannot provide information on this topic as it does not contain information relevant to AI in the provided context.", "source_url": "https://test.com", "category": "AI News"}'
    valid, err, _, _ = validate_ai_response(refusal_json, 'Fallback', 'https://test.com', 'AI_NEWS')
    assert valid is False and 'Refusal' in err, f'Refusal phrase passed: {err}'
    print("Test 4 (Refusal Phrase Detection): PASS")

    # Test 5: Off-topic pre-filter (trebuchets / wildfires / etc.)
    assert is_on_topic('Medieval Trebuchet reconstruction project', 'Building a wooden catapult in backyard', 'TECH_DEVELOPMENT') is False
    assert is_on_topic('Wildfire spreads across region', 'Firefighters battle blaze', 'AI_NEWS') is False
    assert is_on_topic('New LLM Framework Released by Hugging Face', 'Python library for agent orchestration', 'AI_TOOLS') is True
    print("Test 5 (Pre-filter & Blacklist): PASS")

    print("\n✅ ALL 5 VALIDATION TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    run_tests()
