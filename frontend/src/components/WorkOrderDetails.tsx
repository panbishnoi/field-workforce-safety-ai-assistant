import { useLocation, useNavigate } from 'react-router-dom';
import { useState } from 'react';
import '@components/WorkOrderDetails.css';
import 'leaflet/dist/leaflet.css';
import { postEmergencyCheckRequest } from '@lib/api';
import UnifiedMap from '@components/UnifiedMap';
import { Emergency } from '@/types/emergency';
import WebSocketSafetyCheck from '@components/WebSocketSafetyCheck';
import {
  Container,
  Header,
  SpaceBetween,
  Button,
  StatusIndicator,
  Box,
  ExpandableSection,
} from "@cloudscape-design/components";

interface LocationDetails {
  latitude: number;
  longitude: number;
}

interface WorkOrder {
  work_order_id: string;
  description: string;
  asset_id: string;
  scheduled_start_timestamp: string;
  scheduled_finish_timestamp: string;
  owner_name: string;
  status: string;
  priority: string;
  location_name: string;
  location_details?: LocationDetails;
  safetyCheckResponse?: string;
  safetyCheckPerformedAt?: string;
}

const WorkOrderDetails = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const workOrder = location.state?.workOrder as WorkOrder;
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isLocationVisible, setIsLocationVisible] = useState(true);
  const [isSafetyCheckVisible, setIsSafetyCheckVisible] = useState(true);
  const [safetyCheckResponse, setSafetyCheckResponse] = useState<string>(workOrder?.safetyCheckResponse || "");
  
  const [emergencies, setEmergencies] = useState<Emergency[]>([]);
  const [loadingEmergencies, setLoadingEmergencies] = useState(false);
  
  if (!workOrder) {
    return <div>
      {/* i18n-disable */}
      No details found for this Work Order.
      {/* i18n-enable */}
    </div>;
  }

  const handleSafetyCheckComplete = (response: string, timestamp?: string) => {
    // Update the state with the safety check response
    setSafetyCheckResponse(response);
    
    // Also update the workOrder object if needed for persistence
    workOrder.safetyCheckResponse = response;
    
    // Update the timestamp if provided
    if (timestamp) {
      workOrder.safetyCheckPerformedAt = timestamp;
    }
    
    setLoading(false);
    setError(null);
  };

  const handleSafetyCheckError = (errorMsg: string) => {
    setError(errorMsg);
    setLoading(false);
  };

  const performEmergencyCheck = async () => {
    try {
      setLoadingEmergencies(true);
      // Extract latitude and longitude
      const latitude = workOrder.location_details?.latitude;
      const longitude = workOrder.location_details?.longitude;

      // Validate that both latitude and longitude are defined
      if (latitude === undefined || longitude === undefined) {
        throw new Error('Work order location details are incomplete.');
      }
      const queryObject = {
        latitude: latitude,
        longitude: longitude,
      };

      const response = (await postEmergencyCheckRequest(queryObject) as unknown) as unknown;
      setEmergencies(response as Emergency[]);
      console.log(response);
    } catch (err) {
      setError('Failed to initiate emergency check');
    } finally {
      setLoadingEmergencies(false);
    }
  };

  return (
    <SpaceBetween size="l">
      {/* Back Button */}
      <Button onClick={() => navigate("/")} variant="link">
        {/* i18n-disable */}
        ← Back to List
        {/* i18n-enable */}
      </Button>

      {/* Work Order Details */}
      <Container
        header={<Header>{/* i18n-disable */}Work Order Details{/* i18n-enable */}</Header>}
      >
        <SpaceBetween size="m">
          <Box>
            <strong>ID:</strong> {workOrder.work_order_id}
          </Box>
          <Box>
            {/* i18n-disable */}
            <strong>Description:</strong> {workOrder.description}
            {/* i18n-enable */}
          </Box>
          <Box>
            {/* i18n-disable */}
            <strong>Asset:</strong> {workOrder.asset_id}
            {/* i18n-enable */}
          </Box>
          <Box>
            {/* i18n-disable */}
            <strong>Scheduled Start:</strong>{" "}
            {/* i18n-enable */}
            {new Date(workOrder.scheduled_start_timestamp).toLocaleString()}
          </Box>
          <Box>
            {/* i18n-disable */}
            <strong>Scheduled Finish:</strong>{" "}
            {/* i18n-enable */}
            {new Date(workOrder.scheduled_finish_timestamp).toLocaleString()}
          </Box>
          <Box>
            {/* i18n-disable */}
            <strong>Status:</strong>{" "}
            {/* i18n-enable */}
            <StatusIndicator
              type={
                workOrder.status === "Approved"
                  ? "success"
                  : workOrder.status === "In Progress"
                  ? "info"
                  : workOrder.status === "Pending"
                  ? "warning"
                  : "error"
              }
            >
              {workOrder.status}
            </StatusIndicator>
          </Box>
          <Box>
            {/* i18n-disable */}
            <strong>Priority:</strong> {workOrder.priority}
            {/* i18n-enable */}
          </Box>
          {workOrder.safetyCheckPerformedAt && (
            <Box>
                {/* i18n-disable */}
                <strong>Safety Check Performed:</strong> {
                {/* i18n-enable */}
                  (() => {
                    const timestamp = workOrder.safetyCheckPerformedAt;
                    if (!timestamp) return 'Unknown';
                    
                    // Parse the timestamp parts
                    const [datePart, timePart] = timestamp.split('T');
                    const [year, month, day] = datePart.split('-').map(Number);
                    const [hours, minutes, secondsWithMs] = timePart.split(':');
                    const seconds = parseFloat(secondsWithMs);
                    
                    // Create a UTC Date object (months are 0-indexed in JavaScript)
                    const utcDate = new Date(Date.UTC(year, month - 1, day, hours, minutes, seconds));
                    
                    // Format in the user's local timezone
                    return utcDate.toLocaleString(undefined, {
                      year: 'numeric',
                      month: 'short',
                      day: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit',
                      hour12: true,
                      timeZoneName: 'short'
                    });
                  })()
                }
            </Box>
          )}
        </SpaceBetween>
      </Container>



      {/* Location Section */}
      {workOrder.location_name && (
        <ExpandableSection
          headerText={
            <SpaceBetween direction="horizontal" size="xs">
              {/* i18n-disable */}
              <span>Location Details</span>
              {/* i18n-enable */}
            </SpaceBetween>
          }
          expanded={isLocationVisible}
          onChange={({ detail }) => setIsLocationVisible(detail.expanded)}
        >
          <SpaceBetween size="l">
            {isLocationVisible && (
              <>
                {workOrder.location_details?.latitude && workOrder.location_details?.longitude ? (
                  <UnifiedMap 
                    centerPoint={[
                      workOrder.location_details?.longitude,
                      workOrder.location_details?.latitude,
                    ]}
                    description={workOrder.location_name} 
                    emergencies={emergencies}
                  />
                ) : (
                  "                  {/* i18n-disable */}
                  "No location coordinates available."
                  {/* i18n-enable */}"
                )}
              </>
            )}
            <Button
              variant="primary"
              loading={loadingEmergencies}
              onClick={performEmergencyCheck}
            >
              {/* i18n-disable */}
              Load Emergency Warnings
              {/* i18n-enable */}
            </Button>
          </SpaceBetween>
        </ExpandableSection>
      )}

      {/* Safety Check Section */}
      <ExpandableSection
        headerText="Safety Check"
        expanded={isSafetyCheckVisible}
        onChange={({ detail }) => setIsSafetyCheckVisible(detail.expanded)}
      >
        <WebSocketSafetyCheck 
          workOrder={workOrder}
          onSafetyCheckComplete={handleSafetyCheckComplete}
          onSafetyCheckError={handleSafetyCheckError}
          showResults={false} // Don't show results in this component
        />
      </ExpandableSection>

      {/* Safety Check Response */}
      {error ? (
        <div className="safety-check-response error">{error}</div>
      ) : safetyCheckResponse && (
        <Container
          header={<Header variant="h2">
            <span className="section-heading-complete">
              {/* i18n-disable */}
              Safety Check Results
              {/* i18n-enable */}
            </span>
          </Header>}
        >
          <div className="safety-check-response" 
            dangerouslySetInnerHTML={{ __html: safetyCheckResponse }} 
          />
        </Container>
      )}
    </SpaceBetween>
  );
};

export default WorkOrderDetails;
