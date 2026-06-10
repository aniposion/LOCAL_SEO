'use client';

import React from 'react';

/**
 * Variation C: Local/City Feel
 * - Abstract city map aesthetic
 * - Road-like lines and block patterns
 * - Location pin accent (very subtle)
 * - Warmer teal tones
 */
export default function HeroBackgroundC() {
  return (
    <div className="hero-bg-c absolute inset-0 -z-10 overflow-hidden">
      {/* Base gradient layer */}
      <div className="absolute inset-0 bg-gradient-to-b from-[#0a1018] via-[#0c1a2a] to-[#081420]" />

      {/* Abstract city grid / road pattern */}
      <svg
        className="absolute inset-0 w-full h-full opacity-[0.04]"
        xmlns="http://www.w3.org/2000/svg"
        preserveAspectRatio="xMidYMid slice"
      >
        <defs>
          <pattern id="city-grid" width="120" height="120" patternUnits="userSpaceOnUse">
            {/* Main roads */}
            <path d="M 0,60 L 120,60" stroke="rgba(255,255,255,0.8)" strokeWidth="2" fill="none"/>
            <path d="M 60,0 L 60,120" stroke="rgba(255,255,255,0.8)" strokeWidth="2" fill="none"/>
            {/* Secondary roads */}
            <path d="M 0,30 L 120,30" stroke="rgba(255,255,255,0.4)" strokeWidth="0.5" fill="none"/>
            <path d="M 0,90 L 120,90" stroke="rgba(255,255,255,0.4)" strokeWidth="0.5" fill="none"/>
            <path d="M 30,0 L 30,120" stroke="rgba(255,255,255,0.4)" strokeWidth="0.5" fill="none"/>
            <path d="M 90,0 L 90,120" stroke="rgba(255,255,255,0.4)" strokeWidth="0.5" fill="none"/>
            {/* City blocks (abstract) */}
            <rect x="5" y="5" width="20" height="20" rx="2" fill="rgba(255,255,255,0.05)"/>
            <rect x="35" y="65" width="15" height="25" rx="2" fill="rgba(255,255,255,0.03)"/>
            <rect x="95" y="35" width="20" height="15" rx="2" fill="rgba(255,255,255,0.04)"/>
            <rect x="65" y="95" width="25" height="20" rx="2" fill="rgba(255,255,255,0.03)"/>
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#city-grid)" />
      </svg>

      {/* Location coverage heatmap zones */}
      <div className="absolute inset-0">
        {/* Primary coverage zone - center-right */}
        <div
          className="absolute w-[500px] h-[500px] rounded-full"
          style={{
            top: '10%',
            right: '15%',
            background: 'radial-gradient(circle, rgba(20,184,166,0.22) 0%, rgba(20,184,166,0.08) 40%, transparent 70%)',
            filter: 'blur(60px)',
          }}
        />

        {/* Secondary zone - left */}
        <div
          className="absolute w-[400px] h-[400px] rounded-full"
          style={{
            top: '40%',
            left: '10%',
            background: 'radial-gradient(circle, rgba(6,182,212,0.18) 0%, rgba(6,182,212,0.05) 50%, transparent 70%)',
            filter: 'blur(55px)',
          }}
        />

        {/* Small hotspot - top left */}
        <div
          className="absolute w-[200px] h-[200px] rounded-full"
          style={{
            top: '15%',
            left: '25%',
            background: 'radial-gradient(circle, rgba(45,212,191,0.15) 0%, transparent 60%)',
            filter: 'blur(40px)',
          }}
        />

        {/* Bottom coverage spread */}
        <div
          className="absolute w-[600px] h-[300px] rounded-full"
          style={{
            bottom: '-10%',
            left: '30%',
            background: 'radial-gradient(ellipse, rgba(20,184,166,0.12) 0%, transparent 60%)',
            filter: 'blur(70px)',
          }}
        />
      </div>

      {/* Subtle location pin indicator */}
      <svg
        className="absolute opacity-[0.08]"
        style={{ top: '25%', right: '28%', width: '24px', height: '32px' }}
        viewBox="0 0 24 32"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <path
          d="M12 0C5.4 0 0 5.4 0 12c0 9 12 20 12 20s12-11 12-20c0-6.6-5.4-12-12-12zm0 16c-2.2 0-4-1.8-4-4s1.8-4 4-4 4 1.8 4 4-1.8 4-4 4z"
          fill="rgba(6,182,212,1)"
        />
      </svg>

      {/* Another subtle pin */}
      <svg
        className="absolute opacity-[0.05]"
        style={{ top: '55%', left: '20%', width: '16px', height: '22px' }}
        viewBox="0 0 24 32"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
      >
        <path
          d="M12 0C5.4 0 0 5.4 0 12c0 9 12 20 12 20s12-11 12-20c0-6.6-5.4-12-12-12zm0 16c-2.2 0-4-1.8-4-4s1.8-4 4-4 4 1.8 4 4-1.8 4-4 4z"
          fill="rgba(20,184,166,1)"
        />
      </svg>

      {/* Dotted route line */}
      <svg
        className="absolute inset-0 w-full h-full opacity-[0.06]"
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
      >
        <path
          d="M 20,55 Q 35,50 50,45 T 72,28"
          stroke="rgba(6,182,212,0.8)"
          strokeWidth="0.2"
          fill="none"
          strokeDasharray="0.5,1"
        />
      </svg>

      {/* Text spotlight */}
      <div
        className="absolute left-1/2 top-[40%] -translate-x-1/2 -translate-y-1/2 w-[700px] h-[400px]"
        style={{
          background: 'radial-gradient(ellipse, rgba(20,184,166,0.07) 0%, transparent 55%)',
          filter: 'blur(35px)',
        }}
      />

      {/* Vignette */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background: 'radial-gradient(ellipse at center, transparent 40%, rgba(8,20,32,0.65) 100%)',
        }}
      />
    </div>
  );
}

/**
 * CSS-only version (copy-paste ready)
 *
 * .hero-bg-c {
 *   position: relative;
 *   min-height: 520px;
 *   background:
 *     radial-gradient(ellipse at center, transparent 40%, rgba(8,20,32,0.65) 100%),
 *     radial-gradient(ellipse at 50% 40%, rgba(20,184,166,0.07) 0%, transparent 40%),
 *     radial-gradient(circle at 75% 25%, rgba(20,184,166,0.18) 0%, transparent 35%),
 *     radial-gradient(circle at 25% 55%, rgba(6,182,212,0.14) 0%, transparent 30%),
 *     radial-gradient(circle at 35% 20%, rgba(45,212,191,0.1) 0%, transparent 20%),
 *     radial-gradient(ellipse at 50% 95%, rgba(20,184,166,0.1) 0%, transparent 30%),
 *     linear-gradient(to bottom, #0a1018 0%, #0c1a2a 50%, #081420 100%);
 *   overflow: hidden;
 * }
 */
