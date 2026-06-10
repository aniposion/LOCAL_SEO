import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Features - AI-Powered Local SEO Tools',
  description: 'Discover all features: AI content generation, review management, analytics dashboard, missed call text back, and more. Everything you need for local SEO success.',
  keywords: ['local seo features', 'ai content generation', 'review management', 'google maps analytics', 'business automation'],
  openGraph: {
    title: 'Features | Local SEO Optimizer',
    description: 'AI-powered tools for local SEO: content generation, reviews, analytics, and more.',
    url: '/features',
  },
  alternates: {
    canonical: '/features',
  },
};

export default function FeaturesLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
