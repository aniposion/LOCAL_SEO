'use client';
/* eslint-disable @next/next/no-img-element */

import Link from 'next/link';
import {
  ArrowRight,
  BarChart3,
  CheckCircle,
  MapPin,
  MessageSquare,
  Phone,
  Search,
  ShieldCheck,
  Star,
  Wrench,
} from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';

const pillars = [
  {
    icon: Wrench,
    title: 'Google Business Profile cleanup',
    description:
      'Fix categories, services, hours, descriptions, and profile details so customers see a business that looks current and trustworthy.',
    image:
      'https://images.unsplash.com/photo-1556740749-887f6717d7e4?w=900&h=600&fit=crop',
    bullets: [
      'Category and service alignment',
      'Business info cleanup',
      'Profile freshness checks',
      'Photo and posting baseline',
    ],
  },
  {
    icon: Star,
    title: 'Compliant review system',
    description:
      'Ask real customers for honest feedback by SMS, email, and QR code without fake incentives, review gating, or risky shortcuts.',
    image:
      'https://images.unsplash.com/photo-1556742049-0cfed4f6a45d?w=900&h=600&fit=crop',
    bullets: [
      'Review request templates',
      'Review link and QR setup',
      'Review reply drafts',
      'Negative feedback visibility',
    ],
  },
  {
    icon: Search,
    title: 'Competitor and visibility gap tracking',
    description:
      'See where nearby competitors are stronger so the next month of work is based on real local gaps instead of generic SEO theory.',
    image:
      'https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=900&h=600&fit=crop',
    bullets: [
      'Local competitor snapshots',
      'Review gap analysis',
      'Visibility movement tracking',
      'Priority fix planning',
    ],
  },
  {
    icon: MessageSquare,
    title: 'Content and follow-up support',
    description:
      'Keep Google posts, review replies, and missed-call follow-up moving even when the owner or office manager is busy.',
    image:
      'https://images.unsplash.com/photo-1516321318423-f06f85e504b3?w=900&h=600&fit=crop',
    bullets: [
      'Google post drafting',
      'Approval-friendly copy',
      'Missed-call text-back support',
      'Inbox and exception visibility',
    ],
  },
  {
    icon: BarChart3,
    title: 'Monthly reporting that makes sense to owners',
    description:
      'Show what changed, what work was completed, what needs attention, and whether calls, clicks, directions, or reviews are moving.',
    image:
      'https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=900&h=600&fit=crop',
    bullets: [
      'Calls, clicks, directions, reviews',
      'Completed-this-month summaries',
      'Next-month plan',
      'Operator and client handoff clarity',
    ],
  },
];

const supportPoints = [
  {
    icon: Phone,
    title: 'You do not need to learn SEO',
    description:
      'The product is meant to support a done-for-you service, not force a business owner to decode technical recommendations alone.',
  },
  {
    icon: ShieldCheck,
    title: 'No fake reviews or ranking guarantees',
    description:
      'The positioning stays honest: real customer feedback, practical profile work, and visibility improvement tracking.',
  },
  {
    icon: MapPin,
    title: 'Built around Google Maps calls',
    description:
      'The workflow is organized around discovery, trust, follow-up, and reporting instead of vanity metrics.',
  },
];

export default function FeaturesPage() {
  return (
    <div className="min-h-screen bg-white">
      <header className="sticky top-0 z-50 border-b bg-white/90 backdrop-blur-md">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-4">
          <Link href="/" className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-sky-500 to-cyan-500">
              <MapPin className="h-5 w-5 text-white" />
            </div>
            <span className="text-xl font-bold">Local SEO Optimizer</span>
          </Link>
          <div className="flex items-center gap-4">
            <Link href="/pricing" className="hidden text-sm text-gray-600 hover:text-gray-900 sm:block">
              Pricing
            </Link>
            <Link href="/onboarding">
              <Button className="bg-gradient-to-r from-sky-500 to-cyan-500 hover:from-sky-600 hover:to-cyan-600">
                Get My Free Audit
              </Button>
            </Link>
          </div>
        </div>
      </header>

      <section className="bg-gradient-to-br from-sky-50 via-white to-cyan-50 px-4 py-20">
        <div className="mx-auto max-w-6xl text-center">
          <Badge className="mb-4 bg-sky-100 text-sky-700 hover:bg-sky-100">
            Managed Google Maps growth
          </Badge>
          <h1 className="text-4xl font-bold tracking-tight text-slate-950 sm:text-5xl md:text-6xl">
            What We Actually Do Each Month
          </h1>
          <p className="mx-auto mt-6 max-w-3xl text-lg leading-8 text-gray-600">
            These are not just software features. They are the monthly Google Maps,
            review, local page, and reporting workflows that help a local service
            business earn more trust and more calls.
          </p>
          <div className="mt-8 flex flex-col justify-center gap-3 sm:flex-row">
            <Link href="/onboarding">
              <Button
                size="lg"
                className="h-14 bg-gradient-to-r from-sky-500 to-cyan-500 px-8 text-lg hover:from-sky-600 hover:to-cyan-600"
              >
                Get My Free Maps Audit
                <ArrowRight className="ml-2 h-5 w-5" />
              </Button>
            </Link>
            <Link href="/pricing">
              <Button size="lg" variant="outline" className="h-14 px-8 text-lg">
                See Managed Pricing
              </Button>
            </Link>
          </div>
        </div>
      </section>

      <section className="px-4 py-16 sm:py-20">
        <div className="mx-auto max-w-7xl space-y-20">
          {pillars.map((pillar, index) => (
            <div
              key={pillar.title}
              className={`grid items-center gap-10 lg:grid-cols-2 ${index % 2 === 1 ? 'lg:[&>*:first-child]:order-2 lg:[&>*:last-child]:order-1' : ''}`}
            >
              <div>
                <div className="mb-5 flex h-12 w-12 items-center justify-center rounded-2xl bg-sky-100 text-sky-700">
                  <pillar.icon className="h-6 w-6" />
                </div>
                <h2 className="text-3xl font-bold text-slate-950">{pillar.title}</h2>
                <p className="mt-4 text-base leading-8 text-gray-600">
                  {pillar.description}
                </p>
                <ul className="mt-6 space-y-3">
                  {pillar.bullets.map((bullet) => (
                    <li key={bullet} className="flex items-start gap-3 text-sm text-gray-700">
                      <CheckCircle className="mt-0.5 h-5 w-5 flex-shrink-0 text-green-500" />
                      <span>{bullet}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <Card className="overflow-hidden border-0 shadow-xl">
                <CardContent className="p-0">
                  <img
                    src={pillar.image}
                    alt={pillar.title}
                    className="aspect-[4/3] w-full object-cover"
                  />
                </CardContent>
              </Card>
            </div>
          ))}
        </div>
      </section>

      <section className="bg-slate-50 px-4 py-16 sm:py-20">
        <div className="mx-auto max-w-6xl">
          <div className="text-center">
            <h2 className="text-3xl font-bold text-slate-950 sm:text-4xl">
              Why this is positioned as a service, not just a tool
            </h2>
          </div>

          <div className="mt-10 grid gap-6 md:grid-cols-3">
            {supportPoints.map((point) => (
              <Card key={point.title} className="border-0 shadow-sm">
                <CardContent className="p-6">
                  <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-2xl bg-sky-100 text-sky-700">
                    <point.icon className="h-5 w-5" />
                  </div>
                  <h3 className="text-lg font-semibold text-slate-950">{point.title}</h3>
                  <p className="mt-3 text-sm leading-7 text-gray-600">
                    {point.description}
                  </p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      <section className="bg-gradient-to-br from-sky-600 to-cyan-600 px-4 py-16 sm:py-20">
        <div className="mx-auto max-w-4xl text-center text-white">
          <h2 className="text-3xl font-bold sm:text-4xl">
            Want to see what this looks like for your market?
          </h2>
          <p className="mt-4 text-lg leading-8 text-sky-100">
            Start with the free audit. If there is real opportunity, we&apos;ll show
            what would be fixed first and whether a managed pilot makes sense.
          </p>
          <div className="mt-8 flex flex-col justify-center gap-3 sm:flex-row">
            <Link href="/onboarding">
              <Button size="lg" className="h-14 bg-white px-8 text-lg text-sky-700 hover:bg-slate-100">
                Get My Free Maps Audit
              </Button>
            </Link>
            <Link href="/contact?subject=What%20would%20you%20fix%20for%20my%20business%3F">
              <Button
                size="lg"
                variant="outline"
                className="h-14 border-white/40 px-8 text-lg text-white hover:bg-white/10"
              >
                Ask What We Would Fix
              </Button>
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
