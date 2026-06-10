'use client';

import React from 'react';

interface HeroBackgroundProps {
  /**
   * Background variation
   * - 'premium': Soft heatmap (Variation A) - default
   * - 'data': Data/SEO feel (Variation B)
   * - 'city': Local/city feel (Variation C)
   * - '3d': Original Three.js version (heavier)
   */
  variant?: 'premium' | 'data' | 'city';
}

/**
 * Unified Hero Background Component
 * CSS-based, lightweight, no external dependencies
 *
 * Usage:
 * <HeroBackground variant="premium" />
 */
export default function HeroBackground({ variant = 'premium' }: HeroBackgroundProps) {
  const styles = {
    premium: {
      base: 'from-[#0a0f1a] via-[#0d1829] to-[#0a1628]',
      blobs: [
        { size: 700, top: '-15%', right: '0%', color: 'rgba(6,182,212,0.35)', blur: 100 },
        { size: 600, bottom: '-20%', left: '-10%', color: 'rgba(20,184,166,0.30)', blur: 120 },
        { size: 400, top: '35%', right: '15%', color: 'rgba(6,182,212,0.25)', blur: 80 },
        { size: 300, top: '15%', left: '10%', color: 'rgba(14,165,233,0.20)', blur: 70 },
        { size: 350, bottom: '5%', left: '35%', color: 'rgba(20,184,166,0.18)', blur: 90 },
        { size: 250, top: '50%', left: '50%', color: 'rgba(34,211,238,0.15)', blur: 60 },
      ],
      gridOpacity: 0.06,
      glowOpacity: 0.12,
      vignetteStrength: 0.5,
    },
    data: {
      base: 'from-[#0a0f1a] via-[#0f172a] to-[#0c1425]',
      blobs: [
        { size: 450, top: '-5%', right: '10%', color: 'rgba(6,182,212,0.22)', blur: 50 },
        { size: 350, top: '30%', left: '5%', color: 'rgba(20,184,166,0.16)', blur: 45 },
        { size: 300, top: '45%', left: '50%', color: 'rgba(34,211,238,0.14)', blur: 40 },
        { size: 200, bottom: '15%', right: '25%', color: 'rgba(6,182,212,0.10)', blur: 35 },
      ],
      gridOpacity: 0.04,
      glowOpacity: 0.07,
      vignetteStrength: 0.7,
      useDots: true,
    },
    city: {
      base: 'from-[#0a1018] via-[#0c1a2a] to-[#081420]',
      blobs: [
        { size: 500, top: '10%', right: '15%', color: 'rgba(20,184,166,0.20)', blur: 60 },
        { size: 400, top: '40%', left: '10%', color: 'rgba(6,182,212,0.16)', blur: 55 },
        { size: 200, top: '15%', left: '25%', color: 'rgba(45,212,191,0.12)', blur: 40 },
        { size: 600, bottom: '-10%', left: '30%', color: 'rgba(20,184,166,0.10)', blur: 70 },
      ],
      gridOpacity: 0.04,
      glowOpacity: 0.08,
      vignetteStrength: 0.65,
      useCityGrid: true,
    },
  };

  const config = styles[variant];

  return (
    <div className="absolute inset-0 -z-10 overflow-hidden">
      {/* Base gradient */}
      <div className={`absolute inset-0 bg-gradient-to-b ${config.base}`} />

      {/* Heatmap blobs */}
      <div className="absolute inset-0">
        {config.blobs.map((blob, i) => (
          <div
            key={i}
            className="absolute rounded-full"
            style={{
              width: blob.size,
              height: blob.size,
              top: blob.top,
              bottom: blob.bottom,
              left: blob.left,
              right: blob.right,
              background: `radial-gradient(circle, ${blob.color} 0%, transparent 70%)`,
              filter: `blur(${blob.blur}px)`,
            }}
          />
        ))}
      </div>

      {/* Grid overlay */}
      {'useDots' in config && config.useDots ? (
        <svg
          className="absolute inset-0 w-full h-full"
          style={{ opacity: config.gridOpacity }}
          xmlns="http://www.w3.org/2000/svg"
        >
          <defs>
            <pattern id="dots-pattern" width="30" height="30" patternUnits="userSpaceOnUse">
              <circle cx="15" cy="15" r="1" fill="rgba(6,182,212,0.8)"/>
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#dots-pattern)" />
        </svg>
      ) : 'useCityGrid' in config && config.useCityGrid ? (
        <svg
          className="absolute inset-0 w-full h-full"
          style={{ opacity: config.gridOpacity }}
          xmlns="http://www.w3.org/2000/svg"
        >
          <defs>
            <pattern id="city-pattern" width="100" height="100" patternUnits="userSpaceOnUse">
              <path d="M 0,50 L 100,50" stroke="rgba(255,255,255,0.6)" strokeWidth="1.5" fill="none"/>
              <path d="M 50,0 L 50,100" stroke="rgba(255,255,255,0.6)" strokeWidth="1.5" fill="none"/>
              <path d="M 0,25 L 100,25" stroke="rgba(255,255,255,0.25)" strokeWidth="0.5" fill="none"/>
              <path d="M 0,75 L 100,75" stroke="rgba(255,255,255,0.25)" strokeWidth="0.5" fill="none"/>
              <path d="M 25,0 L 25,100" stroke="rgba(255,255,255,0.25)" strokeWidth="0.5" fill="none"/>
              <path d="M 75,0 L 75,100" stroke="rgba(255,255,255,0.25)" strokeWidth="0.5" fill="none"/>
              <rect x="5" y="5" width="15" height="18" rx="1" fill="rgba(255,255,255,0.03)"/>
              <rect x="55" y="55" width="18" height="15" rx="1" fill="rgba(255,255,255,0.03)"/>
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#city-pattern)" />
        </svg>
      ) : (
        <svg
          className="absolute inset-0 w-full h-full"
          style={{ opacity: config.gridOpacity }}
          xmlns="http://www.w3.org/2000/svg"
        >
          <defs>
            <pattern id="grid-pattern" width="60" height="60" patternUnits="userSpaceOnUse">
              <path d="M 60 0 L 0 0 0 60" fill="none" stroke="white" strokeWidth="0.5"/>
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#grid-pattern)" />
        </svg>
      )}

      {/* Center glow for text readability */}
      <div
        className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[400px] rounded-full"
        style={{
          background: `radial-gradient(ellipse, rgba(6,182,212,${config.glowOpacity}) 0%, transparent 70%)`,
          filter: 'blur(40px)',
        }}
      />

      {/* Edge vignette */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background: `radial-gradient(ellipse at center, transparent 40%, rgba(10,15,26,${config.vignetteStrength}) 100%)`,
        }}
      />
    </div>
  );
}

/**
 * Pure CSS version for copy-paste (no React needed)
 *
 * Add this to your global CSS:
 *
 * .hero-heatmap {
 *   position: relative;
 *   min-height: 520px;
 *   overflow: hidden;
 *   background:
 *     radial-gradient(ellipse at center, transparent 40%, rgba(10,15,26,0.6) 100%),
 *     radial-gradient(ellipse at 50% 50%, rgba(6,182,212,0.08) 0%, transparent 50%),
 *     radial-gradient(circle at 85% 15%, rgba(6,182,212,0.18) 0%, transparent 40%),
 *     radial-gradient(circle at 10% 85%, rgba(20,184,166,0.14) 0%, transparent 38%),
 *     radial-gradient(circle at 75% 55%, rgba(6,182,212,0.10) 0%, transparent 28%),
 *     radial-gradient(circle at 20% 25%, rgba(14,165,233,0.08) 0%, transparent 22%),
 *     linear-gradient(to bottom, #0a0f1a 0%, #0d1829 50%, #0a1628 100%);
 * }
 */
