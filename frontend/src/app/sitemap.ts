import { MetadataRoute } from 'next';

export default function sitemap(): MetadataRoute.Sitemap {
  const siteUrl = process.env.NEXT_PUBLIC_SITE_URL || 'https://localseooptimizer.com';
  const currentDate = new Date().toISOString();

  // Public pages
  const publicPages = [
    {
      url: siteUrl,
      lastModified: currentDate,
      changeFrequency: 'weekly' as const,
      priority: 1.0,
    },
    {
      url: `${siteUrl}/features`,
      lastModified: currentDate,
      changeFrequency: 'weekly' as const,
      priority: 0.9,
    },
    {
      url: `${siteUrl}/pricing`,
      lastModified: currentDate,
      changeFrequency: 'weekly' as const,
      priority: 0.9,
    },
    {
      url: `${siteUrl}/demo`,
      lastModified: currentDate,
      changeFrequency: 'monthly' as const,
      priority: 0.8,
    },
    {
      url: `${siteUrl}/contact`,
      lastModified: currentDate,
      changeFrequency: 'monthly' as const,
      priority: 0.7,
    },
    {
      url: `${siteUrl}/login`,
      lastModified: currentDate,
      changeFrequency: 'monthly' as const,
      priority: 0.5,
    },
    {
      url: `${siteUrl}/signup`,
      lastModified: currentDate,
      changeFrequency: 'monthly' as const,
      priority: 0.6,
    },
    {
      url: `${siteUrl}/terms`,
      lastModified: currentDate,
      changeFrequency: 'yearly' as const,
      priority: 0.3,
    },
    {
      url: `${siteUrl}/privacy`,
      lastModified: currentDate,
      changeFrequency: 'yearly' as const,
      priority: 0.3,
    },
  ];

  return publicPages;
}
