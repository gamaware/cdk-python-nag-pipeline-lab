# 0001. Run cdk-nag as a validation plugin that fails synth

## Status

Accepted

## Context

Rule packs such as AWS Solutions catch unencrypted buckets, missing access logs and wildcard IAM grants before
CloudFormation sees a template. Run as a separate report, they are easy to skip: a pipeline can deploy while the
report lists findings nobody reads.

cdk-nag 3 plugs into the CDK policy validation hook (`Validations.of(app).add_plugins(...)`). A finding at `ERROR`
level makes `cdk synth` exit non-zero.

## Decision

- `app.py` registers `AwsSolutionsChecks` once, on the whole app, so every stack and stage is checked.
- The same `cdk synth` runs locally (`make synth`), in CI (`make verify`) and in the pipeline's synth step. The synth
  step runs `uv run pytest` first.
- Nothing is deployed from a cloud assembly that failed validation: the pipeline stops at `Build`.

## Consequences

- A new resource that breaks a rule fails the pull request and the pipeline, not a later audit.
- Every accepted finding needs an acknowledgment in code ([ADR 0002](0002-acknowledgments-next-to-the-resource.md)).
- cdk-nag and the CDK library are pinned in `uv.lock`; a rule pack update can add findings and fail synth until
  they are fixed or acknowledged.
- Other packs (HIPAA, NIST 800-53, PCI DSS, Serverless) register the same way and add their own findings.

## Compliance

Automated in `tests/unit/test_nag.py`: the real app synthesizes with no unacknowledged finding, and a plain
`s3.Bucket` in a scratch app fails synth with AwsSolutions-S1 and S10.

## Notes

- [cdk-nag rules](https://github.com/cdklabs/cdk-nag/blob/main/RULES.md).
