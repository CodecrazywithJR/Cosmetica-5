'use client';

/**
 * Debug Auth Page - DEV ONLY
 * 
 * Internal diagnostic page to verify authentication state.
 * Shows: logged in status, tokens present, user data, and test API call.
 */

import { useAuth } from '@/lib/auth-context';
import { API_ROUTES } from '@/lib/api-config';
import apiClient from '@/lib/api-client';
import { useState } from 'react';

export default function DebugAuthPage() {
  const { user, isLoading, isAuthenticated } = useAuth();
  const [testResult, setTestResult] = useState<string>('');

  if (process.env.NODE_ENV !== 'development') {
    return <div className="p-8">This page is only available in development mode.</div>;
  }

  const testApiCall = async () => {
    setTestResult('Testing...');
    try {
      const response = await apiClient.get(API_ROUTES.AUTH.ME);
      setTestResult(`✅ SUCCESS: ${JSON.stringify(response.data, null, 2)}`);
    } catch (error: any) {
      setTestResult(`❌ ERROR: ${error.message}\n${JSON.stringify(error.response?.data || {}, null, 2)}`);
    }
  };

  const testAppointments = async () => {
    setTestResult('Testing appointments...');
    try {
      const response = await apiClient.get(API_ROUTES.CLINICAL.APPOINTMENTS);
      setTestResult(`✅ SUCCESS: Received ${response.data.length || 0} appointments`);
    } catch (error: any) {
      setTestResult(`❌ ERROR: ${error.message}\n${JSON.stringify(error.response?.data || {}, null, 2)}`);
    }
  };

  const tokensPresent = typeof window !== 'undefined' ? {
    access_token: !!localStorage.getItem('access_token'),
    refresh_token: !!localStorage.getItem('refresh_token'),
    user: !!localStorage.getItem('user'),
  } : {};

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <h1 className="text-3xl font-bold mb-6">🔐 Auth Debug Page</h1>
      
      <div className="space-y-6">
        {/* Authentication State */}
        <div className="bg-gray-100 p-4 rounded">
          <h2 className="text-xl font-semibold mb-2">Authentication State</h2>
          <div className="space-y-1 font-mono text-sm">
            <p>Logged in: <strong className={isAuthenticated ? 'text-green-600' : 'text-red-600'}>{isAuthenticated ? 'YES' : 'NO'}</strong></p>
            <p>Loading: {isLoading ? 'YES' : 'NO'}</p>
          </div>
        </div>

        {/* Tokens Present */}
        <div className="bg-gray-100 p-4 rounded">
          <h2 className="text-xl font-semibold mb-2">Tokens in localStorage</h2>
          <div className="space-y-1 font-mono text-sm">
            <p>access_token: <strong className={tokensPresent.access_token ? 'text-green-600' : 'text-red-600'}>{tokensPresent.access_token ? 'PRESENT' : 'MISSING'}</strong></p>
            <p>refresh_token: <strong className={tokensPresent.refresh_token ? 'text-green-600' : 'text-red-600'}>{tokensPresent.refresh_token ? 'PRESENT' : 'MISSING'}</strong></p>
            <p>user data: <strong className={tokensPresent.user ? 'text-green-600' : 'text-red-600'}>{tokensPresent.user ? 'PRESENT' : 'MISSING'}</strong></p>
          </div>
        </div>

        {/* User Data */}
        {user && (
          <div className="bg-gray-100 p-4 rounded">
            <h2 className="text-xl font-semibold mb-2">User Data</h2>
            <pre className="text-sm overflow-auto">{JSON.stringify(user, null, 2)}</pre>
          </div>
        )}

        {/* API Base URL */}
        <div className="bg-gray-100 p-4 rounded">
          <h2 className="text-xl font-semibold mb-2">API Configuration</h2>
          <div className="space-y-1 font-mono text-sm">
            <p>Base URL: <strong>{apiClient.defaults.baseURL}</strong></p>
            <p>Timeout: {apiClient.defaults.timeout}ms</p>
          </div>
        </div>

        {/* Test API Calls */}
        <div className="bg-gray-100 p-4 rounded">
          <h2 className="text-xl font-semibold mb-2">Test API Calls</h2>
          <div className="space-x-2 mb-4">
            <button 
              onClick={testApiCall}
              className="bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded"
            >
              Test /auth/me/
            </button>
            <button 
              onClick={testAppointments}
              className="bg-green-500 hover:bg-green-600 text-white px-4 py-2 rounded"
            >
              Test /appointments/
            </button>
          </div>
          {testResult && (
            <pre className="bg-white p-3 rounded text-sm overflow-auto whitespace-pre-wrap">{testResult}</pre>
          )}
        </div>

        {/* Console Instructions */}
        <div className="bg-yellow-50 border-l-4 border-yellow-400 p-4">
          <h2 className="text-lg font-semibold mb-2">📋 Console Logs to Check</h2>
          <p className="text-sm mb-2">Open Safari Web Inspector → Console and look for:</p>
          <ul className="list-disc list-inside text-sm space-y-1 font-mono">
            <li>[AUTH] TOKENS_LOADED - On page load</li>
            <li>[AUTH] LOGIN_SUBMIT - When clicking login</li>
            <li>[AUTH] TOKENS_SAVED - After successful login</li>
            <li>[API] method url &#123;AUTH_HEADER_PRESENT: true/false&#125; - Before each request</li>
            <li>[API SUCCESS] status method url - On successful response</li>
            <li>[API ERROR] status method url - On error response</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
