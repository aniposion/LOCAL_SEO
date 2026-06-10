import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Sign In',
  description: 'Sign in to your Local SEO Optimizer account to manage your Google Maps marketing.',
  robots: {
    index: false,
    follow: true,
  },
  alternates: {
    canonical: '/login',
  },
};

export default function LoginLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
