import pytest

from ask.search import STOPWORDS, content_words, fts_search
from ask.store import add_repo, connect


def build(tmp_path, files, name="r"):
    root = tmp_path / name
    root.mkdir()
    for fname, text in files.items():
        (root / fname).write_text(text)
    con = connect()
    add_repo(con, root, name)
    return con


def test_content_words_lowercases_splits_and_drops_stopwords():
    assert content_words("Where is the Atlas-API deployed?") == ["atlas", "api", "deployed"]


def test_content_words_dedupes_keeping_order():
    assert content_words("beta alpha BETA alpha gamma") == ["beta", "alpha", "gamma"]


def test_content_words_empty_and_all_stopwords():
    assert content_words("") == []
    assert content_words("who is the") == []


def test_stopwords_fixed_set():
    assert {"the", "s", "now", "just", "whose"} <= STOPWORDS
    assert "api" not in STOPWORDS


def test_strict_hit_needs_every_word(ask_home, tmp_path):
    con = build(tmp_path, {"a.md": "alpha beta\n\ngamma\n"})
    assert len(fts_search(con, ["alpha", "beta"], ["r"])) == 1
    assert fts_search(con, ["alpha", "gamma"], ["r"]) == []


def test_fallback_allows_one_missing_word_with_three_words(ask_home, tmp_path):
    con = build(tmp_path, {"a.md": "alpha beta\n\ngamma only\n"})
    hits = fts_search(con, ["alpha", "beta", "zzzz"], ["r"])
    assert [(h.path, h.line) for h in hits] == [("a.md", 1)]


def test_fallback_not_allowed_with_two_words(ask_home, tmp_path):
    con = build(tmp_path, {"a.md": "alpha\n\nbeta\n"})
    assert fts_search(con, ["alpha", "beta"], ["r"]) == []


def test_fallback_cannot_drop_two_words(ask_home, tmp_path):
    con = build(tmp_path, {"a.md": "alpha\n\nbeta\n"})
    assert fts_search(con, ["alpha", "zzzz", "yyyy"], ["r"]) == []


def test_cites_line_with_most_content_words(ask_home, tmp_path):
    text = "intro line\nnothing here\nthe deploy pipeline runs\nlast\n"
    con = build(tmp_path, {"a.md": text})
    hit = fts_search(con, ["deploy", "pipeline"], ["r"])[0]
    assert (hit.line, hit.quote) == (3, "the deploy pipeline runs")


def test_ties_go_to_first_line(ask_home, tmp_path):
    con = build(tmp_path, {"a.md": "x\nalpha one\nalpha two\n"})
    assert fts_search(con, ["alpha"], ["r"])[0].line == 2


def test_five_character_prefix_matches_inflected_line_token(ask_home, tmp_path):
    con = build(tmp_path, {"a.md": "unrelated\ndeploys happen\n"})
    hit = fts_search(con, ["deploy"], ["r"])[0]
    assert hit.line == 2


def test_short_word_needs_equal_token(ask_home, tmp_path):
    con = build(tmp_path, {"a.md": "apis everywhere\napi docs\n"})
    hits = fts_search(con, ["api"], ["r"])
    assert hits[0].line == 2


def test_limit_and_repo_filter(ask_home, tmp_path):
    con = build(tmp_path, {f"{i}.md": "needle here\n" for i in range(5)})
    assert len(fts_search(con, ["needle"], ["r"])) == 3
    assert len(fts_search(con, ["needle"], ["r"], limit=5)) == 5
    assert fts_search(con, ["needle"], ["other"]) == []
    assert fts_search(con, ["needle"], []) == []


@pytest.mark.parametrize("word", ['"quoted"', "OR", "*", ":", "NEAR", "a'b"])
def test_syntax_characters_do_not_raise(ask_home, tmp_path, word):
    con = build(tmp_path, {"a.md": "plain text\n"})
    fts_search(con, [word], ["r"])
