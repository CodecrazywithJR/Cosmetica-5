/**
 * Proposals hooks
 */

import { useState } from 'react';

export function useGenerateProposal() {
  const [loading, setLoading] = useState(false);
  
  const generateProposal = async (encounterId: number) => {
    setLoading(true);
    try {
      console.log(`Generate proposal for encounter ${encounterId}`);
    } finally {
      setLoading(false);
    }
  };

  return { generateProposal, loading };
}
