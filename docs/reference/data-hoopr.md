# `pippen.data.hoopr`

Bulk historical download from the hoopR NBA data repository, which publishes
one Parquet file per season under CC BY 4.0.

Downloads are atomic. Each file streams to a temporary sibling, has its Parquet
footer validated, and only then replaces the target. A crash partway through
cannot leave a truncated file where a later run would skip it as already
present, which would silently poison every calculation downstream.

::: pippen.data.hoopr
