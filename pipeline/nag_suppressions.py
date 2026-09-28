"""Accepted cdk-nag findings for the pipeline stack, each with its reason.

Every finding here comes from IAM policies that CDK Pipelines generates. cdk-nag
v3 has no prefix matching, so each wildcard finding is acknowledged by its exact
ID. A new wildcard (for example ``s3:*`` added by hand) produces a new ID that is
not in this list, and synth fails.
"""

from aws_cdk import Acknowledgment, Stack, Validations
from constructs import IConstruct

ARTIFACT_READ = (
    "CDK grant on the pipeline artifact bucket. The action wildcard covers "
    "read-only S3 actions and the policy is scoped to that single bucket."
)
ARTIFACT_WRITE = (
    "CDK grant on the pipeline artifact bucket. The wildcard lets the stage "
    "write and clean up its own artifacts in that single bucket."
)
ARTIFACT_OBJECTS = "Objects in the pipeline artifact bucket, which has no other content."
ARTIFACT_KEY = (
    "CDK grant on the artifact bucket KMS key. The action wildcard covers data "
    "key variants and the policy is scoped to that single key."
)
BUILD_LOGS = "CodeBuild writes logs and test reports only under its own project name."
ASSET_ROLE = (
    "CDK Pipelines creates the file asset role before the asset project exists, "
    "so it grants CodeBuild logs, reports and build control on every CodeBuild "
    "resource in the account and region. Accepted for a single-purpose lab account."
)


def _logical_id(construct: IConstruct) -> str:
    stack = Stack.of(construct)
    return stack.resolve(stack.get_logical_id(construct.node.default_child))


def _acknowledge(scope: IConstruct, findings: dict[str, str]) -> None:
    Validations.of(scope).acknowledge(
        *(
            Acknowledgment(id=f"AwsSolutions-IAM5[{finding}]", reason=reason)
            for finding, reason in findings.items()
        )
    )


def apply_to_pipeline(stack) -> None:
    pipeline = stack.pipeline
    logs_arn = f"arn:aws:logs:{stack.region}:{stack.account}:log-group:/aws/codebuild"
    reports_arn = f"arn:aws:codebuild:{stack.region}:{stack.account}:report-group"
    bucket = _logical_id(stack.artifact_bucket)

    read = {
        "Action::s3:GetBucket*": ARTIFACT_READ,
        "Action::s3:GetObject*": ARTIFACT_READ,
        "Action::s3:List*": ARTIFACT_READ,
        f"Resource::<{bucket}.Arn>/*": ARTIFACT_OBJECTS,
    }
    write = {
        "Action::s3:Abort*": ARTIFACT_WRITE,
        "Action::s3:DeleteObject*": ARTIFACT_WRITE,
    }
    key = {
        "Action::kms:GenerateDataKey*": ARTIFACT_KEY,
        "Action::kms:ReEncrypt*": ARTIFACT_KEY,
    }

    def project_logs(project) -> dict[str, str]:
        name = _logical_id(project)
        return {
            f"Resource::{logs_arn}/<{name}>:*": BUILD_LOGS,
            f"Resource::{reports_arn}/<{name}>-*": BUILD_LOGS,
        }

    # Pipeline role: also runs the source and approval actions.
    _acknowledge(pipeline.pipeline.role, read | write | key)

    # Synth project: pytest and cdk synth, writes the cloud assembly.
    _acknowledge(
        pipeline.synth_project.role,
        read | write | key | project_logs(pipeline.synth_project),
    )

    # Self-mutation project: runs cdk deploy on this stack.
    _acknowledge(
        pipeline.self_mutation_project.role,
        read
        | key
        | project_logs(pipeline.self_mutation_project)
        | {
            f"Resource::arn:*:iam::{stack.account}:role/*": (
                "Assumes only CDK bootstrap roles: the statement has a condition "
                "on the aws-cdk:bootstrap-role tag."
            ),
            "Resource::*": (
                "cloudformation:DescribeStacks and s3:ListBucket, needed by the "
                "CDK CLI before it assumes the bootstrap deploy role."
            ),
        },
    )

    # File asset publishing project, created by CDK Pipelines without a handle.
    assets_role = pipeline.node.find_child("Assets").node.find_child("FileRole")
    _acknowledge(
        assets_role,
        read
        | {
            f"Resource::{logs_arn}/*": ASSET_ROLE,
            f"Resource::{reports_arn}/*": ASSET_ROLE,
            "Resource::*": ASSET_ROLE,
        },
    )
