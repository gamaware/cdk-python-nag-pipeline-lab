"""Sample workload: an S3 bucket read by a Lambda function behind API Gateway."""

from pathlib import Path

from aws_cdk import Acknowledgment, Duration, RemovalPolicy, Stack, Validations
from aws_cdk import aws_apigateway as apigw
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from aws_cdk import aws_s3 as s3
from constructs import Construct

RUNTIME_DIR = Path(__file__).parent / "runtime"
API_CLOUDWATCH_POLICY = (
    "Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AmazonAPIGatewayPushToCloudWatchLogs"
)


class ServiceStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

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

        self.data_bucket = s3.Bucket(
            self,
            "DataBucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            versioned=True,
            server_access_logs_bucket=access_logs,
            server_access_logs_prefix="data-bucket/",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        function_logs = logs.LogGroup(
            self,
            "FunctionLogs",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Explicit role with inline, resource-scoped permissions instead of the
        # AWSLambdaBasicExecutionRole managed policy.
        function_role = iam.Role(
            self,
            "FunctionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Least-privilege role for the sample function",
        )
        function_role.add_to_policy(
            iam.PolicyStatement(
                actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                resources=[function_logs.log_group_arn],
            )
        )
        function_role.add_to_policy(
            iam.PolicyStatement(
                actions=["s3:ListBucket"],
                resources=[self.data_bucket.bucket_arn],
            )
        )

        self.function = lambda_.Function(
            self,
            "Function",
            runtime=lambda_.Runtime.PYTHON_3_14,
            handler="handler.handler",
            code=lambda_.Code.from_asset(str(RUNTIME_DIR)),
            role=function_role,
            log_group=function_logs,
            memory_size=128,
            timeout=Duration.seconds(10),
            environment={"BUCKET_NAME": self.data_bucket.bucket_name},
        )

        api_logs = logs.LogGroup(
            self,
            "ApiAccessLogs",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Accepted findings are acknowledged next to the resource they cover.
        # cdk-nag fails synth on any finding that is not acknowledged here.
        self.api = apigw.LambdaRestApi(
            self,
            "Api",
            handler=self.function,
            proxy=False,
            # The logging role is an account and region setting shared by the Dev
            # and Prod stages, so it is retained when either stack is deleted.
            cloud_watch_role=True,
            deploy_options=apigw.StageOptions(
                stage_name="v1",
                access_log_destination=apigw.LogGroupLogDestination(api_logs),
                access_log_format=apigw.AccessLogFormat.json_with_standard_fields(
                    caller=False,
                    http_method=True,
                    ip=True,
                    protocol=True,
                    request_time=True,
                    resource_path=True,
                    response_length=True,
                    status=True,
                    user=False,
                ),
                logging_level=apigw.MethodLoggingLevel.ERROR,
                tracing_enabled=True,
                throttling_burst_limit=10,
                throttling_rate_limit=5,
            ),
        )
        Validations.of(self.api.node.find_child("CloudWatchRole")).acknowledge(
            Acknowledgment(
                id=f"AwsSolutions-IAM4[{API_CLOUDWATCH_POLICY}]",
                reason=(
                    "AWS managed policy documented for the account-level API "
                    "Gateway logging role. It grants only CloudWatch Logs writes."
                ),
            )
        )
        Validations.of(self.api.deployment_stage).acknowledge(
            Acknowledgment(
                id="AwsSolutions::AwsSolutions-APIG3",
                reason=(
                    "Lab endpoint with IAM auth and stage throttling. AWS WAF adds "
                    "a monthly web ACL charge that the lab does not justify."
                ),
            )
        )

        validator = self.api.add_request_validator(
            "RequestValidator",
            validate_request_body=True,
            validate_request_parameters=True,
        )
        method = self.api.root.add_resource("objects").add_method(
            "GET",
            authorization_type=apigw.AuthorizationType.IAM,
            request_validator=validator,
        )
        Validations.of(method).acknowledge(
            Acknowledgment(
                id="AwsSolutions::AwsSolutions-COG4",
                reason=(
                    "The method uses IAM (SigV4) authorization. Callers are AWS "
                    "principals, so a Cognito user pool authorizer does not apply."
                ),
            )
        )
