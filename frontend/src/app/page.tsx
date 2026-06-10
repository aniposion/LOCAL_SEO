'use client';

import Link from 'next/link';
import {
  ArrowRight,
  CheckCircle,
  MapPin,
  Phone,
  Search,
  ShieldCheck,
  Star,
  Wrench,
} from 'lucide-react';

import { Button } from '@/components/ui/button';

const problemPoints = [
  'Wrong or incomplete business info',
  'Weak review velocity compared with nearby competitors',
  'No recent photos or fresh Google posts',
  'Missing services and weak category coverage',
  'No clear local landing pages for core service areas',
  'No simple monthly reporting tied to calls and visibility',
];

const serviceItems = [
  {
    title: 'Google Business Profile Cleanup',
    description:
      'We update categories, services, hours, descriptions, photos, and profile details so the listing is easier to trust.',
    icon: Wrench,
  },
  {
    title: 'Review Request System',
    description:
      'We help you ask real customers for honest reviews by SMS, email, and QR code without fake incentives or review gating.',
    icon: Star,
  },
  {
    title: 'Local Competitor Tracking',
    description:
      'We compare your profile against nearby competitors for the services and cities that matter most.',
    icon: Search,
  },
  {
    title: 'Local Landing Pages',
    description:
      'We build or improve service and city pages so customers understand what you do and where you serve.',
    icon: MapPin,
  },
  {
    title: 'Monthly Calls Report',
    description:
      'You get a simple monthly report showing calls, clicks, reviews, visibility movement, and the work completed.',
    icon: Phone,
  },
];

const processSteps = [
  {
    title: 'Free audit',
    description:
      'We review your Google Maps presence and show the biggest gaps that may be costing calls.',
  },
  {
    title: '15-minute review call',
    description:
      'We walk through the findings in plain English and show what we would fix first.',
  },
  {
    title: '3-month managed pilot',
    description:
      'Month one fixes the profile and tracking. Months two and three focus on reviews, pages, and visibility momentum.',
  },
];

const packageTeasers = [
  {
    title: 'Maps Starter',
    price: '$699/mo',
    note: '$499 setup',
    description: 'For smaller local service businesses that need their profile fixed and maintained.',
  },
  {
    title: 'Calls Growth',
    price: '$999/mo',
    note: '$799 setup',
    description: 'For home service businesses that want more calls from Google Maps without learning SEO.',
  },
  {
    title: 'Competitive Market',
    price: 'From $1,499/mo',
    note: '$1,500 setup',
    description: 'For high-competition cities, high-ticket services, or multi-location teams.',
  },
];

export default function Home() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-50 to-white">
      <header className="sticky top-0 z-50 border-b bg-white/90 backdrop-blur-md">
        <div className="container mx-auto flex h-16 items-center justify-between px-4">
          <Link href="/" className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-sky-500 to-cyan-500">
              <MapPin className="h-5 w-5 text-white" />
            </div>
            <span className="hidden text-xl font-bold sm:block">Local SEO Optimizer</span>
          </Link>

          <nav className="hidden items-center gap-8 md:flex">
            <a href="#what-we-fix" className="text-sm text-gray-600 hover:text-gray-900">
              What We Fix
            </a>
            <Link href="/pricing" className="text-sm text-gray-600 hover:text-gray-900">
              Pricing
            </Link>
            <Link href="/contact" className="text-sm text-gray-600 hover:text-gray-900">
              Contact
            </Link>
          </nav>

          <div className="flex items-center gap-3">
            <Link href="/login">
              <Button variant="ghost" size="sm">
                Sign in
              </Button>
            </Link>
            <Link href="/onboarding">
              <Button
                size="sm"
                className="bg-gradient-to-r from-sky-500 to-cyan-500 hover:from-sky-600 hover:to-cyan-600"
              >
                Get My Free Audit
              </Button>
            </Link>
          </div>
        </div>
      </header>

      <section className="px-4 py-20 sm:py-28">
        <div className="container mx-auto max-w-6xl">
          <div className="grid items-center gap-10 lg:grid-cols-[1.2fr_0.8fr]">
            <div>
              <div className="mb-5 inline-flex items-center gap-2 rounded-full border border-sky-200 bg-sky-50 px-4 py-2 text-sm font-medium text-sky-700">
                Managed Google Maps growth for local service businesses
              </div>
              <h1 className="max-w-4xl text-4xl font-bold tracking-tight text-slate-950 sm:text-5xl md:text-6xl">
                Get More Calls From Google Maps
              </h1>
              <p className="mt-6 max-w-2xl text-lg leading-8 text-gray-600">
                We help local service businesses fix and manage their Google Business
                Profile, review request system, local pages, and monthly reporting so
                nearby customers can find and call them.
              </p>
              <div className="mt-8 flex flex-col gap-3 sm:flex-row">
                <Link href="/onboarding">
                  <Button
                    size="lg"
                    className="h-14 w-full bg-gradient-to-r from-sky-500 to-cyan-500 px-8 text-lg hover:from-sky-600 hover:to-cyan-600 sm:w-auto"
                  >
                    Get My Free Maps Audit
                    <ArrowRight className="ml-2 h-5 w-5" />
                  </Button>
                </Link>
                <Link href="/pricing">
                  <Button size="lg" variant="outline" className="h-14 w-full px-8 text-lg sm:w-auto">
                    See Pricing
                  </Button>
                </Link>
              </div>
              <p className="mt-4 text-sm text-gray-500">
                No fake reviews. No ranking guarantees. Just practical local SEO work done for you.
              </p>
            </div>

            <div className="rounded-3xl border border-sky-100 bg-white p-6 shadow-xl shadow-sky-100/70">
              <div className="text-sm font-semibold uppercase tracking-[0.18em] text-sky-700">
                Free Audit Includes
              </div>
              <div className="mt-5 space-y-4">
                {[
                  'A plain-English Google Maps visibility review',
                  'A competitor gap snapshot for your main service area',
                  'Top 3 issues that may be costing calls',
                  'A recommended 30-day fix plan',
                ].map((item) => (
                  <div key={item} className="flex items-start gap-3">
                    <CheckCircle className="mt-0.5 h-5 w-5 flex-shrink-0 text-green-500" />
                    <p className="text-sm leading-6 text-gray-700">{item}</p>
                  </div>
                ))}
              </div>
              <div className="mt-6 rounded-2xl border border-sky-100 bg-sky-50 p-4 text-sm text-sky-900">
                We show the problem first, then review whether a managed 3-month pilot makes sense for your market.
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="border-y bg-white px-4 py-16">
        <div className="container mx-auto max-w-5xl">
          <div className="text-center">
            <h2 className="text-3xl font-bold text-slate-950 sm:text-4xl">
              Most local businesses lose calls because of simple Google Maps issues
            </h2>
            <p className="mx-auto mt-4 max-w-2xl text-base leading-7 text-gray-600">
              Owners usually do not need another dashboard. They need someone to spot what is broken and keep the weekly local SEO work moving.
            </p>
          </div>

          <div className="mt-10 grid gap-4 md:grid-cols-2">
            {problemPoints.map((item) => (
              <div
                key={item}
                className="rounded-2xl border border-slate-200 bg-slate-50 px-5 py-4 text-sm font-medium text-slate-800"
              >
                {item}
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="what-we-fix" className="px-4 py-16 sm:py-20">
        <div className="container mx-auto max-w-6xl">
          <div className="max-w-3xl">
            <h2 className="text-3xl font-bold text-slate-950 sm:text-4xl">
              What We Fix For You
            </h2>
            <p className="mt-4 text-base leading-7 text-gray-600">
              We present the work as deliverables, not software features, because the point is to improve calls and customer trust, not to make you learn SEO.
            </p>
          </div>

          <div className="mt-10 grid gap-5 lg:grid-cols-2 xl:grid-cols-3">
            {serviceItems.map((item) => (
              <div
                key={item.title}
                className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm"
              >
                <div className="mb-5 flex h-12 w-12 items-center justify-center rounded-2xl bg-sky-100 text-sky-700">
                  <item.icon className="h-6 w-6" />
                </div>
                <h3 className="text-xl font-semibold text-slate-950">{item.title}</h3>
                <p className="mt-3 text-sm leading-7 text-gray-600">{item.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="bg-slate-50 px-4 py-16 sm:py-20">
        <div className="container mx-auto max-w-5xl">
          <div className="text-center">
            <h2 className="text-3xl font-bold text-slate-950 sm:text-4xl">
              A Simple Sales Flow That Leads to Monthly Retention
            </h2>
          </div>

          <div className="mt-10 grid gap-6 md:grid-cols-3">
            {processSteps.map((step, index) => (
              <div key={step.title} className="rounded-3xl border border-slate-200 bg-white p-6">
                <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-sky-600 text-xl font-bold text-white">
                  {index + 1}
                </div>
                <h3 className="text-xl font-semibold text-slate-950">{step.title}</h3>
                <p className="mt-3 text-sm leading-7 text-gray-600">{step.description}</p>
              </div>
            ))}
          </div>

          <div className="mt-8 rounded-3xl border border-emerald-200 bg-emerald-50 p-6">
            <div className="flex items-start gap-3">
              <ShieldCheck className="mt-0.5 h-5 w-5 flex-shrink-0 text-emerald-600" />
              <p className="text-sm leading-7 text-emerald-900">
                You keep ownership of your Google Business Profile. We only need manager access, not your password.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="px-4 py-16 sm:py-20">
        <div className="container mx-auto max-w-6xl">
          <div className="text-center">
            <h2 className="text-3xl font-bold text-slate-950 sm:text-4xl">
              Managed Packages
            </h2>
            <p className="mx-auto mt-4 max-w-2xl text-base leading-7 text-gray-600">
              We would rather show a realistic starting price than hide everything behind a generic demo request.
            </p>
          </div>

          <div className="mt-10 grid gap-5 lg:grid-cols-3">
            {packageTeasers.map((plan) => (
              <div key={plan.title} className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
                <div className="text-sm font-semibold uppercase tracking-[0.18em] text-sky-700">
                  {plan.title}
                </div>
                <div className="mt-4 text-4xl font-bold text-slate-950">{plan.price}</div>
                <div className="mt-1 text-sm text-gray-500">{plan.note}</div>
                <p className="mt-4 text-sm leading-7 text-gray-600">{plan.description}</p>
              </div>
            ))}
          </div>

          <div className="mt-8 text-center">
            <Link href="/pricing">
              <Button size="lg" variant="outline" className="h-12 px-8">
                Compare Managed Packages
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </Link>
          </div>
        </div>
      </section>

      <section className="bg-gradient-to-br from-sky-600 to-cyan-600 px-4 py-16 sm:py-20">
        <div className="container mx-auto max-w-3xl text-center text-white">
          <h2 className="text-3xl font-bold sm:text-4xl">
            Show Me What&apos;s Costing Calls
          </h2>
          <p className="mt-4 text-base leading-8 text-sky-100 sm:text-lg">
            Start with a free Google Maps audit. If the gaps are real, we&apos;ll review the fix plan and outline whether a managed 3-month pilot is the right next step.
          </p>
          <div className="mt-8 flex flex-col justify-center gap-3 sm:flex-row">
            <Link href="/onboarding">
              <Button size="lg" className="h-14 bg-white px-8 text-lg text-sky-700 hover:bg-slate-100">
                Get My Free Maps Audit
              </Button>
            </Link>
            <Link href="/contact">
              <Button
                size="lg"
                variant="outline"
                className="h-14 border-white/40 px-8 text-lg text-white hover:bg-white/10"
              >
                Book an Audit Review
              </Button>
            </Link>
          </div>
        </div>
      </section>

      <footer className="bg-slate-950 px-4 py-10 text-gray-400">
        <div className="container mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 md:flex-row">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-sky-500 to-cyan-500">
              <MapPin className="h-5 w-5 text-white" />
            </div>
            <span className="font-bold text-white">Local SEO Optimizer</span>
          </div>
          <div className="flex gap-5 text-sm">
            <Link href="/pricing" className="hover:text-white">
              Pricing
            </Link>
            <Link href="/contact" className="hover:text-white">
              Contact
            </Link>
            <Link href="/privacy" className="hover:text-white">
              Privacy
            </Link>
            <Link href="/terms" className="hover:text-white">
              Terms
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
