# Installation

## From PyPI

```bash
pip install pippen
```

Optional extras install only what you need:

| Extra | Installs | For |
|---|---|---|
| `sources` | `nba_api`, `pbpstats` | Downloading raw data yourself |
| `fit` | NumPyro, LightGBM, Optuna, MLflow, SHAP | Fitting models rather than using published ones |
| `api` | FastAPI, Uvicorn | Running the inference service |
| `dashboard` | Streamlit, Plotly | Running the dashboard locally |

```bash
pip install "pippen[sources,fit]"
```

## From source

This project uses [uv](https://docs.astral.sh/uv/), which manages the virtual
environment and the lockfile together.

```bash
git clone https://github.com/AlphaNerdFx/pippen
cd pippen
uv sync --extra dev
uv run pippen --help
```

!!! note "Why uv rather than pip and venv"
    `uv sync` reads `uv.lock`, which pins every transitive dependency to an exact
    version. Two people running it on different machines get byte-identical
    environments. That is what makes a result reproducible.

If you would rather not use uv, `requirements.txt` is generated from the same
lockfile:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

## Supported versions

Python 3.10 through 3.13, tested on every push. Linux and macOS are tested;
Windows should work but is not covered by continuous integration.
