import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "scripts"))

from process_ai_content import validate_ai_response
from fetch_feeds import is_on_topic

def run_tests():
    # Test 1: Valid AI response
    valid_json = '{"headline": "OpenAI Releases GPT-5 with Advanced Autonomous Capabilities", "hook": "A massive leap in agentic capabilities for modern software workflows.", "body": "OpenAI has officially announced their newest frontier model featuring deep reasoning and tool use capabilities designed specifically for enterprise workflows and multi-agent coordination systems. The system integrates real-time web browsing, code execution environments, and dynamic task decomposition, enabling developers to build sophisticated autonomous pipelines that operate reliably over long-horizon workflows without human intervention.", "why_it_matters": "Fundamental transformation for enterprise agent development.", "key_points": ["Enhanced multi-step reasoning", "Native tool calling and execution sandbox", "Optimized inference latency"], "source_url": "https://openai.com/news", "category": "AI News", "hashtags": ["#AI", "##OpenAI", "Tech"]}'
    valid, err, post, _ = validate_ai_response(valid_json, 'Fallback', 'https://openai.com', 'AI_NEWS')
    assert valid is True, f'Valid JSON failed: {err}'
    assert "##" not in post, f"Hashtag ## not cleaned: {post}"
    print("Test 1 (Valid Response & Hashtag auto-clean): PASS")

    # Test 2: Invalid single-line text (catches raw empty body posts)
    invalid_text = 'Just a single headline line with no body'
    valid, err, _, _ = validate_ai_response(invalid_text, 'Fallback', 'https://openai.com', 'AI_NEWS')
    assert valid is False, f'Single-line text should fail: {err}'
    print("Test 2 (Single-line / Empty Body Rejection): PASS")

    # Test 3: Short body (< minimum char threshold)
    short_json = '{"headline": "Short News Title", "body": "Too short snippet under threshold.", "source_url": "https://test.com", "category": "AI News"}'
    valid, err, _, _ = validate_ai_response(short_json, 'Fallback', 'https://test.com', 'AI_NEWS')
    assert valid is False and 'Body Length Check' in err, f'Short body passed: {err}'
    print("Test 3 (Short Body Length Under Min Bound): PASS")

    # Test 4: Body exceeding max length bound
    long_body = "This is a super long repetitive story body text. " * 60  # > 2700 chars
    long_json = f'{{"headline": "Too Long Article", "body": "{long_body}", "source_url": "https://test.com", "category": "AI News"}}'
    valid, err, _, _ = validate_ai_response(long_json, 'Fallback', 'https://test.com', 'AI_NEWS')
    assert valid is False and 'Body Length Check' in err, f'Overlong body passed: {err}'
    print("Test 4 (Overlong Body Exceeding Max Bound): PASS")

    # Test 5: Refusal phrase
    refusal_json = '{"headline": "AI Summary", "body": "I cannot provide information on this topic as it does not contain information relevant to AI in the provided context and is out of scope for our models.", "source_url": "https://test.com", "category": "AI News"}'
    valid, err, _, _ = validate_ai_response(refusal_json, 'Fallback', 'https://test.com', 'AI_NEWS')
    assert valid is False and 'Refusal' in err, f'Refusal phrase passed: {err}'
    print("Test 5 (Refusal Phrase Detection): PASS")

    # Test 6: Off-topic pre-filter (trebuchets / wildfires / etc.)
    assert is_on_topic('Medieval Trebuchet reconstruction project', 'Building a wooden catapult in backyard', 'TECH_DEVELOPMENT') is False
    assert is_on_topic('Wildfire spreads across region', 'Firefighters battle blaze', 'AI_NEWS') is False
    assert is_on_topic('New LLM Framework Released by Hugging Face', 'Python library for agent orchestration', 'AI_TOOLS') is True
    print("Test 6 (Pre-filter & Blacklist): PASS")

    # Test 7: Pre-formatted Telegram post text validation
    formatted_post = "🚨 *OpenAI Releases GPT-5 Frontier Architecture*\n\nA major breakthrough in reasoning models has arrived today as researchers unveil new agentic capabilities and native tool orchestration pipelines across enterprise ecosystems.\n\nThis release introduces autonomous multi-step planning, integrated code verification, and high-throughput execution engines designed to power next-generation developer tooling.\n\nKey Takeaways:\n• Deep multi-step reasoning capabilities\n• Built-in code interpreter and secure sandbox\n• Optimized inference latency for production\n\n🔗 [Read Full Article](https://openai.com/news)\n\n#AI #OpenAI #TechNews"
    valid, err, clean, _ = validate_ai_response(formatted_post, 'Fallback', 'https://openai.com', 'AI_NEWS')
    assert valid is True, f'Valid formatted post failed: {err}'
    print("Test 7 (Pre-formatted Telegram Post): PASS")

    print("\n✅ ALL 7 VALIDATION TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    run_tests()
