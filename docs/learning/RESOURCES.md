# Resources

Sources used to ground lessons. Every claim in a lesson should trace to one of
these rather than to model recall.

## Packaging and distribution

| Resource | Type | Why it is trusted | Used in |
|---|---|---|---|
| [Python Packaging User Guide](https://packaging.python.org/) | Official guide | Maintained by the PyPA, the people who maintain the tooling | 0002 |
| [PEP 561](https://peps.python.org/pep-0561/) | Standard | The normative text on `py.typed` and type distribution | 0002 |
| [Typing spec: distributing type information](https://typing.python.org/en/latest/spec/distributing.html) | Standard | The maintained successor to PEP 561's prose | 0002 |
| [`importlib.resources`](https://docs.python.org/3/library/importlib.resources.html) | Stdlib docs | Normative on `files()` and `as_file()` | 0002 |

## Release and supply chain

| Resource | Type | Why it is trusted | Used in |
|---|---|---|---|
| [PyPI Trusted Publishers](https://docs.pypi.org/trusted-publishers/) | Official docs | PyPI's own specification of the OIDC exchange | pending |
| [Trusted Publishers security model](https://docs.pypi.org/trusted-publishers/security-model/) | Official docs | States the threat model explicitly, including what it does not defend | pending |
| [Introducing Trusted Publishers](https://blog.pypi.org/posts/2023-04-20-introducing-trusted-publishers/) | Announcement | Primary source for the 2023 date and the motivation | pending |

## Git internals

| Resource | Type | Why it is trusted | Used in |
|---|---|---|---|
| [Pro Git, chapter 10, Git Internals](https://git-scm.com/book/en/v2/Git-Internals-Plumbing-and-Porcelain) | Book, free | The standard reference on blobs, trees and the index | pending |
| [`gitrevisions(7)`](https://git-scm.com/docs/gitrevisions) | Manual | Normative on the `:path` syntax the pre-commit hook uses | pending |

## Communities

Wisdom comes from testing work outside the learning environment. These are where
this project's audience actually is.

- [r/nbaanalytics](https://www.reddit.com/r/nbaanalytics/) for the basketball side.
- [APBRmetrics forum](http://www.apbr.org/metrics/) for the measurement side,
  where RAPM was largely worked out in public.
- [Python Discourse, packaging category](https://discuss.python.org/c/packaging/14)
  for the engineering side. The people who wrote the standards answer there.
