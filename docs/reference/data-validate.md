# `pippen.data.validate`

Cross-table validation, run after ingest and before anything computes.

Where `schemas` sees one table, this sees a season. A file can be perfectly
well formed and still disagree with the file next to it, and only a check that
looks at both will notice.

::: pippen.data.validate
