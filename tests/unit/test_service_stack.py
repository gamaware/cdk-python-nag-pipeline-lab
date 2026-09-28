import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Match, Template

from service.service_stack import ServiceStack


@pytest.fixture
def template(app) -> Template:
    stack = ServiceStack(
        app, "Service", env=cdk.Environment(account="123456789012", region="us-east-1")
    )
    return Template.from_stack(stack)


def test_buckets_block_public_access_and_are_encrypted(template):
    buckets = template.find_resources("AWS::S3::Bucket")
    assert len(buckets) == 2
    for bucket in buckets.values():
        props = bucket["Properties"]
        assert props["PublicAccessBlockConfiguration"] == {
            "BlockPublicAcls": True,
            "BlockPublicPolicy": True,
            "IgnorePublicAcls": True,
            "RestrictPublicBuckets": True,
        }
        assert "BucketEncryption" in props


def test_data_bucket_is_versioned_and_logged(template):
    template.has_resource_properties(
        "AWS::S3::Bucket",
        {
            "VersioningConfiguration": {"Status": "Enabled"},
            "LoggingConfiguration": Match.object_like({"LogFilePrefix": "data-bucket/"}),
        },
    )


def test_bucket_policies_deny_insecure_transport(template):
    policies = template.find_resources("AWS::S3::BucketPolicy")
    assert len(policies) == 2
    for policy in policies.values():
        statements = policy["Properties"]["PolicyDocument"]["Statement"]
        assert any(
            s["Effect"] == "Deny"
            and s.get("Condition") == {"Bool": {"aws:SecureTransport": "false"}}
            for s in statements
        )


def test_function_uses_current_python_runtime(template):
    template.has_resource_properties(
        "AWS::Lambda::Function", {"Runtime": "python3.14", "Handler": "handler.handler"}
    )


def test_function_role_has_no_managed_policies_or_wildcards(template):
    roles = template.find_resources(
        "AWS::IAM::Role",
        {
            "Properties": {
                "AssumeRolePolicyDocument": Match.object_like(
                    {
                        "Statement": [
                            Match.object_like({"Principal": {"Service": "lambda.amazonaws.com"}})
                        ]
                    }
                )
            }
        },
    )
    function_role = next(
        r for r in roles.values() if "Least-privilege" in r["Properties"].get("Description", "")
    )
    assert "ManagedPolicyArns" not in function_role["Properties"]

    policies = template.find_resources("AWS::IAM::Policy")
    function_policy = next(p for name, p in policies.items() if name.startswith("FunctionRole"))
    for statement in function_policy["Properties"]["PolicyDocument"]["Statement"]:
        actions = statement["Action"]
        actions = actions if isinstance(actions, list) else [actions]
        assert all("*" not in action for action in actions)
        assert statement["Resource"] != "*"


def test_api_method_requires_iam_auth(template):
    template.has_resource_properties(
        "AWS::ApiGateway::Method",
        {"HttpMethod": "GET", "AuthorizationType": "AWS_IAM"},
    )


def test_api_stage_has_access_logs_and_tracing(template):
    template.has_resource_properties(
        "AWS::ApiGateway::Stage",
        {
            "StageName": "v1",
            "TracingEnabled": True,
            "AccessLogSetting": Match.object_like({"DestinationArn": Match.any_value()}),
        },
    )


def test_log_groups_have_retention(template):
    template.all_resources_properties("AWS::Logs::LogGroup", {"RetentionInDays": 30})
