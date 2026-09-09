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
