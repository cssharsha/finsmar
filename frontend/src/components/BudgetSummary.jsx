import React, { useState, useEffect } from 'react';
import axios from 'axios';
// Import Recharts components
import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from 'recharts';

const API_BASE_URL = 'http://localhost:5001'; // Backend URL

// Predefined colors for categories - expand as needed
const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884d8', '#82ca9d', '#ffc658'];

// Helper to format currency
const formatCurrency = (value) => {
  if (value === null || value === undefined) return 'N/A';
  return Number(value).toLocaleString('en-US', { style: 'currency', currency: 'USD' });
};

const BudgetSummary = ({ year, month }) => { // Accept year/month as props
  const [summaryData, setSummaryData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  // Ensure year is 4 digits and month is 2 digits with leading zero if needed
  const formattedYear = String(year).padStart(4, '0');
  const formattedMonth = String(month).padStart(2, '0');

  useEffect(() => {
    const fetchSummary = async () => {
      if (!year || !month) {
         setError("Year and month are required.");
         setLoading(false);
         return;
      }
      
      setLoading(true);
      setError(null);
      try {
        const response = await axios.get(`${API_BASE_URL}/api/budget/summary/${formattedYear}/${formattedMonth}`);
        console.log(`Budget summary for ${formattedYear}-${formattedMonth}:`, response.data);

        // Prepare data for Pie chart (needs 'name' and 'value')
        // Assuming 'total' is negative for expenses, make value positive for chart
        const chartData = response.data
             // .filter(item => item.total < 0) // Filter only expenses for typical budget chart
             .map(item => ({
                 name: item.category,
                 value: Math.abs(item.total) // Use absolute value for chart size
             }));

        setSummaryData(chartData);
      } catch (fetchError) {
        console.error(`Error fetching budget summary for ${formattedYear}-${formattedMonth}:`, fetchError.response ? fetchError.response.data : fetchError);
        setError(`Failed to fetch budget summary for ${formattedYear}-${formattedMonth}.`);
      } finally {
        setLoading(false);
      }
    };

    fetchSummary();
  }, [year, month]); // Re-fetch if year or month props change

  if (loading) return <p>Loading budget summary...</p>;
  if (error) return <p style={{ color: 'red' }}>Error: {error}</p>;
  if (summaryData.length === 0) return <p>No expense data found for {formattedYear}-{formattedMonth} to display summary.</p>;

  return (
    <div style={{ width: '100%', height: 300 }}> {/* Set height for ResponsiveContainer */}
      <h4>Expenses for {formattedYear}-{formattedMonth}</h4>
      <ResponsiveContainer>
        <PieChart>
          <Pie
            data={summaryData}
            cx="50%" // Center X
            cy="50%" // Center Y
            labelLine={false}
            // label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`} // Example label
            outerRadius={80}
            fill="#8884d8"
            dataKey="value" // Tells Pie which data field determines slice size
          >
            {summaryData.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
            ))}
          </Pie>
          {/* Tooltip shows details on hover */}
          <Tooltip formatter={(value) => formatCurrency(value)} />
          {/* Legend lists categories */}
          <Legend />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
};

export default BudgetSummary;
