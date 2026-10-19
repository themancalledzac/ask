import pytest

from ask.owners import find_codeowners, owners_for_path, parse_codeowners


def owners(text, path):
    rule = owners_for_path(parse_codeowners(text), path)
    return None if rule is None else rule.owners


def test_last_match_beats_first():
    text = "*.py @first\napps/ @second\n*.py @third\n"
    assert owners(text, "apps/x.py") == ["@third"]


def test_no_match_returns_none():
    assert owners_for_path(parse_codeowners("*.js @a\n"), "x.py") is None


def test_leading_slash_dir_is_anchored():
    text = "/docs/ @a\n"
    assert owners(text, "docs/x.md") == ["@a"]
    assert owners(text, "src/docs/x.md") is None


def test_trailing_slash_dir_matches_at_any_depth():
    text = "docs/ @a\n"
    assert owners(text, "docs/x.md") == ["@a"]
    assert owners(text, "src/docs/x.md") == ["@a"]
    assert owners(text, "docs") is None


def test_dir_without_trailing_slash_matches_children():
    text = "apps/web @a\n"
    assert owners(text, "apps/web/x.ts") == ["@a"]
    assert owners(text, "apps/web") == ["@a"]
    assert owners(text, "apps/webby/x.ts") is None


def test_star_extension_any_depth():
    text = "*.js @a\n"
    assert owners(text, "x.js") == ["@a"]
    assert owners(text, "a/b/x.js") == ["@a"]
    assert owners(text, "a/b/x.ts") is None


def test_double_star_in_middle_spans_zero_or_more_segments():
    text = "/build/**/logs @a\n"
    assert owners(text, "build/logs") == ["@a"]
    assert owners(text, "build/a/b/logs") == ["@a"]
    assert owners(text, "other/build/logs") is None


def test_trailing_slash_star_is_one_level_only():
    text = "docs/* @a\n"
    assert owners(text, "docs/a.md") == ["@a"]
    assert owners(text, "docs/x/a.md") is None


def test_star_does_not_cross_slash():
    text = "/src/*.py @a\n"
    assert owners(text, "src/a.py") == ["@a"]
    assert owners(text, "src/sub/a.py") is None


def test_question_mark_matches_one_non_slash_char():
    text = "/a?c.txt @a\n"
    assert owners(text, "abc.txt") == ["@a"]
    assert owners(text, "ac.txt") is None
    assert owners(text, "a/c.txt") is None


def test_trailing_comment_stripped():
    rules = parse_codeowners("*.js @a @org/team # frontend\n")
    assert rules[0].owners == ["@a", "@org/team"]


def test_escaped_hash_is_literal():
    rules = parse_codeowners("\\#notes.md @a\n")
    assert rules[0].pattern == "#notes.md"
    assert rules[0].owners == ["@a"]


def test_comment_and_blank_lines_skipped_and_line_numbers_kept():
    rules = parse_codeowners("# header\n\n*.js @a\r\n  \n*.py @b\n")
    assert [(r.pattern, r.line) for r in rules] == [("*.js", 3), ("*.py", 5)]


def test_rule_with_no_owners_clears_ownership():
    text = "*.js @a\n/vendor/ \n"
    rule = owners_for_path(parse_codeowners(text), "vendor/x.js")
    assert rule is not None
    assert rule.owners == []


def test_email_owner_kept():
    assert owners("* dev@example.com\n", "x") == ["dev@example.com"]


@pytest.mark.parametrize("line", ["!*.js @a", "docs/[ab].md @a", "x]y @a"])
def test_negation_and_ranges_skipped(line):
    assert parse_codeowners(line + "\n") == []


def test_find_prefers_github_dir(tmp_path):
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github" / "CODEOWNERS").write_text("* @a\n")
    (tmp_path / "CODEOWNERS").write_text("* @b\n")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "CODEOWNERS").write_text("* @c\n")
    assert find_codeowners(tmp_path) == tmp_path / ".github" / "CODEOWNERS"


def test_find_root_before_docs(tmp_path):
    (tmp_path / "CODEOWNERS").write_text("* @b\n")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "CODEOWNERS").write_text("* @c\n")
    assert find_codeowners(tmp_path) == tmp_path / "CODEOWNERS"


def test_find_docs_when_only_one(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "CODEOWNERS").write_text("* @c\n")
    assert find_codeowners(tmp_path) == tmp_path / "docs" / "CODEOWNERS"


def test_find_none_and_directory_ignored(tmp_path):
    assert find_codeowners(tmp_path) is None
    (tmp_path / "CODEOWNERS").mkdir()
    assert find_codeowners(tmp_path) is None
