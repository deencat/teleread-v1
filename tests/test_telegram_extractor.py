from src.telegram_extractor import TelegramExtractor


def test_normalize_strips_leading_emoji():
    raw = "🐉短炒世界升级系统-刘市群(Donald sir)"
    assert TelegramExtractor._normalize_channel_name(raw) == "短炒世界升级系统-刘市群(donaldsir)"


def test_normalize_strips_leading_at():
    assert TelegramExtractor._normalize_channel_name("@donald_sir") == "donald_sir"

