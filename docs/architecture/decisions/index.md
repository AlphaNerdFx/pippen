# Architecture decision records

**What they are.** A numbered, append-only log of significant technical
decisions. Each record states the situation that forced a choice, the choice
made, the alternatives rejected, and what the project accepts as a consequence.
Records are never edited once accepted. A decision that turns out wrong gets a
new record that supersedes the old one, and the old one stays in place.

**Where they come from.** Michael Nygard proposed the format in 2011, out of a
much older engineering practice: the design rationale document. The principle is
that **the reasoning is more valuable than the conclusion**. A conclusion tells a
newcomer what to do. The reasoning tells them when to stop doing it. Without it,
every past decision looks arbitrary, and teams either cargo-cult choices they do
not understand or relitigate them every six months.

**Who uses them and why.** Widely adopted in infrastructure and platform
engineering, where decisions are expensive to reverse and the people who made
them move on. Kubernetes, Terraform providers and many Apache projects keep
them in-repo. They also appear in regulated industries, where auditors ask not
what you built but why.

**Why this project uses them.** It is a research project whose credibility rests
on its choices being defensible. "Why not Rust" and "why not use EPM as the
target" are questions a reviewer will actually ask, and the answer should exist
in writing rather than in someone's memory. They also make the project legible
to a contributor arriving cold.

**What it costs.** Roughly an hour per significant decision, and the discipline
to write the record before acting rather than after.

## Records

| ID | Title | Status |
|---|---|---|
| [0001](0001-python-as-orchestration-layer.md) | Python as the orchestration layer | Accepted |
