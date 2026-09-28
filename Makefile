.DEFAULT_GOAL := help
SHELL := bash
.SHELLFLAGS := -euo pipefail -c

UV ?= uv
RUN := $(UV) run --frozen
CDK_CLI_VERSION := 2.1143.0
# Example values only: 123456789012 is the AWS documentation example account. Synth needs no credentials.
SYNTH_CONTEXT := -c account=123456789012 -c region=us-east-1 \
	-c repository=example-org/cdk-python-nag-pipeline-lab \
	-c connection_arn=arn:aws:codeconnections:us-east-1:123456789012:connection/00000000-0000-0000-0000-000000000000

.PHONY: help setup lint test synth verify clean

help: ## List targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-8s %s\n", $$1, $$2}'

setup: ## Install the pinned Python toolchain into .venv
	$(UV) sync --frozen

lint: ## Ruff lint and format check
	$(RUN) ruff check
	$(RUN) ruff format --check

test: ## Template assertions and the cdk-nag gate tests
	$(RUN) pytest

synth: ## cdk synth with example context; fails on any unacknowledged cdk-nag finding
	JSII_SILENCE_WARNING_UNTESTED_NODE_VERSION=1 npx --yes aws-cdk@$(CDK_CLI_VERSION) synth --quiet $(SYNTH_CONTEXT)

verify: lint test synth ## Everything CI runs, offline and without AWS credentials
	@echo "verify: all checks passed"

clean: ## Remove caches and the cloud assembly
	rm -rf cdk.out .pytest_cache .ruff_cache
