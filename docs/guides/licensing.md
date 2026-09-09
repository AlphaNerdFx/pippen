# Data licensing

The code is **Apache-2.0**. Data artifacts this project publishes are
**CC BY 4.0**.

## The rule

!!! danger "No exceptions"
    If a value was not computed from a source that permits redistribution, it
    does not go into a release.

## Position by input

| Input | Source | Position |
|---|---|---|
| RAPM (own) | Computed from possession data | Ours. Published. |
| Four Factors, Net Rating, box-score rates | hoopR-nba-data, CC BY 4.0 | Published, with attribution. |
| Tracking features | `nba_api` | Derived features only. Raw responses are never redistributed. |
| BPM, VORP, Win Shares | Basketball-Reference | **Local validation only.** Never in a release artifact. |
| EPM | Dunks & Threes | **Not used.** API access is a paid tier and values are not redistributable. |
| DARKO | darko.app | **Not used.** A public download exists but states no licence, which is not a basis to build on. |

EPM and DARKO are still the right things to measure against. This project
compares against them by rank correlation, using their public leaderboards, and
publishes the comparison rather than the values.

## Underlying league data

NBA statistics carry usage restrictions from the rights holders. This project is
for personal and research use. Commercial use of the underlying data requires
licensing that this project neither grants nor can grant.

## Attribution requirements

If you use this project's published data, CC BY 4.0 asks you to credit it. If you
redistribute anything derived from hoopR, credit the SportsDataverse authors as
well, since their licence carries through.

## Rate limits observed

| Source | Limit | How it is respected |
|---|---|---|
| NBA stats endpoints | about 1 request per second | Enforced in the client, with backoff on failure |
| Basketball-Reference | 20 requests per minute | Validation only, and off the critical path |

Scraping faster than a source allows gets the source taken away from everyone.
