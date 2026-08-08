from app.lib.chunking import split_into_chunks, split_at_sentence_boundaries, count_tokens_approximate


def test_short_text_no_split():
    text = "短いテスト文です。"
    chunks = split_into_chunks(text, max_tokens=512)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_long_text_splits():
    sentences = ["これはテスト文です。"] * 200
    text = "".join(sentences)
    chunks = split_into_chunks(text, max_tokens=512)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) > 0


def test_sentence_boundary_detection():
    text = "今日は天気が良い。明日は雨かもしれない。来週は晴れるだろう。"
    sentences = split_at_sentence_boundaries(text)
    assert len(sentences) == 3
    assert sentences[0] == "今日は天気が良い。"


def test_chunk_overlap():
    sentences = [f"これは文{i}です。" for i in range(100)]
    text = "".join(sentences)
    chunks = split_into_chunks(text, max_tokens=50, overlap_sentences=1)
    assert len(chunks) > 1


def test_token_count_japanese():
    count = count_tokens_approximate("日本語テスト")
    assert count > 0


def test_token_count_mixed():
    count = count_tokens_approximate("Hello世界test")
    assert count > 0


def test_empty_text():
    assert split_into_chunks("") == [""]
    assert split_at_sentence_boundaries("") == []
