# 0003. Keep account-wide settings in the pipeline stack, and grant the connection under both prefixes

## Status

Accepted

## Context

The Dev and Prod stages deploy the same workload stack to the same account and region. API Gateway logging needs an
account-level CloudWatch Logs role (`AWS::ApiGateway::Account`), which is one setting per account and region. With
`cloud_watch_role=True` on each REST API, both stage stacks would own that setting and overwrite each other's role.

The pipeline reads source through a CodeConnections connection. CDK Pipelines grants
`codestar-connections:UseConnection` only, while AWS documents `codeconnections:UseConnection` as well for
connections created under the new service name.

## Decision

- The pipeline stack, deployed once per account and region, owns the API Gateway logging role and
  `AWS::ApiGateway::Account`. The workload stack sets `cloud_watch_role=False`.
- The logging role keeps the AWS managed policy `AmazonAPIGatewayPushToCloudWatchLogs`, acknowledged with a reason
  that states its real scope: create, write and read CloudWatch Logs in the account.
- The pipeline role gets `codeconnections:UseConnection` on the one connection ARN, next to the generated grant.

## Consequences

- Deleting a stage stack no longer changes API Gateway logging for the other stage.
- The stage stacks depend on the pipeline stack having set the logging role. The pipeline stack is always deployed
  first (by hand, then by self-mutation), so the order holds.
- Deleting the pipeline stack removes the logging role; API Gateway then keeps a role ARN that no longer exists
  until another stack or a person sets it.

## Compliance

Automated in `tests/unit/test_pipeline_stack.py` and `tests/unit/test_service_stack.py`: one
`AWS::ApiGateway::Account` in the pipeline stack, none in the workload stack, and both `UseConnection` actions on
the pipeline role.

## Notes

- [AWS::ApiGateway::Account](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-apigateway-account.html).
