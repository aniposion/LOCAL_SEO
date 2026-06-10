import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Book an Audit Review',
  description:
    'Contact Local SEO Optimizer to review your Google Maps audit, ask about managed local SEO pricing, or request a pilot.',
  keywords: ['google maps audit review', 'managed local seo pricing', 'local seo pilot'],
  openGraph: {
    title: 'Book an Audit Review | Local SEO Optimizer',
    description: 'Review your Google Maps audit and ask about managed local SEO packages.',
    url: '/contact',
  },
  alternates: {
    canonical: '/contact',
  },
};

export default function ContactLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
