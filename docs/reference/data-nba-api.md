# `pippen.data.nba_api`

The one module allowed to talk to stats.nba.com. Every call is paced at one
request per second and retried with a bounded backoff.

The pacing is a compliance rule rather than a performance choice. Exceeding it
risks the endpoint being blocked for every user of this package.

::: pippen.data.nba_api
