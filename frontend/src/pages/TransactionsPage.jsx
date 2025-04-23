import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';

const API_BASE_URL = 'http://localhost:5001';

// --- Add formatting helpers ---
const formatDate = (dateString) => {
    if (!dateString) return 'N/A';
    return new Date(dateString).toLocaleDateString('en-CA'); // YYYY-MM-DD format
};
const formatCurrency = (value) => {
  if (value === null || value === undefined) return 'N/A';
  return Number(value).toLocaleString('en-US', { style: 'currency', currency: 'USD' });
};
// -----------------------------

const TransactionsPage = () => {
    const [transactions, setTransactions] = useState([]);
    const [pagination, setPagination] = useState({
        page: 1, per_page: 50, total_items: 0, total_pages: 1
    });
    const [filters, setFilters] = useState({
        category: '', start_date: '', end_date: '' // Add account_id later if needed
    });
    const [sorting, setSorting] = useState({ sort_by: 'date', sort_dir: 'desc' });
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [categories, setCategories] = useState([]);

    // Function to fetch transactions based on current state
    const fetchTransactions = useCallback(async () => {
        setLoading(true);
        setError(null);
        console.log("Fetching transactions with filters:", filters);
        try {
            // Construct query parameters
            const params = new URLSearchParams({
                page: pagination.page,
                per_page: pagination.per_page,
                sort_by: sorting.sort_by,
                sort_dir: sorting.sort_dir,
            });
            if (filters.category) params.append('category', filters.category);
            if (filters.start_date) params.append('start_date', filters.start_date);
            if (filters.end_date) params.append('end_date', filters.end_date);
            // if (filters.account_id) params.append('account_id', filters.account_id);
            const queryString = params.toString();
            console.log("API Query String:", queryString);

            const response = await axios.get(`${API_BASE_URL}/api/transactions?${queryString}`);
            setTransactions(response.data.transactions || []);
            setPagination(response.data.pagination || { page: 1, per_page: 50, total_items: 0, total_pages: 1 });
            console.log("Fetched transactions:", response.data);
        } catch (err) {
            console.error("Error fetching transactions:", err.response ? err.response.data : err);
            setError("Failed to fetch transactions.");
        } finally {
            setLoading(false);
        }
    }, [pagination.page, pagination.per_page, filters, sorting]); // Dependencies for useCallback

    useEffect(() => {
        const fetchCategories = async () => {
            try {
                const response = await axios.get(`${API_BASE_URL}/api/budget/categories`);
                setCategories(response.data.categories || []);
                console.log("Fetched categories:", response.data.categories);
            } catch (err) {
                console.error("Error fetching categories:", err);
                // Optional: Set an error state specific to category fetching
            }
        };
        fetchCategories();
    }, []);

    // Fetch data when component mounts or dependencies change
    useEffect(() => {
        fetchTransactions();
    }, [fetchTransactions]); // fetchTransactions is memoized by useCallback

    // --- Event Handlers ---
    const handleSort = (column) => {
        setSorting(prev => ({
            sort_by: column,
            // Toggle direction if same column clicked, else default to desc
            sort_dir: prev.sort_by === column && prev.sort_dir === 'desc' ? 'asc' : 'desc'
        }));
        setPagination(prev => ({ ...prev, page: 1 })); // Reset to page 1 on sort change
    };

    const handleFilterChange = (e) => {
         setFilters(prev => ({ ...prev, [e.target.name]: e.target.value }));
         console.log("Filter chsnged: ", e.target.name, ", ", e.target.value);
         // Optionally trigger fetch here, or require explicit button click
    };

    const handleFilterSubmit = (e) => {
         e.preventDefault();
         setPagination(prev => ({ ...prev, page: 1 })); // Reset to page 1 on filter change
         fetchTransactions(); // Re-fetch with new filters (needed if not fetching on change)
    };

    const handlePageChange = (newPage) => {
        if (newPage >= 1 && newPage <= pagination.total_pages) {
            setPagination(prev => ({ ...prev, page: newPage }));
        }
    };
    // ----------------------

    return (
        <div>
            <h2>Transactions</h2>

            {/* --- Modify Filter Form --- */}
            <form onSubmit={handleFilterSubmit} style={{ marginBottom: '15px' }}>
                <label> Category:
                    {/* Replace text input with select dropdown */}
                    <select
                        name="category"
                        value={filters.category}
                        onChange={handleFilterChange}
                    >
                        <option value="">All Categories</option> {/* Default option */}
                        {categories.map(cat => (
                            <option key={cat} value={cat}>{cat}</option>
                        ))}
                    </select>
                </label>
                {/* Keep date inputs */}
                <label style={{ marginLeft: '10px' }}> Start Date: <input type="date" name="start_date" value={filters.start_date} onChange={handleFilterChange} /> </label>
                <label style={{ marginLeft: '10px' }}> End Date: <input type="date" name="end_date" value={filters.end_date} onChange={handleFilterChange} /> </label>
                <button type="submit" style={{ marginLeft: '10px' }}>Apply Filters</button>
            </form>

            {loading && <p>Loading transactions...</p>}
            {error && <p style={{ color: 'red' }}>Error: {error}</p>}

            {!loading && !error && (
                <>
                    <table border="1" style={{ width: '100%', borderCollapse: 'collapse' }}>
                        <thead>
                            <tr>
                                {/* Add onClick handlers for sorting */}
                                <th onClick={() => handleSort('date')} style={{cursor: 'pointer'}}>Date {sorting.sort_by === 'date' ? (sorting.sort_dir === 'desc' ? '▼' : '▲') : ''}</th>
                                <th onClick={() => handleSort('name')} style={{cursor: 'pointer'}}>Name {sorting.sort_by === 'name' ? (sorting.sort_dir === 'desc' ? '▼' : '▲') : ''}</th>
                                <th onClick={() => handleSort('amount')} style={{cursor: 'pointer'}}>Amount {sorting.sort_by === 'amount' ? (sorting.sort_dir === 'desc' ? '▼' : '▲') : ''}</th>
                                <th onClick={() => handleSort('budget_category')} style={{cursor: 'pointer'}}>Category {sorting.sort_by === 'budget_category' ? (sorting.sort_dir === 'desc' ? '▼' : '▲') : ''}</th>
                                {/* Add other columns if needed */}
                            </tr>
                        </thead>
                        <tbody>
                            {transactions.map(txn => (
                                <tr key={txn.id || txn.plaid_transaction_id}>
                                    <td>{formatDate(txn.date)}</td>
                                    <td>{txn.name}</td>
                                    <td style={{ textAlign: 'right', color: txn.amount < 0 ? 'red' : 'green' }}>{formatCurrency(txn.amount)}</td>
                                    <td>{txn.budget_category}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>

                    {/* --- Pagination Controls --- */}
                    <div style={{ marginTop: '15px' }}>
                         <button onClick={() => handlePageChange(pagination.page - 1)} disabled={pagination.page <= 1}> Previous </button>
                         <span style={{ margin: '0 10px' }}>
                             Page {pagination.page} of {pagination.total_pages} ({pagination.total_items} items)
                         </span>
                         <button onClick={() => handlePageChange(pagination.page + 1)} disabled={pagination.page >= pagination.total_pages}> Next </button>
                    </div>
                    {/* ------------------------- */}
                </>
            )}
        </div>
    );
};

export default TransactionsPage;
