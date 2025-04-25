import React from 'react';
import ProfileSettings from '../components/ProfileSettings';
import RecurringExpensesManager from '../components/RecurringExpensesManager';
import LoanSettings from '../components/LoanSettings';
import CreditCardSettings from '../components/CreditCardSettings.jsx'

const SettingsPage = () => {
  return (
    <div>
      <h2>Settings</h2>

      <section>
        <h3>Profile / Salary</h3>
        <ProfileSettings />
      </section>

      <hr style={{margin: '20px 0'}}/>

      <section>
        <h3>Recurring Expenses</h3>
        <RecurringExpensesManager />
      </section>

       <hr style={{margin: '20px 0'}}/>

       <section>
         <h3>Loan Account Details</h3>
         <LoanSettings />
       </section>

       <hr style={{margin: '20px 0'}}/>
       <section>
         <h3>Credit Card Details</h3>
         <CreditCardSettings />
       </section>

    </div>
  );
};

export default SettingsPage;
