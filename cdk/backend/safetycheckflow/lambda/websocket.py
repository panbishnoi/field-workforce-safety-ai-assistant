import json
import os
import boto3
import time
import requests
from datetime import datetime
import functools
import traceback
import re
from collections import OrderedDict
from boto3.dynamodb.conditions import Key
from jose import jwt
from botocore.config import Config
from aws_lambda_powertools import Logger
import uuid

# Initialize services and constants
logger = Logger()
def log(message):
    logger.info(message)
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['WS_CONNECTION_TABLE_NAME'])

# Environment variables
REGION = os.environ.get("REGION", "us-east-1")
USER_POOL_ID = os.environ.get("USER_POOL_ID", "")
CLIENT_ID = os.environ.get("CLIENT_ID", "")
AGENT_ALIAS_ID = os.getenv("AGENT_ALIAS_ID")
AGENT_ID = os.getenv("AGENT_ID")

bedrock_agent_runtime_client = boto3.client(
        'bedrock-agent-runtime',
        config=Config(
            retries=dict(
                max_attempts=3,
                mode='adaptive'
            ),
            read_timeout=120,
            connect_timeout=5
        )
)    
def verify_token(token: str) -> dict:
    try:
        url = f"https://cognito-idp.{REGION}.amazonaws.com/{USER_POOL_ID}/.well-known/jwks.json"
        response = requests.get(url)
        response.raise_for_status()  # Raise exception for non-200 responses
        
        keys = response.json().get("keys", [])
        if not keys:
            raise ValueError("No keys found in JWKS response")
            
        header = jwt.get_unverified_header(token)
        if not header or "kid" not in header:
            raise ValueError("Invalid token header")
            
        matching_keys = [k for k in keys if k.get("kid") == header.get("kid")]
        if not matching_keys:
            raise ValueError(f"No matching key found for kid: {header.get('kid')}")
            
        key = matching_keys[0]
        
        decoded = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            options={"verify_at_hash": False},
            audience=CLIENT_ID,
        )
        return decoded
    except requests.RequestException as e:
        logger.error(f"Error fetching JWKS: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Token verification error: {str(e)}")
        raise

def handle_connect(connection_id):
    try:
        logger.info(f"Adding new connection entry to DynamoDB for {connection_id}")
        table.put_item(
            Item={
                'connectionId': connection_id,
                'ttl': int(time.time()) + 10 * 60,  # 10 minute TTL (comment says 24 hour but code was 10 min)
                'timestamp': str(datetime.now())
            }
        )
        return {'statusCode': 200, 'body': 'Connected'}
    except Exception as e:
        logger.error(f"Connection handling error: {str(e)}")
        logger.error(traceback.format_exc())
        return {'statusCode': 200, 'body': 'Connected'}

def handle_disconnect(connection_id):
    try:
        logger.info(f"Removing connection {connection_id} from DynamoDB")
        table.delete_item(Key={'connectionId': connection_id})
        return {'statusCode': 200, 'body': 'Disconnected'}
    except Exception as e:
        logger.error(f"Disconnect handling error: {str(e)}")
        logger.error(traceback.format_exc())
        return {'statusCode': 200, 'body': 'Disconnected'}

def handle_message(api_gateway_management, connection_id, event):
    try:
        # Parse request body
        event_body = json.loads(event["body"])

        session_id = event_body.get('session_id', str(uuid.uuid4()))
        

        # Generate unique request ID
        request_id = str(uuid.uuid4())
        
        payload = json.dumps(event_body)

        try:
            # Extract query object
            query_object = event_body['query']
            workorderdetails = event_body['workorderdetails']
            work_order_id = workorderdetails['work_order_id']
            # Remove safetycheckresponse from nested workOrderLocationAssetDetails
            if "workOrderLocationAssetDetails" in workorderdetails:
                workOrderLocationAssetDetails = workorderdetails["workOrderLocationAssetDetails"]
                if "safetycheckresponse" in workOrderLocationAssetDetails:
                    del workOrderLocationAssetDetails["safetycheckresponse"]
                if "safetyCheckPerformedAt" in workOrderLocationAssetDetails:
                    del workOrderLocationAssetDetails["safetyCheckPerformedAt"]

            # Create prompt string by concatenating query and workorder details
            payload = f"{query_object} {json.dumps(workorderdetails)}"    
        except Exception as ex:
            logger.error(f"Error in getting work order: {str(ex)}")

        logger.info('work_order_id is :',work_order_id)
        logger.info('payload is :',payload)
  
        logger.info(f"Performing safety checks for: {payload}")
        

    
        # Prepare input parameters for Bedrock agent
        input_params = {
            "inputText": payload,
            "agentId": AGENT_ID,
            "agentAliasId": AGENT_ALIAS_ID,
            "sessionId": session_id,
            "enableTrace": True
        }
        
        

        logger.info(f"Invoking Bedrock agent with params: {json.dumps(input_params, default=str)}")
        
        # Invoke the agent API
        response = bedrock_agent_runtime_client.invoke_agent(**input_params)

        completion = ""
        
        # Process the response chunks
        for event_item in response['completion']:
            if 'chunk' in event_item:
                chunk = event_item['chunk']
                if 'bytes' in chunk:
                    chunk_data = chunk['bytes'].decode('utf-8')
                    completion += chunk_data
                    
                    # Send chunk to client
                    send_to_client(api_gateway_management, connection_id, {
                        'type': 'chunk',
                        'content': chunk_data
                    })
            
            if 'trace' in event_item:
                trace = event_item['trace']
                timestamp = int(time.time() * 1000)
                
                # Send trace to client
                send_to_client(api_gateway_management, connection_id, {
                    'type': 'trace',
                    'traceType': trace.get('traceType', 'Unknown'),
                    'content': trace
                })
        
        # Send final completion
        request_id = f"ws-{connection_id}-{int(time.time())}"
        send_to_client(api_gateway_management, connection_id, {
            'type': 'final',
            'requestId': request_id,
            'status': 'COMPLETED',
            'safetycheckresponse': completion
        })
        
        return {'statusCode': 200, 'body': 'Message sent'}
                
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {str(e)}")
        return {'statusCode': 400, 'body': 'Invalid message format'}
    except Exception as e:
        logger.error(f"Message handling error: {str(e)}")
        logger.error(traceback.format_exc())
        return {'statusCode': 500, 'body': f'Failed to process message: {str(e)}'}

def send_to_client(api_gateway_management, connection_id, message):
    """Send message to WebSocket client"""
    try:
        # Convert datetime to string before JSON serialization
        current_time = str(datetime.now())
        
        api_gateway_management.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps({
                'message': message,
                'sender': connection_id,
                'timestamp': current_time  # Use string instead of datetime object
            }, default=str)  # Add default=str to handle any other non-serializable objects
        )
        
        logger.info(f"Message sent to {connection_id}: {message['type']}")
    except api_gateway_management.exceptions.GoneException:
        # Connection is no longer valid
        logger.warning(f"Connection {connection_id} is invalid (GoneException).")
        try:
            table.delete_item(Key={'connectionId': connection_id})
        except Exception as e:
            logger.error(f"Error deleting stale connection: {str(e)}")
    except Exception as e:
        logger.error(f"Error sending message: {str(e)}")
        logger.error(traceback.format_exc())
        # Don't re-raise the exception to prevent Lambda failure
        # This allows the function to continue processing even if one message fails

@logger.inject_lambda_context(log_event=True)
def lambda_handler(event, context):
    try:
        # Log the incoming event for debugging
        logger.info(f"Received event: {json.dumps(event, default=str)}")
        
        # Safely get requestContext or raise a more descriptive error
        if 'requestContext' not in event:
            logger.error(f"Missing requestContext in event: {event}")
            return {'statusCode': 400, 'body': 'Invalid WebSocket event structure'}
            
        request_context = event['requestContext']
        route_key = request_context.get('routeKey')
        connection_id = request_context.get('connectionId')
        
        if not route_key or not connection_id:
            logger.error(f"Missing required fields in requestContext: {request_context}")
            return {'statusCode': 400, 'body': 'Missing required WebSocket fields'}

        if route_key == '$connect':
            logger.info(f"New connection: {connection_id}")
            return handle_connect(connection_id)
        elif route_key == '$disconnect':
            logger.info(f"Disconnection: {connection_id}")
            return handle_disconnect(connection_id)
        elif route_key == '$default':
            # Check if body exists and is valid JSON
            if 'body' not in event or not event['body']:
                logger.error("Missing or empty body in event")
                return {'statusCode': 400, 'body': 'Missing request body'}
                
            try:
                message = json.loads(event['body'])
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in body: {str(e)}")
                return {'statusCode': 400, 'body': 'Invalid JSON in request body'}
            
            # Check if the message is a heartbeat
            if message.get('messageType') == 'heartbeat':
                logger.info(f"Heartbeat received from {connection_id}")
                return {
                    'statusCode': 200,
                    'body': json.dumps({'message': 'Heartbeat received, no action taken'})
                }
                   
            # Initialize API client
            api_client = None
            logger.info(f"Processing message from {connection_id}")
            
            if request_context.get('domainName') and request_context.get('stage'):
                domain_name = request_context['domainName']
                stage = request_context['stage']
                api_client = boto3.client(
                    'apigatewaymanagementapi',
                    endpoint_url=f'https://{domain_name}/{stage}'
                )
            else:
                logger.error("Missing domainName or stage in requestContext")
                return {'statusCode': 500, 'body': 'Missing API Gateway configuration'}
        
            if not api_client:
                return {'statusCode': 500, 'body': 'Failed to initialize API client'}
                
            # Verify token
            token = message.get("token")
            if not token:
                logger.error("Token is missing in the request")
                return {'statusCode': 403, 'body': 'Token is required'}
            
            try:
                decoded = verify_token(token)
                user_email = decoded.get('email', 'unknown')
                logger.info(f"Valid token for user: {user_email}")
                return handle_message(api_client, connection_id, event)
            except Exception as e:
                logger.error(f"Token verification failed: {str(e)}")
                logger.error(traceback.format_exc())
                return {'statusCode': 403, 'body': 'Invalid Token'}
        else:
            logger.warning(f"Unsupported route: {route_key}")
            return {'statusCode': 400, 'body': f'Unsupported route: {route_key}'}
            
    except Exception as e:
        logger.error(f"Lambda handler error: {str(e)}")
        logger.error(traceback.format_exc())
        return {'statusCode': 500, 'body': f'Internal server error: {str(e)}'}
