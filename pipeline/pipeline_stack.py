"""Self-mutating CDK Pipelines pipeline: source, synth, dev, approval, prod."""

import shlex

from aws_cdk import Environment, RemovalPolicy, Stack, Stage, pipelines
from aws_cdk import aws_codepipeline as codepipeline
from aws_cdk import aws_kms as kms
from aws_cdk import aws_s3 as s3
from constructs import Construct

from pipeline import nag_suppressions
from service.service_stack import ServiceStack

CDK_CLI_VERSION = "2.1143.0"
UV_VERSION = "0.12.19"


class ServiceStage(Stage):
    """One deployable copy of the workload."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self.service = ServiceStack(self, "Service")


class PipelineStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        repository: str,
        branch: str,
        connection_arn: str,
        synth_context: dict[str, str],
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # A customer managed key on the artifact bucket also encrypts every
        # CodeBuild project the pipeline creates (AwsSolutions-CB4).
        artifact_key = kms.Key(
            self,
            "ArtifactKey",
            enable_key_rotation=True,
            removal_policy=RemovalPolicy.DESTROY,
        )
        access_logs = s3.Bucket(
            self,
            "AccessLogsBucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            object_ownership=s3.ObjectOwnership.BUCKET_OWNER_ENFORCED,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )
        self.artifact_bucket = s3.Bucket(
            self,
            "ArtifactBucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.KMS,
            encryption_key=artifact_key,
            enforce_ssl=True,
            server_access_logs_bucket=access_logs,
            server_access_logs_prefix="artifacts/",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        source = pipelines.CodePipelineSource.connection(
            repository, branch, connection_arn=connection_arn
        )
        context_args = " ".join(
            f"-c {shlex.quote(f'{key}={value}')}" for key, value in sorted(synth_context.items())
        )

        self.pipeline = pipelines.CodePipeline(
            self,
            "Pipeline",
            pipeline_name="cdk-nag-lab",
            pipeline_type=codepipeline.PipelineType.V2,
            artifact_bucket=self.artifact_bucket,
            self_mutation=True,
            use_pipeline_role_for_actions=True,
            publish_assets_in_parallel=False,
            synth=pipelines.ShellStep(
                "Synth",
                input=source,
                install_commands=[f"pip install uv=={UV_VERSION}", "uv sync --frozen"],
                commands=[
                    "uv run pytest",
                    f"npx aws-cdk@{CDK_CLI_VERSION} synth {context_args}",
                ],
            ),
        )

        env = Environment(account=self.account, region=self.region)
        self.pipeline.add_stage(ServiceStage(self, "Dev", env=env))
        self.pipeline.add_stage(
            ServiceStage(self, "Prod", env=env),
            pre=[pipelines.ManualApprovalStep("PromoteToProd")],
        )

        # The pipeline's roles and projects only exist after build_pipeline().
        self.pipeline.build_pipeline()
        nag_suppressions.apply_to_pipeline(self)
