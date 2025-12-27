/**
 * User Management Page
 * Admin-only interface for managing users
 */

'use client';

import React, { useState, useEffect } from 'react';
import { useTranslations, useLocale } from 'next-intl';
import { useRouter } from 'next/navigation';
import { useAuth, ROLES } from '@/lib/auth-context';
import { routes, type Locale } from '@/lib/routing';
import AppLayout from '@/components/layout/app-layout';
import Unauthorized from '@/components/unauthorized';
import apiClient from '@/lib/api-client';
import { API_ROUTES } from '@/lib/api-config';

interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  full_name: string;
  is_active: boolean;
  must_change_password: boolean;
  roles: string[];
  is_practitioner: boolean;
  last_login: string | null;
  created_at: string;
}

export default function UsersListPage() {
  const { hasRole, isLoading: authLoading } = useAuth();
  const t = useTranslations('users');
  const tCommon = useTranslations('common');
  const router = useRouter();
  const locale = useLocale() as Locale;

  const [users, setUsers] = useState<User[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');

  // Check authorization
  const isAdmin = hasRole(ROLES.ADMIN);

  useEffect(() => {
    if (!authLoading && isAdmin) {
      loadUsers();
    }
  }, [authLoading, isAdmin]);

  const loadUsers = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const response = await apiClient.get('/api/v1/users/');
      
      // Normalize response: handle both array and paginated responses
      let usersData: User[] = [];
      if (Array.isArray(response.data)) {
        usersData = response.data;
      } else if (response.data?.results) {
        // DRF paginated response
        usersData = response.data.results;
      } else if (response.data?.data) {
        // Wrapped response
        usersData = response.data.data;
      } else if (response.data?.users) {
        // Another common wrapper
        usersData = response.data.users;
      }
      
      setUsers(usersData);
    } catch (err: any) {
      console.error('Failed to load users:', err);
      setError(err.response?.data?.detail || t('messages.loadError'));
    } finally {
      setIsLoading(false);
    }
  };

  // Wait for auth to load
  if (authLoading) {
    return (
      <AppLayout>
        <div className="loading-container">
          <p>{tCommon('loading')}</p>
        </div>
      </AppLayout>
    );
  }

  // Show 403 if not admin
  if (!isAdmin) {
    return <Unauthorized />;
  }

  // Normalize users to array (defensive programming)
  const usersList = Array.isArray(users) ? users : [];

  // Filter users by search term with null-safe access
  const searchTermLower = searchTerm.trim().toLowerCase();
  const filteredUsers = usersList.filter((user) => {
    if (!searchTermLower) return true;
    
    const fullName = (user?.full_name ?? user?.first_name ?? '').toLowerCase();
    const email = (user?.email ?? '').toLowerCase();
    
    return fullName.includes(searchTermLower) || email.includes(searchTermLower);
  });

  return (
    <AppLayout>
      <div className="users-page">
        {/* Header */}
        <div className="page-header">
          <div>
            <h1>{t('title')}</h1>
            <p className="page-description">{t('list')}</p>
          </div>
          <button
            onClick={() => router.push(routes.users.create(locale))}
            className="btn-primary"
          >
            <PlusIcon />
            {t('actions.create')}
          </button>
        </div>

        {/* Search */}
        <div className="search-bar">
          <SearchIcon />
          <input
            type="text"
            placeholder={t('search_placeholder')}
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="search-input"
          />
        </div>

        {/* Loading State */}
        {isLoading && (
          <div className="loading-container">
            <p>{tCommon('loading')}</p>
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="error-container">
            <p className="error-message">{error}</p>
            <button onClick={loadUsers} className="btn-secondary">
              {tCommon('retry')}
            </button>
          </div>
        )}

        {/* Users Table */}
        {!isLoading && !error && (
          <div className="table-container">
            {filteredUsers.length === 0 ? (
              <div className="empty-state">
                <p>{t('no_users')}</p>
              </div>
            ) : (
              <table className="users-table">
                <thead>
                  <tr>
                    <th>{t('table.name')}</th>
                    <th>{t('table.email')}</th>
                    <th>{t('table.roles')}</th>
                    <th>{t('table.status')}</th>
                    <th>{t('table.practitioner')}</th>
                    <th>{t('table.actions')}</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredUsers.map((user) => (
                    <tr key={user.id}>
                      <td>
                        <div className="user-name">
                          <span className="name">{user.full_name}</span>
                          {user.must_change_password && (
                            <span className="badge badge-warning">
                              {t('fields.mustChangePassword')}
                            </span>
                          )}
                        </div>
                      </td>
                      <td>{user.email}</td>
                      <td>
                        <div className="roles">
                          {user.roles.map((role) => (
                            <span key={role} className="badge">
                              {role}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td>
                        <span className={`status-badge ${user.is_active ? 'active' : 'inactive'}`}>
                          {user.is_active ? t('status.active') : t('status.inactive')}
                        </span>
                      </td>
                      <td>
                        {user.is_practitioner ? (
                          <span className="badge badge-info">{t('fields.isPractitioner')}</span>
                        ) : (
                          '-'
                        )}
                      </td>
                      <td>
                        <button
                          onClick={() => router.push(routes.users.edit(locale, user.id))}
                          className="btn-icon"
                          title={tCommon('edit')}
                        >
                          <EditIcon />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>

      <style jsx>{`
        .users-page {
          padding: 24px;
        }

        .page-header {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          margin-bottom: 32px;
        }

        h1 {
          font-size: 28px;
          font-weight: 700;
          color: var(--color-text-primary, #111827);
          margin: 0 0 4px 0;
        }

        .page-description {
          font-size: 14px;
          color: var(--color-text-secondary, #6b7280);
          margin: 0;
        }

        .btn-primary {
          display: flex;
          align-items: center;
          gap: 8px;
          padding: 10px 20px;
          background-color: var(--color-primary, #3b82f6);
          color: white;
          border: none;
          border-radius: 6px;
          font-size: 14px;
          font-weight: 500;
          cursor: pointer;
          transition: background-color 0.2s;
        }

        .btn-primary:hover {
          background-color: var(--color-primary-hover, #2563eb);
        }

        .search-bar {
          position: relative;
          margin-bottom: 24px;
        }

        .search-input {
          width: 100%;
          padding: 10px 10px 10px 40px;
          border: 1px solid var(--color-border, #d1d5db);
          border-radius: 6px;
          font-size: 14px;
        }

        .search-input:focus {
          outline: none;
          border-color: var(--color-primary, #3b82f6);
        }

        .loading-container,
        .error-container,
        .empty-state {
          text-align: center;
          padding: 48px 24px;
          color: var(--color-text-secondary, #6b7280);
        }

        .error-message {
          color: var(--color-error, #dc2626);
          margin-bottom: 16px;
        }

        .table-container {
          background: white;
          border-radius: 8px;
          border: 1px solid var(--color-border, #e5e7eb);
          overflow: hidden;
        }

        .users-table {
          width: 100%;
          border-collapse: collapse;
        }

        .users-table th {
          padding: 12px 16px;
          text-align: left;
          font-size: 12px;
          font-weight: 600;
          text-transform: uppercase;
          color: var(--color-text-secondary, #6b7280);
          background: var(--color-background, #f9fafb);
          border-bottom: 1px solid var(--color-border, #e5e7eb);
        }

        .users-table td {
          padding: 16px;
          border-bottom: 1px solid var(--color-border, #e5e7eb);
        }

        .users-table tbody tr:hover {
          background: var(--color-background, #f9fafb);
        }

        .user-name {
          display: flex;
          align-items: center;
          gap: 8px;
        }

        .name {
          font-weight: 500;
          color: var(--color-text-primary, #111827);
        }

        .roles {
          display: flex;
          gap: 6px;
          flex-wrap: wrap;
        }

        .badge {
          display: inline-block;
          padding: 2px 8px;
          font-size: 12px;
          font-weight: 500;
          border-radius: 4px;
          background: var(--color-primary-light, #dbeafe);
          color: var(--color-primary, #3b82f6);
        }

        .badge-warning {
          background: #fef3c7;
          color: #d97706;
        }

        .badge-info {
          background: #dbeafe;
          color: #3b82f6;
        }

        .status-badge {
          display: inline-block;
          padding: 4px 12px;
          font-size: 12px;
          font-weight: 500;
          border-radius: 12px;
        }

        .status-badge.active {
          background: #d1fae5;
          color: #065f46;
        }

        .status-badge.inactive {
          background: #fee2e2;
          color: #991b1b;
        }

        .btn-icon {
          padding: 6px;
          background: transparent;
          border: none;
          cursor: pointer;
          color: var(--color-text-secondary, #6b7280);
          transition: color 0.2s;
        }

        .btn-icon:hover {
          color: var(--color-primary, #3b82f6);
        }

        .btn-secondary {
          padding: 8px 16px;
          background: var(--color-background, #f3f4f6);
          color: var(--color-text-primary, #111827);
          border: 1px solid var(--color-border, #d1d5db);
          border-radius: 6px;
          font-size: 14px;
          cursor: pointer;
        }

        .btn-secondary:hover {
          background: var(--color-background-hover, #e5e7eb);
        }
      `}</style>
    </AppLayout>
  );
}

// Icons
function PlusIcon() {
  return (
    <svg width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
    </svg>
  );
}

function SearchIcon() {
  return (
    <svg
      width="20"
      height="20"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: '#9ca3af' }}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
      />
    </svg>
  );
}

function EditIcon() {
  return (
    <svg width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
      />
    </svg>
  );
}
