import React, { useState, useEffect, useCallback, useMemo } from 'react';
import axios from 'axios';

const API_BASE_URL = 'http://localhost:5001';

// Formatting helper
const formatCurrency = (value) => {
    if (value === null || value === undefined) return 'N/A';
    return Number(value).toLocaleString('en-US', { style: 'currency', currency: 'USD' });
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

// Helper to convert DB decimal rate (e.g., 0.055) to % string ('5.5')
const formatRateToPercentString = (decimalRate) => {
    if (decimalRate === null || decimalRate === undefined) return '';
    try {
        // Multiply by 100, handle potential floating point issues, format
        return (Number(decimalRate) * 100).toFixed(4); // Keep good precision for editing
    } catch { return ''; }
};
 // Helper to convert % string ('5.5') to decimal string ('0.055') for saving
 const formatPercentStringToDecimalString = (percentString) => {
     if (!percentString || String(percentString).trim() === '') return null;
     try {
         const rate = parseFloat(percentString);
         if (isNaN(rate)) return null;
         return String(rate / 100.0);
     } catch { return null; }
 };

const LoanSettings = () => {
    const [loanAccounts, setLoanAccounts] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    // State to hold the current input value for each loan's payment
    const [paymentInputs, setPaymentInputs] = useState({}); // { accountId: 'value', ... }
    // State to track saving status for each row
    const [savingStates, setSavingStates] = useState({}); // { accountId: true/false, ... }
    // State for messages per row
    const [messageStates, setMessageStates] = useState({}); // { accountId: {type: 'success'/'error', text: '...'}, ...}

    // State to hold input/calculated values PER account ID
    const [accountState, setAccountState] = useState({});
    // Example structure for accountState[id]:
    // {
    //    balance: 15000, // Fetched
    //    rateInput: '3.5', // Input for Annual Rate (%)
    //    durationInput: '5', // Input for Desired Duration (Years)
    //    paymentInput: '350.75', // User's chosen monthly payment (saved to DB)
    //    calculatedPayment: 300.50, // Calculated based on rate/duration
    //    paybackTime: { years: 4, months: 3 }, // Calculated based on paymentInput
    //    isSaving: false,
    //    message: { type: 'success'/'error', text: '...' }
    // }
    const [fetchingRateId, setFetchingRateId] = useState(null); // Track which rate is being fetched

    // --- Recalculate derived values when inputs change ---
    const recalculateForAccount = (accountId, currentState) => {
         const balance = currentState.balance;
         const rate = parseFloat(currentState.rateInput || 0);
         const duration = parseFloat(currentState.durationInput || 0);
         const payment = parseFloat(currentState.paymentInput || 0);

         const newCalculatedPayment = calculateMonthlyPayment(balance, rate, duration);
         const newPaybackTime = calculatePaybackTime(balance, rate, payment);

         return {
             ...currentState,
             calculatedPayment: newCalculatedPayment,
             paybackTime: newPaybackTime
         };
    };

    // Fetch all account data on mount to filter loans
    const fetchAndInitialize = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            // Use the overview endpoint which includes account type
            const response = await axios.get(`${API_BASE_URL}/api/portfolio/overview`);
            const allAccounts = response.data?.account_details || [];
            const loans = allAccounts.filter(acc => acc.type === 'loan');
            setLoanAccounts(loans);

            // Initialize state for each loan account
            const initialStates = {};
            loans.forEach(acc => {
                const dbRate = acc.loan_interest_rate; // Raw decimal from DB (e.g., 0.055)
                const dbPayment = acc.loan_monthly_payment; // Raw number from DB

                initialStates[acc.id] = {
                    balance: acc.balance ?? 0,
                    rateInput: formatRateToPercentString(dbRate), // Convert decimal rate TO percentage string for input
                    durationInput: '', // Start duration empty
                    paymentInput: dbPayment !== null ? String(dbPayment) : '', // User's chosen payment
                    durationInput: '',
                    // Store original DB values to compare for changes
                    dbRate: dbRate,
                    dbPayment: dbPayment,
                    // Initialize others
                    calculatedPayment: null, paybackTime: null,
                    isSaving: false, isFetchingRate: false, message: null
                };
                // Perform initial calculation based on DB values / empty inputs
                initialStates[acc.id] = recalculateForAccount(acc.id, initialStates[acc.id]);
            });
            setAccountState(initialStates);

        } catch (err) {
            console.error("Error fetching accounts for loan settings:", err);
            setError("Could not load account data.");
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchAndInitialize();
    }, [fetchAndInitialize]);

    // --- Handler for Fetching Rate ---
    const handleFetchRate = async (accountId) => {
        setAccountState(prev => ({ ...prev, [accountId]: {...prev[accountId], isFetchingRate: true, message: null} }));
        try {
            const response = await axios.get(`${API_BASE_URL}/api/accounts/${accountId}/fetch_plaid_rate`);
            if (response.data && response.data.interest_rate !== null) {
                const fetchedDecimalRate = response.data.interest_rate;
                const fetchedRatePercentStr = formatRateToPercentString(fetchedDecimalRate);

                // Update the input field *and* recalculate
                setAccountState(prev => {
                     const updatedState = {
                          ...prev[accountId],
                          rateInput: fetchedRatePercentStr, // Update input with fetched rate
                          isFetchingRate: false,
                          message: { type: 'success', text: 'Rate fetched!' }
                     };
                     const recalculatedState = recalculateForAccount(accountId, updatedState);
                     return { ...prev, [accountId]: recalculatedState };
                });
                setTimeout(() => setAccountState(prev => ({ ...prev, [accountId]: {...prev[accountId], message: null} })), 3000);
            } else {
                 setAccountState(prev => ({ ...prev, [accountId]: {...prev[accountId], isFetchingRate: false, message: { type: 'info', text: response.data.error || 'Rate not available' } } }));
            }
        } catch (err) {
             console.error(`Error fetching Plaid rate for account ${accountId}:`, err.response?.data || err);
             setMessageStates(prev => ({...prev, [accountId]: { type: 'error', text: err.response?.data?.error || 'Failed to fetch rate' }}));
        } finally {
            setFetchingRateId(null); // Clear loading state for this button
        }
    };

    // Handle changes in any input field for a specific loan
    const handleInputChange = (accountId, fieldName, value) => {
        setAccountState(prev => {
             // Update the specific field and then recalculate dependent values
            const updatedState = { ...prev[accountId], [fieldName]: value, message: null };
            const recalculatedState = recalculateForAccount(accountId, updatedState);
            return { ...prev, [accountId]: recalculatedState };
        });
    };

    // Handle saving the payment for a specific loan
    const handleSaveLoanDetails = async (accountId) => {
        const currentDetails = accountState[accountId];
        if (!currentDetails) return;

        setAccountState(prev => ({ ...prev, [accountId]: {...prev[accountId], isSaving: true, message: null} }));

        try {
            // Convert rate from % string to decimal string or null for backend
            const rateDecimalString = formatPercentStringToDecimalString(currentDetails.rateInput);
             const paymentValue = currentDetails.paymentInput.trim() === '' ? null : currentDetails.paymentInput;

            const payload = {
                loan_interest_rate: rateDecimalString,
                loan_monthly_payment: paymentValue
            };

            const response = await axios.put(`${API_BASE_URL}/api/accounts/${accountId}`, payload);

            // Update state with successfully saved values from response
            const savedRate = response.data.loan_interest_rate;
            const savedPayment = response.data.loan_monthly_payment;
            const savedRateStr = formatRateToPercentString(savedRate);
            const savedPaymentStr = savedPayment !== null ? String(savedPayment) : '';

            setAccountState(prev => {
                 const updatedState = {
                      ...prev[accountId],
                      isSaving: false,
                      message: { type: 'success', text: 'Saved!' },
                      // Update inputs AND db values to match saved state
                      rateInput: savedRateStr,
                      paymentInput: savedPaymentStr,
                      dbRate: savedRate,
                      dbPayment: savedPayment,
                 };
                 const recalculatedState = recalculateForAccount(accountId, updatedState);
                 return { ...prev, [accountId]: recalculatedState };
             });
            setTimeout(() => setAccountState(prev => ({ ...prev, [accountId]: {...prev[accountId], message: null} })), 3000);
        } catch (err) {
            console.error(`Error updating payment for account ${accountId}:`, err.response?.data || err);
            setMessageStates(prev => ({ ...prev, [accountId]: { type: 'error', text: err.response?.data?.error || 'Save failed' } }));
        } finally {
            setSavingStates(prev => ({ ...prev, [accountId]: false }));
        }
    };


    // --- Render Logic ---
    if (loading) return <p>Loading loan accounts...</p>;
    if (error) return <p style={{ color: 'red' }}>Error: {error}</p>;

    return (
        <div>
            {loanAccounts.length === 0 ? (
                <p>No accounts marked as 'loan' type found.</p>
            ) : (
                <ul>
                    {loanAccounts.map(acc => {
                        const state = accountState[acc.id] || {}; // Get state for this account
                        const isSaving = state.isSaving;
                        const message = state.message;
                        // Check if relevant inputs changed from original fetched values
                        const rateChanged = state.originalRate !== state.rateInput;
                        const paymentChanged = state.originalPayment !== state.paymentInput;
                        const isChanged = rateChanged || paymentChanged;
                        const isFetchingRate = fetchingRateId === acc.id;

                        return (
                            <li key={acc.id} style={{ marginBottom: '10px', paddingBottom: '10px', borderBottom: '1px dotted #ccc' }}>
                                <strong>{acc.name}</strong> ({acc.source})
                                <br /> Current Balance: {formatCurrency(acc.balance)}

                                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '15px', marginTop: '10px', alignItems: 'center' }}>
                                     {/* Interest Rate Input */}
                                    <div>
                                        <label>Annual Rate (%): </label><br />
                                        <input type="number" step="0.01" value={state.rateInput || ''}
                                               onChange={(e) => handleInputChange(acc.id, 'rateInput', e.target.value)}
                                               placeholder="e.g., 5.0" disabled={isSaving || isFetchingRate} style={{width:'80px'}}/>
                                        <button
                                            type="button"
                                            onClick={() => handleFetchRate(acc.id)}
                                            disabled={isSaving || isFetchingRate}
                                            style={{marginLeft:'5px'}}
                                            title="Attempt to fetch rate from Plaid"
                                        >
                                            {isFetchingRate ? 'Fetching...' : 'Fetch'}
                                        </button>
                                    </div>

                                    {/* Desired Duration Input */}
                                    <div>
                                        <label>Desired Payoff (Yrs): </label><br />
                                        <input type="number" step="0.5" value={state.durationInput || ''}
                                               onChange={(e) => handleInputChange(acc.id, 'durationInput', e.target.value)}
                                               placeholder="e.g., 5" disabled={isSaving} style={{width:'60px'}}/>
                                    </div>

                                     {/* Calculated Payment Display */}
                                    <div>
                                        <label>Est. Monthly Payment:</label><br />
                                        <span style={{ display:'inline-block', minWidth:'80px', fontWeight:'bold'}}>
                                            {state.calculatedPayment !== null ? formatCurrency(state.calculatedPayment) : 'N/A'}
                                        </span>
                                    </div>

                                    {/* User Chosen Payment Input */}
                                    <div>
                                        <label>Your Monthly Payment:</label><br />
                                        <input type="number" step="0.01" value={state.paymentInput || ''}
                                               onChange={(e) => handleInputChange(acc.id, 'paymentInput', e.target.value)}
                                               placeholder="Enter amount" disabled={isSaving} style={{width:'100px'}}/>
                                    </div>

                                    {/* Calculated Payback Time Display */}
                                    <div>
                                         <label>Est. Payback Time:</label><br/>
                                         <span style={{ display:'inline-block', minWidth:'100px', fontWeight:'bold'}}>
                                             {state.paybackTime ?
                                                 (state.paybackTime.years === Infinity ? 'Never (Payment < Interest)' : `${state.paybackTime.years} yrs, ${state.paybackTime.months} mos`)
                                                 : 'N/A'
                                             }
                                         </span>
                                     </div>

                                    {/* Save Button & Messages */}
                                    <div>
                                        <button onClick={() => handleSaveLoanDetails(acc.id)} disabled={isSaving || !isChanged}> {/* Only enable if changed */}
                                            {isSaving ? 'Saving...' : 'Save Rate/Payment'}
                                        </button>
                                        {message && ( <span style={{ color: message.type === 'success' ? 'green' : 'red', marginLeft: '10px' }}> {message.text} </span> )}
                                    </div>
                                </div>
                            </li>
                        );
                    })}
                </ul>
            )}
        </div>
    );
};

export default LoanSettings;
