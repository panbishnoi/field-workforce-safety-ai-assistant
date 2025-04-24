import os
from aws_cdk import (
    Stack,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_s3 as s3,
    aws_s3_deployment as s3deploy,
    aws_dynamodb as dynamodb,
    CfnOutput,
    Duration,
    RemovalPolicy,
    aws_bedrock as bedrock,
    aws_logs as logs,
    CustomResource,
)
from constructs import Construct
from cdk_nag import NagSuppressions, NagPackSuppression


class BedrockAgentsStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        collaborator_foundation_model: str,
        supervisor_foundation_model: str,
        openweather_api_key: str,
        **kwargs
    ) -> None:
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
                )
            ]
        )

        # Create S3 Bucket for CSV files
        data_bucket = s3.Bucket(
            self,
            f"{self.stack_name}-DataBucket",
            versioned=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,  # Enable auto-deletion of objects when bucket is deleted
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,  # Enforce SSL for all requests
        )
        
        # Add NAG suppression for S3 bucket server access logs
        NagSuppressions.add_resource_suppressions(
            data_bucket,
            [
                NagPackSuppression(
                    id="AwsSolutions-S1",
                    reason="Server access logs are not required for this demo bucket as it only contains sample data files"
                )
            ]
        )

        # Deploy CSV files from local data directory to S3 bucket
        data_deployment = s3deploy.BucketDeployment(
             self,
             f"{self.stack_name}-DeployCSVFiles",
             sources=[s3deploy.Source.asset("../data", exclude=["**/*", "!**/*.csv"])],
             destination_bucket=data_bucket,
             log_retention=logs.RetentionDays.ONE_WEEK,
             memory_limit=512
        )
        
        # The stack-level suppression will handle the L1 error for the BucketDeployment Lambda
        # We need to add a specific suppression for the IAM5 error on this resource
        NagSuppressions.add_resource_suppressions(
            data_deployment,
            [
                NagPackSuppression(
                    id="AwsSolutions-IAM5",
                    reason="The BucketDeployment construct requires s3:DeleteObject* permissions to clean up files during deployment"
                )
            ],
            apply_to_children=True
        )
        # Create DynamoDB Tables
        work_orders_table = dynamodb.Table(
            self,
            f"{self.stack_name}-WorkOrdersTable",
            table_name=f"{construct_id.lower()}-work-orders",
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            partition_key=dynamodb.Attribute(
                name="work_order_id",
                type=dynamodb.AttributeType.STRING
            ),
            removal_policy=RemovalPolicy.DESTROY,
        )
        
        work_orders_table.add_global_secondary_index(
            index_name="LocationIndex",
            partition_key=dynamodb.Attribute(
                name="location_name",
                type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL
        )

        locations_table = dynamodb.Table(
            self,
            f"{self.stack_name}-LocationsTable",
            table_name=f"{construct_id.lower()}-locations",
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            partition_key=dynamodb.Attribute(
                name="location_name",
                type=dynamodb.AttributeType.STRING
            ),
            removal_policy=RemovalPolicy.DESTROY,
        )

        hazards_table = dynamodb.Table(
            self,
            f"{self.stack_name}-HazardsTable",
            table_name=f"{construct_id.lower()}-hazards",
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            partition_key=dynamodb.Attribute(
                name="hazard_id",
                type=dynamodb.AttributeType.STRING
            ),
            removal_policy=RemovalPolicy.DESTROY,
        )
        
        hazards_table.add_global_secondary_index(
            index_name="LocationIndex",
            partition_key=dynamodb.Attribute(
                name="location_name",
                type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL
        )

        incidents_table = dynamodb.Table(
            self,
            f"{self.stack_name}-IncidentsTable",
            table_name=f"{construct_id.lower()}-incidents",
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            partition_key=dynamodb.Attribute(
                name="incident_id",
                type=dynamodb.AttributeType.STRING
            ),
            removal_policy=RemovalPolicy.DESTROY,
        )
        
        incidents_table.add_global_secondary_index(
            index_name="LocationIndex",
            partition_key=dynamodb.Attribute(
                name="location_name",
                type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL
        )

        control_measures_table = dynamodb.Table(
            self,
            f"{self.stack_name}-ControlMeasuresTable",
            table_name=f"{construct_id.lower()}-control-measures",
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            partition_key=dynamodb.Attribute(
                name="control_measure_id",
                type=dynamodb.AttributeType.STRING
            ),
            removal_policy=RemovalPolicy.DESTROY,
        )
        
        control_measures_table.add_global_secondary_index(
            index_name="LocationHazardIndex",
            partition_key=dynamodb.Attribute(
                name="location_hazard_id",
                type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL
        )

        assets_table = dynamodb.Table(
            self,
            f"{self.stack_name}-AssetsTable",
            table_name=f"{construct_id.lower()}-assets",
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            partition_key=dynamodb.Attribute(
                name="asset_id",
                type=dynamodb.AttributeType.STRING
            ),
            removal_policy=RemovalPolicy.DESTROY,
        )
        
        assets_table.add_global_secondary_index(
            index_name="LocationIndex",
            partition_key=dynamodb.Attribute(
                name="location_name",
                type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL
        )

        location_hazards_table = dynamodb.Table(
            self,
            f"{self.stack_name}-LocationHazardsTable",
            table_name=f"{construct_id.lower()}-location-hazards",
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            partition_key=dynamodb.Attribute(
                name="location_name",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="hazard_id",
                type=dynamodb.AttributeType.STRING
            ),
            removal_policy=RemovalPolicy.DESTROY,
        )
        
        location_hazards_table.add_global_secondary_index(
            index_name="HazardIndex",
            partition_key=dynamodb.Attribute(
                name="hazard_id",
                type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL
        )

        # Create Lambda execution role
        lambda_execution_role = iam.Role(
            self,
            f"{self.stack_name}-LambdaExecutionRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ]
        )
        
        # Add NAG suppression for Lambda execution role managed policy
        NagSuppressions.add_resource_suppressions(
            lambda_execution_role,
            [
                NagPackSuppression(
                    id="AwsSolutions-IAM4",
                    reason="Using AWS managed policy for Lambda basic execution is acceptable for this use case"
                )
            ],
            apply_to_children=True
        )

        # Add policies to Lambda execution role
        lambda_execution_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:ListBucket",
                    "s3:GetBucketLocation"
                ],
                resources=[data_bucket.bucket_arn]
            )
        )
        
        lambda_execution_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:DeleteObject"
                ],
                resources=[f"{data_bucket.bucket_arn}/*"]
            )
        )
        
        # Add NAG suppression for the Lambda execution role S3 permissions
        NagSuppressions.add_resource_suppressions(
            lambda_execution_role,
            [
                NagPackSuppression(
                    id="AwsSolutions-IAM5",
                    reason="Lambda needs specific S3 object permissions to process files in the bucket"
                )
            ],
            apply_to_children=True
        )
        
        lambda_execution_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "dynamodb:GetItem",
                    "dynamodb:Query",
                    "dynamodb:Scan",
                    "dynamodb:BatchWriteItem",
                    "dynamodb:PutItem"
                ],
                resources=[
                    work_orders_table.table_arn,
                    locations_table.table_arn,
                    hazards_table.table_arn,
                    incidents_table.table_arn,
                    assets_table.table_arn,
                    location_hazards_table.table_arn,
                    control_measures_table.table_arn,
                    f"{work_orders_table.table_arn}/index/*",
                    f"{locations_table.table_arn}/index/*",
                    f"{hazards_table.table_arn}/index/*",
                    f"{incidents_table.table_arn}/index/*",
                    f"{assets_table.table_arn}/index/*",
                    f"{location_hazards_table.table_arn}/index/*",
                    f"{control_measures_table.table_arn}/index/*"
                ]
            )
        )

        # Create Data Import Lambda Function
        data_import_function = lambda_.Function(
            self,
            f"{self.stack_name}-DataImportFunction",
            function_name=f"{construct_id.lower()}-data-import",
            runtime=lambda_.Runtime.PYTHON_3_13,  # Updated to latest Python runtime
            handler="index.handler",
            code=lambda_.Code.from_asset("./bedrock_agents/data_import"),
            role=lambda_execution_role,
            timeout=Duration.seconds(300),
            memory_size=256,
            environment={
                "S3_BUCKET_NAME": data_bucket.bucket_name,
                "WORK_ORDERS_TABLE_NAME": work_orders_table.table_name,
                "LOCATIONS_TABLE_NAME": locations_table.table_name,
                "HAZARDS_TABLE_NAME": hazards_table.table_name,
                "INCIDENTS_TABLE_NAME": incidents_table.table_name,
                "ASSETS_TABLE_NAME": assets_table.table_name,
                "LOCATION_HAZARDS_TABLE_NAME": location_hazards_table.table_name,
                "CONTROL_MEASURES_TABLE_NAME": control_measures_table.table_name
            }
        )
        # Add NAG suppression for Lambda runtime
        NagSuppressions.add_resource_suppressions(
            data_import_function,
            [
                NagPackSuppression(
                    id="AwsSolutions-L1",
                    reason="Using the latest Python runtime version 3.13"
                )
            ]
        )
        
        # Create a simple custom resource to trigger the data import function after deployment
        data_import_trigger = CustomResource(
            self,
            f"{self.stack_name}-DataImportTrigger",
            service_token=data_import_function.function_arn,
        )
        
        # Add explicit dependencies to ensure proper execution order
        data_import_trigger.node.add_dependency(data_deployment)
        data_import_trigger.node.add_dependency(work_orders_table)
        data_import_trigger.node.add_dependency(locations_table)
        data_import_trigger.node.add_dependency(hazards_table)
        data_import_trigger.node.add_dependency(incidents_table)
        data_import_trigger.node.add_dependency(assets_table)
        data_import_trigger.node.add_dependency(location_hazards_table)
        data_import_trigger.node.add_dependency(control_measures_table)

        # Create Weather Agent Lambda Function
        weather_agent_function = lambda_.Function(
            self,
            f"{self.stack_name}-WeatherAgentFunction",
            function_name=f"{construct_id.lower()}-weather-agent",
            runtime=lambda_.Runtime.PYTHON_3_13,  # Updated to latest Python runtime
            handler="index.lambda_handler",
            code=lambda_.Code.from_asset("./bedrock_agents/weather_agent"),
            role=lambda_execution_role,
            timeout=Duration.seconds(30),
            memory_size=256,
            environment={
                "OPENWEATHERMAP_API_KEY": openweather_api_key,
                "LOG_LEVEL": "INFO"
            }
        )
        
        # Add NAG suppression for Lambda runtime
        NagSuppressions.add_resource_suppressions(
            weather_agent_function,
            [
                NagPackSuppression(
                    id="AwsSolutions-L1",
                    reason="Using the latest Python runtime version 3.13"
                )
            ]
        )
        
        # Create Location Alert Lambda Function
        location_alert_function = lambda_.Function(
            self,
            f"{self.stack_name}-LocationAlertFunction",
            function_name=f"{construct_id.lower()}-location-alert",
            runtime=lambda_.Runtime.PYTHON_3_13,  # Updated to latest Python runtime
            handler="index.lambda_handler",
            code=lambda_.Code.from_asset("./bedrock_agents/location_alert"),
            role=lambda_execution_role,
            timeout=Duration.seconds(30),
            memory_size=256,
            environment={
                "WORK_ORDERS_TABLE_NAME": work_orders_table.table_name,
                "LOCATIONS_TABLE_NAME": locations_table.table_name,
                "HAZARDS_TABLE_NAME": hazards_table.table_name,
                "INCIDENTS_TABLE_NAME": incidents_table.table_name,
                "LOCATION_HAZARDS_TABLE_NAME": location_hazards_table.table_name,
                "CONTROL_MEASURES_TABLE_NAME": control_measures_table.table_name,
                "LOG_LEVEL": "INFO"
            }
        )
        
        # Add NAG suppression for Lambda runtime
        NagSuppressions.add_resource_suppressions(
            location_alert_function,
            [
                NagPackSuppression(
                    id="AwsSolutions-L1",
                    reason="Using the latest Python runtime version 3.13"
                )
            ]
        )
        
        # Create Emergency Alert Lambda Function
        emergency_alert_function = lambda_.Function(
            self,
            f"{self.stack_name}-EmergencyAlertFunction",
            function_name=f"{construct_id.lower()}-emergency-alert",
            runtime=lambda_.Runtime.PYTHON_3_13,  # Updated to latest Python runtime
            handler="index.lambda_handler",
            code=lambda_.Code.from_asset("./bedrock_agents/emergency_alert"),
            role=lambda_execution_role,
            timeout=Duration.seconds(30),
            memory_size=256,
            environment={
                "LOG_LEVEL": "INFO"
            }
        )
        
        # Add NAG suppression for Lambda runtime
        NagSuppressions.add_resource_suppressions(
            emergency_alert_function,
            [
                NagPackSuppression(
                    id="AwsSolutions-L1",
                    reason="Using the latest Python runtime version 3.13"
                )
            ]
        )
        
        # Create Weather Agent IAM Role
        weather_agent_role = iam.Role(
            self,
            f"{self.stack_name}-WeatherBedrockAgentExecutionRole",
            assumed_by=iam.ServicePrincipal("bedrock.amazonaws.com"),
            description='Execution role for Weather Bedrock Agent'
        )
        
        # Add permissions for Weather agent to invoke Lambda function
        weather_agent_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:GetFoundationModel"
                ],
                resources=["*"]
            )
        )
        
        weather_agent_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["lambda:InvokeFunction"],
                resources=[weather_agent_function.function_arn]
            )
        )
        
        # Create Location Alert Agent IAM Role
        location_alert_agent_role = iam.Role(
            self,
            f"{self.stack_name}-LocationAlertBedrockAgentExecutionRole",
            assumed_by=iam.ServicePrincipal("bedrock.amazonaws.com"),
            description='Execution role for Location Alert Bedrock Agent'
        )
        
        # Add permissions for Location Alert agent to invoke Lambda function
        location_alert_agent_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:GetFoundationModel"
                ],
                resources=["*"]
            )
        )
        
        location_alert_agent_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["lambda:InvokeFunction"],
                resources=[location_alert_function.function_arn]
            )
        )
        
        # Create Emergency Alert Agent IAM Role
        emergency_alert_agent_role = iam.Role(
            self,
            "EmergencyAlertBedrockAgentExecutionRole",
            assumed_by=iam.ServicePrincipal("bedrock.amazonaws.com"),
            description='Execution role for Emergency Alert Bedrock Agent'
        )
        
        # Add permissions for Emergency Alert agent to invoke Lambda function
        emergency_alert_agent_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:GetFoundationModel"
                ],
                resources=["*"]
            )
        )
        
        emergency_alert_agent_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=["lambda:InvokeFunction"],
                resources=[emergency_alert_function.function_arn]
            )
        )
        
        # Create Supervisor Agent IAM Role
        supervisor_agent_role = iam.Role(
            self,
            "SupervisorAgentRole",
            assumed_by=iam.ServicePrincipal("bedrock.amazonaws.com"),
            description='Execution role for Supervisor Bedrock Agent'
        )
        
        # Add permissions for Supervisor agent
        supervisor_agent_role.add_to_policy(
            iam.PolicyStatement(
                sid="AmazonBedrockAgentInferencProfilePolicy1",
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock:InvokeModel*",
                    "bedrock:CreateInferenceProfile"
                ],
                resources=[
                    "arn:aws:bedrock:*::foundation-model/*",
                    "arn:aws:bedrock:*:*:inference-profile/*",
                    "arn:aws:bedrock:*:*:application-inference-profile/*"
                ]
            )
        )
        
        supervisor_agent_role.add_to_policy(
            iam.PolicyStatement(
                sid="AmazonBedrockAgentInferencProfilePolicy2",
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock:GetInferenceProfile",
                    "bedrock:ListInferenceProfiles",
                    "bedrock:DeleteInferenceProfile",
                    "bedrock:TagResource",
                    "bedrock:UntagResource",
                    "bedrock:ListTagsForResource"
                ],
                resources=[
                    "arn:aws:bedrock:*:*:inference-profile/*",
                    "arn:aws:bedrock:*:*:application-inference-profile/*"
                ]
            )
        )
        
        supervisor_agent_role.add_to_policy(
            iam.PolicyStatement(
                sid="AmazonBedrockAgentBedrockFoundationModelPolicy",
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock:GetAgentAlias",
                    "bedrock:InvokeAgent"
                ],
                resources=[
                    "arn:aws:bedrock:*:*:agent/*",
                    "arn:aws:bedrock:*:*:agent-alias/*"
                ]
            )
        )
        
        supervisor_agent_role.add_to_policy(
            iam.PolicyStatement(
                sid="AmazonBedrockAgentBedrockInvokeGuardrailModelPolicy",
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:GetGuardrail",
                    "bedrock:ApplyGuardrail"
                ],
                resources=["arn:aws:bedrock:*:*:guardrail/*"]
            )
        )
        
        supervisor_agent_role.add_to_policy(
            iam.PolicyStatement(
                sid="QueryKB",
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock:Retrieve",
                    "bedrock:RetrieveAndGenerate"
                ],
                resources=["arn:aws:bedrock:*:*:knowledge-base/*"]
            )
        )
        
        # Add CloudWatch Logs permissions for all agent roles
        for role in [weather_agent_role, location_alert_agent_role, emergency_alert_agent_role, supervisor_agent_role]:
            role.add_to_policy(
                iam.PolicyStatement(
                    effect=iam.Effect.ALLOW,
                    actions=[
                        'logs:CreateLogGroup',
                        'logs:CreateLogStream',
                        'logs:PutLogEvents'
                    ],
                    resources=[
                        f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/bedrock/*"
                    ]
                )
            )
        
 
    
        # Add NAG suppression for Bedrock agent role
        NagSuppressions.add_resource_suppressions(
            weather_agent_role,
            [
                NagPackSuppression(
                    id="AwsSolutions-IAM4",
                    reason="Giving Bedrock permissions on Agent Role"
                )
            ],
            apply_to_children=True
        )
        # Add NAG suppression for Bedrock agent role
        NagSuppressions.add_resource_suppressions(
            location_alert_agent_role,
            [
                NagPackSuppression(
                    id="AwsSolutions-IAM4",
                    reason="Giving Bedrock permissions on Agent Role"
                )
            ],
            apply_to_children=True
        )

        # Add NAG suppression for Bedrock agent role
        NagSuppressions.add_resource_suppressions(
            emergency_alert_agent_role,
            [
                NagPackSuppression(
                    id="AwsSolutions-IAM4",
                    reason="Giving Bedrock permissions on Agent Role"
                )
            ],
            apply_to_children=True
        )

        # Add NAG suppression for Bedrock agent role
        NagSuppressions.add_resource_suppressions(
            supervisor_agent_role,
            [
                NagPackSuppression(
                    id="AwsSolutions-IAM4",
                    reason="Giving Bedrock permissions on Agent Role"
                )
            ],
            apply_to_children=True
        )

        # Create Weather Agent Action Group
        weather_agent_action_group = bedrock.CfnAgent.AgentActionGroupProperty(
            action_group_name="WeatherForecast",
            action_group_executor=bedrock.CfnAgent.ActionGroupExecutorProperty(
                lambda_=weather_agent_function.function_arn
            ),
            description="Get weather forecast for a specific location and time",
            action_group_state="ENABLED",
            function_schema=bedrock.CfnAgent.FunctionSchemaProperty(
                functions=[
                    bedrock.CfnAgent.FunctionProperty(
                        name="weatherforecast",
                        description="Get weather forecast at lat and long for the datetime entered",
                        parameters={
                            "lat": bedrock.CfnAgent.ParameterDetailProperty(
                                type="string",
                                description="Latitude",
                                required=True
                            ),
                            "long": bedrock.CfnAgent.ParameterDetailProperty(
                                type="string",
                                description="Longitude",
                                required=True
                            ),
                            "target_datetime": bedrock.CfnAgent.ParameterDetailProperty(
                                type="string",
                                description="Target Date and Time",
                                required=True
                            )
                        }
                    )
                ]
            )
        )
        
        # Create Location Alert Action Group
        location_alert_action_group = bedrock.CfnAgent.AgentActionGroupProperty(
            action_group_name="LocationAlerts",
            action_group_executor=bedrock.CfnAgent.ActionGroupExecutorProperty(
                lambda_=location_alert_function.function_arn
            ),
            description="Get safety alerts for a specific work order location",
            action_group_state="ENABLED",
            function_schema=bedrock.CfnAgent.FunctionSchemaProperty(
                functions=[
                    bedrock.CfnAgent.FunctionProperty(
                        name="fetch_location_alerts",
                        description="Get all incidents and hazards reported the location where the workorder has been created",
                        parameters={
                            "work_order_id": bedrock.CfnAgent.ParameterDetailProperty(
                                type="string",
                                description="Work Order ID",
                                required=True
                            )
                        }
                    )
                ]
            )
        )
        
        # Create Emergency Alert Action Group
        emergency_alert_action_group = bedrock.CfnAgent.AgentActionGroupProperty(
            action_group_name="EmergencyAlerts",
            action_group_executor=bedrock.CfnAgent.ActionGroupExecutorProperty(
                lambda_=emergency_alert_function.function_arn
            ),
            description="Get emergency alerts for a specific location",
            action_group_state="ENABLED",
            function_schema=bedrock.CfnAgent.FunctionSchemaProperty(
                functions=[
                    bedrock.CfnAgent.FunctionProperty(
                        name="emvalert",
                        description="Get emergency alert at lat and long",
                        parameters={
                            "lat": bedrock.CfnAgent.ParameterDetailProperty(
                                type="string",
                                description="Latitude",
                                required=True
                            ),
                            "long": bedrock.CfnAgent.ParameterDetailProperty(
                                type="string",
                                description="Longitude",
                                required=True
                            )
                        }
                    )
                ]
            )
        )
        
        # Create Weather Agent with autoPrepare=True
        weather_agent = bedrock.CfnAgent(
            self,
            "WeatherAlertAgent",
            agent_name="FieldSafetyWeatherAgent",
            agent_resource_role_arn=weather_agent_role.role_arn,
            foundation_model=collaborator_foundation_model,
            instruction="Goal: Fetch the weather information at a latitude and longitude at a target datetime.,Instructions: Fetch the weather information at a latitude and longitude at a target datetime. You may get the Workorder details in JSON format including workorder location",
            action_groups=[weather_agent_action_group],
            idle_session_ttl_in_seconds=1800,
            auto_prepare=True  # Use autoPrepare instead of custom resource
        )
        
        # Create Location Alert Agent with autoPrepare=True
        location_alert_agent = bedrock.CfnAgent(
            self,
            "LocationAlertAgent",
            agent_name="FieldSafetyLocationAlertAgent",
            agent_resource_role_arn=location_alert_agent_role.role_arn,
            foundation_model=collaborator_foundation_model,
            instruction="Role: Safety officer, Goal: When a workorder is assigned to a field workforce technician, provide all possible incidents and hazards reported at the location for the workorder to ensure that the technician is well informed",
            action_groups=[location_alert_action_group],
            idle_session_ttl_in_seconds=1800,
            auto_prepare=True  # Use autoPrepare instead of custom resource
        )
        
        # Create Emergency Alert Agent with autoPrepare=True
        emergency_alert_agent = bedrock.CfnAgent(
            self,
            "EmergencyAlertAgent",
            agent_name="FieldSafetyEmergencyAlertAgent",
            agent_resource_role_arn=emergency_alert_agent_role.role_arn,
            foundation_model=collaborator_foundation_model,
            instruction="You are an emergency assistant that provides emergency alerts for specific locations. Fetch the emergency warnings at a latitude and longitude.You will get the latitude and longitude details from Workorder location.",
            action_groups=[emergency_alert_action_group],
            idle_session_ttl_in_seconds=1800,
            auto_prepare=True  # Use autoPrepare instead of custom resource
        )
        
        # Create agent aliases
        weather_agent_alias = bedrock.CfnAgentAlias(
            self,
            "WeatherAgentAlias",
            agent_id=weather_agent.attr_agent_id,
            agent_alias_name="WeatherAgentAlias",
        )
        
        location_alert_agent_alias = bedrock.CfnAgentAlias(
            self,
            "LocationAlertAgentAlias",
            agent_id=location_alert_agent.attr_agent_id,
            agent_alias_name="LocationAlertAgentAlias",
        )
        
        emergency_alert_agent_alias = bedrock.CfnAgentAlias(
            self,
            "EmergencyAlertAgentAlias",
            agent_id=emergency_alert_agent.attr_agent_id,
            agent_alias_name="EmergencyAlertAgentAlias",
        )
        
        # Set dependencies to ensure proper creation order for agent aliases
        weather_agent_alias.node.add_dependency(weather_agent)
        location_alert_agent_alias.node.add_dependency(location_alert_agent)
        emergency_alert_agent_alias.node.add_dependency(emergency_alert_agent)
        
        # Create Supervisor Agent with collaborators using native CDK constructs
        supervisor_agent = bedrock.CfnAgent(
            self,
            "SupervisorAgent",
            agent_name="FieldSafetySupervisorAgent",
            agent_resource_role_arn=supervisor_agent_role.role_arn,
            foundation_model=supervisor_foundation_model,
            instruction="""You are a Workorder Safety helper bot. You must perform hazard, emergency and weather checks against a supplied work order. When you receive a work order, extract the workorder and location information from the JSON and perform hazard, weather, and emergency checks using provided agents. You must make a call to all the available collaborators to come up with a comprehensive safety briefing. The report must be returned in valid HTML format with proper structure and semantic tags for rendering on a web application. Use headings, paragraphs, bullet points, and other appropriate HTML elements to organize the content. The report must start with a proper title.""",
            idle_session_ttl_in_seconds=1800,
            auto_prepare=True,  # Use autoPrepare instead of custom resource
            # Add agent collaboration configuration
            agent_collaboration="SUPERVISOR",
            agent_collaborators=[
                bedrock.CfnAgent.AgentCollaboratorProperty(
                    agent_descriptor=bedrock.CfnAgent.AgentDescriptorProperty(
                        alias_arn=weather_agent_alias.attr_agent_alias_arn
                    ),
                    collaboration_instruction="Use this agent to get weather forecasts for specific locations and times.",
                    collaborator_name="WeatherAgent",
                    relay_conversation_history="TO_COLLABORATOR"
                ),
                bedrock.CfnAgent.AgentCollaboratorProperty(
                    agent_descriptor=bedrock.CfnAgent.AgentDescriptorProperty(
                        alias_arn=location_alert_agent_alias.attr_agent_alias_arn
                    ),
                    collaboration_instruction="Use this agent to get safety alerts for work order locations.",
                    collaborator_name="LocationAlertAgent",
                    relay_conversation_history="TO_COLLABORATOR"
                ),
                bedrock.CfnAgent.AgentCollaboratorProperty(
                    agent_descriptor=bedrock.CfnAgent.AgentDescriptorProperty(
                        alias_arn=emergency_alert_agent_alias.attr_agent_alias_arn
                    ),
                    collaboration_instruction="Use this agent to get emergency alerts for specific locations.",
                    collaborator_name="EmergencyAlertAgent",
                    relay_conversation_history="TO_COLLABORATOR"
                )
            ]
        )
        
        # Create Supervisor Agent Alias
        supervisor_agent_alias = bedrock.CfnAgentAlias(
            self,
            "SupervisorAgentAlias",
            agent_id=supervisor_agent.attr_agent_id,
            agent_alias_name="SupervisorAgentAlias",
        )
        
        # Set explicit dependencies for supervisor agent and its alias
        supervisor_agent.node.add_dependency(weather_agent)
        supervisor_agent.node.add_dependency(location_alert_agent)
        supervisor_agent.node.add_dependency(emergency_alert_agent)
        supervisor_agent.node.add_dependency(weather_agent_alias)
        supervisor_agent.node.add_dependency(location_alert_agent_alias)
        supervisor_agent.node.add_dependency(emergency_alert_agent_alias)

        supervisor_agent_alias.node.add_dependency(supervisor_agent)
        
        

       # Add explicit Lambda permissions for Bedrock agents
        weather_lambda_permission = lambda_.CfnPermission(
            self,
            "WeatherLambdaPermission",
            action="lambda:InvokeFunction",
            function_name=weather_agent_function.function_name,
            principal="bedrock.amazonaws.com",
            source_arn=f"arn:aws:bedrock:{self.region}:{self.account}:agent/{weather_agent.attr_agent_id}"
        )
        
        location_alert_lambda_permission = lambda_.CfnPermission(
            self,
            "LocationAlertLambdaPermission",
            action="lambda:InvokeFunction",
            function_name=location_alert_function.function_name,
            principal="bedrock.amazonaws.com",
            source_arn=f"arn:aws:bedrock:{self.region}:{self.account}:agent/{location_alert_agent.attr_agent_id}"
        )
        
        emergency_alert_lambda_permission = lambda_.CfnPermission(
            self,
            "EmergencyAlertLambdaPermission",
            action="lambda:InvokeFunction",
            function_name=emergency_alert_function.function_name,
            principal="bedrock.amazonaws.com",
            source_arn=f"arn:aws:bedrock:{self.region}:{self.account}:agent/{emergency_alert_agent.attr_agent_id}"
        )
        
        # Set dependencies to ensure proper creation order
        weather_lambda_permission.node.add_dependency(weather_agent)
        location_alert_lambda_permission.node.add_dependency(location_alert_agent)
        emergency_alert_lambda_permission.node.add_dependency(emergency_alert_agent)


        # Store references to resources for outputs
        self.work_orders_table_name = work_orders_table.table_name
        self.locations_table_name = locations_table.table_name
        self.supervisor_agent_id = supervisor_agent.attr_agent_id
        self.supervisor_agent_alias_id = supervisor_agent_alias.attr_agent_alias_id

        # Add outputs
        CfnOutput(
            self,
            "WorkOrdersTableName",
            value=work_orders_table.table_name,
            export_name=f"{construct_id}-WorkOrdersTableName"
        )
        
        CfnOutput(
            self,
            "LocationsTableName",
            value=locations_table.table_name,
            export_name=f"{construct_id}-LocationsTableName"
        )
        
        CfnOutput(
            self,
            "WeatherAgentId",
            value=weather_agent.attr_agent_id,
            export_name=f"{construct_id}-WeatherAgentId"
        )
        
        CfnOutput(
            self,
            "LocationAlertAgentId",
            value=location_alert_agent.attr_agent_id,
            export_name=f"{construct_id}-LocationAlertAgentId"
        )
        
        CfnOutput(
            self,
            "EmergencyAlertAgentId",
            value=emergency_alert_agent.attr_agent_id,
            export_name=f"{construct_id}-EmergencyAlertAgentId"
        )
        
        # Add outputs for the supervisor agent
        CfnOutput(
            self,
            "SupervisorAgentId",
            value=supervisor_agent.attr_agent_id,
            export_name=f"{construct_id}-SupervisorAgentId"
        )
        
        CfnOutput(
            self,
            "SupervisorAgentAliasId",
            value=supervisor_agent_alias.attr_agent_alias_id,
            export_name=f"{construct_id}-SupervisorAgentAliasId"
        )
