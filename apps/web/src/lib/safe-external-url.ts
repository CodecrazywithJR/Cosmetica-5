/**
 * Safe external URL handler
 */

export function safeExternalUrl(url: string): string {
  if (!url) return '#';
  
  // Ensure URL has protocol
  if (!url.startsWith('http://') && !url.startsWith('https://')) {
    return `https://${url}`;
  }
  
  return url;
}
