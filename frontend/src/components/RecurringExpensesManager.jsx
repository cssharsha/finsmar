import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';

const API_BASE_URL = 'http://localhost:5001';

// Formatting helpers (can move to a utils file later)
const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    // Input type="date" expects YYYY-MM-DD, so ensure consistent format
    try {
        return new Date(dateString).toISOString().split('T')[0];
    } catch (e) { return 'Invalid Date'; }
};
const formatCurrency = (value) => {
    if (value === null || value === undefined) return 'N/A';
    return Number(value).toLocaleString('en-US', { style: 'currency', currency: 'USD' });
};

const RecurringExpensesManager = () => {
    // State for the list of expenses
    const [expenses, setExpenses] = useState([]);
    const [loadingList, setLoadingList] = useState(true);
    const [listError, setListError] = useState(null);

    // State for the 'Add New Expense' form
    const [newExpense, setNewExpense] = useState({
        name: '', amount: '', budget_category: '', frequency: 'monthly', next_due_date: '', notes: ''
    });
    const [isAdding, setIsAdding] = useState(false);
    const [addError, setAddError] = useState(null);
    const [addSuccess, setAddSuccess] = useState('');

    const [editingExpenseId, setEditingExpenseId] = useState(null); // ID of expense being edited, or null
    const [editFormData, setEditFormData] = useState({}); // Data for the expense being edited
    const [isUpdating, setIsUpdating] = useState(false);
    const [updateError, setUpdateError] = useState(null);
    const [updateSuccess, setUpdateSuccess] = useState('');
    const [availableCategories, setAvailableCategories] = useState([]);

    // --- Fetching Logic ---
    const fetchExpenses = useCallback(async () => {
        setLoadingList(true);
        setListError(null);
        try {
            const response = await axios.get(`${API_BASE_URL}/api/recurring_expenses`);
            setExpenses(response.data || []);
        } catch (err) {
            console.error("Error fetching recurring expenses:", err);
            setListError("Could not load recurring expenses.");
        } finally {
            setLoadingList(false);
        }
    }, []);

    // Fetch expenses when component mounts
    useEffect(() => {
        fetchExpenses();
    }, [fetchExpenses]);

    useEffect(() => {
        const fetchCategories = async () => {
            try {
                const response = await axios.get(`${API_BASE_URL}/api/budget/categories`);
                setAvailableCategories(response.data.categories || []);
                console.log("Fetched available categories for dropdown:", response.data.categories);
            } catch (err) {
                console.error("Error fetching budget categories for dropdown:", err);
                // Handle error - maybe show a message or allow text input as fallback?
                // For now, dropdown will just be empty if fetch fails.
            }
        };
        fetchCategories();
    }, []);

    // --- Form Handling ---
    const handleNewExpenseChange = (e) => {
        const { name, value } = e.target;
        setNewExpense(prev => ({ ...prev, [name]: value }));
    };

    const handleAddExpense = async (e) => {
        e.preventDefault();
        // Basic validation
        if (!newExpense.name || !newExpense.amount || !newExpense.budget_category) {
            setAddError("Name, Amount, and Category are required.");
            return;
        }
        setIsAdding(true);
        setAddError(null);
        setAddSuccess('');

        try {
            const payload = {
                ...newExpense,
                // Ensure amount is sent as a number string if needed, or backend handles Decimal conversion
                amount: newExpense.amount,
                next_due_date: newExpense.next_due_date || null // Send null if empty
            };
            const response = await axios.post(`${API_BASE_URL}/api/recurring_expenses`, payload);
            setAddSuccess(`Expense "${response.data.name}" added successfully!`);
            setNewExpense({ name: '', amount: '', budget_category: '', frequency: 'monthly', next_due_date: '', notes: '' }); // Clear form
            fetchExpenses(); // Refresh the list
        } catch (err) {
            console.error("Error adding recurring expense:", err.response?.data || err);
            setAddError(err.response?.data?.error || "Failed to add expense.");
        } finally {
            setIsAdding(false);
        }
    };

    const handleDeleteExpense = async (expenseId, expenseName) => {
        // Confirm before deleting
        if (!window.confirm(`Are you sure you want to delete "${expenseName}"? This will mark it inactive.`)) {
            return;
        }
        // We don't need specific loading state for delete, list loading handles refresh
        setListError(null); // Clear previous list errors
        try {
            await axios.delete(`${API_BASE_URL}/api/recurring_expenses/${expenseId}`);
            // Optionally show a temporary success message
            alert(`Expense "${expenseName}" marked inactive.`); // Simple alert for now
            fetchExpenses(); // Refresh the list to remove the item visually
        } catch (err) {
            console.error("Error deleting recurring expense:", err.response?.data || err);
            setListError(err.response?.data?.error || "Failed to delete expense."); // Show error related to the list
        }
    };

    const handleEditClick = (expense) => {
        setEditingExpenseId(expense.id);
        // Pre-fill edit form data (make sure date is formatted correctly for input type="date")
        setEditFormData({
            ...expense,
            amount: expense.amount ?? '', // Use original number or empty string
            next_due_date: expense.next_due_date ? formatDate(expense.next_due_date) : '', // Format date
        });
        setUpdateError(null); // Clear any previous edit errors
        setUpdateSuccess('');
        setAddError(null); // Clear add errors when starting edit
        setAddSuccess('');
    };

    const handleCancelEdit = () => {
        setEditingExpenseId(null);
        setEditFormData({});
        setUpdateError(null);
        setUpdateSuccess('');
    };

    const handleEditFormChange = (e) => {
        const { name, value } = e.target;
        setEditFormData(prev => ({ ...prev, [name]: value }));
    };

    const handleUpdateExpense = async (e) => {
        e.preventDefault();
        if (!editingExpenseId) return;

        // Basic validation
        if (!editFormData.name || editFormData.amount === '' || !editFormData.budget_category) {
            setUpdateError("Name, Amount, and Category are required for update.");
            return;
        }
        setIsUpdating(true);
        setUpdateError(null);
        setUpdateSuccess('');

        try {
            const payload = {
                ...editFormData,
                 // Ensure amount is number string or backend handles Decimal
                amount: editFormData.amount,
                next_due_date: editFormData.next_due_date || null // Send null if empty
            };
            // Remove id from payload if backend doesn't expect it
            delete payload.id;
            delete payload.created_at;
            delete payload.updated_at;

            const response = await axios.put(`${API_BASE_URL}/api/recurring_expenses/${editingExpenseId}`, payload);
            setUpdateSuccess(`Expense "${response.data.name}" updated successfully!`);
            setEditingExpenseId(null); // Exit edit mode
            fetchExpenses(); // Refresh the list
        } catch (err) {
            console.error("Error updating recurring expense:", err.response?.data || err);
            setUpdateError(err.response?.data?.error || "Failed to update expense.");
        } finally {
            setIsUpdating(false);
        }
    };

    // --- Render Logic ---
    return (
        <div>
            {/* --- Conditionally Render Add or Edit Form --- */}
            {editingExpenseId ? (
                <> {/* --- Edit Form --- */}
                 <h4>Edit Recurring Expense</h4>
                 <form onSubmit={handleUpdateExpense} style={{ marginBottom: '20px', padding: '10px', border: '1px solid #ccc', backgroundColor: '#f0f0f0' }}>
                     {/* Use editFormData and handleEditFormChange */}
                     <div>
                        <label>Name*: <input type="text" name="name" value={editFormData.name || ''} onChange={handleEditFormChange} required disabled={isUpdating} /></label>
                        <label style={{ marginLeft: '10px' }}>Amount*: <input type="number" step="0.01" name="amount" value={editFormData.amount || ''} onChange={handleEditFormChange} required disabled={isUpdating} /></label>
                    </div>
                    {/* ... other inputs for category, frequency, due date, notes, bound to editFormData ... */}
                    <div style={{marginTop: '10px'}}>
                     <label>Category*:
                        {/* --- Use Dropdown in Edit Form --- */}
                            <select
                                 name="budget_category"
                                 value={editFormData.budget_category || ''}
                                 onChange={handleEditFormChange} // Use edit form handler
                                 required
                                 disabled={isUpdating}
                             >
                                 <option value="">-- Select Category --</option>
                                 {/* You might want a combined list of existing + maybe specific edit category */}
                                 {/* Simple approach: Use fetched categories */}
                                 {availableCategories.map(cat => (
                                     <option key={cat} value={cat}>{cat}</option>
                                 ))}
                                 {/* Ensure the currently saved category is an option even if not in fetched list? Edge case.*/}
                                 {editFormData.budget_category && !availableCategories.includes(editFormData.budget_category) && (
                                     <option key={editFormData.budget_category} value={editFormData.budget_category}>{editFormData.budget_category} (Current)</option>
                                 )}
                             </select>
                            {/* -------------------------------- */}
                         </label>
                     <label style={{ marginLeft: '10px' }}>Frequency*:
                        <select name="frequency" value={editFormData.frequency || 'monthly'} onChange={handleEditFormChange} disabled={isUpdating}>
                            <option value="monthly">Monthly</option> <option value="yearly">Yearly</option>
                            <option value="quarterly">Quarterly</option> <option value="weekly">Weekly</option>
                        </select>
                     </label>
                    </div>
                    <div style={{marginTop: '10px'}}>
                        <label>Next Due Date: <input type="date" name="next_due_date" value={editFormData.next_due_date || ''} onChange={handleEditFormChange} disabled={isUpdating} /></label>
                     </div>
                     <div style={{marginTop: '10px'}}>
                         <label>Notes: <textarea name="notes" value={editFormData.notes || ''} onChange={handleEditFormChange} disabled={isUpdating} rows={2} style={{verticalAlign: 'middle'}}></textarea></label>
                     </div>
                    {/* Save and Cancel Buttons */}
                    <div style={{marginTop: '10px'}}>
                        <button type="submit" disabled={isUpdating}>
                            {isUpdating ? 'Saving...' : 'Save Changes'}
                        </button>
                        <button type="button" onClick={handleCancelEdit} disabled={isUpdating} style={{ marginLeft: '10px' }}>
                            Cancel Edit
                        </button>
                        {updateError && <span style={{ color: 'red', marginLeft: '10px' }}>Error: {updateError}</span>}
                        {updateSuccess && <span style={{ color: 'green', marginLeft: '10px' }}>{updateSuccess}</span>}
                    </div>
                 </form>
                </>
            ) : (
                <>{/* --- Add Expense Form --- */}
                    <h4>Add New Recurring Expense</h4>
                    <form onSubmit={handleAddExpense} style={{ marginBottom: '20px', padding: '10px', border: '1px solid #ccc' }}>
                        <div>
                            <label>Name*: <input type="text" name="name" value={newExpense.name} onChange={handleNewExpenseChange} required disabled={isAdding} /></label>
                            <label style={{ marginLeft: '10px' }}>Amount*: <input type="number" step="0.01" name="amount" value={newExpense.amount} onChange={handleNewExpenseChange} required disabled={isAdding} /></label>
                        </div>
                        <div style={{marginTop: '10px'}}>
                             <label>Category*:
                                    {/* --- Replace text input with Dropdown --- */}
                                <select
                                    name="budget_category"
                                    value={newExpense.budget_category}
                                    onChange={handleNewExpenseChange} // Use add form handler
                                    required
                                    disabled={isAdding}
                                >
                                    <option value="">-- Select Category --</option>
                                    {availableCategories.map(cat => (
                                        <option key={cat} value={cat}>{cat}</option>
                                    ))}
                                    {/* Option to add a new category? More complex */}
                                </select>
                             </label>
                             <label style={{ marginLeft: '10px' }}>Frequency*:
                                <select name="frequency" value={newExpense.frequency} onChange={handleNewExpenseChange} disabled={isAdding}>
                                    <option value="monthly">Monthly</option>
                                    <option value="yearly">Yearly</option>
                                    <option value="quarterly">Quarterly</option>
                                    <option value="weekly">Weekly</option>
                                    {/* Add other frequencies if needed */}
                                </select>
                             </label>
                        </div>
                         <div style={{marginTop: '10px'}}>
                            <label>Next Due Date: <input type="date" name="next_due_date" value={newExpense.next_due_date} onChange={handleNewExpenseChange} disabled={isAdding} /></label>
                         </div>
                         <div style={{marginTop: '10px'}}>
                             <label>Notes: <textarea name="notes" value={newExpense.notes} onChange={handleNewExpenseChange} disabled={isAdding} rows={2} style={{verticalAlign: 'middle'}}></textarea></label>
                         </div>
                         <div style={{marginTop: '10px'}}>
                            <button type="submit" disabled={isAdding}>
                                 {isAdding ? 'Adding...' : 'Add Expense'}
                            </button>
                            {addError && <span style={{ color: 'red', marginLeft: '10px' }}>Error: {addError}</span>}
                            {addSuccess && <span style={{ color: 'green', marginLeft: '10px' }}>{addSuccess}</span>}
                         </div>
                    </form>
                </>
            )}

            {/* --- List of Expenses --- */}
            <h4>Current Recurring Expenses</h4>
            {loadingList && <p>Loading expenses...</p>}
            {listError && <p style={{ color: 'red' }}>Error: {listError}</p>}
            {!loadingList && !listError && (
                <table border="1" style={{ width: '100%', borderCollapse: 'collapse' }}>
                    <thead>
                        <tr>
                            <th>Name</th>
                            <th>Amount</th>
                            <th>Frequency</th>
                            <th>Category</th>
                            <th>Next Due</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {expenses.length === 0 && <tr><td colSpan="6">No recurring expenses added yet.</td></tr>}
                        {expenses.map(exp => (
                            <tr key={exp.id}>
                                <td>{exp.name}</td>
                                <td>{formatCurrency(exp.amount)}</td>
                                <td>{exp.frequency}</td>
                                <td>{exp.budget_category}</td>
                                <td>{formatDate(exp.next_due_date)}</td>
                                <td>
                                    <button onClick={() => handleEditClick(exp)} disabled={editingExpenseId === exp.id}>
                                        Edit
                                    </button>
                                    <button
                                        onClick={() => handleDeleteExpense(exp.id, exp.name)}
                                        style={{ marginLeft: '5px', color: 'red' }}
                                    >
                                        Delete
                                    </button>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            )}
        </div>
    );
};

export default RecurringExpensesManager;
