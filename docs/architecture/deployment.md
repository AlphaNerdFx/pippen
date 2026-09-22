# Deployment

This project runs entirely on free tiers. That is a deliberate constraint, and it
matches how comparable open-source sports-data projects actually operate.

## What runs where

| Need | Service | Cost |
|---|---|---|
| Scheduling | GitHub Actions cron | free on public repositories |
| Artifact storage | GitHub Releases, Hugging Face Datasets | free |
| Inference API | FastAPI in Docker on Hugging Face Spaces | free CPU tier |
| Dashboard | Streamlit on Hugging Face Spaces | free CPU tier |
| Documentation | MkDocs on GitHub Pages | free |
| Drift reporting | Evidently report rendered into the docs site | free |

## What this costs you

Honest accounting of what a free tier does not provide:

- **No autoscaling.** One container, one machine.
- **Cold starts.** A free Space sleeps when idle. First request after a quiet
  period takes several seconds.
- **No live-traffic drift detection.** Drift is computed against new data on a
  schedule, not against production requests, because there is not enough
  production traffic to compute anything from.
- **No zero-downtime deploys.** A redeploy is a restart.

None of these matter for a project serving a research metric. All of them would
matter for a product.

## Kubernetes

The repository contains KServe manifests under `deploy/kubernetes/`. They are
validated in continuous integration and tested against a
[kind](https://kind.sigs.k8s.io/) cluster, which runs Kubernetes inside Docker on
a laptop at no cost.

They are not used in production, because production here is one container serving
occasional requests, and Kubernetes exists to solve a problem this project does
not have. They exist so the deployment path is real and tested rather than
hypothetical.

## Container

The image is built from `deploy/Dockerfile`, multi-stage, non-root, with the
model baked in at build time rather than downloaded at start. Startup that
depends on a network fetch is startup that fails when the network does.

## The serving layer, as built

`src/pippen/api/app.py` is a FastAPI application over the tables that ship
inside the wheel. Five endpoints, no model loading, and nothing computed per
request. A response is a filtered read of a 228 KB Parquet file, so the cold
start on a sleeping free tier is process boot rather than numpyro importing jax.

| Endpoint | Returns |
|---|---|
| `GET /health` | Liveness, version, and the seasons the process is serving |
| `GET /ratings` | Players ranked by impact per 100 possessions |
| `GET /ratings/{player_id}` | One player across every window they appear in |
| `GET /reliability` | Measured split-half reliability of each box-score metric |
| `GET /possession-coefficient/{season}` | The measured value, against the 0.44 convention |

No endpoint returns a per-player interval, and the OpenAPI description says so
rather than leaving a caller to notice.
[ADR 0007](decisions/0007-the-api-serves-shipped-tables-and-no-interval.md) has
the reasoning: the only candidate was a bootstrap standard error on a ridge
coefficient, and Phase 2 measured that it rises with possessions rather than
falling.

### Container

`deploy/Dockerfile` builds in two stages. The first produces a wheel, the second
installs only that wheel, so the runtime image carries no build backend, no test
suite and no git history. It runs as uid 10001, and because the wheel already
contains the computed tables the container needs no volume, no download on boot
and no network access at all.

Verified locally: the image builds from a clean checkout, `/health` answers,
`id -u` reports 10001, and a write to `/` is refused.

One number worth knowing before this is deployed anywhere with a size limit.
The image is **939 MB**, of which 588 MB is the dependency install. `import
pippen` needs pandas and pyarrow, but scipy, scikit-learn, pandera, typer and
rich are all core dependencies, so every install pulls the full RAPM computation
stack to serve a static table.

### Kubernetes

`deploy/kubernetes/inferenceservice.yaml` is a KServe `InferenceService`,
scale-to-zero, one request per replica, read-only root filesystem with every
capability dropped. Nothing applies it to a cluster: this project runs on free
tiers and a cluster solves no problem it has. CI validates it with `kubeconform`
against the KServe CRD schema, so the manifest is checked rather than claimed.
