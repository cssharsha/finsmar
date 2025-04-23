import React, { useState, useEffect } from 'react';
import axios from 'axios';

const API_BASE_URL = 'http://localhost:5001';

// Use currency formatting helper if needed
const formatCurrency = (value) => {
  if (value === null || value === undefined) return 'N/A';
  return Number(value).toLocaleString('en-US', { style: 'currency', currency: 'USD' });
};

const BudgetCalculationDisplay = () => {
    const [calcData, setCalcData] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    // Fetch calculation data
    const fetchCalculation = async () => {
         setLoading(true);
         setError(null);
         try {
             const response = await axios.get(`${API_BASE_URL}/api/budget/calculation`);
             setCalcData(response.data);
         } catch (err) {
             console.error("Error fetching budget calculation:", err.response?.data || err);
             setError("Could not load budget calculation.");
         } finally {
             setLoading(false);
         }
     };

    // Fetch on mount
    useEffect(() => {
        fetchCalculation();
        // TODO: Add mechanism to re-fetch when underlying data changes (e.g., after saving salary)
        // Could use a global state, context, or prop drilling/callbacks.
    }, []);

    if (loading) {
        return <p>Loading budget calculation...</p>;
    }
    if (error) {
         return <p style={{ color: 'red' }}>Error: {error}</p>;
    }
    if (!calcData) {
         return <p>Budget calculation data unavailable.</p>;
    }

    // Display the data
    return (
        <div style={{ border: '1px solid #eee', padding: '10px', margin: '15px 0' }}>
            <h4>Budget Calculation</h4>
            <p>Est. Monthly Salary: {formatCurrency(calcData.monthly_salary_estimate)}</p>
            <p>Total Recurring Expenses: {formatCurrency(calcData.total_recurring_expenses_monthly)}</p>
            <p>Total Loan Payments: {formatCurrency(calcData.total_loan_payments_monthly)}</p>
            <p><strong>Estimated Available/Surplus: {formatCurrency(calcData.estimated_available_monthly)}</strong></p>
            <small>Calculation as of: {new Date(calcData.calculation_timestamp).toLocaleString()}</small>
            {/* Add button to refresh? onClick={fetchCalculation} */}
        </div>
    );
};

export default BudgetCalculationDisplay;
