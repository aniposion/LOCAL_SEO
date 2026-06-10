'use client';

import { Suspense, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import {
  ArrowLeft,
  CheckCircle,
  Clock,
  Loader2,
  Mail,
  MessageSquare,
  Send,
} from 'lucide-react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { contactApi } from '@/lib/api';
import { getApiErrorMessage } from '@/lib/api-errors';

const SALES_EMAIL = 'sales@localseo.app';

function ContactPageInner() {
  const searchParams = useSearchParams();

  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [subject, setSubject] = useState('');
  const [message, setMessage] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSubmitted, setIsSubmitted] = useState(false);

  useEffect(() => {
    const nextSubject = searchParams.get('subject');
    const nextMessage = searchParams.get('message');

    if (nextSubject && !subject) {
      setSubject(nextSubject);
    }

    if (nextMessage && !message) {
      setMessage(nextMessage);
    }
  }, [message, searchParams, subject]);

  const mailtoHref = useMemo(() => {
    const lines = [
      `Name: ${name || 'Not provided'}`,
      `Email: ${email || 'Not provided'}`,
      '',
      message || '',
    ];

    const params = new URLSearchParams({
      subject: subject || 'Local SEO audit review request',
      body: lines.join('\n'),
    });

    return `mailto:${SALES_EMAIL}?${params.toString()}`;
  }, [email, message, name, subject]);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();

    if (!name.trim() || !email.trim() || !message.trim()) {
      toast.error('Please fill in your name, email, and message.');
      return;
    }

    setIsSubmitting(true);

    try {
      await contactApi.createRequest({
        name: name.trim(),
        email: email.trim(),
        subject: subject.trim() || 'Local SEO audit review request',
        message: message.trim(),
        source: 'contact_page',
        metadata: {
          path: typeof window !== 'undefined' ? window.location.pathname : '/contact',
        },
      });
      setIsSubmitted(true);
      toast.success('Your request was received.');
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Could not submit the request. You can still send the email draft below.'));
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isSubmitted) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-sky-50 via-white to-cyan-50 p-4">
        <Card className="w-full max-w-md border-0 shadow-xl">
          <CardContent className="pt-8 text-center">
            <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-green-100">
              <CheckCircle className="h-8 w-8 text-green-600" />
            </div>
            <h2 className="text-xl font-bold">Your request was received</h2>
            <p className="mt-2 text-sm text-gray-600">
              We saved your audit review request. You can also send the same note directly to{' '}
              <a href={`mailto:${SALES_EMAIL}`} className="font-medium text-sky-700 underline">
                {SALES_EMAIL}
              </a>
              .
            </p>
            <div className="mt-6 space-y-3">
              <a href={mailtoHref}>
                <Button className="w-full bg-gradient-to-r from-sky-500 to-cyan-500 hover:from-sky-600 hover:to-cyan-600">
                  Send Email Backup
                </Button>
              </a>
              <Link href="/">
                <Button variant="outline" className="w-full">
                  Back to Home
                </Button>
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-sky-50 via-white to-cyan-50">
      <div className="border-b bg-white/80 backdrop-blur-sm">
        <div className="mx-auto max-w-6xl px-4 py-6">
          <Link
            href="/"
            className="mb-4 inline-flex items-center text-sm text-gray-600 hover:text-gray-900"
          >
            <ArrowLeft className="mr-1 h-4 w-4" />
            Back to Home
          </Link>
          <h1 className="text-3xl font-bold">Book an Audit Review</h1>
          <p className="mt-2 text-gray-600">
            Tell us a little about the business and we&apos;ll open a prefilled email draft for your audit review request.
          </p>
        </div>
      </div>

      <div className="mx-auto grid max-w-6xl gap-8 px-4 py-12 md:grid-cols-3">
        <div className="space-y-6">
          <Card className="border-0 shadow-lg">
            <CardContent className="p-6">
              <div className="flex items-start gap-4">
                <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg bg-sky-100">
                  <Mail className="h-5 w-5 text-sky-600" />
                </div>
                <div>
                  <h3 className="font-semibold">Email</h3>
                  <p className="mt-1 text-sm text-gray-600">{SALES_EMAIL}</p>
                  <p className="text-xs text-gray-500">
                    Best for audit reviews, pricing questions, and pilot requests.
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="border-0 shadow-lg">
            <CardContent className="p-6">
              <div className="flex items-start gap-4">
                <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg bg-sky-100">
                  <Clock className="h-5 w-5 text-sky-600" />
                </div>
                <div>
                  <h3 className="font-semibold">Response window</h3>
                  <p className="mt-1 text-sm text-gray-600">
                    We usually reply within one business day.
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="border-0 shadow-lg">
            <CardContent className="p-6">
              <div className="flex items-start gap-4">
                <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg bg-sky-100">
                  <MessageSquare className="h-5 w-5 text-sky-600" />
                </div>
                <div>
                  <h3 className="font-semibold">What happens next</h3>
                  <p className="mt-1 text-sm text-gray-600">
                    We review the audit, highlight what may be costing calls, and outline whether a 3-month managed pilot makes sense.
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        <div className="md:col-span-2">
          <Card className="border-0 shadow-xl">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <MessageSquare className="h-5 w-5 text-sky-600" />
                Request a Review Call
              </CardTitle>
              <CardDescription>
                This saves your request and gives you an email fallback for anything urgent.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="space-y-6">
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="name">Name *</Label>
                    <Input
                      id="name"
                      placeholder="Your name"
                      value={name}
                      onChange={(event) => setName(event.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="email">Email *</Label>
                    <Input
                      id="email"
                      type="email"
                      placeholder="you@example.com"
                      value={email}
                      onChange={(event) => setEmail(event.target.value)}
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="subject">Subject</Label>
                  <Input
                    id="subject"
                    placeholder="Free audit review for My Business"
                    value={subject}
                    onChange={(event) => setSubject(event.target.value)}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="message">Message *</Label>
                  <textarea
                    id="message"
                    className="h-48 w-full resize-none rounded-lg border p-3 focus:outline-none focus:ring-2 focus:ring-sky-500"
                    placeholder="Tell us what service, city, or audit questions you want to cover."
                    value={message}
                    onChange={(event) => setMessage(event.target.value)}
                  />
                </div>

                <Button
                  type="submit"
                  className="h-12 w-full bg-gradient-to-r from-sky-500 to-cyan-500 hover:from-sky-600 hover:to-cyan-600"
                  disabled={isSubmitting}
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Sending request...
                    </>
                  ) : (
                    <>
                      <Send className="mr-2 h-4 w-4" />
                      Send Request
                    </>
                  )}
                </Button>
              </form>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

export default function ContactPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-sky-50 via-white to-cyan-50">
          <Loader2 className="h-8 w-8 animate-spin text-sky-600" />
        </div>
      }
    >
      <ContactPageInner />
    </Suspense>
  );
}
