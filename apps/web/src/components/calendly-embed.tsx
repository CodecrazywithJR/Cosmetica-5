/**
 * CalendlyEmbed Component
 * 
 * FASE 4.0 - Calendly Embed Integration
 * Reusable wrapper for Calendly InlineWidget (react-calendly).
 * 
 * This component ONLY handles rendering the Calendly widget.
 * It does NOT contain logic for:
 * - Checking if URL is configured
 * - Showing "not configured" state
 * - Fallback to env vars
 * 
 * Use with useCalendlyConfig() hook:
 * ```tsx
 * const { calendlyUrl, isConfigured } = useCalendlyConfig();
 * 
 * if (!isConfigured) {
 *   return <CalendlyNotConfigured />;
 * }
 * 
 * return <CalendlyEmbed url={calendlyUrl!} />;
 * ```
 * 
 * @see docs/PROJECT_DECISIONS.md §12.17 (CalendlyEmbed Component)
 * @see docs/PROJECT_DECISIONS.md §12.18 (FASE 4.2 Debt - Settings Page)
 */

'use client';

import { InlineWidget } from 'react-calendly';

interface CalendlyEmbedProps {
  /**
   * Calendly scheduling URL.
   * Must be a valid Calendly URL (e.g., https://calendly.com/username/event).
   * 
   * IMPORTANT: This component does NOT validate the URL.
   * Caller is responsible for ensuring URL is valid and non-empty.
   * 
   * If empty/invalid URL is passed, component returns null (fail-safe).
   */
  url: string;
  
  /**
   * Optional: Pre-fill patient name for scheduling.
   * Will be passed to Calendly widget.
   */
  prefill?: {
    name?: string;
    email?: string;
    customAnswers?: Record<string, string>;
  };
}

/**
 * Calendly Embed Component
 * 
 * Renders Calendly InlineWidget with consistent styling.
 * 
 * Safety:
 * - If url is empty/null, returns null (fail-safe)
 * - If react-calendly fails to load, error boundary should catch it
 * 
 * Styling:
 * - Full width container
 * - Minimum height to prevent layout shift
 * - Consistent with app's card-based layout
 */
export function CalendlyEmbed({ url, prefill }: CalendlyEmbedProps) {
  // Fail-safe: If URL is empty/invalid, return null
  // This should NOT happen if caller uses useCalendlyConfig() correctly,
  // but prevents app crash if misused.
  if (!url || url.trim().length === 0) {
    console.warn('CalendlyEmbed: Empty URL provided. Component will not render.');
    return null;
  }
  
  return (
    <div className="card">
      <div className="card-body" style={{ padding: 0 }}>
        <div style={{ minHeight: '700px' }}>
          <InlineWidget
            url={url}
            prefill={prefill}
            styles={{
              height: '700px',
              width: '100%',
            }}
          />
        </div>
      </div>
    </div>
  );
}
