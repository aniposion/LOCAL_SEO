'use client';

import React from 'react';

/**
 * Variation A: Premium Heatmap
 * - Safest, most enterprise-friendly design
 * - Soft cyan/teal blobs on deep navy
 * - Minimal visual noise, maximum readability
 */
export default function HeroBackgroundA() {
  return (
    <div className="hero-bg-a absolute inset-0 -z-10 overflow-hidden">
      {/* Base gradient layer */}
      <div className="absolute inset-0 bg-gradient-to-b from-[#0a0f1a] via-[#0d1829] to-[#0a1628]" />

      {/* Heatmap blobs layer */}
      <div className="absolute inset-0">
        {/* Large primary blob - top right */}
        <div
          className="absolute w-[600px] h-[600px] rounded-full opacity-20"
          style={{
            top: '-10%',
            right: '5%',
            background: 'radial-gradient(circle, rgba(6,182,212,0.4) 0%, rgba(6,182,212,0) 70%)',
            filter: 'blur(80px)',
          }}
        />

        {/* Large secondary blob - bottom left */}
        <div
          className="absolute w-[500px] h-[500px] rounded-full opacity-15"
          style={{
            bottom: '-15%',
            left: '-5%',
            background: 'radial-gradient(circle, rgba(20,184,166,0.4) 0%, rgba(20,184,166,0) 70%)',
            filter: 'blur(100px)',
          }}
        />

        {/* Medium blob - center right */}
        <div
          className="absolute w-[300px] h-[300px] rounded-full opacity-12"
          style={{
            top: '40%',
            right: '20%',
            background: 'radial-gradient(circle, rgba(6,182,212,0.35) 0%, rgba(6,182,212,0) 70%)',
            filter: 'blur(60px)',
          }}
        />

        {/* Small blob - top left */}
        <div
          className="absolute w-[200px] h-[200px] rounded-full opacity-10"
          style={{
            top: '20%',
            left: '15%',
            background: 'radial-gradient(circle, rgba(14,165,233,0.3) 0%, rgba(14,165,233,0) 70%)',
            filter: 'blur(50px)',
          }}
        />

        {/* Small blob - bottom center */}
        <div
          className="absolute w-[250px] h-[250px] rounded-full opacity-8"
          style={{
            bottom: '10%',
            left: '40%',
            background: 'radial-gradient(circle, rgba(20,184,166,0.25) 0%, rgba(20,184,166,0) 70%)',
            filter: 'blur(70px)',
          }}
        />
      </div>

      {/* Subtle grid overlay */}
      <svg
        className="absolute inset-0 w-full h-full opacity-[0.03]"
        xmlns="http://www.w3.org/2000/svg"
      >
        <defs>
          <pattern id="grid-a" width="60" height="60" patternUnits="userSpaceOnUse">
            <path d="M 60 0 L 0 0 0 60" fill="none" stroke="white" strokeWidth="0.5"/>
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#grid-a)" />
      </svg>

      {/* Center glow for text readability */}
      <div
        className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[400px] rounded-full"
        style={{
          background: 'radial-gradient(ellipse, rgba(6,182,212,0.08) 0%, transparent 70%)',
          filter: 'blur(40px)',
        }}
      />

      {/* Edge vignette */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background: 'radial-gradient(ellipse at center, transparent 40%, rgba(10,15,26,0.6) 100%)',
        }}
      />
    </div>
  );
}

/**
 * CSS-only version (copy-paste ready)
 *
 * .hero-bg-a {
 *   position: relative;
 *   min-height: 520px;
 *   background:
 *     radial-gradient(ellipse at center, transparent 40%, rgba(10,15,26,0.6) 100%),
 *     radial-gradient(ellipse at 50% 50%, rgba(6,182,212,0.08) 0%, transparent 50%),
 *     radial-gradient(circle at 85% 20%, rgba(6,182,212,0.15) 0%, transparent 40%),
 *     radial-gradient(circle at 15% 80%, rgba(20,184,166,0.12) 0%, transparent 35%),
 *     radial-gradient(circle at 70% 60%, rgba(6,182,212,0.08) 0%, transparent 25%),
 *     radial-gradient(circle at 25% 30%, rgba(14,165,233,0.06) 0%, transparent 20%),
 *     linear-gradient(to bottom, #0a0f1a 0%, #0d1829 50%, #0a1628 100%);
 *   overflow: hidden;
 * }
 */
