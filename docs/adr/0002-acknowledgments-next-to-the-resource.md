# 0002. Acknowledge each accepted finding on its construct, with a reason

## Status

Accepted

## Context

Suppressions added at stack or app level to make a build pass hide every later finding of the same rule. Reasons
such as "not needed" give a reviewer nothing to check.

Some findings come from constructs this code does not write: CDK Pipelines generates the IAM roles and policies for
its CodeBuild projects, and several of them carry wildcard actions or resources.

## Decision

- Fix first. An acknowledgment is written only when the control does not apply or a compensating control covers the
  same risk.
- Each acknowledgment targets one construct and, for granular rules such as IAM5, one finding ID
  (`AwsSolutions-IAM5[Action::s3:GetObject*]`), with a reason that names the control or the scope that limits it.
- Acknowledgments for resources written here sit next to the resource in `service/service_stack.py`. Those for
  roles that CDK Pipelines generates live in `pipeline/nag_suppressions.py`, one block per role.

## Consequences

- A new wildcard produces a new finding ID that no acknowledgment covers, so synth fails.
- `pipeline/nag_suppressions.py` depends on the construct paths and logical IDs CDK Pipelines generates. A CDK
  upgrade that renames them fails synth and needs the IDs updated.
- Where a generated grant is broader than the pipeline needs, the fix is in code, not in the reason. The asset
  publishing role gets an explicit deny on starting, retrying and stopping builds
  ([ADR 0003](0003-shared-settings-owned-once.md) covers the other generated-scope change).

## Compliance

Automated: `tests/unit/test_nag.py` synthesizes the real app, and `tests/unit/test_pipeline_stack.py` asserts the
deny on the asset role. Review: [docs/nag-findings.md](../nag-findings.md) lists every acknowledgment and why it is
accepted.

## Notes

- Related: [ADR 0001](0001-cdk-nag-as-a-synth-gate.md).
