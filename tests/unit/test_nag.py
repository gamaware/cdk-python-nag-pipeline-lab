"""The cdk-nag gate: the real app synthesizes clean, and a bad resource fails."""

import json
from pathlib import Path

import aws_cdk as cdk
import pytest
from aws_cdk import aws_s3 as s3
from cdk_nag import AwsSolutionsChecks

from app import build_app


def test_app_has_no_unacknowledged_nag_findings(app):
    build_app(app)
    # Validation plugins run during synth and raise on any unacknowledged finding.
    app.synth()


def test_unacknowledged_finding_fails_synth(tmp_path):
    app = cdk.App(outdir=str(tmp_path))
    stack = cdk.Stack(app, "Bad")
    s3.Bucket(stack, "PlainBucket")
    cdk.Validations.of(app).add_plugins(AwsSolutionsChecks(app))

    with pytest.raises(RuntimeError, match="ValidationFailed"):
        app.synth()

    report = json.loads(Path(tmp_path, "validation-report.json").read_text())
    rules = {
        violation["ruleName"]
        for plugin in report["pluginReports"]
        for violation in plugin["violations"]
    }
    assert {"AwsSolutions-S1", "AwsSolutions-S10"} <= rules


def test_missing_context_is_rejected(tmp_path):
    app = cdk.App(outdir=str(tmp_path))
    with pytest.raises(ValueError, match="connection_arn"):
        build_app(app)
