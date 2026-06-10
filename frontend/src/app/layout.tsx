import type { Metadata } from 'next';

import { Toaster } from '@/components/ui/sonner';

import './globals.css';
import { Providers } from './providers';

const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || 'https://localseooptimizer.com';

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: {
    default: 'Local SEO Optimizer | Managed Google Maps Growth for Local Businesses',
    template: '%s | Local SEO Optimizer',
  },
  description:
    'Get more calls from Google Maps with a free audit, Google Business Profile cleanup, compliant review systems, local pages, and monthly reporting.',
  keywords: [
    'google maps marketing',
    'google business profile management',
    'managed local seo service',
    'local seo for plumbers',
    'local seo for hvac',
    'local seo for roofers',
    'google maps audit',
    'review request system',
    'local landing pages',
    'google business profile optimization',
  ],
  authors: [{ name: 'Local SEO Optimizer' }],
  creator: 'Local SEO Optimizer',
  publisher: 'Local SEO Optimizer',
  robots: {
    index: true,
    follow: true,
  },
  openGraph: {
    type: 'website',
    locale: 'en_US',
    url: siteUrl,
    siteName: 'Local SEO Optimizer',
    title: 'Local SEO Optimizer | Get More Calls From Google Maps',
    description:
      'Free Google Maps audit plus managed Google Business Profile cleanup, review systems, local pages, and monthly reporting for local service businesses.',
    images: [
      {
        url: '/images/og-image.png',
        width: 1200,
        height: 630,
        alt: 'Local SEO Optimizer - Managed Google Maps growth',
      },
    ],
  },
  twitter: {
    card: 'summary_large_image',
    title: 'Local SEO Optimizer | Get More Calls From Google Maps',
    description:
      'Free Google Maps audit and managed monthly work for local service businesses.',
    images: ['/images/og-image.png'],
  },
  alternates: {
    canonical: siteUrl,
  },
  category: 'business',
};

const serviceJsonLd = {
  '@context': 'https://schema.org',
  '@type': 'Service',
  name: 'Local SEO Optimizer',
  serviceType: 'Managed Google Maps growth service',
  description:
    'A managed service for local businesses that combines Google Business Profile cleanup, review request systems, local pages, and monthly reporting.',
  provider: {
    '@type': 'Organization',
    name: 'Local SEO Optimizer',
    url: siteUrl,
  },
  areaServed: {
    '@type': 'Country',
    name: 'United States',
  },
  url: siteUrl,
};

const organizationJsonLd = {
  '@context': 'https://schema.org',
  '@type': 'Organization',
  name: 'Local SEO Optimizer',
  url: siteUrl,
  logo: `${siteUrl}/images/logo.png`,
  description:
    'Managed Google Maps growth and Google Business Profile support for local service businesses.',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <link rel="icon" href="/favicon.ico" sizes="any" />
        <link rel="icon" href="/icon.svg" type="image/svg+xml" />
        <link rel="apple-touch-icon" href="/apple-touch-icon.png" />
        <link rel="manifest" href="/manifest.json" />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(serviceJsonLd) }}
        />
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(organizationJsonLd) }}
        />
      </head>
      <body className="font-sans antialiased">
        <Providers>
          {children}
          <Toaster position="top-right" richColors />
        </Providers>
      </body>
    </html>
  );
}
