import React, { useState } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom'; // To redirect after success

const API_BASE_URL = 'http://localhost:5001';

const AddAccountPage = () => {
    const navigate = useNavigate(); // Hook for navigation
    const [formData, setFormData] = useState({
        name: '',
        account_type: 'depository', // Default type
        account_subtype: '',
        balance: '', // Will store quantity for investment/crypto
        // Loan specific
        loan_monthly_payment: '',
        loan_original_amount: '',
        loan_interest_rate: '', // Expect user to enter decimal e.g., 0.05 for 5%
    });
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState(null);
    const [success, setSuccess] = useState('');

    const accountTypes = ['depository', 'credit', 'loan', 'investment', 'crypto', 'other'];

    const handleInputChange = (e) => {
        const { name, value } = e.target;
        setFormData(prev => ({ ...prev, [name]: value }));
        setError(null); // Clear errors on input change
        setSuccess('');
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setIsLoading(true);
        setError(null);
        setSuccess('');

        // Basic frontend validation
        if (!formData.name || !formData.account_type || formData.balance === '') {
             setError("Name, Account Type, and Balance/Quantity are required.");
             setIsLoading(false);
             return;
        }

        // Prepare payload based on type
        const payload = {
            name: formData.name,
            account_type: formData.account_type,
            balance: formData.balance, // Backend expects decimal string or number
            account_subtype: formData.account_subtype || null, // Send null if empty
        };

        if (formData.account_type === 'loan') {
            if (formData.loan_monthly_payment) payload.loan_monthly_payment = formData.loan_monthly_payment;
            if (formData.loan_original_amount) payload.loan_original_amount = formData.loan_original_amount;
            if (formData.loan_interest_rate) payload.loan_interest_rate = formData.loan_interest_rate; // Send decimal representation string
        }

        try {
            const response = await axios.post(`${API_BASE_URL}/api/accounts`, payload);
            setSuccess(`Account "${response.data.name}" created successfully! Redirecting...`);
            // Clear form (optional)
            setFormData({ name: '', account_type: 'depository', account_subtype: '', balance: '', loan_monthly_payment: '', loan_original_amount: '', loan_interest_rate: '' });
            // Redirect to dashboard after a short delay
            setTimeout(() => {
                navigate('/'); // Navigate to dashboard
            }, 2000); // 2 second delay

        } catch (err) {
            console.error("Error adding manual account:", err.response?.data || err);
            setError(err.response?.data?.error || "Failed to add account.");
        } finally {
            setIsLoading(false);
        }
    };

    // Determine balance label based on type
    const balanceLabel = ['investment', 'crypto'].includes(formData.account_type) ? 'Quantity*' : 'Current Balance*';

    return (
        <div>
            <h2>Add Manual Account</h2>
            <form onSubmit={handleSubmit}>
                {/* Account Type Dropdown */}
                <div>
                    <label htmlFor="account_type">Account Type*: </label>
                    <select name="account_type" id="account_type" value={formData.account_type} onChange={handleInputChange} required>
                        {accountTypes.map(type => (
                            <option key={type} value={type}>{type.charAt(0).toUpperCase() + type.slice(1)}</option>
                        ))}
                    </select>
                </div>

                {/* Common Fields */}
                <div style={{marginTop: '10px'}}>
                    <label htmlFor="name">Account Name*: </label>
                    <input type="text" id="name" name="name" value={formData.name} onChange={handleInputChange} required />
                </div>
                <div style={{marginTop: '10px'}}>
                    <label htmlFor="balance">{balanceLabel}: </label>
                    <input type="number" id="balance" name="balance" value={formData.balance} onChange={handleInputChange} required step="any" placeholder={balanceLabel === 'Quantity*' ? "e.g., 10.5" : "e.g., 1000.00"}/>
                </div>
                <div style={{marginTop: '10px'}}>
                    <label htmlFor="account_subtype">Subtype/Symbol: </label>
                    <input type="text" id="account_subtype" name="account_subtype" value={formData.account_subtype} onChange={handleInputChange} placeholder={formData.account_type === 'investment' || formData.account_type === 'crypto' ? 'e.g., VTI or BTC' : 'e.g., Checking'}/>
                </div>

                {/* Conditional Loan Fields */}
                {formData.account_type === 'loan' && (
                    <>
                         <hr style={{margin:'15px 0'}}/>
                         <h4>Loan Details (Optional)</h4>
                         <div style={{marginTop: '10px'}}>
                            <label htmlFor="loan_monthly_payment">Monthly Payment: </label>
                            <input type="number" id="loan_monthly_payment" name="loan_monthly_payment" value={formData.loan_monthly_payment} onChange={handleInputChange} step="0.01" />
                        </div>
                         <div style={{marginTop: '10px'}}>
                            <label htmlFor="loan_interest_rate">Interest Rate (Decimal): </label>
                            <input type="number" id="loan_interest_rate" name="loan_interest_rate" value={formData.loan_interest_rate} onChange={handleInputChange} step="0.0001" placeholder="e.g., 0.05 for 5%"/>
                        </div>
                        <div style={{marginTop: '10px'}}>
                            <label htmlFor="loan_original_amount">Original Amount: </label>
                            <input type="number" id="loan_original_amount" name="loan_original_amount" value={formData.loan_original_amount} onChange={handleInputChange} step="0.01" />
                        </div>
                        <hr style={{margin:'15px 0'}}/>
                    </>
                )}

                {/* Submit Button & Messages */}
                <div style={{marginTop: '20px'}}>
                    <button type="submit" disabled={isLoading}>
                        {isLoading ? 'Saving...' : 'Add Account'}
                    </button>
                    {error && <p style={{ color: 'red' }}>Error: {error}</p>}
                    {success && <p style={{ color: 'green' }}>{success}</p>}
                </div>
            </form>
        </div>
    );
};

export default AddAccountPage;
