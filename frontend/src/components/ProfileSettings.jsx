import React, { useState, useEffect } from 'react';
import axios from 'axios';

const API_BASE_URL = 'http://localhost:5001';

const ProfileSettings = () => {
    const [salary, setSalary] = useState('');
    const [initialSalary, setInitialSalary] = useState(''); // To check if changed
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState(null);
    const [successMessage, setSuccessMessage] = useState('');

    // Fetch current profile on mount
    useEffect(() => {
        const fetchProfile = async () => {
            setIsLoading(true);
            setError(null);
            try {
                const response = await axios.get(`${API_BASE_URL}/api/profile`);
                const currentSalary = response.data?.monthly_salary_estimate ?? '';
                setSalary(String(currentSalary)); // Store as string for input field
                setInitialSalary(String(currentSalary));
            } catch (err) {
                console.error("Error fetching profile:", err);
                setError("Could not load profile data.");
            } finally {
                setIsLoading(false);
            }
        };
        fetchProfile();
    }, []);

    const handleSalaryChange = (e) => {
        setSalary(e.target.value);
        setSuccessMessage(''); // Clear message on change
    };

    const handleSave = async (e) => {
        e.preventDefault();
        setIsLoading(true);
        setError(null);
        setSuccessMessage('');
        try {
            // Only send if value actually changed? Optional.
            const response = await axios.put(`${API_BASE_URL}/api/profile`, {
                // Send null if empty, otherwise send the value (backend handles conversion)
                monthly_salary_estimate: salary.trim() === '' ? null : salary
            });
            const updatedSalary = response.data?.monthly_salary_estimate ?? '';
            setSalary(String(updatedSalary)); // Update state with saved value
            setInitialSalary(String(updatedSalary));
            setSuccessMessage('Salary updated successfully!');
        } catch (err) {
            console.error("Error updating profile:", err.response?.data || err);
            setError(err.response?.data?.error || "Failed to update salary.");
        } finally {
            setIsLoading(false);
        }
    };

    if (isLoading && !salary) { // Show loading only initially
         return <p>Loading profile...</p>;
    }

    return (
        <form onSubmit={handleSave}>
            <label htmlFor="salaryInput">Estimated Monthly Salary (Net or Gross?): </label>
            <input
                type="number"
                id="salaryInput"
                name="salary"
                value={salary}
                onChange={handleSalaryChange}
                placeholder="e.g., 5000.00"
                step="0.01"
                disabled={isLoading}
            />
            <button type="submit" disabled={isLoading || salary === initialSalary} style={{marginLeft: '10px'}}>
                {isLoading ? 'Saving...' : 'Save Salary'}
            </button>
            {error && <p style={{ color: 'red', marginTop: '5px' }}>Error: {error}</p>}
            {successMessage && <p style={{ color: 'green', marginTop: '5px' }}>{successMessage}</p>}
        </form>
    );
};

export default ProfileSettings;
