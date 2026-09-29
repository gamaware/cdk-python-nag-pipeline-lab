import pytest
from aws_cdk.assertions import Match, Template

from app import build_app


@pytest.fixture
def template(app) -> Template:
    return Template.from_stack(build_app(app))


def stage_names(template: Template) -> list[str]:
    pipeline = next(iter(template.find_resources("AWS::CodePipeline::Pipeline").values()))
    return [stage["Name"] for stage in pipeline["Properties"]["Stages"]]


def test_stage_order(template):
    assert stage_names(template) == ["Source", "Build", "UpdatePipeline", "Assets", "Dev", "Prod"]


def test_prod_starts_with_manual_approval(template):
    pipeline = next(iter(template.find_resources("AWS::CodePipeline::Pipeline").values()))
    prod = next(s for s in pipeline["Properties"]["Stages"] if s["Name"] == "Prod")
    first = min(prod["Actions"], key=lambda action: action["RunOrder"])
    assert first["ActionTypeId"]["Category"] == "Approval"
    assert first["Name"] == "PromoteToProd"


def test_source_is_codestar_connection_from_context(template):
    template.has_resource_properties(
        "AWS::CodePipeline::Pipeline",
        {
            "PipelineType": "V2",
            "Stages": Match.array_with(
                [
                    Match.object_like(
                        {
                            "Name": "Source",
                            "Actions": [
                                Match.object_like(
                                    {
                                        "ActionTypeId": Match.object_like(
                                            {"Provider": "CodeStarSourceConnection"}
                                        ),
                                        "Configuration": Match.object_like(
                                            {
                                                "ConnectionArn": Match.string_like_regexp(
                                                    "connection/0{8}-"
                                                ),
                                                "FullRepositoryId": (
                                                    "example-org/cdk-python-nag-pipeline-lab"
                                                ),
                                                "BranchName": "main",
                                            }
                                        ),
                                    }
                                )
                            ],
                        }
                    )
                ]
            ),
        },
    )


def test_artifact_bucket_uses_rotating_kms_key(template):
    template.has_resource_properties("AWS::KMS::Key", {"EnableKeyRotation": True})
    template.has_resource_properties(
        "AWS::S3::Bucket",
        {
            "BucketEncryption": {
                "ServerSideEncryptionConfiguration": [
                    Match.object_like(
                        {
                            "ServerSideEncryptionByDefault": Match.object_like(
                                {"SSEAlgorithm": "aws:kms"}
                            )
                        }
                    )
                ]
            }
        },
    )


def test_synth_step_runs_tests_before_cdk_synth(template):
    projects = template.find_resources("AWS::CodeBuild::Project")
    buildspecs = [p["Properties"]["Source"]["BuildSpec"] for p in projects.values()]
    synth = next(spec for spec in buildspecs if "uv run pytest" in spec)
    assert synth.index("uv run pytest") < synth.index("synth -c")


def _statements(template: Template, role_prefix: str) -> list[dict]:
    policies = template.find_resources("AWS::IAM::Policy")
    return [
        statement
        for name, policy in policies.items()
        if name.startswith(role_prefix)
        for statement in policy["Properties"]["PolicyDocument"]["Statement"]
    ]


def test_asset_role_cannot_start_or_stop_builds(template):
    denies = [s for s in _statements(template, "PipelineAssetsFileRole") if s["Effect"] == "Deny"]
    assert len(denies) == 1
    assert set(denies[0]["Action"]) == {
        "codebuild:StartBuild",
        "codebuild:StartBuildBatch",
        "codebuild:RetryBuild",
        "codebuild:RetryBuildBatch",
        "codebuild:StopBuild",
        "codebuild:StopBuildBatch",
    }
    assert denies[0]["Resource"] == "*"


def test_pipeline_role_can_use_the_connection_under_both_prefixes(template):
    actions = {
        action
        for statement in _statements(template, "PipelineRoleDefaultPolicy")
        if statement["Effect"] == "Allow"
        for action in (
            statement["Action"] if isinstance(statement["Action"], list) else [statement["Action"]]
        )
        if "UseConnection" in action
    }
    assert actions == {"codestar-connections:UseConnection", "codeconnections:UseConnection"}


def test_api_gateway_logging_setting_is_owned_once_by_the_pipeline_stack(template):
    template.resource_count_is("AWS::ApiGateway::Account", 1)
