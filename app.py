#!/usr/bin/env python3
"""CDK entry point. Applies the AWS Solutions cdk-nag pack to the whole app."""

import aws_cdk as cdk
from cdk_nag import AwsSolutionsChecks

from pipeline.pipeline_stack import PipelineStack

REQUIRED_CONTEXT = ("account", "region", "connection_arn", "repository")


def build_app(app: cdk.App) -> PipelineStack:
    missing = [key for key in REQUIRED_CONTEXT if not app.node.try_get_context(key)]
    if missing:
        raise ValueError(
            "Missing CDK context: "
            + ", ".join(missing)
            + ". Pass each one with -c key=value (see README)."
        )
    context = {key: app.node.try_get_context(key) for key in REQUIRED_CONTEXT}
    context["branch"] = app.node.try_get_context("branch") or "main"

    stack = PipelineStack(
        app,
        "NagLabPipeline",
        repository=context["repository"],
        branch=context["branch"],
        connection_arn=context["connection_arn"],
        synth_context=context,
        env=cdk.Environment(account=context["account"], region=context["region"]),
    )
    cdk.Validations.of(app).add_plugins(AwsSolutionsChecks(app, verbose=True))
    return stack


if __name__ == "__main__":
    app = cdk.App()
    build_app(app)
    app.synth()
