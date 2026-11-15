"""AuthStack: the Identity_Provider (Cognito user pool and public app client), Req. 22.2, 22.3.

Email sign-in, no self-service sign-up (the jury gets a pre-created demo user), and an app client
without a secret that uses the authorization code grant with PKCE. Outputs the identifiers the UI
reads from ``config.json`` and the Session_API authorizer uses. No credentials are stored here.
"""
from __future__ import annotations

from typing import Sequence

from aws_cdk import CfnOutput, Duration, RemovalPolicy, Stack, aws_cognito as cognito
from constructs import Construct

DEFAULT_CALLBACK_URLS = ("http://localhost:5173/",)


class AuthStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        callback_urls: Sequence[str] = DEFAULT_CALLBACK_URLS,
        logout_urls: Sequence[str] | None = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)
        callbacks = list(callback_urls)
        self.user_pool = cognito.UserPool(
            self,
            "UserPool",
            user_pool_name="guide-users",
            self_sign_up_enabled=False,
            sign_in_aliases=cognito.SignInAliases(email=True, username=False),
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            standard_attributes=cognito.StandardAttributes(
                email=cognito.StandardAttribute(required=True, mutable=True)
            ),
            password_policy=cognito.PasswordPolicy(
                min_length=12,
                require_lowercase=True,
                require_uppercase=True,
                require_digits=True,
                require_symbols=True,
                temp_password_validity=Duration.days(7),
            ),
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            mfa=cognito.Mfa.OFF,
            removal_policy=RemovalPolicy.DESTROY,
        )
        self.user_pool_client = self.user_pool.add_client(
            "AppClient",
            user_pool_client_name="guide-ui",
            generate_secret=False,
            auth_flows=cognito.AuthFlow(user_srp=True),
            prevent_user_existence_errors=True,
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(authorization_code_grant=True, implicit_code_grant=False),
                scopes=[cognito.OAuthScope.OPENID, cognito.OAuthScope.EMAIL],
                callback_urls=callbacks,
                logout_urls=list(logout_urls) if logout_urls is not None else callbacks,
            ),
            access_token_validity=Duration.hours(1),
            id_token_validity=Duration.hours(1),
            refresh_token_validity=Duration.days(1),
            enable_token_revocation=True,
        )
        CfnOutput(self, "UserPoolId", value=self.user_pool.user_pool_id)
        CfnOutput(self, "UserPoolArn", value=self.user_pool.user_pool_arn)
        CfnOutput(self, "UserPoolClientId", value=self.user_pool_client.user_pool_client_id)
