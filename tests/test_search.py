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


def test_one_or_two_words_need_every_word(ask_home, tmp_path):
    con = build(tmp_path, {"a.md": "alpha beta\n\ngamma\n"})
    assert len(fts_search(con, ["alpha", "beta"], ["r"])) == 1
    assert fts_search(con, ["alpha", "gamma"], ["r"]) == []


def test_two_words_with_one_present_is_not_found(ask_home, tmp_path):
    con = build(tmp_path, {"a.md": "alpha\n\nbeta\n"})
    assert fts_search(con, ["alpha", "beta"], ["r"]) == []


def test_three_words_with_one_present_is_not_found(ask_home, tmp_path):
    con = build(tmp_path, {"a.md": "alpha\n\nbeta\n"})
    assert fts_search(con, ["alpha", "zzzz", "yyyy"], ["r"]) == []


def test_three_words_need_two(ask_home, tmp_path):
    con = build(tmp_path, {"a.md": "alpha beta\n\ngamma only\n"})
    hits = fts_search(con, ["alpha", "beta", "zzzz"], ["r"])
    assert [(h.path, h.line) for h in hits] == [("a.md", 1)]


def test_five_words_need_three(ask_home, tmp_path):
    con = build(tmp_path, {"a.md": "one two three\n\none two\n"})
    hits = fts_search(con, ["one", "two", "three", "four", "five"], ["r"])
    assert [(h.path, h.line) for h in hits] == [("a.md", 1)]


def test_more_covered_words_rank_first(ask_home, tmp_path):
    con = build(tmp_path, {"a.md": "alpha beta\n", "b.md": "alpha beta gamma\n"})
    hits = fts_search(con, ["alpha", "beta", "gamma"], ["r"])
    assert [h.path for h in hits] == ["b.md", "a.md"]


def test_four_letter_word_matches_as_prefix(ask_home, tmp_path):
    con = build(tmp_path, {"a.md": "the production release\n"})
    assert fts_search(con, ["prod"], ["r"])[0].line == 1


def test_three_letter_word_does_not_match_as_prefix(ask_home, tmp_path):
    con = build(tmp_path, {"a.md": "the production release\n"})
    assert fts_search(con, ["pro"], ["r"]) == []


def test_chunk_quoting_the_question_is_dropped(ask_home, tmp_path):
    files = {"log.md": "Q: where is the   Cache?\nthe cache lives in redis\n", "doc.md": "the cache lives in redis\n"}
    con = build(tmp_path, files)
    hits = fts_search(con, ["cache"], ["r"], question="Where is the cache?")
    assert [h.path for h in hits] == ["doc.md"]
    assert len(fts_search(con, ["cache"], ["r"])) == 2


def test_echo_threshold_counts_raw_words_not_content_words(ask_home, tmp_path):
    files = {
        "log.md": '1. "what\'s the repo for courier?" asked by devon\n',
        "doc.md": "the courier repo lives at github.com/org/courier\n",
    }
    con = build(tmp_path, files)
    question = "what's the repo for courier?"
    assert len(content_words(question)) < 3
    hits = fts_search(con, content_words(question), ["r"], question=question)
    assert [h.path for h in hits] == ["doc.md"]


def test_four_words_with_two_covered_is_not_found(ask_home, tmp_path):
    con = build(tmp_path, {"a.md": "alpha beta\n"})
    assert fts_search(con, ["alpha", "beta", "zzzz", "yyyy", "xxxx"], ["r"]) == []


def test_short_question_is_not_treated_as_an_echo(ask_home, tmp_path):
    con = build(tmp_path, {"a.md": "the cache lives in redis\n"})
    assert len(fts_search(con, ["cache"], ["r"], question="cache?")) == 1


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
