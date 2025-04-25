import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';

const API_BASE_URL = 'http://localhost:5001';

// Formatting helper
const formatCurrency = (value) => {
    if (value === null || value === undefined) return 'N/A';
    return Number(value).toLocaleString('en-US', { style: 'currency', currency: 'USD' });
};

const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleDateString('en-CA'); // YYYY-MM-DD format
};
// --- Loan Calculation Helpers ---
function calculateMonthlyPayment(principal, annualRatePercent, years) {
    if (!principal || principal <= 0 || !annualRatePercent || annualRatePercent < 0 || !years || years <= 0) {
        return null; // Not enough info or invalid input
    }
    const monthlyRate = (annualRatePercent / 100) / 12;
    const numberOfPayments = years * 12;

    if (monthlyRate === 0) { // Handle 0% interest rate
        return principal / numberOfPayments;
    }

    const payment = principal * (monthlyRate * Math.pow(1 + monthlyRate, numberOfPayments)) / (Math.pow(1 + monthlyRate, numberOfPayments) - 1);
    return payment;
}

function calculatePaybackTime(principal, annualRatePercent, monthlyPayment) {
     if (!principal || principal <= 0 || !monthlyPayment || monthlyPayment <= 0) {
         return null; // Cannot calculate without principal or positive payment
     }
     const monthlyRate = (annualRatePercent / 100) / 12;

     if (monthlyRate === 0) { // 0% interest
         const months = Math.ceil(principal / monthlyPayment);
         return { years: Math.floor(months / 12), months: months % 12 };
     }

     // Check if payment covers interest
     if (monthlyPayment <= principal * monthlyRate) {
         return { years: Infinity, months: Infinity }; // Payment doesn't cover interest
     }

     // Formula: n = -log(1 - (P * i) / M) / log(1 + i)
     const numberOfPayments = -Math.log(1 - (principal * monthlyRate) / monthlyPayment) / Math.log(1 + monthlyRate);
     const totalMonths = Math.ceil(numberOfPayments);

     if (!isFinite(totalMonths) || totalMonths <= 0) return null;

     const years = Math.floor(totalMonths / 12);
     const months = totalMonths % 12;
     return { years, months };
}

const CreditCardSettings = () => {
    const [creditAccounts, setCreditAccounts] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    // State for fetched Plaid details per account ID
    const [cardDetails, setCardDetails] = useState({}); // { accountId: { apr_percent: 19.99, ... } }
    // State for user's chosen payment input per account ID
    const [paymentInputs, setPaymentInputs] = useState({}); // { accountId: 'value' }
    // State for calculated payback time per account ID
    const [paybackTimes, setPaybackTimes] = useState({}); // { accountId: { years: Y, months: M } }
    // State for loading details per account ID
    const [fetchingDetailsId, setFetchingDetailsId] = useState(null);
    // State for messages per account ID
    const [messageStates, setMessageStates] = useState({});

    // Fetch accounts on mount
    const fetchAccounts = useCallback(async () => {
        // ... (Similar to LoanSettings: fetch from /api/portfolio/overview, filter type='credit') ...
        setLoading(true); setError(null);
         try {
             const response = await axios.get(`${API_BASE_URL}/api/portfolio/overview`);
             const allAccounts = response.data?.account_details || [];
             const cards = allAccounts.filter(acc => acc.type === 'credit');
             setCreditAccounts(cards);
             // Init payment inputs
             const initialPayments = {};
             cards.forEach(acc => { initialPayments[acc.id] = ''; }); // Start payment input empty
             setPaymentInputs(initialPayments);
         } catch (err) { setError("Could not load account data."); }
          finally { setLoading(false); }
    }, []);

    useEffect(() => { fetchAccounts(); }, [fetchAccounts]);

    // Fetch Plaid details when user clicks button
    const handleFetchDetails = async (accountId) => {
        setFetchingDetailsId(accountId);
        setMessageStates(prev => ({ ...prev, [accountId]: null }));
        setCardDetails(prev => ({ ...prev, [accountId]: undefined })); // Clear previous details
        try {
            const response = await axios.get(`${API_BASE_URL}/api/accounts/${accountId}/fetch_plaid_card_details`);
            setCardDetails(prev => ({ ...prev, [accountId]: response.data }));
            setMessageStates(prev => ({ ...prev, [accountId]: { type: 'success', text: 'Details fetched.' } }));
            setTimeout(() => setMessageStates(prev => ({ ...prev, [accountId]: null })), 3000);
        } catch (err) {
             const errorMsg = err.response?.data?.error || 'Failed to fetch details';
             console.error(`Error fetching Plaid details for ${accountId}:`, err.response?.data || err);
             setCardDetails(prev => ({ ...prev, [accountId]: { error: errorMsg } })); // Store error state
             setMessageStates(prev => ({ ...prev, [accountId]: { type: 'error', text: errorMsg } }));
        } finally {
            setFetchingDetailsId(null);
        }
    };

    // Handle payment input change and recalculate payback
    const handlePaymentInputChange = (accountId, value) => {
         setPaymentInputs(prev => ({ ...prev, [accountId]: value }));
         // Recalculate payback time immediately
         const details = cardDetails[accountId];
         const account = creditAccounts.find(acc => acc.id === accountId);
         if (details && !details.error && account) {
              const payback = calculatePaybackTime(
                  account.balance, // Current balance from overview
                  details.apr_percent, // Fetched APR
                  parseFloat(value || 0) // Current input payment
              );
              setPaybackTimes(prev => ({ ...prev, [accountId]: payback }));
         } else {
              setPaybackTimes(prev => ({ ...prev, [accountId]: null })); // Clear if no rate or payment
         }
    };

    // --- Render Logic ---
    if (loading) return <p>Loading credit card accounts...</p>;
    if (error) return <p style={{ color: 'red' }}>Error: {error}</p>;

    return (
        <div>
            {creditAccounts.length === 0 ? (
                <p>No accounts marked as 'credit' type found.</p>
            ) : (
                <ul>
                    {creditAccounts.map(acc => {
                        const details = cardDetails[acc.id];
                        const paymentInput = paymentInputs[acc.id] ?? '';
                        const payback = paybackTimes[acc.id];
                        const isFetching = fetchingDetailsId === acc.id;
                        const message = messageStates[acc.id];

                        return (
                            <li key={acc.id} style={{ marginBottom: '15px', paddingBottom: '15px', borderBottom: '1px dotted #ccc' }}>
                                <strong>{acc.name}</strong> ({acc.source}) - Current Balance: {formatCurrency(acc.balance)}
                                <button onClick={() => handleFetchDetails(acc.id)} disabled={isFetching} style={{marginLeft: '15px'}}>
                                    {isFetching ? 'Fetching...' : 'Fetch Details'}
                                </button>
                                {message && (<span style={{ color: message.type === 'success' ? 'green' : 'red', marginLeft: '10px' }}> {message.text} </span>)}

                                {/* Display fetched details if available */}
                                {details && !details.error && (
                                    <div style={{fontSize: '0.9em', marginLeft: '10px', marginTop: '5px'}}>
                                         <span>APR: <strong>{details.apr_percent !== null ? `${details.apr_percent.toFixed(2)}%` : 'N/A'}</strong> | </span>
                                         <span>Stmt Bal: <strong>{formatCurrency(details.statement_balance)}</strong> | </span>
                                         <span>Min Pay: <strong>{formatCurrency(details.minimum_payment)}</strong> | </span>
                                         <span>Due: <strong>{formatDate(details.next_due_date)}</strong> </span>
                                         <p style={{margin:'5px 0'}}><em>Payment needed to avoid interest: ~{formatCurrency(details.statement_balance)}</em></p>
                                    </div>
                                )}
                                {details && details.error && <p style={{color: 'orange', marginLeft: '10px', fontSize:'0.9em'}}>Could not fetch details from Plaid.</p>}

                                 {/* Payback Calculation UI */}
                                 {details && !details.error && details.apr_percent !== null && ( // Only show if APR is known
                                    <div style={{marginTop:'10px', marginLeft: '10px'}}>
                                        <label htmlFor={`cc_payment_${acc.id}`}>Your Chosen Monthly Payment: $</label>
                                        <input
                                            type="number"
                                            id={`cc_payment_${acc.id}`}
                                            value={paymentInput}
                                            onChange={(e) => handlePaymentInputChange(acc.id, e.target.value)}
                                            placeholder="e.g., 500"
                                            step="1"
                                            style={{width:'100px', marginLeft:'5px'}}
                                        />
                                         <span style={{marginLeft:'15px'}}>Est. Payback Time:
                                             <strong style={{marginLeft:'5px'}}>
                                                 {payback ?
                                                     (payback.years === Infinity ? 'Never (Payment < Interest?)' : `${payback.years} yrs, ${payback.months} mos`)
                                                     : (paymentInput ? 'Calculating...' : 'Enter payment')
                                                 }
                                             </strong>
                                         </span>
                                    </div>
                                )}
                            </li>
                        );
                    })}
                </ul>
            )}
        </div>
    );
};

export default CreditCardSettings;
