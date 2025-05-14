# Copyright 2022 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: LicenseRef-.amazon.com.-AmznSL-1.0
# Licensed under the Amazon Software License  http://aws.amazon.com/asl/

from aws_cdk import (
    Stack,
    NestedStack,
    CfnOutput,
    aws_dynamodb as dynamodb,
    aws_iam as iam,
    RemovalPolicy,
)
from constructs import Construct

import core_constructs as coreconstructs
from .workorderlistflow import WorkOrderApiStack
from .vicemergencyflow import VicEmergencyStack
from .safetycheckflow import WebSocketApiStack

EMBEDDINGS_SIZE = 512


class BackendStack(NestedStack):
    """Nested stack for Backend functionality"""
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        agent_id:  str,
        agent_alias_id: str,
        work_order_table_name:  str,
        location_table_name: str,
        language_code: str = "en",
        **kwargs
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.cognito = coreconstructs.CoreCognito(
            self,
            "Cognito",
            region=self.region,
        )
        self.apigw = coreconstructs.CoreApiGateway(
            self,
            "ApiGateway",
            region=self.region,
            user_pool=self.cognito.user_pool,
        )

        # APIGW for workorder list
        self.apigw_workorder = coreconstructs.CoreApiGateway(
            self,
            "WorkOrderApiGateway",
            region=self.region,
            user_pool=self.cognito.user_pool,
        )

        # Fetch WorkOrders flow
        self.workorder_workflow = WorkOrderApiStack(
            self,
            "WorkOrdersAPI",
            api_gateway=self.apigw_workorder,
            dynamo_db_workorder_table=work_order_table_name,
            dynamo_db_location_table=location_table_name
        )

        # Emergency Warnings flow
        self.vicemergencyStack = VicEmergencyStack(
            self,
            "VicEmergencyStack",
            api_gateway=self.apigw,
            dynamo_db_workorder_table=work_order_table_name,
        )
        
        # WebSocket API for real-time safety check
        self.websocket_api_stack = WebSocketApiStack(
            self,
            "WebSocketApiStack",
            agent_id=agent_id,
            agent_alias_id=agent_alias_id,
            region=self.region,
            user_pool=self.cognito.user_pool.user_pool_id,
            client_id=self.cognito.user_pool_client.user_pool_client_id,
            work_order_table_name=work_order_table_name,
        )

        # Store outputs as properties for easy access by the frontend stack
        self.api_endpoint = self.apigw.rest_api.url
        self.workorder_api_endpoint = self.apigw_workorder.rest_api.url
        self.websocket_api_endpoint = self.websocket_api_stack.websocket_api_endpoint
        self.region_name = self.region
        self.user_pool_id = self.cognito.user_pool.user_pool_id
        self.user_pool_client_id = self.cognito.user_pool_client.user_pool_client_id
        self.identity_pool_id = self.cognito.identity_pool.ref

        # Export all required outputs for frontend
        CfnOutput(
            self,
            "RegionName",
            value=self.region_name,
            export_name=f"{Stack.of(self).stack_name}RegionName",
        )
        
        CfnOutput(
            self,
            "ApiGatewayRestApiEndpoint",
            value=self.api_endpoint,
            export_name=f"{Stack.of(self).stack_name}ApiEndpoint",
        )
        
        CfnOutput(
            self,
            "WorkOrderApiEndpoint",
            value=self.workorder_api_endpoint,
            export_name=f"{Stack.of(self).stack_name}WorkOrderApiEndpoint",
        )
        
        CfnOutput(
            self,
            "WebSocketApiEndpoint",
            value=self.websocket_api_endpoint,
            export_name=f"{Stack.of(self).stack_name}WebSocketApiEndpoint",
        )
        
        CfnOutput(
            self,
            "CognitoUserPoolId",
            value=self.user_pool_id,
            export_name=f"{Stack.of(self).stack_name}UserPoolId",
        )
        
        CfnOutput(
            self,
            "CognitoUserPoolClientId",
            value=self.user_pool_client_id,
            export_name=f"{Stack.of(self).stack_name}UserPoolClientId",
        )
        
        CfnOutput(
            self,
            "CognitoIdentityPoolId",
            value=self.identity_pool_id,
            export_name=f"{Stack.of(self).stack_name}IdentityPoolId",
        )
