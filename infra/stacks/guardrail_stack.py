"""Optional GuardrailStack: Bedrock Guardrail ``verdict-guardrail``.

For the hackathon the Guardrail already exists (created with the CLI; its ID is in
``config.yaml``, version DRAFT), so this stack is optional and is not wired into
``infra/app.py`` by default. Output-only denied topics block instructions to place or
simulate orders, transfers, or brokerage or bank actions, and return predictions. A HIGH
prompt-attack filter applies to input. There is no personalized-advice topic: it blocked
valid demo verdicts, and the code-side guidance-only check covers that wording.
"""
from __future__ import annotations

from aws_cdk import CfnOutput, Stack, aws_bedrock as bedrock
from constructs import Construct

BLOCKED_MESSAGE = (
    "The Guide_System only provides guidance in a simulation. It never places, routes, or "
    "triggers an order, transfer, or brokerage or bank action, and it makes no return prediction."
)

DENIED_TOPICS = (
    {
        "name": "RealTransactions",
        "definition": (
            "Instructions to place, route, prefill, trigger, or simulate the execution of an order, "
            "transfer, or brokerage or bank action."
        ),
        "examples": [
            "Place a market order to buy 100 shares of XEQT now.",
            "Transfer 5,000 CAD from your chequing account to your brokerage account.",
            "Log in to your broker and sell the position today.",
        ],
    },
    {
        "name": "ReturnPredictions",
        "definition": "Statements that predict or promise a future return, price, or market level.",
        "examples": [
            "This portfolio will return 9 percent next year.",
            "The stock will double within two years.",
            "You are guaranteed to beat the market.",
        ],
    },
)


class GuardrailStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self.guardrail = bedrock.CfnGuardrail(
            self,
            "VerdictGuardrail",
            name="verdict-guardrail",
            description="Guidance-only guardrail for the Guide_System: no transactions, no predictions.",
            blocked_input_messaging=BLOCKED_MESSAGE,
            blocked_outputs_messaging=BLOCKED_MESSAGE,
            topic_policy_config=bedrock.CfnGuardrail.TopicPolicyConfigProperty(
                topics_config=[
                    bedrock.CfnGuardrail.TopicConfigProperty(
                        name=t["name"],
                        definition=t["definition"],
                        examples=t["examples"],
                        type="DENY",
                        input_action="NONE",
                        input_enabled=False,
                        output_action="BLOCK",
                        output_enabled=True,
                    )
                    for t in DENIED_TOPICS
                ]
            ),
            content_policy_config=bedrock.CfnGuardrail.ContentPolicyConfigProperty(
                filters_config=[
                    bedrock.CfnGuardrail.ContentFilterConfigProperty(
                        type="PROMPT_ATTACK",
                        input_strength="HIGH",
                        output_strength="NONE",
                        input_action="BLOCK",
                        input_enabled=True,
                        output_enabled=False,
                    )
                ]
            ),
        )
        CfnOutput(self, "GuardrailId", value=self.guardrail.attr_guardrail_id)
        CfnOutput(self, "GuardrailArn", value=self.guardrail.attr_guardrail_arn)
