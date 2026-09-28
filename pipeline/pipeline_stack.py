"""Self-mutating CDK Pipelines pipeline: source, synth, dev, approval, prod."""

import shlex

from aws_cdk import Environment, RemovalPolicy, Stack, Stage, pipelines
from aws_cdk import aws_apigateway as apigw
from aws_cdk import aws_codepipeline as codepipeline
from aws_cdk import aws_iam as iam
from aws_cdk import aws_kms as kms
from aws_cdk import aws_s3 as s3
from constructs import Construct

from pipeline import nag_suppressions
from service.service_stack import ServiceStack

CDK_CLI_VERSION = "2.1143.0"
UV_VERSION = "0.12.19"
# Build control the asset publishing role never needs. CDK Pipelines grants
# StartBuild on every project, which would let that role run the self-mutation
# project, and its deploy access, with overridden commands.
BUILD_CONTROL = [
    "codebuild:StartBuild",
    "codebuild:StartBuildBatch",
    "codebuild:RetryBuild",
    "codebuild:RetryBuildBatch",
    "codebuild:StopBuild",
    "codebuild:StopBuildBatch",
]


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
                    f"npx --yes aws-cdk@{CDK_CLI_VERSION} synth {context_args}",
                ],
            ),
        )

        env = Environment(account=self.account, region=self.region)
        self.pipeline.add_stage(ServiceStage(self, "Dev", env=env))
        self.pipeline.add_stage(
            ServiceStage(self, "Prod", env=env),
            pre=[pipelines.ManualApprovalStep("PromoteToProd")],
        )

        # API Gateway logging is one setting per account and region. It lives in
        # this stack, deployed once, so the Dev and Prod stages do not both own it.
        self.api_logging_role = iam.Role(
            self,
            "ApiGatewayLoggingRole",
            assumed_by=iam.ServicePrincipal("apigateway.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AmazonAPIGatewayPushToCloudWatchLogs"
                )
            ],
        )
        apigw.CfnAccount(
            self,
            "ApiGatewayAccount",
            cloud_watch_role_arn=self.api_logging_role.role_arn,
        )

        # The pipeline's roles and projects only exist after build_pipeline().
        self.pipeline.build_pipeline()

        # CDK Pipelines grants the legacy codestar-connections action only. AWS
        # documents codeconnections:UseConnection as well for the same connection.
        self.pipeline.pipeline.role.add_to_principal_policy(
            iam.PolicyStatement(
                actions=["codeconnections:UseConnection"],
                resources=[connection_arn],
            )
        )
        assets_role = self.pipeline.node.find_child("Assets").node.find_child("FileRole")
        assets_role.add_to_principal_policy(
            iam.PolicyStatement(effect=iam.Effect.DENY, actions=BUILD_CONTROL, resources=["*"])
        )
        nag_suppressions.apply_to_pipeline(self)
