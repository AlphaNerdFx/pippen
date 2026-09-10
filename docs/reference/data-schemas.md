# `pippen.data.schemas`

Validates the shape of every table at the point of ingest, before a bad file
reaches any calculation.

A column that silently changes dtype between two seasons will not stop the
solver from printing an answer. It stops the answer from being right, and
nothing else in the pipeline would say so.

::: pippen.data.schemas
