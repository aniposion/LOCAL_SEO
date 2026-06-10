import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Pricing - Plans That Replace Agency Work',
  description: 'Simple pricing starting at $99/month. Start with a 3-day free preview, then choose a paid plan to unlock AI, SMS, publishing, and automation.',
  keywords: ['local seo pricing', 'google maps marketing cost', 'seo software pricing', 'affordable local seo'],
  openGraph: {
    title: 'Pricing | Local SEO Optimizer',
    description: 'Simple pricing starting at $99/month. Replace agency tasks with automation.',
    url: '/pricing',
  },
  alternates: {
    canonical: '/pricing',
  },
};

export default function PricingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
