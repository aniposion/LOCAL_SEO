import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Start Your Free Preview',
  description: 'Create your free Local SEO Optimizer account. Get a free Google Maps audit and 3-day dashboard preview. No credit card required.',
  keywords: ['local seo free preview', 'google maps marketing preview', 'free seo audit'],
  openGraph: {
    title: 'Start Your Free Preview | Local SEO Optimizer',
    description: 'Create your account and get a free Google Maps audit. No credit card required.',
    url: '/signup',
  },
  alternates: {
    canonical: '/signup',
  },
};

export default function SignupLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
