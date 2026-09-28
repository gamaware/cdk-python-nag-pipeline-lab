# Architecture decision records

Architecture decision records follow the *Fundamentals of Software Architecture* (2nd ed.) format. The Compliance
section says how each decision is checked, automated where possible.

| Number | Title | Status |
| --- | --- | --- |
| [0001](0001-cdk-nag-as-a-synth-gate.md) | Run cdk-nag as a validation plugin that fails synth | Accepted |
| [0002](0002-acknowledgments-next-to-the-resource.md) | Acknowledge each accepted finding on its construct, with a reason | Accepted |
| [0003](0003-shared-settings-owned-once.md) | Keep account-wide settings in the pipeline stack, and grant the connection under both prefixes | Accepted |

To add a record, copy the section headings of an existing one, take the next number, and link it here.
