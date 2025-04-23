import React from 'react'; // Removed useState, useEffect
// Keep Recharts imports
import { PieChart, Pie, Cell, Tooltip, Legend, ResponsiveContainer } from 'recharts';

// Keep COLORS array and formatCurrency helper
const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884d8', '#82ca9d', '#ffc658'];


// Helper to format currency
const formatCurrency = (value) => {
  if (value === null || value === undefined) return 'N/A';
  return Number(value).toLocaleString('en-US', { style: 'currency', currency: 'USD' });
};

const BudgetSummaryTransactions = ({ data, title = "Expense Summary"})=> {

  // Basic validation of the passed data
  if (!data) {
    return <p>Loading summary data...</p>; // Or some loading indicator
  }
  if (!Array.isArray(data)) {
     console.error("BudgetSummary received invalid data prop:", data);
     return <p>Invalid summary data format.</p>;
  }
   if (data.length === 0) {
    return <p>No expense data found for this period/filter.</p>;
  }

   // Prepare data for Pie chart (assuming input 'data' is like [{category: 'X', total: -100}, ...])
   // Filter expenses and map to { name: category, value: abs(total) }
   const chartData = data
     // .filter(item => item.total < 0) // Ensure we only chart expenses
     .map(item => ({
         name: item.category,
         value: Math.abs(item.total)
     }));

   if (chartData.length === 0) {
       return <p>No expense data found for this period/filter to display chart.</p>
   }

  // Rendering logic remains the same, using chartData
  return (
    <div style={{ width: '100%', height: 300 }}>
      <h4>{title}</h4> {/* Use title prop */}
      <ResponsiveContainer>
        <PieChart>
          <Pie
            data={chartData} // Use processed chartData
            cx="50%" // Center X
            cy="50%" // Center Y
            labelLine={false}
            // label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`} // Example label
            outerRadius={80}
            fill="#8884d8"
            dataKey="value"
          >
            {chartData.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip formatter={(value) => formatCurrency(value)} />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
};

export default BudgetSummaryTransactions;
