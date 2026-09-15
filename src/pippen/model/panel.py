"""The team-season table every candidate is scored against.

Why this is a type
------------------
``features``, ``target`` and ``seasons`` were passed as three separate
arguments through five functions, and the fold logic that derives from them was
a private helper each of those functions called. Three values that always travel
together, plus the operations that only make sense on all three at once, is a
type.

Making it one also makes a guarantee enforceable that was previously a comment.
Rows with no next-season target cannot be scored by anything, and dropping them
in one constructor is what makes "every candidate is scored on the same
team-seasons" true rather than asserted. Two modules previously disagreed about
this: :mod:`pippen.model.claim` filtered on ``target.notna()`` and
:mod:`pippen.model.baselines` did not, so a paired comparison between a single
metric and a baseline was silently comparing different row sets.

Folds
-----
Splitting is by season and never by team. Two teams in the same season played
each other, so a model that saw part of a season would be predicting the rest
of it rather than the future.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

import pandas as pd

#: Rows a training split needs before a fit is attempted.
MIN_TRAINING_ROWS: Final = 5


class EmptyPanelError(ValueError):
    """No team-season survived construction, so nothing can be scored."""


class NotEnoughSeasonsError(ValueError):
    """Fewer than two seasons, so no season can be held out."""


@dataclass(frozen=True)
class Fold:
    """One leave-one-season-out split.

    Attributes:
        held_out: The season being predicted.
        train: True for rows the model may learn from.
        test: True for rows it is scored on.
    """

    held_out: int
    train: pd.Series
    test: pd.Series

    @property
    def usable(self) -> bool:
        """True when the split has enough rows on both sides to be worth fitting."""
        return bool(self.train.sum() >= MIN_TRAINING_ROWS and self.test.sum() > 0)


@dataclass(frozen=True)
class TeamPanel:
    """Candidate values and the target, for every team-season being scored.

    Attributes:
        features: One column per candidate, indexed by ``(season, team_id)``.
        target: Next season's net rating for the same index.
        seasons: Season each row belongs to, taken from the index.
    """

    features: pd.DataFrame
    target: pd.Series
    seasons: pd.Series

    @classmethod
    def build(cls, features: pd.DataFrame, target: pd.Series) -> TeamPanel:
        """Assemble a panel, dropping rows that cannot be scored.

        Args:
            features: One column per candidate, indexed by ``(season, team_id)``.
            target: Next season's net rating, on the same index.

        Returns:
            A panel whose every row has a target.

        Raises:
            EmptyPanelError: If no row has one.
        """
        aligned = target.reindex(features.index)
        keep = aligned.notna()
        if not keep.any():
            raise EmptyPanelError(
                f"none of {len(features)} team-seasons has a next-season target; "
                f"the last season in a window cannot be scored and may be all there is"
            )
        kept = features[keep]
        return cls(
            features=kept,
            target=aligned[keep],
            seasons=pd.Series([index[0] for index in kept.index], index=kept.index),
        )

    @property
    def candidates(self) -> tuple[str, ...]:
        """Names of the candidates this panel can score."""
        return tuple(self.features.columns)

    @property
    def n_observations(self) -> int:
        """Team-seasons in the panel."""
        return len(self.features)

    def without(self, *names: str) -> TeamPanel:
        """Return a panel with some candidates removed.

        Used to ask what the box score can do on its own, by dropping RAPM and
        the fused rating.

        Args:
            *names: Candidates to drop. Names not present are ignored, so a
                caller need not know which columns a window happened to have.

        Returns:
            A new panel. The original is unchanged.
        """
        present = [name for name in names if name in self.features.columns]
        return TeamPanel(
            features=self.features.drop(columns=present),
            target=self.target,
            seasons=self.seasons,
        )

    def only(self, *names: str) -> TeamPanel:
        """Return a panel holding only the named candidates."""
        present = [name for name in names if name in self.features.columns]
        return TeamPanel(features=self.features[present], target=self.target, seasons=self.seasons)

    def folds(self, *, over: Sequence[int] | None = None) -> list[Fold]:
        """Return one leave-one-season-out split per season.

        Args:
            over: Restrict to these seasons. Used to build the inner folds of a
                nested search, where the outer held-out season must not appear.

        Returns:
            One :class:`Fold` per season, in season order.

        Raises:
            NotEnoughSeasonsError: If fewer than two seasons are available,
                leaving no split that holds one out.
        """
        available = sorted(self.seasons.unique()) if over is None else sorted(over)
        if len(available) < 2:
            raise NotEnoughSeasonsError(
                f"only {len(available)} season(s) available; a leave-one-season-out "
                f"split needs at least two"
            )
        eligible = self.seasons.isin(available)
        return [
            Fold(
                held_out=int(season),
                train=eligible & (self.seasons != season),
                test=eligible & (self.seasons == season),
            )
            for season in available
        ]

    def describe(self) -> str:
        """Return a one-line summary of the panel's size."""
        seasons = sorted(self.seasons.unique())
        span = f"{seasons[0]}-{seasons[-1]}" if len(seasons) > 1 else str(seasons[0])
        return (
            f"{self.n_observations} team-seasons over {len(seasons)} seasons ({span}), "
            f"{len(self.candidates)} candidates"
        )
