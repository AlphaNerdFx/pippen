# Security Policy

## Where this project is

`pippen` is **pre-release**. Version 0.0.0 exists on PyPI to reserve the name and
to prove the publishing path works. It is not a usable release: there is no data
pipeline, no model, and no metric behind it yet.

That shapes what this policy can honestly promise. Until a real release exists,
the most valuable thing in this repository is not the code. It is the release
pipeline, because that is the only part an attacker could use to reach somebody
else's machine.

## Supported versions

| Version | Supported |
|---|---|
| Latest published release | Yes |
| Everything earlier | No |

While below 1.0, only the newest version receives fixes. There are no long-term
support branches and there will not be until the metric is validated.

## Reporting a vulnerability

**Do not open a public issue.**

Use GitHub's private vulnerability reporting on this repository, under the
**Security** tab, then **Report a vulnerability**. That channel is enabled and
goes only to the maintainers.

Please include what the problem is and what an attacker could achieve, the steps
to reproduce it, and the version or commit you tested.

Expect an acknowledgement within seven days and an assessment within thirty.
This is a student research project, not a staffed product, so those are honest
targets rather than a service level agreement.

## Scope

**In scope**

- The published package and its command-line interface.
- The release and continuous integration workflows, including anything that
  would let an outside contributor publish a package, alter a release, or run
  code with repository credentials.
- The inference API and its container image, once they exist.
- Any published dataset artifact, if it could be made to carry something other
  than what it claims.

**Out of scope**

- Vulnerabilities in upstream data providers such as the NBA stats endpoints,
  hoopR or Basketball-Reference.
- Rate limiting, availability or correctness of third-party sources.
- Issues requiring an attacker to already control the machine running the code.
- Disagreements about the metric's accuracy. Those are welcome, but they belong
  in a public issue, not here.

## What this project handles

`pippen` processes public sports statistics. It stores no personal data, no
credentials and no payment information. Nothing it publishes is derived from a
private source.

The one thing it does hold that matters is the ability to publish under a name
other people will install. Hardening effort goes there.

## How the supply chain is protected

| Control | State | Why |
|---|---|---|
| Private vulnerability reporting | Enabled | A private channel for exactly this policy |
| Dependabot alerts | Enabled | Notifies about vulnerable dependencies |
| Dependabot automated pull requests | **Disabled** | Deliberate: every commit keeps a human author. Updates are applied by hand with `make upgrade` |
| Secret scanning and push protection | Enabled | Blocks a credential from entering history in the first place |
| Committed lockfile | Yes | `uv.lock` pins every transitive dependency to an exact version |
| Lockfile drift check in CI | Yes | A dependency cannot be added without being locked |
| Actions pinned | Yes | Two are pinned exactly because they publish no major tag |
| Data payload commit guard | Yes | A pre-commit hook refuses Parquet, CSV and pickle files |

## Where this is going

The controls above will tighten as the project becomes something people depend
on. Planned, in the order they become worth doing:

1. **PyPI Trusted Publishing** for every real release, so no API token exists to
   be stolen. The release workflow is already written this way; the publisher
   configuration lands with the first genuine version.
2. **Build provenance attestation**, so anyone installing `pippen` can verify
   cryptographically that the wheel was built by this repository's workflow from
   this repository's source.
3. **A software bill of materials** attached to each release.
4. **CodeQL** static analysis and **OpenSSF Scorecard**, once there is enough
   code for either to say something meaningful.

None of these are in place today, and this document will be wrong the moment
they are. If it disagrees with the repository settings, the settings are the
truth and this file is a bug.

## A note on credentials

Never send an API token, of any service, through an issue, a discussion, a pull
request or a chat log. If one is exposed, revoke it first and ask questions
afterwards. A token that has appeared in a transcript is compromised whether or
not anybody used it.
