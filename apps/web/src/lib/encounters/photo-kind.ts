/**
 * Photo Kind Utilities for Encounters
 * Deterministic UI mapping for clinical photo kinds
 */

// UI domain for photo kind (closed set)
export type PhotoKindUI = 'before' | 'after' | 'progress' | 'other';

const PHOTO_KIND_UI: PhotoKindUI[] = ['before', 'after', 'progress', 'other'];

// Deterministic mapping: only allow UI domain, everything else (including 'clinical') → 'other'
export function mapPhotoKind(kind: unknown): PhotoKindUI {
  return PHOTO_KIND_UI.includes(kind as PhotoKindUI) ? (kind as PhotoKindUI) : 'other';
}
