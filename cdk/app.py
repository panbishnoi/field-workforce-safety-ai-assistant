#!/usr/bin/env python3

# Copyright 2022 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: LicenseRef-.amazon.com.-AmznSL-1.0
# Licensed under the Amazon Software License  http://aws.amazon.com/asl/

import aws_cdk as cdk
from aws_cdk import (
    Stack,
    NestedStack,
    CfnParameter,
    CfnOutput
)
from constructs import Construct
from cdk_nag import AwsSolutionsChecks, NagSuppressions, NagPackSuppression

# Import nested stack classes directly from their respective modules
from bedrock_agents import BedrockAgentsStack
from backend import BackendStack
from webappstack import FrontendStack

class FieldWorkforceSafetyParentStack(Stack):
    """Parent stack that contains all nested stacks"""
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Add stack-level NAG suppressions for common patterns
        NagSuppressions.add_stack_suppressions(
            self,
            [
                NagPackSuppression(
                    id="AwsSolutions-IAM5",
                    reason="Custom resources and CDK constructs require certain IAM permissions with wildcards"
                ),
                NagPackSuppression(
                    id="AwsSolutions-IAM4",
                    reason="Using AWS managed policies is acceptable for this demo application"
                ),
                NagPackSuppression(
                    id="AwsSolutions-L1",
                    reason="CDK BucketDeployment construct uses a Lambda function with a runtime managed by CDK that we cannot directly control"
                ),
            ]
        )

        # Get configuration parameters from context
        deploy_frontend = self.node.try_get_context("deploy_frontend")
        if deploy_frontend is None:
            deploy_frontend = "yes"

        # Get configuration parameters from context
        openweather_api_key = self.node.try_get_context("openweather_api_key")
        if openweather_api_key is None:
            openweather_api_key = "dummy_key"  # Provide a default value

        # Get foundation model parameters from context
        collaborator_foundation_model = self.node.try_get_context("collaborator_foundation_model")
        if collaborator_foundation_model is None:
            collaborator_foundation_model = "anthropic.claude-3-sonnet-20240229-v1:0"

        supervisor_foundation_model = self.node.try_get_context("supervisor_foundation_model")
        if supervisor_foundation_model is None:
            supervisor_foundation_model = "anthropic.claude-3-sonnet-20240229-v1:0"

        # Default language
        language_code = "en"

        # Deploy Bedrock Agents nested stack (always deployed)
        bedrock_agents_stack = BedrockAgentsStack(
            self,
            "BedrockAgentStack",
            collaborator_foundation_model=collaborator_foundation_model,
            supervisor_foundation_model=supervisor_foundation_model,
            openweather_api_key=openweather_api_key
        )

        # Conditionally deploy Backend and Frontend stacks based on the single parameter
        if deploy_frontend.lower() == "yes":
            # Deploy Backend stack
            backend_stack = BackendStack(
                self,
                "BackendAPIStack",
                language_code=language_code,
                agent_id=bedrock_agents_stack.supervisor_agent_id,
                agent_alias_id=bedrock_agents_stack.supervisor_agent_alias_id,
                work_order_table_name=bedrock_agents_stack.work_orders_table_name,
                location_table_name=bedrock_agents_stack.locations_table_name,
            )
            # Add dependency to ensure Bedrock Agents stack is created first
            backend_stack.add_dependency(bedrock_agents_stack)

            # Deploy Frontend stack
            frontend_stack = FrontendStack(
                self,
                "FrontendStack",
                api_endpoint=backend_stack.api_endpoint,
                workorder_api_endpoint=backend_stack.workorder_api_endpoint,
                websocket_api_endpoint=backend_stack.websocket_api_endpoint,
                region_name=backend_stack.region_name,
                cognito_user_pool_id=backend_stack.user_pool_id,
                cognito_user_pool_client_id=backend_stack.user_pool_client_id,
                cognito_identity_pool_id=backend_stack.identity_pool_id
            )
            # Add dependency to ensure Backend stack is created first
            frontend_stack.add_dependency(backend_stack)

            # Add output for webapp url
            CfnOutput(
                self,
                "FrontendUrl",
                value=frontend_stack.frontend_url,
                description="Frontend App Access URL"
            )

# Create the app and deploy the parent stack
app = cdk.App()
parent_stack = FieldWorkforceSafetyParentStack(app, "FieldWorkforceSafetyParentStack")
cdk.Aspects.of(app).add(AwsSolutionsChecks())
app.synth()
