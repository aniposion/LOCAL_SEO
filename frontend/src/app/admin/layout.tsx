import { Metadata } from 'next';

export const metadata: Metadata = {
  title: 'Admin Dashboard - Local SEO Optimizer',
  description: 'Manage users, credits, and system settings',
};

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
