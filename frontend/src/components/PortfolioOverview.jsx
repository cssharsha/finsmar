// frontend/src/components/PortfolioOverview.jsx
import React, { useState, useEffect } from 'react';
import axios from 'axios';

const API_BASE_URL = 'http://localhost:5001'; // Backend URL

// Helper to format currency nicely
const formatCurrency = (value) => {
  if (value === null || value === undefined) return 'N/A';
  // Use toLocaleString for basic formatting, add more robust library later if needed
  return Number(value).toLocaleString('en-US', { style: 'currency', currency: 'USD' });
};

// Helper to format quantity/balance
 const formatQuantity = (value) => {
    if (value === null || value === undefined) return 'N/A';
    // Adjust formatting based on typical precision needed
    return Number(value).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 8 });
 };


const PortfolioOverview = () => {
  const [portfolioData, setPortfolioData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchPortfolio = async () => {
      setLoading(true);
      setError(null);
      try {
        const response = await axios.get(`${API_BASE_URL}/api/portfolio/overview`);
        console.log("Portfolio data received:", response.data); // Log for debugging
        setPortfolioData(response.data);
      } catch (fetchError) {
        console.error('Error fetching portfolio overview:', fetchError.response ? fetchError.response.data : fetchError);
        setError('Failed to fetch portfolio data. Is the backend running?');
      } finally {
        setLoading(false);
      }
    };

    fetchPortfolio();
    // Optional: Add a timer to refetch periodically?
    // const intervalId = setInterval(fetchPortfolio, 60000); // e.g., every 60 seconds
    // return () => clearInterval(intervalId); // Cleanup interval on unmount
  }, []); // Empty array means run once on mount

  if (loading) {
    return <p>Loading portfolio...</p>;
  }

  if (error) {
    return <p style={{ color: 'red' }}>Error: {error}</p>;
  }

  if (!portfolioData || !portfolioData.account_details) {
    return <p>No portfolio data available.</p>;
  }

  // Basic rendering - improve styling later
  return (
    <div>
      <h3>Summary</h3>
      <p><strong>Total Value (Assets):</strong> {formatCurrency(portfolioData.total_value_usd)}</p>
      <p><strong>Cash:</strong> {formatCurrency(portfolioData.cash_total_usd)}</p>
      <p><strong>Investments (Stocks/ETF):</strong> {formatCurrency(portfolioData.investment_total_usd)}</p>
      <p><strong>Crypto:</strong> {formatCurrency(portfolioData.crypto_total_usd)}</p>
      {portfolioData.loan_total_usd > 0 && (
         <p><strong>Loans (Outstanding):</strong> {formatCurrency(portfolioData.loan_total_usd)}</p>
      )}

      <h3>Accounts / Holdings</h3>
      {portfolioData.account_details.length === 0 ? (
         <p>No accounts or holdings found.</p>
      ) : (
        <table border="1" style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th>Name/Symbol</th>
              <th>Type</th>
              <th>Source</th>
              <th>Quantity/Balance</th>
              <th>Price (USD)</th>
              <th>Market Value (USD)</th>
            </tr>
          </thead>
          <tbody>
            {portfolioData.account_details.map((account) => (
              <tr key={account.id || account.external_id}> {/* Use a unique key */}
                <td>{account.name || account.subtype || 'N/A'}</td>
                <td>{account.type}{account.subtype ? ` (${account.subtype})` : ''}</td>
                <td>{account.source}</td>
                {/* Display native balance */}
                <td>{formatQuantity(account.balance)}</td>
                 {/* Display price and market value if available */}
                <td>{account.price_usd !== null ? formatCurrency(account.price_usd) : 'N/A'}</td>
                <td>{account.market_value_usd !== null ? formatCurrency(account.market_value_usd) : 'N/A'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
};

export default PortfolioOverview;
