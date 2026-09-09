# nba-impact

**Reliability-adjusted NBA player impact estimates, with calibrated uncertainty.**

!!! warning "Pre-release"
    The data layer and the metric are under construction. No results have been
    published yet, and nothing here is stable.

## The idea in one paragraph

Public NBA impact metrics disagree with one another, and none reports how much to
trust any single number. This project treats those metrics as **noisy
measurements of one quantity nobody observes directly**: a player's true
contribution to point differential. That turns player evaluation into a
measurement-error problem, which is a solved area of statistics. Each metric's
reliability is *measured* rather than asserted, the metrics are combined by
inverse-variance weighting, and every player gets an interval rather than a bare
number.

## The claim under test

> Does RAIM predict next-season team net rating better than any single input
> metric does, out of sample?

If the answer turns out to be no, that will be published here. A falsifiable
claim stated before the experiment is what separates research from a demo.

## Where to start

<div class="grid cards" markdown>

- **[Installation](guides/installation.md)** — get it running
- **[Quickstart](guides/quickstart.md)** — the five commands that matter
- **[Method](methodology/index.md)** — how the metric is built
- **[Limitations](methodology/limitations.md)** — read before quoting a number

</div>

## Licensing in one line

Code is Apache-2.0, published data is CC BY 4.0, and nothing paywalled ever
enters a release. The full position is on the
[data licensing](guides/licensing.md) page.
