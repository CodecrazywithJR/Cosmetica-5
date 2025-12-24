/**
 * DataState Component
 * 
 * Unified component for handling data loading states across the application.
 * Provides consistent UX for loading, error, empty, and success states.
 * 
 * Usage:
 * <DataState
 *   isLoading={isLoading}
 *   error={error}
 *   isEmpty={data?.results.length === 0}
 *   emptyMessage="No data found"
 *   emptyAction={{ label: "Create New", onClick: handleCreate }}
 * >
 *   {your content here}
 * </DataState>
 */

'use client';

import { ReactNode } from 'react';

interface EmptyAction {
  label: string;
  onClick?: () => void;
}

interface DataStateProps {
  isLoading: boolean;
  error?: Error | null;
  isEmpty?: boolean;
  emptyMessage?: string;
  emptyDescription?: string;
  emptyAction?: EmptyAction;
  loadingMessage?: string;
  errorTitle?: string;
  errorDescription?: string;
  errorMessage?: string; // Legacy: deprecated, use errorTitle + errorDescription
  children: ReactNode;
}

export function DataState({
  isLoading,
  error,
  isEmpty = false,
  emptyMessage = 'No data available',
  emptyDescription,
  emptyAction,
  loadingMessage = 'Loading...',
  errorTitle,
  errorDescription,
  errorMessage, // Legacy
  children,
}: DataStateProps) {
  // Loading state
  if (isLoading) {
    return (
      <div className="card">
        <div className="card-body" style={{ textAlign: 'center', padding: '48px 20px' }}>
          <div style={{ fontSize: '16px', color: 'var(--gray-600)' }}>{loadingMessage}</div>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="card">
        <div className="card-body" style={{ textAlign: 'center', padding: '48px 20px' }}>
          <div
            style={{
              fontSize: '48px',
              marginBottom: '16px',
              opacity: 0.3,
            }}
          >
            ⚠️
          </div>
          <h3 style={{ fontSize: '18px', fontWeight: 600, marginBottom: '8px', color: 'var(--error)' }}>
            {errorTitle || errorMessage || 'Error'}
          </h3>
          {errorDescription && (
            <p style={{ color: 'var(--gray-600)', fontSize: '14px', maxWidth: '400px', margin: '0 auto' }}>
              {errorDescription}
            </p>
          )}
        </div>
      </div>
    );
  }

  // Empty state
  if (isEmpty) {
    return (
      <div className="card">
        <div className="card-body" style={{ textAlign: 'center', padding: '48px 20px' }}>
          <div
            style={{
              fontSize: '48px',
              marginBottom: '16px',
              opacity: 0.3,
            }}
          >
            📋
          </div>
          <h3 style={{ fontSize: '18px', fontWeight: 600, marginBottom: '8px' }}>
            {emptyMessage}
          </h3>
          {emptyDescription && (
            <p style={{ color: 'var(--gray-600)', marginBottom: '24px', fontSize: '14px' }}>
              {emptyDescription}
            </p>
          )}
          {emptyAction && (
            <button
              onClick={emptyAction.onClick}
              className="btn-primary"
              disabled={!emptyAction.onClick}
            >
              {emptyAction.label}
            </button>
          )}
        </div>
      </div>
    );
  }

  // Success state - render children
  return <>{children}</>;
}
