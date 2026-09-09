# Security Policy

## Supported versions

This project is pre-release. Only the latest published version receives fixes.

| Version | Supported |
|---|---|
| latest release | yes |
| everything else | no |

## Reporting a vulnerability

**Do not open a public issue for a security problem.**

Use GitHub's private vulnerability reporting on this repository, under the
**Security** tab, **Report a vulnerability**. That channel is private to the
maintainers.

Please include:

- what the problem is and what an attacker could achieve;
- the steps to reproduce it;
- the version or commit you tested.

Expect an acknowledgement within seven days and an assessment within thirty.

## Scope

In scope:

- the published package and its command-line interface;
- the inference API and its container image;
- the continuous integration and release workflows, including anything that could
  let an outside contributor publish a package or alter a release.

Out of scope:

- vulnerabilities in upstream data providers;
- rate limiting or availability of third-party sources;
- issues that require an attacker to already control the machine running the code.

## What this project handles

pippen processes public sports statistics. It stores no personal data, no
credentials, and no payment information. The most valuable thing in this
repository is its release pipeline, so that is where hardening effort goes:
publishing uses PyPI Trusted Publishing rather than a stored token, and workflow
permissions are scoped per job.
