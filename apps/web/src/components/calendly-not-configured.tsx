/**
 * CalendlyNotConfigured Component
 * 
 * FASE 4.0 - Calendly URL per practitioner
 * Shows a message when practitioner_calendly_url is not configured or invalid.
 * 
 * This component enforces "Opción 2 siempre" decision:
 * Without valid practitioner_calendly_url, scheduling is NOT allowed.
 * 
 * URL Validation:
 * - Rejects internal Calendly panel URLs (e.g., /app/scheduling/meeting_types/user/me)
 * - Only accepts public booking URLs (e.g., https://calendly.com/username/event-type)
 * 
 * Usage:
 * ```tsx
 * const { isConfigured } = useCalendlyConfig();
 * 
 * if (!isConfigured) {
 *   return <CalendlyNotConfigured />;
 * }
 * ```
 * 
 * @see docs/PROJECT_DECISIONS.md §12.16 (Frontend Implementation - Opción 2)
 * @see docs/PROJECT_DECISIONS.md §12.26 (Calendly URL Validation)
 */

'use client';

import { useTranslations } from 'next-intl';
import { useAuth } from '@/lib/auth-context';

interface CalendlyNotConfiguredProps {
  /**
   * Optional: Custom action handler for "Go to settings" button.
   * If not provided, button will be disabled (no settings page yet).
   */
  onGoToSettings?: () => void;
}

export function CalendlyNotConfigured({ onGoToSettings }: CalendlyNotConfiguredProps) {
  const t = useTranslations('calendly.notConfigured');
  const { user } = useAuth();
  
  // Detect if user has an invalid URL (internal panel URL)
  const rawUrl = user?.practitioner_calendly_url?.trim();
  const isInternalPanelUrl = rawUrl && rawUrl.includes('/app/scheduling/');
  
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
          📅
        </div>
        <h3 style={{ fontSize: '18px', fontWeight: 600, marginBottom: '8px' }}>
          {t('title')}
        </h3>
        
        {isInternalPanelUrl ? (
          // Invalid URL case: User has an internal Calendly dashboard URL
          <div>
            <p style={{ color: 'var(--red-600)', marginBottom: '16px', fontSize: '14px', maxWidth: '500px', margin: '0 auto 16px' }}>
              ⚠️ The configured Calendly URL is an internal dashboard link and cannot be embedded.
            </p>
            <p style={{ color: 'var(--gray-600)', marginBottom: '16px', fontSize: '14px', maxWidth: '500px', margin: '0 auto 16px' }}>
              Please use your <strong>public booking URL</strong> instead.
            </p>
            <div style={{ 
              background: 'var(--gray-50)', 
              border: '1px solid var(--gray-200)',
              borderRadius: '8px',
              padding: '16px',
              marginBottom: '24px',
              maxWidth: '500px',
              margin: '0 auto 24px',
              textAlign: 'left'
            }}>
              <p style={{ fontSize: '13px', marginBottom: '8px', fontWeight: 600 }}>
                How to find your public booking URL:
              </p>
              <ol style={{ fontSize: '13px', paddingLeft: '20px', margin: 0, color: 'var(--gray-700)' }}>
                <li>Go to your Calendly dashboard</li>
                <li>Click on an event type (e.g., "30 Minute Meeting")</li>
                <li>Click "Copy Link" to get your public booking URL</li>
                <li>It should look like: <code style={{ background: 'white', padding: '2px 4px', borderRadius: '3px' }}>https://calendly.com/yourname/30min</code></li>
              </ol>
            </div>
            <p style={{ color: 'var(--gray-500)', fontSize: '12px', fontStyle: 'italic' }}>
              Contact administrator to update your Calendly URL in the system.
            </p>
          </div>
        ) : (
          // No URL case: User hasn't configured any URL
          <div>
            <p style={{ color: 'var(--gray-600)', marginBottom: '24px', fontSize: '14px', maxWidth: '400px', margin: '0 auto 24px' }}>
              {t('description')}
            </p>
            {onGoToSettings && (
              <button
                onClick={onGoToSettings}
                className="btn-primary"
              >
                {t('action')}
              </button>
            )}
            {!onGoToSettings && (
              <p style={{ color: 'var(--gray-500)', fontSize: '12px', fontStyle: 'italic' }}>
                {/* TODO FASE 4.2: Add profile/settings page */}
                Contact administrator to configure Calendly URL
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
