'use client';
/* eslint-disable @next/next/no-img-element */

import { useState } from 'react';
import Link from 'next/link';
import {
  ArrowLeft,
  CheckCircle,
  ClipboardList,
  MapPin,
  MessageSquare,
  Phone,
  Search,
} from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';

const walkthroughSections = [
  {
    id: 'audit',
    title: 'Free audit snapshot',
    caption: 'What we show before asking for a call',
    description:
      'The audit highlights the top issues that may be costing calls, not a fake Google score or a giant technical checklist.',
    details: [
      'Local visibility readiness score',
      'Top 3 issues affecting calls or trust',
      'Review gap against nearby competitors',
      'Simple estimate of missed call opportunity',
    ],
    image:
      'https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=1200&h=675&fit=crop',
    icon: Search,
  },
  {
    id: 'review-call',
    title: 'Audit review call',
    caption: 'What the short review call is meant to do',
    description:
      'Instead of pushing a generic SaaS demo, the review call explains what we would fix first and whether a 3-month pilot is worth it.',
    details: [
      'Review the real issues in plain English',
      'Explain the first 30-day fix plan',
      'Check whether the market is worth pursuing',
      'Recommend the smallest package that fits',
    ],
    image:
      'https://images.unsplash.com/photo-1516321318423-f06f85e504b3?w=1200&h=675&fit=crop',
    icon: MessageSquare,
  },
  {
    id: 'monthly-work',
    title: 'Monthly work and reporting',
    caption: 'What ongoing clients actually receive',
    description:
      'The retained service is about profile work, review systems, local page progress, and a report that owners can understand quickly.',
    details: [
      'Google Business Profile cleanup and updates',
      'Review request system and reply drafts',
      'Calls, clicks, directions, and review reporting',
      'Completed-this-month and next-month plan',
    ],
    image:
      'https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=1200&h=675&fit=crop',
    icon: ClipboardList,
  },
];

const trustPoints = [
  'No fake reviews or review gating',
  'No ranking guarantees',
  'You keep ownership of your Google Business Profile',
  'The point is more calls and clearer monthly work, not more dashboard busywork',
];

export default function DemoPage() {
  const [activeSection, setActiveSection] = useState(walkthroughSections[0]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-sky-950 to-slate-950">
      <div className="border-b border-white/10">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-4">
          <Link
            href="/"
            className="inline-flex items-center text-sm text-gray-400 transition-colors hover:text-white"
          >
            <ArrowLeft className="mr-1 h-4 w-4" />
            Back to Home
          </Link>
          <Link href="/onboarding">
            <Button className="bg-gradient-to-r from-sky-500 to-cyan-500 hover:from-sky-600 hover:to-cyan-600">
              Get My Free Audit
            </Button>
          </Link>
        </div>
      </div>

      <div className="mx-auto max-w-7xl px-4 py-12">
        <div className="text-center">
          <h1 className="text-4xl font-bold text-white md:text-5xl">
            What the Sales and Delivery Flow Actually Looks Like
          </h1>
          <p className="mx-auto mt-4 max-w-3xl text-xl text-gray-300">
            This is not a fake video player. It is a guided walkthrough of the
            free audit, the review call, and the monthly work a managed client
            would actually see.
          </p>
        </div>

        <div className="mt-12 grid gap-6 lg:grid-cols-[0.34fr_0.66fr]">
          <div className="space-y-4">
            {walkthroughSections.map((section) => (
              <button
                key={section.id}
                onClick={() => setActiveSection(section)}
                className={`w-full rounded-2xl border p-5 text-left transition-all ${
                  activeSection.id === section.id
                    ? 'border-sky-400 bg-sky-500/10'
                    : 'border-white/10 bg-white/5 hover:border-white/20 hover:bg-white/10'
                }`}
              >
                <div className="flex items-start gap-3">
                  <div className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-2xl bg-white/10 text-sky-300">
                    <section.icon className="h-5 w-5" />
                  </div>
                  <div>
                    <div className="text-lg font-semibold text-white">{section.title}</div>
                    <div className="mt-1 text-sm text-gray-400">{section.caption}</div>
                  </div>
                </div>
              </button>
            ))}

            <Card className="border-white/10 bg-white/5">
              <CardContent className="p-6">
                <div className="flex items-center gap-2 text-white">
                  <Phone className="h-5 w-5 text-sky-300" />
                  <h3 className="font-semibold">Why this matters</h3>
                </div>
                <p className="mt-3 text-sm leading-7 text-gray-300">
                  Local owners do not usually want another SEO tool to learn.
                  They want a clear explanation of what is broken, what gets
                  fixed, and whether that work is likely to turn into more calls.
                </p>
              </CardContent>
            </Card>
          </div>

          <Card className="overflow-hidden border-white/10 bg-white/5 backdrop-blur-sm">
            <div className="relative aspect-video">
              <img
                src={activeSection.image}
                alt={activeSection.title}
                className="h-full w-full object-cover"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/20 to-transparent" />
              <div className="absolute bottom-0 left-0 right-0 p-6">
                <div className="text-sm font-medium uppercase tracking-[0.18em] text-sky-300">
                  {activeSection.caption}
                </div>
                <h2 className="mt-2 text-3xl font-bold text-white">
                  {activeSection.title}
                </h2>
                <p className="mt-3 max-w-3xl text-sm leading-7 text-gray-200">
                  {activeSection.description}
                </p>
              </div>
            </div>

            <CardContent className="grid gap-8 p-6 md:grid-cols-[0.58fr_0.42fr]">
              <div>
                <h3 className="text-lg font-semibold text-white">
                  What this stage includes
                </h3>
                <ul className="mt-4 space-y-3">
                  {activeSection.details.map((item) => (
                    <li key={item} className="flex items-start gap-3 text-sm text-gray-300">
                      <CheckCircle className="mt-0.5 h-5 w-5 flex-shrink-0 text-green-400" />
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </div>

              <div className="rounded-2xl border border-white/10 bg-black/20 p-5">
                <div className="flex items-center gap-2 text-white">
                  <MapPin className="h-5 w-5 text-sky-300" />
                  <h3 className="font-semibold">Trust checks</h3>
                </div>
                <ul className="mt-4 space-y-3">
                  {trustPoints.map((point) => (
                    <li key={point} className="flex items-start gap-3 text-sm text-gray-300">
                      <CheckCircle className="mt-0.5 h-4 w-4 flex-shrink-0 text-green-400" />
                      <span>{point}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      <div className="border-t border-white/10 bg-black/30">
        <div className="mx-auto max-w-4xl px-4 py-16 text-center">
          <h2 className="text-3xl font-bold text-white">
            Want to walk through your market instead?
          </h2>
          <p className="mx-auto mt-4 max-w-2xl text-gray-300">
            Start with the free audit and we&apos;ll use your own business, city,
            and competitor context instead of a generic product tour.
          </p>
          <div className="mt-8 flex flex-col justify-center gap-4 sm:flex-row">
            <Link href="/onboarding">
              <Button
                size="lg"
                className="h-14 bg-gradient-to-r from-sky-500 to-cyan-500 px-8 text-lg hover:from-sky-600 hover:to-cyan-600"
              >
                Get My Free Maps Audit
              </Button>
            </Link>
            <Link href="/contact?subject=Walk%20me%20through%20my%20Google%20Maps%20audit">
              <Button
                size="lg"
                variant="outline"
                className="h-14 border-sky-300/40 px-8 text-lg text-sky-200 hover:bg-sky-500/10 hover:text-white"
              >
                Book an Audit Review
              </Button>
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
