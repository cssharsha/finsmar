// frontend/src/components/PlaidLinkButton.jsx
import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios'; // For making HTTP requests
import { usePlaidLink } from 'react-plaid-link'; // Plaid's React hook

// Define the backend API base URL (adjust if your backend runs elsewhere)
// Ideally, use environment variables for this in a real app
const API_BASE_URL = 'http://localhost:5001'; // Points to your Flask backend

const PlaidLinkButton = () => {
  const [linkToken, setLinkToken] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [exchangeResult, setExchangeResult] = useState(null); // To show success/error after token exchange

  // Callback function after successful Plaid Link connection
  const onSuccess = useCallback(async (public_token, metadata) => {
    setLoading(true); // Indicate processing
    setError(null);
    setExchangeResult(null);
    console.log('Plaid Link Success! public_token:', public_token, 'metadata:', metadata);

    try {
      // Send the public_token to your backend to exchange for an access_token
      const response = await axios.post(`${API_BASE_URL}/api/exchange_public_token`, {
        public_token: public_token,
      });
      console.log('Token exchange successful:', response.data);
      setExchangeResult({ success: true, message: response.data.message || 'Account linked successfully!' });
      // TODO: In a real app, trigger a refresh of account data here
    } catch (exchangeError) {
      console.error('Error exchanging public token:', exchangeError.response ? exchangeError.response.data : exchangeError);
      const errorMsg = exchangeError.response?.data?.error || 'Failed to exchange public token.';
      setError(`Failed to link account: ${errorMsg}`);
      setExchangeResult({ success: false, message: errorMsg });
    } finally {
      setLoading(false);
    }
  }, []); // Empty dependency array means this function doesn't change

  // Setup Plaid Link configuration using the hook
  const { open, ready } = usePlaidLink({
    token: linkToken, // Pass the link_token obtained from your backend
    onSuccess, // Pass the onSuccess callback
    onExit: (err, metadata) => {
         console.log('Plaid Link exited.', err, metadata);
         if (err) {
            setError(`Plaid Link exited with error: ${err.display_message || err.error_message || err.error_code || 'Unknown error'}`);
         }
    },
    // onEvent: (eventName, metadata) => { // Optional: Log events
    //    console.log('Plaid Event:', eventName, metadata);
    // }
  });

  // Effect to fetch the link_token when the component mounts
  useEffect(() => {
    const fetchToken = async () => {
      setLoading(true);
      setError(null);
      setExchangeResult(null);
      try {
        const response = await axios.post(`${API_BASE_URL}/api/create_link_token`);
        if (response.data.link_token) {
          console.log('Link token fetched successfully');
          setLinkToken(response.data.link_token);
        } else {
           throw new Error("link_token missing from response");
        }
      } catch (fetchError) {
        console.error('Error fetching link token:', fetchError.response ? fetchError.response.data : fetchError);
        setError('Failed to initialize Plaid Link. Could not fetch link token.');
      } finally {
        setLoading(false);
      }
    };
    fetchToken();
  }, []); // Empty dependency array ensures this runs only once on mount


  return (
    <div>
      <button onClick={() => open()} disabled={!ready || loading || !linkToken}>
        {loading ? 'Loading...' : 'Connect Bank Account'}
      </button>
      {error && <p style={{ color: 'red' }}>Error: {error}</p>}
      {exchangeResult && (
         <p style={{ color: exchangeResult.success ? 'green' : 'red' }}>
           {exchangeResult.message}
         </p>
      )}
    </div>
  );
};

export default PlaidLinkButton;
