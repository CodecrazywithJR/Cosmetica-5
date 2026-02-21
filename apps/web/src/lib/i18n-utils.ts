/**
 * i18n utilities - Helper functions for internationalization
 * Works with existing next-intl setup
 */

export type SexCode = 'male' | 'female' | 'other' | 'unknown';

/**
 * Map sex code to translation key
 * Usage: t(mapSexCode('male')) where t is from useTranslations('common')
 * Returns relative key without namespace (e.g., 'sex.male' not 'common.sex.male')
 * 
 * Backend uses: 'male', 'female', 'other', 'unknown' (lowercase, full words)
 */
export function mapSexCode(code: SexCode | string): string {
  const mapping: Record<string, string> = {
    male: 'sex.male',
    female: 'sex.female',
    other: 'sex.other',
    unknown: 'sex.unknown',
  };
  return mapping[code] || 'sex.unknown';
}

/**
 * Format date for display
 */
export function formatDate(dateString: string, locale: string = 'en'): string {
  if (!dateString) return '';
  try {
    const date = new Date(dateString);
    return date.toLocaleDateString(locale, {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  } catch (e) {
    return dateString;
  }
}

/**
 * Format datetime for display
 */
export function formatDateTime(dateString: string, locale: string = 'en'): string {
  if (!dateString) return '';
  try {
    const date = new Date(dateString);
    return date.toLocaleString(locale, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch (e) {
    return dateString;
  }
}
