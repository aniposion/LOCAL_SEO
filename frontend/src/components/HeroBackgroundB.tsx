'use client';

import React from 'react';

/**
 * Variation B: Data/SEO Feel
 * - More "analytical" and "data-driven" appearance
 * - Includes subtle dot matrix pattern
 * - Hexagonal/honeycomb undertones suggesting data clusters
 * - Slightly more vibrant accent colors
 */
export default function HeroBackgroundB() {
  return (
    <div className="hero-bg-b absolute inset-0 -z-10 overflow-hidden">
      {/* Base gradient layer - slightly warmer navy */}
      <div className="absolute inset-0 bg-gradient-to-br from-[#0a0f1a] via-[#0f172a] to-[#0c1425]" />

      {/* Data visualization dots pattern */}
      <svg
        className="absolute inset-0 w-full h-full opacity-[0.04]"
        xmlns="http://www.w3.org/2000/svg"
      >
        <defs>
          <pattern id="dots-b" width="30" height="30" patternUnits="userSpaceOnUse">
            <circle cx="15" cy="15" r="1" fill="rgba(6,182,212,0.8)"/>
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#dots-b)" />
      </svg>

      {/* Heatmap clusters - more defined edges */}
      <div className="absolute inset-0">
        {/* Primary data cluster - top right */}
        <div
          className="absolute w-[450px] h-[450px] rounded-full"
          style={{
            top: '-5%',
            right: '10%',
            background: `
              radial-gradient(circle, rgba(6,182,212,0.25) 0%, rgba(6,182,212,0.1) 40%, transparent 70%)
            `,
            filter: 'blur(50px)',
          }}
        />

        {/* Secondary cluster - left side */}
        <div
          className="absolute w-[350px] h-[350px] rounded-full"
          style={{
            top: '30%',
            left: '5%',
            background: 'radial-gradient(circle, rgba(20,184,166,0.2) 0%, rgba(20,184,166,0.05) 50%, transparent 70%)',
            filter: 'blur(45px)',
          }}
        />

        {/* Data hotspot - center */}
        <div
          className="absolute w-[300px] h-[300px] rounded-full"
          style={{
            top: '45%',
            left: '50%',
            transform: 'translateX(-50%)',
            background: 'radial-gradient(circle, rgba(34,211,238,0.18) 0%, transparent 60%)',
            filter: 'blur(40px)',
          }}
        />

        {/* Small analytics node - bottom right */}
        <div
          className="absolute w-[200px] h-[200px] rounded-full"
          style={{
            bottom: '15%',
            right: '25%',
            background: 'radial-gradient(circle, rgba(6,182,212,0.15) 0%, transparent 60%)',
            filter: 'blur(35px)',
          }}
        />

        {/* Subtle connection line effect */}
        <svg className="absolute inset-0 w-full h-full opacity-[0.06]" viewBox="0 0 100 100" preserveAspectRatio="none">
          <defs>
            <linearGradient id="line-grad" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="rgba(6,182,212,0)" />
              <stop offset="50%" stopColor="rgba(6,182,212,0.5)" />
              <stop offset="100%" stopColor="rgba(6,182,212,0)" />
            </linearGradient>
          </defs>
          <path
            d="M 10,80 Q 30,60 50,55 T 90,30"
            stroke="url(#line-grad)"
            strokeWidth="0.15"
            fill="none"
            strokeDasharray="1,2"
          />
        </svg>
      </div>

      {/* Hexagonal overlay hint */}
      <svg
        className="absolute inset-0 w-full h-full opacity-[0.02]"
        xmlns="http://www.w3.org/2000/svg"
      >
        <defs>
          <pattern id="hex-b" width="56" height="100" patternUnits="userSpaceOnUse" patternTransform="scale(0.5)">
            <path
              d="M28,0 L56,17 L56,51 L28,68 L0,51 L0,17 Z M28,68 L56,85 L56,100 M28,68 L0,85 L0,100"
              fill="none"
              stroke="rgba(6,182,212,0.5)"
              strokeWidth="0.5"
            />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#hex-b)" />
      </svg>

      {/* Center spotlight for text */}
      <div
        className="absolute left-1/2 top-[45%] -translate-x-1/2 -translate-y-1/2 w-[900px] h-[350px]"
        style={{
          background: 'radial-gradient(ellipse, rgba(6,182,212,0.06) 0%, transparent 60%)',
          filter: 'blur(30px)',
        }}
      />

      {/* Edge vignette - stronger */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background: 'radial-gradient(ellipse at center, transparent 35%, rgba(10,15,26,0.7) 100%)',
        }}
      />
    </div>
  );
}

/**
 * CSS-only version (copy-paste ready)
 *
 * .hero-bg-b {
 *   position: relative;
 *   min-height: 520px;
 *   background:
 *     radial-gradient(ellipse at center, transparent 35%, rgba(10,15,26,0.7) 100%),
 *     radial-gradient(ellipse at 50% 45%, rgba(6,182,212,0.06) 0%, transparent 40%),
 *     radial-gradient(circle at 80% 15%, rgba(6,182,212,0.2) 0%, transparent 35%),
 *     radial-gradient(circle at 20% 45%, rgba(20,184,166,0.15) 0%, transparent 30%),
 *     radial-gradient(circle at 50% 60%, rgba(34,211,238,0.12) 0%, transparent 25%),
 *     radial-gradient(circle at 70% 75%, rgba(6,182,212,0.1) 0%, transparent 20%),
 *     linear-gradient(to bottom right, #0a0f1a 0%, #0f172a 50%, #0c1425 100%);
 *   overflow: hidden;
 * }
 *
 * .hero-bg-b::before {
 *   content: '';
 *   position: absolute;
 *   inset: 0;
 *   background-image: radial-gradient(rgba(6,182,212,0.15) 1px, transparent 1px);
 *   background-size: 30px 30px;
 *   opacity: 0.3;
 * }
 */
