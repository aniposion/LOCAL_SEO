'use client';

import { useState, useEffect } from 'react';
import type { CopyLength } from '@/lib/copy';

// Hook to determine copy length based on screen size
export function useCopyLength(): CopyLength {
  const [length, setLength] = useState<CopyLength>('medium');

  useEffect(() => {
    const updateLength = () => {
      const width = window.innerWidth;
      if (width < 640) {
        setLength('short');
      } else if (width < 1024) {
        setLength('medium');
      } else {
        setLength('long');
      }
    };

    updateLength();
    window.addEventListener('resize', updateLength);
    return () => window.removeEventListener('resize', updateLength);
  }, []);

  return length;
}

// Helper to get copy based on length
export function getCopyForLength<T extends Record<CopyLength, string>>(
  copies: T,
  length: CopyLength
): string {
  return copies[length];
}
