// src/utils/connection-handler.js
import { useState, useEffect, useRef } from 'react';

/**
 * Custom hook that provides a debounced connection status
 * to prevent flashing "disconnected" state during brief connection interruptions
 * 
 * @param {boolean} actualConnectionStatus - The actual current connection status
 * @param {number} disconnectionDelay - Delay in ms before showing disconnected state (default: 2000ms)
 * @param {number} connectionDelay - Delay in ms before showing connected state (default: 0ms)
 * @returns {boolean} - The debounced connection status
 */
export const useStableConnectionStatus = (
  actualConnectionStatus, 
  disconnectionDelay = 2000, 
  connectionDelay = 0
) => {
  const [stableStatus, setStableStatus] = useState(actualConnectionStatus);
  const disconnectionTimerRef = useRef(null);
  const connectionTimerRef = useRef(null);

  useEffect(() => {
    // When connection status changes
    if (actualConnectionStatus) {
      // If we're newly connected
      // Clear any pending disconnection timer
      if (disconnectionTimerRef.current) {
        clearTimeout(disconnectionTimerRef.current);
        disconnectionTimerRef.current = null;
      }

      // Apply connection delay if specified
      if (connectionDelay > 0) {
        if (connectionTimerRef.current) {
          clearTimeout(connectionTimerRef.current);
        }
        connectionTimerRef.current = setTimeout(() => {
          setStableStatus(true);
          connectionTimerRef.current = null;
        }, connectionDelay);
      } else {
        // No delay for connected state
        setStableStatus(true);
      }
    } else {
      // If we're newly disconnected
      // Clear any pending connection timer
      if (connectionTimerRef.current) {
        clearTimeout(connectionTimerRef.current);
        connectionTimerRef.current = null;
      }

      // Only show disconnected state after delay
      if (!disconnectionTimerRef.current) {
        disconnectionTimerRef.current = setTimeout(() => {
          setStableStatus(false);
          disconnectionTimerRef.current = null;
        }, disconnectionDelay);
      }
    }

    return () => {
      // Clean up any pending timers on unmount
      if (disconnectionTimerRef.current) {
        clearTimeout(disconnectionTimerRef.current);
      }
      if (connectionTimerRef.current) {
        clearTimeout(connectionTimerRef.current);
      }
    };
  }, [actualConnectionStatus, disconnectionDelay, connectionDelay]);

  return stableStatus;
};
