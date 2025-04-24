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
                initialStates[acc.id] = {
                    balance: acc.balance ?? 0,
                    rateInput: acc.loan_interest_rate !== null ? String(acc.loan_interest_rate * 100) : '', // Convert decimal rate TO percentage string for input
                    durationInput: '', // Start duration empty
                    paymentInput: acc.loan_monthly_payment !== null ? String(acc.loan_monthly_payment) : '', // User's chosen payment
                    calculatedPayment: null,
                    paybackTime: null,
                    isSaving: false,
                    message: null,
                    // Store original fetched values to check for changes
                    originalRate: acc.loan_interest_rate !== null ? String(acc.loan_interest_rate * 100) : '',
                    originalPayment: acc.loan_monthly_payment !== null ? String(acc.loan_monthly_payment) : ''
                };
                // Initial calculation if possible
                 initialStates[acc.id].calculatedPayment = calculateMonthlyPayment(
                       initialStates[acc.id].balance,
                       parseFloat(initialStates[acc.id].rateInput || 0),
                       parseFloat(initialStates[acc.id].durationInput || 0)
                 );
                 initialStates[acc.id].paybackTime = calculatePaybackTime(
                       initialStates[acc.id].balance,
                       parseFloat(initialStates[acc.id].rateInput || 0),
                       parseFloat(initialStates[acc.id].paymentInput || 0)
                 );
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

    // --- Handler for Fetching Rate ---
    const handleFetchRate = async (accountId) => {
        setFetchingRateId(accountId); // Show loading state for this button
        // Clear previous message for this account
        setAccountState(prev => ({...prev, [accountId]: {...prev[accountId], message: null}}));
        try {
            const response = await axios.get(`${API_BASE_URL}/api/accounts/${accountId}/fetch_plaid_rate`);
            if (response.data && response.data.interest_rate !== null) {
                const ratePercent = (response.data.interest_rate * 100).toFixed(4); // Convert decimal to % string
                // Update the input field state
                handleInputChange(accountId, 'rateInput', ratePercent);
                 setMessageStates(prev => ({...prev, [accountId]: { type: 'success', text: 'Rate fetched!' }}));
                 setTimeout(() => setMessageStates(prev => ({ ...prev, [accountId]: null })), 3000);
            } else {
                 setMessageStates(prev => ({...prev, [accountId]: { type: 'error', text: response.data.error || 'Rate not available' }}));
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
            const newState = {
                ...prev,
                [accountId]: recalculateForAccount(accountId, {
                    ...prev[accountId],
                    [fieldName]: value,
                    message: null // Clear message on input change
                })
            };
            return newState;
        });
    };

    // Handle saving the payment for a specific loan
    const handleSaveLoanDetails = async (accountId) => {
        const currentDetails = accountState[accountId];
        if (!currentDetails) return;

        setAccountState(prev => ({ ...prev, [accountId]: {...prev[accountId], isSaving: true, message: null} }));

        try {
            // Convert rate from % string to decimal string or null for backend
            let rateDecimal = null;
            if (currentDetails.rateInput.trim() !== '') {
                 rateDecimal = String(parseFloat(currentDetails.rateInput) / 100.0);
            }

            const payload = {
                // Send user's chosen payment (allow null)
                loan_monthly_payment: currentDetails.paymentInput.trim() === '' ? null : currentDetails.paymentInput,
                // Send interest rate (allow null)
                loan_interest_rate: rateDecimal
                // We don't save duration or original amount currently
            };

            const response = await axios.put(`${API_BASE_URL}/api/accounts/${accountId}`, payload);

            // Update state with saved values from response to ensure consistency
            const updatedRateStr = response.data.loan_interest_rate !== null ? String(response.data.loan_interest_rate * 100) : '';
            const updatedPaymentStr = response.data.loan_monthly_payment !== null ? String(response.data.loan_monthly_payment) : '';

            setAccountState(prev => ({
                 ...prev,
                 [accountId]: recalculateForAccount(accountId, {
                     ...prev[accountId],
                     isSaving: false,
                     message: { type: 'success', text: 'Saved!' },
                     // Update inputs to match saved state
                     rateInput: updatedRateStr,
                     paymentInput: updatedPaymentStr,
                     // Update original values to prevent immediate re-save
                     originalRate: updatedRateStr,
                     originalPayment: updatedPaymentStr
                 })
             }));
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
                                        <button onClick={() => handleSaveLoanDetails(acc.id)} disabled={isSaving || !isChanged}>
                                            {isSaving ? 'Saving...' : 'Save Details'}
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
