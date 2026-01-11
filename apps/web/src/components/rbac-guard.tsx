/**
 * RBAC Guard
 * Component-level permission guard
 */

'use client';

import { useHasAnyRole } from '@/lib/auth-context';
import { ReactNode } from 'react';

interface RBACGuardProps {
  roles: string[];
  children: ReactNode;
  fallback?: ReactNode;
}

export function RBACGuard({ roles, children, fallback = null }: RBACGuardProps) {
  const hasRole = useHasAnyRole(roles);

  if (!hasRole) {
    return <>{fallback}</>;
  }

  return <>{children}</>;
}
