# Changelog

This file records all notable changes to this lab. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- `Makefile` with `setup`, `lint`, `test`, `synth` and `verify`; CI runs `make verify` and the shared lint, secrets
  and security workflows from `gamaware/.github`.
- Architecture decision records in `docs/adr/`, `CHANGELOG.md`, `CODEOWNERS` and a Vale configuration.
- Tests for the asset-role deny, both connection permissions and the single API Gateway logging setting.

### Changed

- The API Gateway logging role and `AWS::ApiGateway::Account` moved from each stage to the pipeline stack, so Dev
  and Prod no longer both own the account setting.
- The asset publishing role gets an explicit deny on starting, retrying and stopping CodeBuild builds.
- The pipeline role also gets `codeconnections:UseConnection` on the connection.
- The IAM4 acknowledgment for the logging role states the managed policy's real scope.
- The synth step calls `npx --yes`; Python 3.13 locally and in CI.
- README follows the portfolio section order; `SECURITY.md` points to the shared policy.

## [0.1.0]

- Initial lab: CDK Pipelines app gated by cdk-nag, the sample workload, template tests and CI.
