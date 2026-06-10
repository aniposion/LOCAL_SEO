'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { ArrowLeft, CalendarDays, Loader2, MapPin, Phone, Pin, Sparkles } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { boardApi } from '@/lib/api';

interface PublicBoardLocation {
  id: string;
  name: string;
  address?: string | null;
  city?: string | null;
  state?: string | null;
  phone?: string | null;
  website_url?: string | null;
}

interface PublicBoardPost {
  id: string;
  title: string;
  body: string;
  image_url?: string | null;
  location_name?: string | null;
  is_pinned: boolean;
  created_at: string;
}

interface PublicBoardPayload {
  location: PublicBoardLocation;
  posts: PublicBoardPost[];
}

export default function PublicBoardPage() {
  const params = useParams();
  const locationId = params.locationId as string;
  const [payload, setPayload] = useState<PublicBoardPayload | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadBoard = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const response = await boardApi.getPublic(locationId);
        setPayload(response.data);
      } catch {
        setError('This board is not available right now.');
      } finally {
        setIsLoading(false);
      }
    };

    if (locationId) {
      void loadBoard();
    }
  }, [locationId]);

  if (isLoading) {
    return (
      <main className="min-h-screen bg-stone-50 px-6 py-16">
        <div className="mx-auto flex max-w-3xl items-center justify-center rounded-3xl border bg-white p-12 text-stone-600 shadow-sm">
          <Loader2 className="mr-3 h-5 w-5 animate-spin" />
          Loading local updates...
        </div>
      </main>
    );
  }

  if (error || !payload) {
    return (
      <main className="min-h-screen bg-stone-50 px-6 py-16">
        <Card className="mx-auto max-w-2xl">
          <CardContent className="space-y-4 p-8 text-center">
            <Sparkles className="mx-auto h-8 w-8 text-stone-300" />
            <h1 className="text-2xl font-semibold text-stone-950">Board unavailable</h1>
            <p className="text-stone-600">{error || 'We could not find this location board.'}</p>
            <Button asChild variant="outline">
              <Link href="/">
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back to home
              </Link>
            </Button>
          </CardContent>
        </Card>
      </main>
    );
  }

  const locationLine = [payload.location.address, payload.location.city, payload.location.state]
    .filter(Boolean)
    .join(', ');

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top_left,#fef3c7,transparent_30%),linear-gradient(135deg,#fafaf9,#ecfeff)] px-5 py-10 text-stone-950 sm:px-8">
      <div className="mx-auto max-w-6xl space-y-8">
        <section className="overflow-hidden rounded-[2rem] border border-white/70 bg-white/85 shadow-xl shadow-stone-200/60 backdrop-blur">
          <div className="grid gap-8 p-8 lg:grid-cols-[minmax(0,1.2fr)_minmax(280px,0.8fr)] lg:p-10">
            <div>
              <Badge className="mb-4 bg-emerald-100 text-emerald-800 hover:bg-emerald-100">Local Updates</Badge>
              <h1 className="max-w-3xl text-4xl font-bold tracking-tight text-stone-950 sm:text-5xl">
                What is new at {payload.location.name}
              </h1>
              <p className="mt-4 max-w-2xl text-lg leading-8 text-stone-600">
                Recent announcements, photos, offers, and helpful notes from the team.
              </p>
            </div>
            <div className="rounded-3xl border border-stone-200 bg-stone-50 p-5">
              <div className="text-sm font-semibold uppercase tracking-[0.18em] text-stone-500">Visit info</div>
              {locationLine ? (
                <p className="mt-3 flex gap-2 text-sm leading-6 text-stone-700">
                  <MapPin className="mt-0.5 h-4 w-4 shrink-0 text-emerald-700" />
                  {locationLine}
                </p>
              ) : null}
              {payload.location.phone ? (
                <p className="mt-3 flex gap-2 text-sm text-stone-700">
                  <Phone className="h-4 w-4 shrink-0 text-emerald-700" />
                  <a href={`tel:${payload.location.phone}`} className="font-medium hover:text-emerald-700">
                    {payload.location.phone}
                  </a>
                </p>
              ) : null}
              {payload.location.website_url ? (
                <Button asChild className="mt-5 w-full">
                  <a href={payload.location.website_url} target="_blank" rel="noreferrer">
                    Visit Website
                  </a>
                </Button>
              ) : null}
            </div>
          </div>
        </section>

        {payload.posts.length === 0 ? (
          <Card className="border-dashed bg-white/80">
            <CardContent className="p-10 text-center">
              <Sparkles className="mx-auto h-9 w-9 text-stone-300" />
              <h2 className="mt-4 text-xl font-semibold">No updates have been published yet</h2>
              <p className="mt-2 text-stone-600">Check back soon for photos, announcements, and customer notes.</p>
            </CardContent>
          </Card>
        ) : (
          <section className="grid gap-5 md:grid-cols-2 xl:grid-cols-3">
            {payload.posts.map((post) => (
              <article key={post.id} className="overflow-hidden rounded-3xl border bg-white shadow-sm">
                {post.image_url ? (
                  <div
                    className="h-56 bg-cover bg-center"
                    style={{ backgroundImage: `url(${post.image_url})` }}
                    aria-label="Board update photo"
                  />
                ) : (
                  <div className="flex h-36 items-center justify-center bg-gradient-to-br from-stone-100 to-emerald-50">
                    <Sparkles className="h-8 w-8 text-emerald-300" />
                  </div>
                )}
                <div className="space-y-4 p-5">
                  <div className="flex items-start justify-between gap-3">
                    <h2 className="text-xl font-semibold leading-7">{post.title}</h2>
                    {post.is_pinned ? (
                      <Badge className="bg-amber-100 text-amber-800 hover:bg-amber-100">
                        <Pin className="mr-1 h-3 w-3" />
                        Pinned
                      </Badge>
                    ) : null}
                  </div>
                  <p className="whitespace-pre-line text-sm leading-7 text-stone-600">{post.body}</p>
                  <div className="flex items-center gap-2 border-t pt-4 text-xs text-stone-500">
                    <CalendarDays className="h-3.5 w-3.5" />
                    {new Date(post.created_at).toLocaleDateString()}
                    {post.location_name ? <span>for {post.location_name}</span> : null}
                  </div>
                </div>
              </article>
            ))}
          </section>
        )}
      </div>
    </main>
  );
}
