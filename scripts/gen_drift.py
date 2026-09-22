"""Render the drift report into the docs site at build time.

Run by mkdocs-gen-files, so the page is always computed from the tables that
ship in the working tree rather than from a copy someone remembered to refresh.

Generating it beats committing it. This repository deliberately runs no bot
commits: Dependabot's automated pull requests are off so that every commit has a
human author, and a scheduled job pushing a regenerated Markdown file would be
the same thing wearing a different hat.
"""

from __future__ import annotations

import mkdocs_gen_files

from pippen import drift, published

with mkdocs_gen_files.open("drift.md", "w") as page:
    page.write(drift.render(drift.report(published.rapm_ratings())))
