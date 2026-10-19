Take-Home: Ship a Small Thing - (Jason)
The Exercise
We'd rather see what you ship than read about what you've shipped. So: build a small tool, automation, or agent that takes a bite out of the friction described below — and actually deploy it so we can run it.
Time: Please cap yourself at 90 minutes. Treat that as a target to protect your time, not a stopwatch — we'd genuinely rather you stop early than polish. The short write-up below is separate from that build time; quick notes are completely fine. We are explicitly not looking for a polished product — we're looking for how you scope, build, and ship under a tight constraint. A small thing that runs beats a big thing that doesn't.
Use AI tooling. Cursor, Claude Code, Codex, whatever you reach for — use it the way you actually work. Third-party libraries, starter templates, and boilerplate are all fair game too — ship however you'd really ship. We'd genuinely like to know how you used it (see the write-up).
The Friction
At our fictional-but-realistic company, engineers and operators are constantly answering the same question: "Where does X live / who owns X / what's the status of X?" The answer is scattered across a GitHub repo, a Notion page, and a Slack channel, and people burn real time hunting it down or pinging each other. There is no single place to ask.
We've put a small bundle of fake "context" in the starter materials: a few markdown docs, a JSON file of "services and owners," and a short log of "questions people asked last week."
agentic-ops-takehome-context-bundle.zip
Your task: Build something that makes answering those questions faster. Some directions people have taken — pick one, or do your own thing:
A tiny CLI that searches the context bundle and returns an answer (and says where it found it).
A minimal web app / chatbot that takes a question and responds from the bundled context.
An agent / automation that, given a question, routes to the right source and drafts an answer with a citation.
A small script that ingests the bundle and produces something useful (a freshness report, an owner map, a "stale docs" flag).
There is no single right answer. We care about taste in scoping and the fact that it runs.
What to Send Us
A way to run it. Ideally a live URL. If that's not practical in the time, a repo we can run in one documented command is completely fine. Tell us exactly how.
A ~1-page write-up (markdown is great) covering:
What you built and why — and what you deliberately left out given the time.
How you'd attack the real problem if you had real time — not just this tool, but the broader "people can't find context" problem. Where's the leverage?
What you'd measure to know it's working.
Safety/exposure — one or two lines on what would have to change before this was safe to put in front of the whole company (secrets, access, what's internal vs. external).
How you used AI tooling — which tools, what you delegated to them, what you kept by hand, and anywhere they led you astray.
How We'll Read It
We are not grading code golf or test coverage. We're looking for: ruthless scoping, the instinct to actually ship and deploy rather than polish, a write-up that treats the friction as a system with leverage points (not a one-off patch), and an honest, fluent relationship with your tooling. If you spent 80 of your 90 minutes making one thing genuinely work end-to-end, that's a great answer.
If you're slammed and can't do the take-home, that's okay — tell us, and we'll do a compressed version live. You'll just have less time to think, so we recommend the take-home if you can swing it.
Delivery note: the in-person interview is a short walkthrough of what I shipped, then pairing on a live ticket in their own control repo, not my code.
