import json
import os
from pathlib import Path

import aws_cdk as cdk
import pytest

os.environ.setdefault("JSII_SILENCE_WARNING_UNTESTED_NODE_VERSION", "1")

# Dummy values only. 123456789012 is the AWS documentation example account.
DUMMY_CONTEXT = {
    "account": "123456789012",
    "region": "us-east-1",
    "repository": "example-org/cdk-python-nag-pipeline-lab",
    "connection_arn": (
        "arn:aws:codeconnections:us-east-1:123456789012:"
        "connection/00000000-0000-0000-0000-000000000000"
    ),
}


# Feature flags from cdk.json, so tests synthesize the same way the CLI does.
FEATURE_FLAGS = json.loads((Path(__file__).parents[1] / "cdk.json").read_text())["context"]


@pytest.fixture
def app(tmp_path) -> cdk.App:
    return cdk.App(context=FEATURE_FLAGS | DUMMY_CONTEXT, outdir=str(tmp_path / "cdk.out"))
