const { S3Client, PutObjectCommand, GetObjectCommand } = require('@aws-sdk/client-s3');
const { Readable } = require('stream');

exports.handler = async function(event, context) {
    console.log('Event:', JSON.stringify(event, null, 2));
    
    const s3Client = new S3Client();
    const requestType = event.RequestType;
    
    if (requestType === 'Create' || requestType === 'Update') {
        try {
            // Get parameters from the event
            const apiEndpoint = event.ResourceProperties.ApiEndpoint;
            const workorderApiEndpoint = event.ResourceProperties.WorkorderApiEndpoint;
            const websocketApiEndpoint = event.ResourceProperties.WebSocketApiEndpoint;
            const regionName = event.ResourceProperties.RegionName;
            const cognitoUserPoolId = event.ResourceProperties.CognitoUserPoolId;
            const cognitoUserPoolClientId = event.ResourceProperties.CognitoUserPoolClientId;
            const cognitoIdentityPoolId = event.ResourceProperties.CognitoIdentityPoolId;
            const s3BucketName = process.env.S3_BUCKET_NAME;
            
            // Create runtime config.js with actual values
            console.log('Creating runtime config.js...');
            const configJsContent = `// Runtime configuration - Generated at ${new Date().toISOString()}
window.APP_CONFIG = {
  VITE_API_ENDPOINT: "${apiEndpoint}",
  VITE_WORKORDER_API_ENDPOINT: "${workorderApiEndpoint}",
  VITE_WEBSOCKET_API_ENDPOINT: "${websocketApiEndpoint}",
  VITE_REGION_NAME: "${regionName}",
  VITE_COGNITO_USER_POOL_ID: "${cognitoUserPoolId}",
  VITE_COGNITO_USER_POOL_CLIENT_ID: "${cognitoUserPoolClientId}",
  VITE_COGNITO_IDENTITY_POOL_ID: "${cognitoIdentityPoolId}",
  VITE_API_NAME: "RestAPI",
  VITE_APP_NAME: "Field Workforce safety assistant",
  VITE_WorkOrder_API_NAME: "WorkOrderAPI",
  VITE_PROTOTYPE_NAME: "WorkOrderSafetyDemo",
  VITE_COGNITO_DOMAIN: ".auth.${regionName}.amazoncognito.com/"
};`;
            
            // Upload config.js to S3
            await s3Client.send(new PutObjectCommand({
                Bucket: s3BucketName,
                Key: 'config.js',
                Body: configJsContent,
                ContentType: 'application/javascript'
            }));
            
            console.log(`Updated config.js in ${s3BucketName}`);
            
            return {
                PhysicalResourceId: context.logStreamName,
                Data: {
                    Message: 'Config.js updated successfully'
                }
            };
        } catch (error) {
            console.error('Error:', error);
            throw error;
        }
    } else if (requestType === 'Delete') {
        // Nothing to do for delete
        return {
            PhysicalResourceId: event.PhysicalResourceId
        };
    }
};
