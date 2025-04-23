import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';

const API_BASE_URL = 'http://localhost:5001';

// Formatting helper
const formatCurrency = (value) => {
    if (value === null || value === undefined) return 'N/A';
    return Number(value).toLocaleString('en-US', { style: 'currency', currency: 'USD' });
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

    // Fetch all account data on mount to filter loans
    const fetchAccounts = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            // Use the overview endpoint which includes account type
            const response = await axios.get(`${API_BASE_URL}/api/portfolio/overview`);
            const allAccounts = response.data?.account_details || [];
            const loans = allAccounts.filter(acc => acc.type === 'loan');
            setLoanAccounts(loans);

            // Initialize paymentInputs state based on fetched data
            const initialPayments = {};
            loans.forEach(acc => {
                initialPayments[acc.id] = acc.loan_monthly_payment !== null && acc.loan_monthly_payment !== undefined
                    ? String(acc.loan_monthly_payment) // Store as string for input
                    : '';
            });
            setPaymentInputs(initialPayments);

        } catch (err) {
            console.error("Error fetching accounts for loan settings:", err);
            setError("Could not load account data.");
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchAccounts();
    }, [fetchAccounts]);

    // Handle changes in the input field for a specific loan
    const handlePaymentChange = (accountId, value) => {
        setPaymentInputs(prev => ({ ...prev, [accountId]: value }));
        // Clear message when user starts typing
        setMessageStates(prev => ({ ...prev, [accountId]: null }));
    };

    // Handle saving the payment for a specific loan
    const handleSavePayment = async (accountId) => {
        setSavingStates(prev => ({ ...prev, [accountId]: true }));
        setMessageStates(prev => ({ ...prev, [accountId]: null })); // Clear previous messages
        const paymentValue = paymentInputs[accountId];

        try {
            const payload = {
                // Send null if empty string, otherwise send the value
                loan_monthly_payment: paymentValue.trim() === '' ? null : paymentValue
            };
            const response = await axios.put(`${API_BASE_URL}/api/accounts/${accountId}`, payload);

            // Update the main loanAccounts state to reflect saved value immediately
            setLoanAccounts(prevAccounts => prevAccounts.map(acc =>
                acc.id === accountId ? { ...acc, loan_monthly_payment: response.data.loan_monthly_payment } : acc
            ));
            // Update the input state as well to handle potential backend formatting/null conversion
            setPaymentInputs(prev => ({ ...prev, [accountId]: String(response.data.loan_monthly_payment ?? '')}));

            setMessageStates(prev => ({ ...prev, [accountId]: { type: 'success', text: 'Saved!' } }));
            // Clear success message after a few seconds
            setTimeout(() => setMessageStates(prev => ({ ...prev, [accountId]: null })), 3000);

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
                         // Check if the current input value is different from the saved value
                        const savedValueStr = String(acc.loan_monthly_payment ?? '');
                        const currentValueStr = paymentInputs[acc.id] ?? '';
                        const isChanged = savedValueStr !== currentValueStr;
                        const isSaving = savingStates[acc.id];
                        const message = messageStates[acc.id];

                        return (
                            <li key={acc.id} style={{ marginBottom: '10px', paddingBottom: '10px', borderBottom: '1px dotted #ccc' }}>
                                <strong>{acc.name}</strong> ({acc.source}) - Current Balance: {formatCurrency(acc.balance)}
                                <div style={{ marginTop: '5px' }}>
                                    <label htmlFor={`loan_payment_${acc.id}`}>Est. Monthly Payment: $</label>
                                    <input
                                        type="number"
                                        id={`loan_payment_${acc.id}`}
                                        value={paymentInputs[acc.id] ?? ''}
                                        onChange={(e) => handlePaymentChange(acc.id, e.target.value)}
                                        placeholder="Enter amount"
                                        step="0.01"
                                        style={{ width: '100px', marginLeft: '5px', marginRight: '10px' }}
                                        disabled={isSaving}
                                    />
                                    <button
                                        onClick={() => handleSavePayment(acc.id)}
                                        disabled={isSaving || !isChanged} // Disable if saving or unchanged
                                    >
                                        {isSaving ? 'Saving...' : 'Save'}
                                    </button>
                                    {message && (
                                        <span style={{ color: message.type === 'success' ? 'green' : 'red', marginLeft: '10px' }}>
                                            {message.text}
                                        </span>
                                    )}
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
