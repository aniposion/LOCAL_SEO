'use client';

import React from 'react';

interface HeroMapOverlayProps {
  variant?: 'grid' | 'dots' | 'city' | 'hex';
  opacity?: number;
}

/**
 * Abstract Map Line SVG Overlays
 * Can be inserted as a background layer in any hero
 *
 * Usage:
 * <HeroMapOverlay variant="city" opacity={0.04} />
 */
export default function HeroMapOverlay({
  variant = 'grid',
  opacity = 0.04
}: HeroMapOverlayProps) {
  const patterns: Record<string, React.ReactNode> = {
    // Simple grid pattern
    grid: (
      <defs>
        <pattern id="map-grid" width="60" height="60" patternUnits="userSpaceOnUse">
          <path
            d="M 60 0 L 0 0 0 60"
            fill="none"
            stroke="rgba(255,255,255,0.8)"
            strokeWidth="0.5"
          />
        </pattern>
      </defs>
    ),

    // Dot matrix pattern
    dots: (
      <defs>
        <pattern id="map-dots" width="24" height="24" patternUnits="userSpaceOnUse">
          <circle cx="12" cy="12" r="1" fill="rgba(6,182,212,0.6)"/>
        </pattern>
      </defs>
    ),

    // Abstract city blocks
    city: (
      <defs>
        <pattern id="map-city" width="100" height="100" patternUnits="userSpaceOnUse">
          {/* Major roads */}
          <path d="M 0,50 L 100,50" stroke="rgba(255,255,255,0.6)" strokeWidth="1.5" fill="none"/>
          <path d="M 50,0 L 50,100" stroke="rgba(255,255,255,0.6)" strokeWidth="1.5" fill="none"/>
          {/* Minor roads */}
          <path d="M 0,25 L 100,25" stroke="rgba(255,255,255,0.3)" strokeWidth="0.5" fill="none"/>
          <path d="M 0,75 L 100,75" stroke="rgba(255,255,255,0.3)" strokeWidth="0.5" fill="none"/>
          <path d="M 25,0 L 25,100" stroke="rgba(255,255,255,0.3)" strokeWidth="0.5" fill="none"/>
          <path d="M 75,0 L 75,100" stroke="rgba(255,255,255,0.3)" strokeWidth="0.5" fill="none"/>
          {/* Buildings/blocks */}
          <rect x="5" y="5" width="15" height="18" rx="1" fill="rgba(255,255,255,0.04)"/>
          <rect x="55" y="8" width="18" height="12" rx="1" fill="rgba(255,255,255,0.03)"/>
          <rect x="28" y="55" width="12" height="20" rx="1" fill="rgba(255,255,255,0.03)"/>
          <rect x="78" y="60" width="16" height="15" rx="1" fill="rgba(255,255,255,0.04)"/>
          <rect x="8" y="78" width="14" height="16" rx="1" fill="rgba(255,255,255,0.03)"/>
        </pattern>
      </defs>
    ),

    // Hexagonal data pattern
    hex: (
      <defs>
        <pattern
          id="map-hex"
          width="56"
          height="100"
          patternUnits="userSpaceOnUse"
          patternTransform="scale(0.6)"
        >
          <path
            d="M28,0 L56,17 L56,51 L28,68 L0,51 L0,17 Z M28,68 L56,85 L56,100 M28,68 L0,85 L0,100"
            fill="none"
            stroke="rgba(6,182,212,0.4)"
            strokeWidth="0.5"
          />
        </pattern>
      </defs>
    ),
  };

  const patternIds: Record<string, string> = {
    grid: 'map-grid',
    dots: 'map-dots',
    city: 'map-city',
    hex: 'map-hex',
  };

  return (
    <svg
      className="absolute inset-0 w-full h-full pointer-events-none"
      style={{ opacity }}
      xmlns="http://www.w3.org/2000/svg"
      preserveAspectRatio="xMidYMid slice"
    >
      {patterns[variant]}
      <rect width="100%" height="100%" fill={`url(#${patternIds[variant]})`} />
    </svg>
  );
}

/**
 * Standalone SVG files for export:
 *
 * === grid.svg ===
 * <svg xmlns="http://www.w3.org/2000/svg" width="60" height="60">
 *   <path d="M 60 0 L 0 0 0 60" fill="none" stroke="rgba(255,255,255,0.08)" stroke-width="0.5"/>
 * </svg>
 *
 * === dots.svg ===
 * <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24">
 *   <circle cx="12" cy="12" r="1" fill="rgba(6,182,212,0.1)"/>
 * </svg>
 *
 * === city.svg ===
 * <svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
 *   <path d="M 0,50 L 100,50" stroke="rgba(255,255,255,0.05)" stroke-width="1.5" fill="none"/>
 *   <path d="M 50,0 L 50,100" stroke="rgba(255,255,255,0.05)" stroke-width="1.5" fill="none"/>
 *   <rect x="5" y="5" width="15" height="18" rx="1" fill="rgba(255,255,255,0.02)"/>
 *   <rect x="55" y="55" width="18" height="12" rx="1" fill="rgba(255,255,255,0.02)"/>
 * </svg>
 */
