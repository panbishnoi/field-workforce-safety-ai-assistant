import os

from aws_cdk import (
    Stack,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_lambda_python_alpha as lambda_python,
    CfnOutput,
    Names,
    Duration,
    RemovalPolicy,
    aws_dynamodb as dynamodb,
    aws_cognito as cognito,
    aws_logs as logs
)
from constructs import Construct


import core_constructs as core

from cdk_nag import NagSuppressions, NagPackSuppression

class WebSocketApiStack(Construct):

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        agent_id:  str,
        agent_alias_id: str,        
        region: str,
        user_pool= str,
        client_id= str,
    ) -> None:
        super().__init__(scope, construct_id)

        # DynamoDB table to store the chat's memory
        web_socket_table = core.CoreTable(
            self,
            "WebSocketConnectionTable",
            table_name=f"{construct_id.lower()}-web-socket-connections",
            partition_key=dynamodb.Attribute(
                name="connectionId", type=dynamodb.AttributeType.STRING
            ),
            # CoreTable already sets removal_policy=RemovalPolicy.DESTROY
        )

        # Define function name first
        function_name = f"{construct_id.lower()}-safety-check"
        
        # Create explicit log group for emergency check request function
        safety_check_log_group = logs.LogGroup(
            self,
            "SafetyCheckLogGroup",
            log_group_name=f"/aws/lambda/{function_name}",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY
        )
        # a lambda function process the customer's question
        web_socket_fn = lambda_python.PythonFunction(
            self,
            "Websocket API",
            function_name=function_name,
            entry=f"{os.path.dirname(os.path.realpath(__file__))}/lambda",
            index="websocket.py",
            handler="lambda_handler",
            runtime=lambda_.Runtime.PYTHON_3_13,
            timeout=Duration.seconds(180),
            memory_size=512,
            environment={
                "WS_CONNECTION_TABLE_NAME": web_socket_table.table_name,  # Use the actual table name
                "CLIENT_ID": client_id,
                "USER_POOL_ID": user_pool,
                "REGION": region,
                "AGENT_ID": agent_id,
                "AGENT_ALIAS_ID": agent_alias_id,
            },
        )
        web_socket_fn.node.add_dependency(safety_check_log_group)
        web_socket_fn_policy = iam.Policy(
            self, 
            "WebSocketFnPolicy",
            # IAM policies don't have a removal policy
        )

        # Create ARNs for the resources
        user_pool_arn = f"arn:aws:cognito-idp:{region}:{Stack.of(self).account}:userpool/{user_pool}"
        agent_arn = f"arn:aws:bedrock:{region}:{Stack.of(self).account}:agent/{agent_id}"
        agent_alias_arn = f"arn:aws:bedrock:{region}:{Stack.of(self).account}:agent-alias/{agent_id}/{agent_alias_id}"
        
        web_socket_fn_policy.add_statements(
            iam.PolicyStatement(
                sid="DynamoDBAccess",
                effect=iam.Effect.ALLOW,
                actions=[
                    "dynamodb:BatchGetItem",
                    "dynamodb:GetItem",
                    "dynamodb:Query",
                    "dynamodb:Scan",
                    "dynamodb:PutItem",
                    "dynamodb:UpdateItem",
                    "dynamodb:DeleteItem"
                ],
                resources=[web_socket_table.table_arn],
            ),
            iam.PolicyStatement(
                sid="CloudWatchLogsAccess",
                effect=iam.Effect.ALLOW,
                actions=[
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                ],
                resources=[safety_check_log_group.log_group_arn],
            ),
            iam.PolicyStatement(
                sid="CognitoAccess",
                effect=iam.Effect.ALLOW,
                actions=[
                    "cognito-idp:DescribeUserPool",
                    "cognito-idp:DescribeUserPoolClient",
                    "cognito-idp:GetJWKS",
                ],
                resources=[user_pool_arn],
            ),
            iam.PolicyStatement(
                sid="BedrockAgentAccess",
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock:InvokeAgent",
                    "bedrock:GetAgent",
                ],
                resources=[
                    agent_arn,
                    agent_alias_arn
                ],
            ),
            iam.PolicyStatement(
                sid="BedrockModelAccess",
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock:InvokeModel",
                ],
                resources=["arn:aws:bedrock:*::foundation-model/*"],
            ),
        )

        # Attach the IAM policy to the Lambda function's role
        web_socket_fn.role.attach_inline_policy(web_socket_fn_policy)

        NagSuppressions.add_resource_suppressions(
            web_socket_fn_policy,
            [
                NagPackSuppression(
                    id="AwsSolutions-IAM5",
                    reason="This Lambda has wildcard permissions to allow choice of Bedrock, Dynamo and manage CloudWatch Logs log groups.",
                )
            ],
            True,
        )

        # create optimization job API method
        self.websocket_api = core.CoreWebSocketApiGateway(
            self, 
            "WebSocketApi",
            region=region,  # Use the provided region parameter instead of hardcoded value
            websocket_handler=web_socket_fn
        )
        
        # Expose the WebSocket API endpoint for other stacks to use
        self.websocket_api_endpoint = self.websocket_api.websocket_api_endpoint

        NagSuppressions.add_resource_suppressions(
            web_socket_fn,
            [
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": """Certain policies will implement wildcard permissions to expedite development. 
            TODO: Replace on Production environment (Path to Production)""",
                },
                {
                    "id": "AwsSolutions-IAM4",
                    "reason": """Prototype will use managed policies to expedite development. 
                        TODO: Replace on Production environment (Path to Production)""",
                    "appliesTo": [
                        "Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
                    ],
                },
                {
                    "id": "AwsSolutions-L1",
                    "reason": """Policy managed by AWS can not specify a different runtime version""",
                },
            ],
            True,
        )
