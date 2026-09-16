# Learning notes

Each note takes one idea that went into this codebase and traces it properly:
where it came from, who uses it and for what, why this project needed it, and
what it cost. The point is to be able to reason about the idea somewhere else,
not only to recognise the code here.

## Notes

Prose, for reading through once.

| Note | Concepts |
|---|---|
| [0001: The data layer](0001-data-layer.md) | Atomic writes, check-then-act races, validation at the boundary, why tests written after code lock in bugs |

## Lessons

Short and interactive, with an exercise to run against this repository.

| Lesson | Concepts | Win |
|---|---|---|
| [0002: Prove what your wheel ships](lessons/0002-prove-what-your-wheel-ships.html) | Wheels and sdists, `dist-info`, `RECORD`, PEP 561 `py.typed`, declaring package data | Open your own artifact and check it against what you intended |

## Reference

Compressed, for looking things up later.

- [Packaging commands and layouts](reference/packaging-commands.html)
