'use client';

import { useEffect, useEffectEvent, useState } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Sheet, SheetContent, SheetTrigger } from '@/components/ui/sheet';
import {
  MapPin,
  LayoutDashboard,
  FileText,
  BarChart3,
  Star,
  Settings,
  LogOut,
  Menu,
  Newspaper,
  Building2,
  CreditCard,
  Users,
  Bell,
  ChevronDown,
  MessageCircleQuestion,
  Phone,
  Globe,
  FileBarChart,
  Instagram,
  FlaskConical,
  Gauge,
  Sparkles,
  Link2,
  Lock,
  Shield,
  Target,
  TrendingUp,
  type LucideIcon,
} from 'lucide-react';
import { useAuthStore } from '@/store/auth';
import { authApi } from '@/lib/api';
import { cn } from '@/lib/utils';
import { useFeatureAccess } from '@/hooks/useFeatureAccess';
import { Badge } from '@/components/ui/badge';
import { TrialBanner } from '@/components/billing/TrialBanner';
import { PageGuide } from '@/components/dashboard/PageGuide';

type PlanId = 'free' | 'maps_starter' | 'calls_growth' | 'competitive_market' | 'starter' | 'pro' | 'premium' | 'agency';

interface NavigationItem {
  name: string;
  href: string;
  icon: LucideIcon;
  feature: string;
  minPlan?: PlanId;
  hideWhenLocked?: boolean;
}

interface NavigationGroup {
  label: string;
  items: NavigationItem[];
}

// Navigation is grouped by the job the user is trying to complete, not by internal feature names.
const navigationGroups: NavigationGroup[] = [
  {
    label: 'Start Here',
    items: [
      { name: 'Today', href: '/dashboard', icon: LayoutDashboard, feature: 'basic_dashboard' },
      { name: 'Integrations', href: '/dashboard/integrations', icon: Link2, feature: 'basic_dashboard' },
      { name: 'Locations', href: '/dashboard/locations', icon: Building2, feature: 'basic_dashboard' },
    ],
  },
  {
    label: 'Get Found',
    items: [
      { name: 'Content Queue', href: '/dashboard/content', icon: FileText, feature: 'google_posts', minPlan: 'starter' },
      { name: 'Create Draft', href: '/dashboard/content/new', icon: Sparkles, feature: 'google_posts', minPlan: 'starter' },
      { name: 'Website Board', href: '/dashboard/board', icon: Newspaper, feature: 'basic_dashboard' },
      { name: 'Website SEO', href: '/dashboard/seo', icon: Globe, feature: 'website_seo_basic', minPlan: 'pro' },
      { name: 'Competitors', href: '/dashboard/competitors', icon: FlaskConical, feature: 'competitor_analysis', minPlan: 'pro' },
      { name: 'UTM Links', href: '/dashboard/utm', icon: Target, feature: 'basic_dashboard' },
    ],
  },
  {
    label: 'Earn Trust',
    items: [
      { name: 'Reviews', href: '/dashboard/reviews', icon: Star, feature: 'review_collection', minPlan: 'starter' },
      { name: 'Review Replies', href: '/dashboard/review-responder', icon: Star, feature: 'ai_review_response', minPlan: 'starter' },
      { name: 'Q&A', href: '/dashboard/qa', icon: MessageCircleQuestion, feature: 'qa_auto_response', minPlan: 'pro' },
      { name: 'Social Proof', href: '/dashboard/social-proof', icon: Sparkles, feature: 'instagram_upload', minPlan: 'pro' },
    ],
  },
  {
    label: 'Capture Leads',
    items: [
      { name: 'Calls & SMS', href: '/dashboard/calls', icon: Phone, feature: 'missed_call_text_back', minPlan: 'premium' },
      { name: 'Social Inbox', href: '/dashboard/social', icon: Instagram, feature: 'social_auto_responder', minPlan: 'premium' },
    ],
  },
  {
    label: 'Prove ROI',
    items: [
      { name: 'Analytics', href: '/dashboard/analytics', icon: BarChart3, feature: 'basic_dashboard' },
      { name: 'ROI', href: '/dashboard/roi', icon: TrendingUp, feature: 'basic_dashboard' },
      { name: 'Reports', href: '/dashboard/reports', icon: FileBarChart, feature: 'weekly_report', minPlan: 'starter' },
      { name: 'Usage', href: '/dashboard/usage', icon: Gauge, feature: 'basic_dashboard' },
    ],
  },
  {
    label: 'Settings',
    items: [
      { name: 'Billing', href: '/dashboard/billing', icon: CreditCard, feature: 'basic_dashboard' },
      { name: 'Notifications', href: '/dashboard/notifications', icon: Bell, feature: 'basic_dashboard' },
      { name: 'Settings', href: '/dashboard/settings', icon: Settings, feature: 'basic_dashboard' },
      { name: 'Agency', href: '/dashboard/agency', icon: Users, feature: 'white_label', minPlan: 'agency', hideWhenLocked: true },
    ],
  },
];

// Admin-only navigation (separate from regular nav)
const adminNavigation = [
  { name: 'Admin', href: '/admin', icon: Shield },
];

// Plan hierarchy for comparison
const PLAN_ORDER: PlanId[] = ['free', 'maps_starter', 'calls_growth', 'competitive_market', 'starter', 'pro', 'premium', 'agency'];

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const { user, setUser, setLoading, logout } = useAuthStore();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const checkAuth = useEffectEvent(async () => {
    try {
      const response = await authApi.me();
      setUser(response.data);
    } catch {
      logout();
      router.push('/login');
    } finally {
      setLoading(false);
    }
  });

  useEffect(() => {
    void checkAuth();
  }, []);

  const handleLogout = async () => {
    await authApi.logout();
    logout();
    router.push('/login');
  };

  const { data: featureAccess } = useFeatureAccess();
  const currentPlan = (featureAccess?.plan || 'free') as PlanId;
  const currentPlanIndex = PLAN_ORDER.indexOf(currentPlan);

  const hasFeatureAccess = (feature: string, minPlan?: PlanId) => {
    if (!featureAccess) return true; // Loading state - show all

    // Check if feature is available
    const featureValue = featureAccess.features[feature as keyof typeof featureAccess.features];
    if (typeof featureValue === 'boolean' && featureValue) return true;

    // Check minimum plan requirement
    if (minPlan) {
      const minPlanIndex = PLAN_ORDER.indexOf(minPlan);
      return currentPlanIndex >= minPlanIndex;
    }

    return false;
  };

  // Check if user is admin (check role or email for superuser)
  const dashboardUser = user as (typeof user & { is_superuser?: boolean }) | null;
  const isAdmin = dashboardUser?.role === 'admin' || dashboardUser?.is_superuser === true;

  const NavLinks = () => (
    <>
      {navigationGroups.map((group) => (
        <div key={group.label} className="space-y-1">
          <p className="px-3 pt-3 text-[11px] font-semibold uppercase tracking-wide text-gray-400 first:pt-0">
            {group.label}
          </p>
          {group.items.map((item) => {
            const isActive = pathname === item.href || pathname.startsWith(item.href + '/');
            const hasAccess = hasFeatureAccess(item.feature, item.minPlan);

            if (!hasAccess && item.hideWhenLocked) {
              return null;
            }

            return (
              <Link
                key={item.name}
                href={hasAccess ? item.href : '/dashboard/billing'}
                className={cn(
                  'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                  isActive && hasAccess
                    ? 'bg-violet-100 text-violet-700'
                    : hasAccess
                      ? 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
                      : 'text-gray-400 hover:bg-gray-50'
                )}
                onClick={() => setSidebarOpen(false)}
              >
                <item.icon className={cn('h-5 w-5', !hasAccess && 'opacity-50')} />
                <span className="flex-1">{item.name}</span>
                {!hasAccess && <Lock className="h-3 w-3 text-gray-400" />}
              </Link>
            );
          })}
        </div>
      ))}

      {/* Admin Section - Only visible to admins */}
      {isAdmin && (
        <>
          <div className="my-3 border-t" />
          <p className="px-3 py-1 text-xs font-semibold text-gray-400 uppercase">Admin</p>
          {adminNavigation.map((item) => {
            const isActive = pathname === item.href || pathname.startsWith(item.href + '/');
            return (
              <Link
                key={item.name}
                href={item.href}
                className={cn(
                  'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-red-100 text-red-700'
                    : 'text-gray-600 hover:bg-gray-100 hover:text-gray-900'
                )}
                onClick={() => setSidebarOpen(false)}
              >
                <item.icon className="w-5 h-5" />
                <span className="flex-1">{item.name}</span>
              </Link>
            );
          })}
        </>
      )}
    </>
  );

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Desktop Sidebar */}
      <aside className="hidden lg:fixed lg:inset-y-0 lg:flex lg:w-64 lg:flex-col">
        <div className="flex flex-col flex-grow bg-white border-r pt-5 pb-4">
          {/* Logo */}
          <div className="flex items-center gap-2 px-4 mb-6">
            <div className="w-8 h-8 bg-gradient-to-br from-violet-600 to-indigo-600 rounded-lg flex items-center justify-center">
              <MapPin className="w-5 h-5 text-white" />
            </div>
            <span className="font-bold text-lg">Local SEO</span>
          </div>

          {/* Navigation */}
          <nav className="flex-1 px-3 space-y-1">
            <NavLinks />
          </nav>

          {/* Plan Badge & Upgrade Banner */}
          <div className="px-3 mt-4 space-y-3">
            {/* Current Plan */}
            <div className="flex items-center justify-between px-3 py-2 bg-gray-50 rounded-lg">
              <span className="text-xs text-gray-500">Current Plan</span>
              <Badge className={cn(
                currentPlan === 'agency' ? 'bg-emerald-100 text-emerald-700' :
                currentPlan === 'premium' ? 'bg-amber-100 text-amber-700' :
                currentPlan === 'pro' ? 'bg-violet-100 text-violet-700' :
                currentPlan === 'starter' ? 'bg-blue-100 text-blue-700' :
                'bg-gray-100 text-gray-700'
              )}>
                {currentPlan.charAt(0).toUpperCase() + currentPlan.slice(1)}
                {featureAccess?.is_trial && ' (Preview)'}
              </Badge>
            </div>

            {/* Upgrade Banner - only show if not on agency plan */}
            {currentPlan !== 'agency' && (
              <Link href="/dashboard/billing">
                <div className="p-4 bg-gradient-to-br from-violet-600 to-indigo-600 rounded-xl text-white cursor-pointer hover:opacity-90 transition-opacity">
                  <p className="text-sm font-medium mb-2">
                    {currentPlan === 'premium' ? 'Expand to Agency' :
                     currentPlan === 'pro' ? 'Upgrade to Premium' :
                     currentPlan === 'starter' ? 'Upgrade to Pro' :
                     'Unlock Growth Workflows'}
                  </p>
                  <p className="text-xs text-violet-200 mb-3">
                    {currentPlan === 'premium' ? 'Multi-location & White Label' :
                     currentPlan === 'pro' ? 'Missed Call + Review Booster included' :
                     currentPlan === 'starter' ? 'Instagram + Competitor Analysis' :
                     'Preview dashboard and setup health first'}
                  </p>
                  <Button size="sm" variant="secondary" className="w-full">
                    View plans
                  </Button>
                </div>
              </Link>
            )}
          </div>
        </div>
      </aside>

      {/* Mobile Header */}
      <div className="lg:hidden sticky top-0 z-40 flex items-center gap-4 bg-white border-b px-4 h-16">
        <Sheet open={sidebarOpen} onOpenChange={setSidebarOpen}>
          <SheetTrigger asChild>
            <Button variant="ghost" size="icon">
              <Menu className="w-5 h-5" />
            </Button>
          </SheetTrigger>
          <SheetContent side="left" className="w-64 p-0">
            <div className="flex flex-col h-full pt-5 pb-4">
              <div className="flex items-center gap-2 px-4 mb-6">
                <div className="w-8 h-8 bg-gradient-to-br from-violet-600 to-indigo-600 rounded-lg flex items-center justify-center">
                  <MapPin className="w-5 h-5 text-white" />
                </div>
                <span className="font-bold text-lg">Local SEO</span>
              </div>
              <nav className="flex-1 px-3 space-y-1">
                <NavLinks />
              </nav>
            </div>
          </SheetContent>
        </Sheet>

        <div className="flex-1" />

        {/* User Menu */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" className="gap-2">
              <Avatar className="w-8 h-8">
                <AvatarFallback className="bg-violet-100 text-violet-700">
                  {user?.full_name?.[0] || user?.email?.[0] || 'U'}
                </AvatarFallback>
              </Avatar>
              <ChevronDown className="w-4 h-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            <DropdownMenuLabel>
              <div className="font-normal">
                <p className="font-medium">{user?.full_name || 'User'}</p>
                <p className="text-sm text-gray-500">{user?.email}</p>
              </div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem asChild>
              <Link href="/dashboard/settings">
                <Settings className="mr-2 h-4 w-4" />
                Settings
              </Link>
            </DropdownMenuItem>
            <DropdownMenuItem asChild>
              <Link href="/dashboard/billing">
                <CreditCard className="mr-2 h-4 w-4" />
                Billing
              </Link>
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={handleLogout} className="text-red-600">
              <LogOut className="mr-2 h-4 w-4" />
              Log out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {/* Main Content */}
      <div className="lg:pl-64">
        {/* Desktop Header */}
        <header className="hidden lg:flex sticky top-0 z-40 items-center justify-between bg-white border-b px-6 h-16">
          <div>
            {/* Breadcrumb or title could go here */}
          </div>
          <div className="flex items-center gap-4">
            <Button variant="ghost" size="icon">
              <Bell className="w-5 h-5" />
            </Button>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" className="gap-2">
                  <Avatar className="w-8 h-8">
                    <AvatarFallback className="bg-violet-100 text-violet-700">
                      {user?.full_name?.[0] || user?.email?.[0] || 'U'}
                    </AvatarFallback>
                  </Avatar>
                  <span className="hidden md:inline">{user?.full_name || 'User'}</span>
                  <ChevronDown className="w-4 h-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56">
                <DropdownMenuLabel>
                  <div className="font-normal">
                    <p className="font-medium">{user?.full_name || 'User'}</p>
                    <p className="text-sm text-gray-500">{user?.email}</p>
                  </div>
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem asChild>
                  <Link href="/dashboard/settings">
                    <Settings className="mr-2 h-4 w-4" />
                    Settings
                  </Link>
                </DropdownMenuItem>
                <DropdownMenuItem asChild>
                  <Link href="/dashboard/billing">
                    <CreditCard className="mr-2 h-4 w-4" />
                    Billing
                  </Link>
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={handleLogout} className="text-red-600">
                  <LogOut className="mr-2 h-4 w-4" />
                  Log out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </header>

        {/* Trial Banner */}
        <TrialBanner />

        {/* Page Content */}
        <main className="mx-auto max-w-7xl space-y-6 p-6">
          <PageGuide pathname={pathname} />
          {children}
        </main>
      </div>
    </div>
  );
}
