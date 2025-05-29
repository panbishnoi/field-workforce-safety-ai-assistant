import React, { useEffect, useState, useRef } from 'react';
import { safetyCheckWebSocket, WebSocketMessage } from '@/lib/api';
import { customAlphabet } from 'nanoid';
import { Button, SpaceBetween, Box, Spinner } from "@cloudscape-design/components";
import './WebSocketSafetyCheck.css';

interface WebSocketSafetyCheckProps {
  workOrder: any;
  onSafetyCheckComplete: (response: string, timestamp?: string) => void;
  onSafetyCheckError: (error: string) => void;
  showResults?: boolean; // Optional prop to control whether to show results in this component
}

const WebSocketSafetyCheck: React.FC<WebSocketSafetyCheckProps> = ({
  workOrder,
  onSafetyCheckComplete,
  onSafetyCheckError,
  showResults = false // Default to not showing results in this component
}) => {
  const [isConnecting, setIsConnecting] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [traceContent, setTraceContent] = useState<string>("");
  const [currentChunk, setCurrentChunk] = useState<string>("");
  const [authError, setAuthError] = useState<string | null>(null);
  const [finalResponseReceived, setFinalResponseReceived] = useState(false);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    const handleMessage = (message: WebSocketMessage) => {
      console.log('Received WebSocket message:', message);

      // Check if the message is in the nested format
      const webSocketMessage = message.message ? message.message : message;
      const messageType = webSocketMessage.type;

      switch (messageType) {
        case 'chunk':
          if (webSocketMessage.content) {
            setCurrentChunk(prev => prev + webSocketMessage.content);
          }
          break;
        case 'trace':
          // Process trace message
          handleTraceMessage(message);
          break;
        case 'final':
          // Process final message
          handleFinalMessage(webSocketMessage);
          break;
        case 'error':
          // Reset states on error
          setIsProcessing(false);
          setIsConnecting(false);
          onSafetyCheckError(webSocketMessage.safetyCheckResponse || 'Unknown error');
          break;
      }
    };

    // Add message handler
    safetyCheckWebSocket.addMessageHandler(handleMessage);

    // Cleanup
    return () => {
      safetyCheckWebSocket.removeMessageHandler(handleMessage);
      
      // Clear timeout when component unmounts
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
    };
  }, [onSafetyCheckComplete, onSafetyCheckError]);

  const handleTraceMessage = (message: WebSocketMessage) => {
    // Extract the actual message content (handle nested structure)
    const webSocketMessage = message.message ? message.message : message;
    const content = webSocketMessage.content;
    
    if (!content) return;
    
    // Extract the rationale text if available
    let rationale = null;
    if (content.trace?.orchestrationTrace?.rationale?.text) {
      rationale = content.trace.orchestrationTrace.rationale.text;
    }
    
    // Only add to trace content if we have a rationale
    if (rationale) {
      // Append the new rationale to the existing trace content
      setTraceContent(prev => {
        // Add a separator if there's already content
        const separator = prev ? '\n\n' : '';
        return prev + separator + rationale;
      });
    }
  };

  const handleFinalMessage = (message: WebSocketMessage) => {
    console.log("Received final message:", message);
    
    // Mark that we've received the final response
    setFinalResponseReceived(true);
    
    // Reset processing state
    setIsProcessing(false);
    setIsConnecting(false);
    
    // Clear the timeout when we receive the final response
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
    
    // Extract the final response - check both direct and nested formats
    let finalResponse = message.safetyCheckResponse || '';
    
    // Extract the safetyCheckPerformedAt timestamp if available
    const timestamp = message.safetyCheckPerformedAt || null;
    
    if (finalResponse) {
      // Clean up the final response
      finalResponse = cleanupFinalResponse(finalResponse);
      
      // Set the current chunk to show the final response (if we're showing results in this component)
      setCurrentChunk(finalResponse);
      
      // Call the completion callback with the cleaned response and timestamp
      if (timestamp) {
        onSafetyCheckComplete(finalResponse, timestamp);
      } else {
        onSafetyCheckComplete(finalResponse);
      }
    } else {
      onSafetyCheckError('No response received from safety check');
    }
  };

  // Function to clean up the final response
  const cleanupFinalResponse = (response: string): string => {
    try {
      // Check if there's any HTML content at all
      if (!response.includes('<') || !response.includes('>')) {
        return response; // No HTML tags at all, return as is
      }
      
      // Remove any leading content before the first HTML tag
      const htmlStartIndex = response.indexOf('<html>');
      if (htmlStartIndex !== -1) {
        response = response.substring(htmlStartIndex);
      } else {
        // If no <html> tag, look for any HTML tag
        const firstTagMatch = response.match(/<[a-z][^>]*>/i);
        if (firstTagMatch && firstTagMatch.index !== undefined) {
          response = response.substring(firstTagMatch.index);
        }
      }
      
      // Remove any empty lines
      response = response.replace(/^\s*[\r\n]/gm, '');
      
      // Remove any model reasoning or non-HTML content at the beginning
      // This regex looks for content before the first HTML tag
      response = response.replace(/^[^<]*/g, '');
      
      // Remove any <safety_report> tags or similar wrapper tags
      response = response.replace(/<\/?safety_report>/g, '');
      
      // If after all this processing we don't have any HTML tags left, return original
      const hasHtmlStructure = /<[a-z][^>]*>.*<\/[a-z][^>]*>/is.test(response);
      if (!hasHtmlStructure) {
        console.log("No valid HTML structure found after cleanup, returning original response");
        return response;
      }
      
      return response;
    } catch (error) {
      console.error('Error cleaning up response:', error);
      return response; // Return original response on error
    }
  };

  const performSafetyCheck = async () => {
    try {
      // Reset state
      setIsProcessing(true);
      setTraceContent("");
      setCurrentChunk("");
      setAuthError(null);
      setFinalResponseReceived(false);

      // Clear any existing timeout
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }

      // Connect to WebSocket if not already connected
      if (!safetyCheckWebSocket.isSocketConnected()) {
        setIsConnecting(true);
        try {
          await safetyCheckWebSocket.connect();
        } catch (error) {
          // Make sure to reset connecting state on connection error
          setIsConnecting(false);
          setIsProcessing(false);
          throw error; // Re-throw to be caught by the outer catch
        }
        setIsConnecting(false);
      }

      const queryObject = {
        workOrderDetails: {
          work_order_id: workOrder.work_order_id,
          latitude: workOrder.location_details?.latitude,
          longitude: workOrder.location_details?.longitude,
          target_datetime: workOrder.scheduled_start_timestamp,
        },
        session_id: customAlphabet("1234567890", 20)()
      };

      // The token will be automatically included by the WebSocket class
      await safetyCheckWebSocket.performSafetyCheck(queryObject);
      
      // Set timeout AFTER the request is sent - this is important
      // We don't want the timeout to start during connection setup
      timeoutRef.current = setTimeout(() => {
        console.log("Safety check timeout triggered");
        if (isProcessing && !finalResponseReceived) {
          console.log("Safety check timed out - still processing and no final response");
          setIsProcessing(false);
          setIsConnecting(false);
          onSafetyCheckError('Error in performing safety check');
        } else {
          console.log("Safety check timeout fired but operation already completed");
        }
      }, 120000); // 2 min timeout
      
    } catch (error: any) {
      console.error('Error sending safety check request:', error);
      
      // Always reset both states on any error
      setIsConnecting(false);
      setIsProcessing(false);
      
      // Clear timeout on error
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
      
      // Check if it's an authentication error
      if (error.message && error.message.includes('authentication')) {
        setAuthError('Authentication failed. Please sign in again.');
        onSafetyCheckError('Authentication failed');
      } else {
        onSafetyCheckError(`Failed to send safety check request: ${error.message || 'Unknown error'}`);
      }
    }
  };

  return (
    <SpaceBetween direction="vertical" size="m">
      {authError && (
        <Box variant="error">
          {authError}
        </Box>
      )}
      
      <Button 
        onClick={performSafetyCheck} 
        loading={isConnecting || isProcessing}
        variant="primary"
        disabled={isProcessing || isConnecting}
      >
        {isConnecting ? 'Connecting...' : isProcessing ? 'Processing...' : 'Perform Safety Check'}
      </Button>
      
      {(isProcessing || (finalResponseReceived && showResults)) && (
        <div className="trace-container">
          {isProcessing && <h3 className="section-heading-processing">
            {/* i18n-disable */}
            Processing Safety Check
            {/* i18n-enable */}
          </h3>}
          {finalResponseReceived && showResults && <h3 className="section-heading-complete">
            {/* i18n-disable */}
            Safety Check Complete
            {/* i18n-enable */}
          </h3>}

          
          {/* Single continuous trace block */}
          <div className="agent-reasoning">
            <h4 className="subsection-heading">
              {/* i18n-disable */}
              Agent Reasoning
              {/* i18n-enable */}
            </h4>
            {traceContent ? (
              <div className="trace-content">
                {traceContent.split('\n\n').map((paragraph, index) => (
                  <p key={index}>{paragraph}</p>
                ))}
              </div>
            ) : (
              <p>
                {/* i18n-disable */}
                No reasoning information available yet.
                {/* i18n-enable */}
              </p>
            )}
          </div>
          
          {/* Only show the response here if showResults is true */}
          {currentChunk && showResults && (
            <div className="current-response">
              <h4 className="subsection-heading">
                {/* i18n-disable */}
                Safety Briefing Response
                {/* i18n-enable */}
              </h4>
              <div 
                className="response-text" 
                dangerouslySetInnerHTML={{ __html: currentChunk }}
              />
            </div>
          )}
          
          {isProcessing && (
            <div className="processing-indicator">
              <Spinner size="normal" /> Processing...
            </div>
          )}
        </div>
      )}
    </SpaceBetween>
  );
};

export default WebSocketSafetyCheck;
