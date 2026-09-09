---
name: add-metric
description: Add a new input metric to the reliability-weighted fusion model. Use when the user wants to incorporate an additional player metric, evaluate whether a metric belongs in the model, or asks why a particular metric is or is not included.
---

# Add an input metric

Every metric entering the fusion model must clear three gates in order. A metric
that fails any gate does not go in, regardless of how well regarded it is.

## Gate 1: licensing

**Can its values be redistributed?**

If it comes from a paid tier, or from a source that states no licence, the answer
is no and the work stops here. This is not negotiable and it is why EPM and DARKO
are absent.

Acceptable: values computed in this repository from a CC BY source, or derived
features that are not the source's own output.

Record the outcome in `docs/guides/licensing.md`.

## Gate 2: measured reliability

**Does it measure signal?**

Compute split-half reliability with the Spearman-Brown correction:

```bash
uv run pippen reliability --metric <name> --seasons 2015-2024
```

Below roughly 0.5, the metric is mostly noise and adds nothing but variance.
Report the measured number, and report it next to whatever tier the prior
research assigned. Where they disagree, say so in `docs/methodology/reliability.md`
rather than quietly preferring one.

## Gate 3: independent information

**Does it tell us anything the model does not already have?**

Inverse-variance weighting assumes errors are independent. Metrics sharing inputs
violate that. Check the correlation of this metric's residuals against the
residuals of metrics already included. A metric correlating above about 0.9 with
an existing one is a duplicate, and adding it makes intervals too narrow rather
than more accurate.

## Implementation

1. Add the loader to `src/pippen/data/`, with a pandera schema.
2. Register it in the metric registry with its licence position.
3. Add unit tests, plus a property test if it involves parsing.
4. Refit and rerun the claim under test.
5. Report the before and after values on a fixed reference season in the pull
   request, as `CONTRIBUTING.md` requires.

## Deliberately excluded

PER, DBPM and unregularised APM. Poor defensive capture, no context adjustment,
and instability under multicollinearity respectively. Reopening any of these
needs new evidence, not a preference.
