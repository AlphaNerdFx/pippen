# Engineering, not statistics, is the learning target

Established from `CLAUDE.md` and the project's own documentation rather than from
a stated claim: the maintainer is a data science student whose statistics,
basketball analytics and modelling are strong, and whose gap is engineering,
infrastructure and MLOps. `CLAUDE.md` encodes this as a standing rule, requiring
engineering concepts to be built from the ground while statistical ones are
assumed.

**Implications.** Lessons spend their budget on the engineering half of any
concept that spans both. Ridge regression needs no introduction; that the design
matrix is 99 percent zeros by construction, and that sparse storage came out of
1960s structural engineering, is where the time goes. Statistical explanation in
a lesson is a wasted session and reads as condescension.

**Evidence.** Phases 0 through 3 produced a validated RAPM at Spearman 0.914, a
measured reliability study across 25 seasons, and a published negative result on
the project's central claim. The statistics were never the blocker. The defects
found in review have been engineering defects: a bootstrap standard error read as
information when it tracked shrinkage, hyperparameters selected on reported
folds, and a pre-commit hook that sized the wrong object.

**Status.** Active. Supersede this if the maintainer corrects `MISSION.md`.
