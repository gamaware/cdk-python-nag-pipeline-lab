# Reading cdk-nag findings

## Anatomy of a finding

```text
ERROR The IAM entity contains wildcard permissions ... (AwsSolutions)
   NagLabPipeline/Pipeline/UpdatePipeline/SelfMutation/Role/DefaultPolicy/Resource aws-cdk-lib.aws_iam.CfnPolicy
   Acknowledge with 'AwsSolutions-IAM5[Resource::*]'
```

- **Level and rule text**: `ERROR` findings fail synth. The rule ID (`AwsSolutions-IAM5`) links to the rule in the
  [cdk-nag rules list](https://github.com/cdklabs/cdk-nag/blob/main/RULES.md).
- **Construct path**: where the resource lives in the construct tree. Use it to find the code that created it.
- **Acknowledge ID**: the exact ID to pass to `Validations.of(construct).acknowledge(...)`. Granular rules such as
  IAM5 add the specific action or resource in brackets, so each wildcard is accepted one by one.

After a failed synth, the full report is in `cdk.out/validation-report.json`.

## Fix first

Most findings have a direct fix, and that is the default:

| Rule | Typical fix |
| --- | --- |
| S1 | `server_access_logs_bucket=...` on the bucket |
| S10 | `enforce_ssl=True` |
| IAM4 | replace the AWS managed policy with an inline, resource-scoped statement |
| L1 | use the latest runtime for the language |
| CB4 | give the pipeline artifact bucket a customer managed KMS key |
| APIG2 | add a request validator |

## When an acknowledgment is acceptable

Acknowledge a finding only when all of these hold:

1. The control does not apply, or a compensating control covers the same risk (for example IAM authorization instead
   of a Cognito authorizer).
2. The reason names that control or the scope that limits the risk. "Not needed" is not a reason.
3. The acknowledgment targets the single construct, and for granular rules the single finding ID. Stack-wide or
   app-wide acknowledgments hide future findings of the same rule.

Put the acknowledgment next to the resource. For resources that a library generates, such as the IAM roles CDK
Pipelines creates, keep them in one module (`pipeline/nag_suppressions.py`) that explains which construct owns each
finding.

## Where the acknowledgments in this repository live

| Finding | Location | Why it is accepted |
| --- | --- | --- |
| IAM4 on the API Gateway CloudWatch role | `service/service_stack.py` | documented AWS managed policy, logs write only |
| APIG3 on the API stage | `service/service_stack.py` | lab cost; IAM auth and throttling are in place |
| COG4 on the GET method | `service/service_stack.py` | IAM (SigV4) authorization instead of Cognito |
| IAM5 on CDK Pipelines roles | `pipeline/nag_suppressions.py` | generated grants; each reason states its real scope |
