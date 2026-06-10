'use client';

import Link from 'next/link';
import { ArrowRight, CheckCircle, MapPin, ShieldCheck } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

const packages = [
  {
    name: 'Maps Starter',
    price: '$699/month',
    setup: '$499 setup',
    target: 'Smaller home service and local businesses in lower-competition markets',
    features: [
      'Google Business Profile cleanup',
      'Category and service optimization',
      'Business description rewrite',
      'Review request link and QR code',
      '4 Google Business Profile posts per month',
      '4 photo uploads per month',
      'Basic competitor check',
      'Simple monthly report',
    ],
  },
  {
    name: 'Calls Growth',
    price: '$999/month',
    setup: '$799 setup',
    target: 'Plumbers, HVAC teams, roofers, garage door companies, and similar service businesses',
    features: [
      'Everything in Maps Starter',
      'Local rank grid tracking',
      'Review request SMS and email templates',
      'Review reply drafts',
      '2 local landing pages per month',
      'Citation cleanup priority list',
      'Competitor review gap report',
      'Monthly strategy call',
    ],
    popular: true,
  },
  {
    name: 'Competitive Market',
    price: 'From $1,499/month',
    setup: '$1,500 setup',
    target: 'High-competition cities, higher-ticket services, or multi-location operators',
    features: [
      'Everything in Calls Growth',
      'More local landing pages',
      'Advanced competitor tracking',
      'Citation cleanup support',
      'Google Business Profile post scheduling',
      'Call tracking setup support',
      'Priority support',
      'Multi-location reporting',
    ],
  },
];

const faqs = [
  {
    question: 'Can you guarantee a #1 Google Maps ranking?',
    answer:
      'No. Nobody can honestly guarantee a #1 Google Maps ranking. We focus on profile quality, review systems, local pages, and monthly visibility tracking.',
  },
  {
    question: 'Do you buy or fake reviews?',
    answer:
      'No. We only help you ask real customers for honest feedback. We do not offer incentives, filter negative reviews, or ask customers to leave specific wording.',
  },
  {
    question: 'Do I need to learn SEO?',
    answer:
      'No. This is a managed service. We handle the profile updates, review request system, local pages, and reporting. You mainly approve key changes and provide business info or photos when needed.',
  },
  {
    question: 'How fast will I see results?',
    answer:
      'The first 30 days usually focus on cleanup, tracking, and the review request process. Visibility gains compound over several months as reviews, photos, pages, and profile activity improve.',
  },
];

export default function PricingPage() {
  return (
    <div className="min-h-screen bg-white">
      <header className="sticky top-0 z-50 border-b bg-white/90 backdrop-blur-md">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-4">
          <Link href="/" className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-sky-500 to-cyan-500">
              <MapPin className="h-5 w-5 text-white" />
            </div>
            <span className="font-bold text-xl">Local SEO Optimizer</span>
          </Link>
          <div className="flex items-center gap-4">
            <Link href="/contact" className="hidden text-sm text-gray-600 hover:text-gray-900 sm:block">
              Contact
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
        <div className="mx-auto max-w-5xl text-center">
          <Badge className="mb-4 bg-sky-100 text-sky-700 hover:bg-sky-100">
            Managed Google Maps growth
          </Badge>
          <h1 className="text-4xl font-bold tracking-tight text-slate-950 sm:text-5xl">
            Pricing Built for Local Service Businesses That Want More Calls
          </h1>
          <p className="mx-auto mt-6 max-w-3xl text-lg leading-8 text-gray-600">
            You run the business. We manage the Google Business Profile work, review system, local page updates, and monthly reporting.
          </p>
          <p className="mt-4 text-sm font-medium uppercase tracking-[0.18em] text-sky-700">
            3-month pilot, then month-to-month
          </p>
        </div>
      </section>

      <section className="-mt-8 px-4 pb-16">
        <div className="mx-auto grid max-w-7xl gap-6 lg:grid-cols-3">
          {packages.map((item) => (
            <Card
              key={item.name}
              className={`border-2 ${item.popular ? 'border-sky-500 shadow-xl' : 'border-slate-200 shadow-sm'}`}
            >
              <CardHeader>
                {item.popular && (
                  <Badge className="mb-3 w-fit bg-sky-500 text-white hover:bg-sky-500">
                    Most common starting point
                  </Badge>
                )}
                <CardTitle className="text-2xl">{item.name}</CardTitle>
                <CardDescription className="text-sm leading-6">
                  {item.target}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="mb-6">
                  <div className="text-4xl font-bold text-slate-950">{item.price}</div>
                  <div className="mt-1 text-sm text-gray-500">{item.setup}</div>
                </div>

                <ul className="space-y-3">
                  {item.features.map((feature) => (
                    <li key={feature} className="flex items-start gap-3 text-sm text-gray-700">
                      <CheckCircle className="mt-0.5 h-5 w-5 flex-shrink-0 text-green-500" />
                      <span>{feature}</span>
                    </li>
                  ))}
                </ul>

                <div className="mt-8">
                  <Link href="/onboarding">
                    <Button
                      className={`w-full ${item.popular ? 'bg-gradient-to-r from-sky-500 to-cyan-500 hover:from-sky-600 hover:to-cyan-600' : ''}`}
                      variant={item.popular ? 'default' : 'outline'}
                    >
                      Start With a Free Audit
                    </Button>
                  </Link>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </section>

      <section className="bg-slate-50 px-4 py-16">
        <div className="mx-auto max-w-5xl">
          <div className="rounded-3xl border border-emerald-200 bg-emerald-50 p-6">
            <div className="flex items-start gap-3">
              <ShieldCheck className="mt-0.5 h-5 w-5 flex-shrink-0 text-emerald-600" />
              <div>
                <h2 className="text-lg font-semibold text-emerald-950">
                  What the first 30 days usually look like
                </h2>
                <p className="mt-2 text-sm leading-7 text-emerald-900">
                  Month one is usually about fixing profile issues, setting up tracking, launching compliant review requests, and establishing a baseline for reporting.
                </p>
              </div>
            </div>
          </div>

          <div className="mt-12 grid gap-6 md:grid-cols-2">
            {faqs.map((faq) => (
              <Card key={faq.question} className="border-0 shadow-sm">
                <CardContent className="p-6">
                  <h3 className="text-lg font-semibold text-slate-950">{faq.question}</h3>
                  <p className="mt-3 text-sm leading-7 text-gray-600">{faq.answer}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      <section className="bg-gradient-to-br from-sky-600 to-cyan-600 px-4 py-16">
        <div className="mx-auto max-w-4xl text-center text-white">
          <h2 className="text-3xl font-bold sm:text-4xl">
            Not sure which package fits?
          </h2>
          <p className="mt-4 text-lg leading-8 text-sky-100">
            Start with the free audit. If the opportunity looks real, we&apos;ll recommend the smallest package that matches the market and workload.
          </p>
          <div className="mt-8 flex flex-col justify-center gap-3 sm:flex-row">
            <Link href="/onboarding">
              <Button size="lg" className="h-14 bg-white px-8 text-lg text-sky-700 hover:bg-slate-100">
                Get My Free Maps Audit
              </Button>
            </Link>
            <Link href="/contact?subject=Managed%20local%20SEO%20pilot%20question">
              <Button
                size="lg"
                variant="outline"
                className="h-14 border-white/40 px-8 text-lg text-white hover:bg-white/10"
              >
                Ask About a Pilot
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
