import './App.css'
import PlaidLinkButton from './components/PlaidLinkButton';
import PortfolioOverview from './components/PortfolioOverview.jsx';

function App() {
  return (
      <div className="App">
          <h1>finsmar</h1>
          <p>Your Personal Finance Dashboard</p>
          <hr />
          <PlaidLinkButton /> {/* Render the button component */}
          <hr />
          <h2>Portfolio Overview</h2>
          <PortfolioOverview /> {/* Render the overview component */}
        </div>
  )
}

export default App
