from pathlib import Path

import pytest
from test_answer import check_quotes

from ask.answer import answer
from ask.model import NOT_FOUND
from ask.store import add_repo, connect

BUNDLE = Path(__file__).resolve().parent.parent / "context-bundle"

CITES = [
    ("how do I deploy to prod? do I need approval?", "docs/deploy-pipeline.md", 11),
    ("is the growth dashboard or the spreadsheet the source of truth?", "docs/data-warehouse.md", 7),
    ("atlas-api is 5xx-ing, who's on call?", "docs/oncall.md", 6),
    ("where's the runbook for beacon backlog?", "docs/oncall.md", 8),
    ("how do I run atlas-api locally? make dev fails", "docs/onboarding.md", 8),
]

NOT_FOUND_QUESTIONS = [
    "kubernetes helm chart",
    "kafka consumer lag dashboard",
    "what language is atlas written in",
    "what does lookout actually pull from?",
]

ALL_QUESTIONS = (
    [q for q, _, _ in CITES]
    + [
        "what's the repo for courier?",
        "where do secrets go? can I just put the key in the repo for now?",
    ]
)


@pytest.fixture
def bundle(ask_home):
    con = connect()
    add_repo(con, BUNDLE, "bundle")
    return con


@pytest.mark.parametrize("question,path,line", CITES)
def test_top_hit_cites_expected_line(bundle, question, path, line):
    result = answer(bundle, question, "employee")
    assert result["status"] == "answered"
    top = result["hits"][0]
    assert (top["path"], top["line"]) == (path, line)
    check_quotes(bundle, result)


def test_courier_question_has_services_json_line(bundle):
    result = answer(bundle, "what's the repo for courier?", "employee")
    assert ("services.json", 29) in [(h["path"], h["line"]) for h in result["hits"]]
    check_quotes(bundle, result)


def test_secrets_question_tops_in_oncall_or_deploy_pipeline(bundle):
    result = answer(bundle, "where do secrets go? can I just put the key in the repo for now?", "employee")
    assert result["status"] == "answered"
    assert result["hits"][0]["path"] in ("docs/oncall.md", "docs/deploy-pipeline.md")
    check_quotes(bundle, result)


@pytest.mark.parametrize("question", ALL_QUESTIONS)
def test_no_hit_comes_from_the_question_log(bundle, question):
    result = answer(bundle, question, "employee")
    assert all(h["path"] != "questions-last-week.md" for h in result["hits"])
    check_quotes(bundle, result)


@pytest.mark.parametrize("question", NOT_FOUND_QUESTIONS)
def test_unanswerable_questions_are_not_found(bundle, question):
    result = answer(bundle, question, "employee")
    assert result["status"] == "not_found"
    assert result["message"] == NOT_FOUND
