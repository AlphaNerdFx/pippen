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
| qSQ, qSI | Second Spectrum | **Not used.** Proprietary and not published anywhere reachable. Assessed 15 September 2026; see below. |

EPM and DARKO are still the right things to measure against. This project
compares against them by rank correlation, using their public leaderboards, and
publishes the comparison rather than the values.

## qSQ and qSI, assessed and rejected

Quantified Shot Quality and Quantified Shooter Impact were considered as inputs,
because qSI is conceptually what the claim under test said was missing:
shooting skill separated from shot difficulty.

They fail the licence gate. They are Second Spectrum's, and they are not served
by any endpoint this project can reach. `nba_api` 1.11.4 has no reference to
them anywhere in its 143 endpoints, and probing stats.nba.com found nothing.
They were visible on NBA.com around 2016 and are not now. That puts them in the
same category as EPM and DARKO: the right thing to want, and not available on
terms this project can build on.

A substitute was then built and measured rather than assumed, because the
substitute is computable from data already on disk. hoopR play-by-play carries
shot coordinates on every shooting play across all 25 seasons under CC BY 4.0,
which supports a location-based expected-points model: a qSQ analogue as the
average expected value of a player's attempts, and a qSI analogue as what he
actually scored above that.

Measured on 2023-24, 374 players with at least 50 attempts per half:

| Quantity | Reliability | Correlation with RAPM |
|---|---|---|
| eFG% | 0.668 | +0.284 |
| Shot quality, location only | 0.949 | −0.032 |
| Shooting skill over expected | 0.601 | +0.348 |

Neither goes in, and the reasons differ.

**Shot quality is rejected on independent information.** It correlates −0.032
with RAPM, which is to say not at all, and its strongest relationship in the
model is 0.655 with offensive rebounds per 36. It is a position descriptor:
players who shoot near the rim have high shot quality. The model already has
four of those, and the project has already shown that adding a high-reliability
zero-validity metric is actively harmful, not merely useless.

**Shooting skill is rejected as a near-duplicate that does not improve on what
it duplicates.** It correlates 0.874 with effective field goal percentage,
against a duplicate threshold of about 0.9, and it loses to eFG% on both of the
axes that would have justified it: less reliable (0.601 against 0.668) and no
better related to impact (+0.348 against true shooting's +0.365).

The reason is instructive. Location-only shot quality mostly measures where a
player shoots from, which is role. Real qSQ conditions on defender distance,
shot clock and touch time, which is what separates an open three from a
contested one at the same spot on the floor. That conditioning is the part that
would matter, and it is the part location alone cannot supply.

**What would change this.** `leaguedashplayerptshot` serves shooting splits by
closest-defender distance, and it is live for 2013-14 through 2024-25, which
covers the whole RAPM window. A shot-quality model conditioned on defender
distance is therefore buildable. It falls under the tracking row above: derived
features may be published, raw responses may not. It is a real piece of work,
about 30 requests per season at one per second, and it is the version of this
idea worth doing.

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
