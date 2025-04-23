import React from 'react';
import { Routes, Route, Link } from 'react-router-dom'; // Import routing components
import './App.css'
// Import components/pages (create TransactionsPage next)
import PlaidLinkButton from './components/PlaidLinkButton';
import PortfolioOverview from './components/PortfolioOverview';
import BudgetSummary from './components/BudgetSummary';
import TransactionsPage from './pages/TransactionsPage'; // We will create this page
import SettingsPage from './pages/SettingsPage';
import BudgetCalculationDisplay from './components/BudgetCalculationDisplay';

function App() {
  const currentDate = new Date();
  const currentYear = currentDate.getFullYear();
  const currentMonth = currentDate.getMonth() + 1;

  return (
    <div className="App">
      <h1>finsmar</h1>
      <nav style={{ marginBottom: '20px', borderBottom: '1px solid #ccc', paddingBottom: '10px' }}>
        <Link to="/" style={{ marginRight: '15px' }}>Dashboard</Link>
        <Link to="/transactions" style={{ marginRight: '15px' }}>Transactions</Link>
        <Link to="/settings">Settings</Link>
        {/* Add more links later */}
      </nav>

      <Routes>
        {/* Route for the main Dashboard */}
        <Route path="/" element={
          <> {/* Use Fragment to group elements */}
            <p>Your Personal Finance Dashboard</p>
            <hr />
            <BudgetCalculationDisplay />
            <hr />
            <PlaidLinkButton />
            <hr />
            <h2>Portfolio Overview</h2>
            <PortfolioOverview />
            <hr />
            <h2>Budget Summary ({currentYear}-{currentMonth})</h2>
            <BudgetSummary year={currentYear} month={currentMonth} />
            <hr />
          </>
        } />

        {/* Route for the Transactions Page */}
        <Route path="/transactions" element={<TransactionsPage />} />
        <Route path="/settings" element={<SettingsPage />} />

        {/* Add more routes later */}
      </Routes>
    </div>
  )
}

export default App
