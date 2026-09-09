# Handover

State of the project for whoever picks it up next, human or model.

## Where things stand

Week 0 is complete and verified on real infrastructure, not just locally.

- Repository: <https://github.com/AlphaNerdFx/pippen>, public
- Documentation: <https://alphanerdfx.github.io/pippen/>
- CI, Rigour and Publish docs all green on GitHub runners
- No data ingested, no model trained

Next: week 1-2, the data layer.

## The plan

`/home/youssef/.claude/plans/you-re-a-senior-data-validated-blanket.md` holds the
full plan. `TODO.md` holds the outline.

## Decisions that are settled

| Decision | Choice | Why |
|---|---|---|
| Ground truth | Own RAPM | EPM is paywalled at the $250 API tier and not redistributable |
| Infrastructure | Free tiers only | No budget; matches how comparable FOSS projects run |
| Code licence | Apache-2.0 | Patent grant, and leaves dual-licensing open |
| Data licence | CC BY 4.0 | Matches hoopR upstream, permits commercial use |
| Orchestration | GitHub Actions | Airflow needs a server there is no budget for |
| Storage | Parquet plus DuckDB | No database server needed |
| Kubernetes | Manifests only, tested on kind | Real and tested, without paying for a cluster |
| Name | PIPPEN | Player Impact from Pooled Priors and Estimated Noise; follows the DARKO/CARMELO convention |
| Docs | MkDocs only, no Wiki | A wiki is a separate repo, unreviewable, and outside the strict build |
| Dependabot | Alerts only, no automated PRs | Every commit keeps a human author; `make upgrade` applies updates |
| Deep CI | Rigour set, not Jenkins or Sonar | Proves the numbers, not just the syntax. See docs/architecture/ci.md |

## Things a newcomer will get wrong

1. **hoopR play-by-play has no lineup column.** It is ESPN-sourced and carries
   event participants only. RAPM needs `pbpstats` against NBA API data.
2. **The research documents in `docs/research/` are prior work, not authority.**
   Several citations are dead, including the one behind the EPM reliability
   figure. Measure, do not cite.
3. **Data never goes in git.** A pre-commit hook enforces it.
4. **EPM and DARKO values must never enter a release artifact.** Compare against
   them by rank correlation only.

## The claim the whole project rests on

Does PIPPEN predict next-season team net rating better than any single input metric
does, out of sample? It has not been tested yet. If it fails, say so publicly.
