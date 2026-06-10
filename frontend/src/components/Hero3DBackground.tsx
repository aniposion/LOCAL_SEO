'use client';

import { useRef } from 'react';
import { Canvas, useFrame } from '@react-three/fiber';
import * as THREE from 'three';

// Polyhedron - expertise and innovation
function Dodecahedron({ position, color, scale, speed }: {
  position: [number, number, number];
  color: string;
  scale: number;
  speed: number;
}) {
  const meshRef = useRef<THREE.Mesh>(null);
  const initialY = position[1];

  useFrame((state) => {
    if (meshRef.current) {
      meshRef.current.rotation.x += 0.003 * speed;
      meshRef.current.rotation.y += 0.005 * speed;
      meshRef.current.position.y = initialY + Math.sin(state.clock.elapsedTime * speed * 0.5) * 0.4;
    }
  });

  return (
    <mesh ref={meshRef} position={position} scale={scale}>
      <dodecahedronGeometry args={[1, 0]} />
      <meshStandardMaterial
        color={color}
        roughness={0.15}
        metalness={0.95}
        transparent
        opacity={0.9}
        emissive={color}
        emissiveIntensity={0.3}
      />
    </mesh>
  );
}

// Octahedron - balance and success
function Octahedron({ position, color, scale, speed }: {
  position: [number, number, number];
  color: string;
  scale: number;
  speed: number;
}) {
  const meshRef = useRef<THREE.Mesh>(null);
  const initialY = position[1];

  useFrame((state) => {
    if (meshRef.current) {
      meshRef.current.rotation.x += 0.004 * speed;
      meshRef.current.rotation.z += 0.006 * speed;
      meshRef.current.position.y = initialY + Math.sin(state.clock.elapsedTime * speed * 0.6) * 0.3;
    }
  });

  return (
    <mesh ref={meshRef} position={position} scale={scale}>
      <octahedronGeometry args={[1, 0]} />
      <meshStandardMaterial
        color={color}
        roughness={0.1}
        metalness={0.98}
        transparent
        opacity={0.85}
        emissive={color}
        emissiveIntensity={0.35}
      />
    </mesh>
  );
}

// Ring - connection and partnership
function Ring({ position, color, scale, speed }: {
  position: [number, number, number];
  color: string;
  scale: number;
  speed: number;
}) {
  const meshRef = useRef<THREE.Mesh>(null);

  useFrame((state) => {
    if (meshRef.current) {
      meshRef.current.rotation.x = state.clock.elapsedTime * speed * 0.2;
      meshRef.current.rotation.y = state.clock.elapsedTime * speed * 0.3;
    }
  });

  return (
    <mesh ref={meshRef} position={position} scale={scale}>
      <torusGeometry args={[1, 0.25, 16, 48]} />
      <meshStandardMaterial
        color={color}
        roughness={0.08}
        metalness={0.98}
        transparent
        opacity={0.8}
        emissive={color}
        emissiveIntensity={0.4}
      />
    </mesh>
  );
}

// Capsule sphere - stability and trust
function CrystalSphere({ position, color, scale, speed }: {
  position: [number, number, number];
  color: string;
  scale: number;
  speed: number;
}) {
  const meshRef = useRef<THREE.Mesh>(null);
  const initialY = position[1];

  useFrame((state) => {
    if (meshRef.current) {
      meshRef.current.rotation.y += 0.002 * speed;
      meshRef.current.position.y = initialY + Math.sin(state.clock.elapsedTime * speed * 0.4) * 0.25;
    }
  });

  return (
    <mesh ref={meshRef} position={position} scale={scale}>
      <sphereGeometry args={[1, 32, 32]} />
      <meshStandardMaterial
        color={color}
        roughness={0.05}
        metalness={1}
        transparent
        opacity={0.7}
        emissive={color}
        emissiveIntensity={0.5}
      />
    </mesh>
  );
}

function Scene() {
  return (
    <>
      {/* Lighting - professional and polished */}
      <ambientLight intensity={0.25} />
      <directionalLight position={[10, 10, 5]} intensity={1} color="#ffffff" />
      <pointLight position={[-10, -5, -5]} intensity={0.8} color="#0ea5e9" />
      <pointLight position={[10, 5, 5]} intensity={0.6} color="#f59e0b" />
      <pointLight position={[0, -8, 5]} intensity={0.4} color="#10b981" />

      {/* Primary shapes - blue/cyan palette for trust and expertise */}
      <Dodecahedron position={[-9, 2, -4]} color="#0284c7" scale={1.6} speed={0.7} />
      <Dodecahedron position={[8, -1, -5]} color="#0891b2" scale={1.3} speed={0.9} />
      <Octahedron position={[6, 3, -4]} color="#06b6d4" scale={1.2} speed={0.8} />
      <Octahedron position={[-7, -2, -3]} color="#0ea5e9" scale={1.0} speed={1.1} />

      {/* Gold/amber accents for success and premium positioning */}
      <Octahedron position={[-4, 4, -5]} color="#f59e0b" scale={0.9} speed={0.6} />
      <Dodecahedron position={[4, -3, -4]} color="#d97706" scale={0.8} speed={0.85} />
      <CrystalSphere position={[0, 3, -6]} color="#fbbf24" scale={0.6} speed={0.5} />

      {/* Emerald/teal accents for growth */}
      <Octahedron position={[-10, 0, -6]} color="#10b981" scale={1.1} speed={0.75} />
      <Dodecahedron position={[10, 1, -5]} color="#14b8a6" scale={0.95} speed={0.95} />

      {/* Ring - connection and network */}
      <Ring position={[-6, -4, -5]} color="#0284c7" scale={0.9} speed={0.4} />
      <Ring position={[7, 4, -6]} color="#f59e0b" scale={0.7} speed={0.5} />
      <Ring position={[0, -5, -4]} color="#10b981" scale={0.6} speed={0.45} />

      {/* Small crystal spheres as accents */}
      <CrystalSphere position={[-3, 5, -5]} color="#38bdf8" scale={0.4} speed={0.6} />
      <CrystalSphere position={[5, 5, -6]} color="#fcd34d" scale={0.35} speed={0.7} />
      <CrystalSphere position={[-8, -4, -4]} color="#34d399" scale={0.3} speed={0.55} />
      <CrystalSphere position={[9, -4, -5]} color="#22d3ee" scale={0.45} speed={0.65} />
    </>
  );
}

export default function Hero3DBackground() {
  return (
    <div
      className="absolute inset-0 w-screen left-1/2 -translate-x-1/2"
      style={{ zIndex: 0 }}
    >
      <Canvas
        camera={{ position: [0, 0, 10], fov: 60 }}
        style={{
          background: 'linear-gradient(135deg, #0c1222 0%, #0f172a 30%, #1e293b 60%, #0f172a 80%, #0c1222 100%)',
          width: '100vw',
          height: '100%'
        }}
      >
        <Scene />
      </Canvas>
      {/* Subtle gradient overlay with brand colors */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background: 'radial-gradient(ellipse at 30% 20%, rgba(14, 165, 233, 0.08) 0%, transparent 50%), radial-gradient(ellipse at 70% 80%, rgba(245, 158, 11, 0.06) 0%, transparent 50%)'
        }}
      />
    </div>
  );
}
