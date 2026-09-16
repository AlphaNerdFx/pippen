# Glossary

Terms used across lessons, defined once. A lesson that uses one of these links
here rather than redefining it.

## Packaging

**sdist** (source distribution). A `.tar.gz` of the project as written,
including the build configuration, so the recipient can build it themselves.

**wheel**. A `.zip` with a `.whl` extension holding the project in its installed
layout. Installing is close to unzipping into `site-packages`.

**pure-Python wheel**. A wheel tagged `py3-none-any`, containing no compiled
code, installable on every platform from one file.

**`dist-info`**. The metadata directory inside a wheel, holding `METADATA`,
`RECORD`, `WHEEL` and any entry points.

**`RECORD`**. The manifest of every file a wheel installs, each with a hash and
a byte count. What `pip uninstall` reads.

**`py.typed`**. A zero-byte marker defined by PEP 561. Its presence tells a type
checker that the package's inline annotations are to be trusted.

**package data**. Non-Python files shipped inside a distribution. They do not
travel by default and must be declared per build target.

**build backend**. The library that turns a source tree into a wheel or sdist.
This project uses hatchling, configured under `[tool.hatch]`.

## Release

**Trusted Publishing**. Publishing to PyPI by proving the workflow's identity
through OpenID Connect, with no stored password. PyPI mints an upload token
valid for at most 15 minutes.

**OIDC** (OpenID Connect). An identity layer over OAuth 2.0. The ID token is a
signed JWT carrying claims, which a verifier checks against a configuration
registered in advance.

**semantic versioning**. `MAJOR.MINOR.PATCH`, where raising MAJOR signals a
break for callers. Below `1.0.0` the guarantee is weaker by convention.

## Git

**blob**. File contents stored with no name and no permissions, addressed by the
hash of those contents.

**tree**. A directory listing: mode, name, and hash per entry.

**index** (also staging area, cache). The binary file at `.git/index` recording
what the next commit will contain. `git commit` builds from the index and never
consults the worktree.

**`:path`**. Revision syntax naming the blob for a path in the index, as in
`git cat-file -s :src/pippen/_data/x.parquet`.

**`core.fileMode`**. Whether git believes the filesystem's report of the
executable bit. False on this repository, which sits on a Windows mount.

## Failure modes

**check-then-act**. Reading a condition and acting on it as though nothing
changed in between. The race variant is TOCTOU.

**TOCTOU** (time-of-check to time-of-use). A check and a use separated by a
window an attacker can exploit.

**path traversal** (CWE-22). Escaping an intended directory through `../` in a
path treated as a string rather than as a path.

**fail-open**. A check that permits when it cannot decide. Sometimes required,
always worth naming.

**mutation testing**. Introducing a deliberate defect and requiring a test to
fail, which is the check on whether tests assert behaviour or merely pass.
