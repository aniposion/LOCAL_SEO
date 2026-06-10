'use client';

import { useCallback, useEffect, useState } from 'react';
import {
  AlertCircle,
  ArrowRight,
  Camera,
  CheckCircle,
  Copy,
  ExternalLink,
  ImagePlus,
  Loader2,
  MapPin,
  Pin,
  Trash2,
} from 'lucide-react';
import { toast } from 'sonner';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { boardApi, extractCollectionPayload, locationsApi, uploadsApi } from '@/lib/api';
import { getApiErrorMessage } from '@/lib/api-errors';

interface BoardLocation {
  id: string;
  name: string;
}

interface BoardPost {
  id: string;
  title: string;
  body: string;
  location_id?: string | null;
  location_name?: string | null;
  image_asset_id?: string | null;
  image_url?: string | null;
  status: 'draft' | 'published' | 'archived';
  is_pinned: boolean;
  created_at: string;
  updated_at: string;
}

interface UploadedImage {
  id: string;
  url: string;
  original_filename: string;
}

const emptyForm = {
  title: '',
  body: '',
  locationId: 'all',
  status: 'published' as 'draft' | 'published',
  isPinned: false,
};

export default function WebsiteBoardPage() {
  const [locations, setLocations] = useState<BoardLocation[]>([]);
  const [posts, setPosts] = useState<BoardPost[]>([]);
  const [statusFilter, setStatusFilter] = useState<'all' | 'draft' | 'published' | 'archived'>('published');
  const [form, setForm] = useState(emptyForm);
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreviewUrl, setImagePreviewUrl] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setIsLoading(true);
    try {
      const [locationResponse, postsResponse] = await Promise.all([
        locationsApi.list(),
        boardApi.list({ status: statusFilter, limit: 60 }),
      ]);
      setLocations(extractCollectionPayload<BoardLocation>(locationResponse.data, 'locations'));
      setPosts(postsResponse.data?.posts || []);
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Could not load the website board'));
    } finally {
      setIsLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  useEffect(() => {
    if (!imageFile) {
      setImagePreviewUrl(null);
      return;
    }

    const objectUrl = URL.createObjectURL(imageFile);
    setImagePreviewUrl(objectUrl);
    return () => URL.revokeObjectURL(objectUrl);
  }, [imageFile]);

  const activePosts = posts.filter((post) => post.status !== 'archived');
  const pinnedCount = posts.filter((post) => post.is_pinned && post.status === 'published').length;
  const previewLocationId = form.locationId !== 'all' ? form.locationId : locations[0]?.id;
  const previewBoardUrl = previewLocationId ? boardApi.publicUrl(previewLocationId) : null;
  const nextAction =
    activePosts.length === 0
      ? 'Publish your first website update'
      : pinnedCount === 0
        ? 'Pin the most important public update'
        : 'Keep the board fresh with one useful update';

  const handleSubmit = async () => {
    if (!form.title.trim() || !form.body.trim()) {
      toast.error('Add a title and body before publishing.');
      return;
    }

    setIsSaving(true);
    try {
      let uploadedImage: UploadedImage | null = null;
      if (imageFile) {
        const uploadResponse = await uploadsApi.uploadImage(imageFile);
        uploadedImage = uploadResponse.data;
      }

      await boardApi.create({
        title: form.title.trim(),
        body: form.body.trim(),
        location_id: form.locationId === 'all' ? null : form.locationId,
        image_asset_id: uploadedImage?.id || null,
        status: form.status,
        is_pinned: form.isPinned,
      });

      toast.success(form.status === 'published' ? 'Board update published' : 'Board draft saved');
      setForm(emptyForm);
      setImageFile(null);
      await loadData();
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Could not save the board update'));
    } finally {
      setIsSaving(false);
    }
  };

  const handleTogglePinned = async (post: BoardPost) => {
    try {
      await boardApi.update(post.id, { is_pinned: !post.is_pinned });
      await loadData();
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Could not update pinned state'));
    }
  };

  const handleArchive = async (post: BoardPost) => {
    try {
      await boardApi.update(post.id, { status: post.status === 'archived' ? 'published' : 'archived' });
      await loadData();
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Could not update board post status'));
    }
  };

  const handleDelete = async (postId: string) => {
    setDeletingId(postId);
    try {
      await boardApi.delete(postId);
      await loadData();
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Could not delete the board post'));
    } finally {
      setDeletingId(null);
    }
  };

  const handleCopyPublicLink = async () => {
    if (!previewBoardUrl) {
      toast.error('Add a location before sharing the public board.');
      return;
    }

    try {
      await navigator.clipboard.writeText(previewBoardUrl);
      toast.success('Public board link copied');
    } catch {
      toast.error('Could not copy the public board link');
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-center">
        <div>
          <h1 className="text-2xl font-bold">Website Board</h1>
          <p className="text-gray-500">Publish simple website updates with optional photos.</p>
        </div>
        <div className="flex flex-col gap-2 sm:flex-row">
          <Button onClick={handleSubmit} disabled={isSaving}>
            {isSaving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <ArrowRight className="mr-2 h-4 w-4" />}
            {form.status === 'published' ? 'Publish update' : 'Save draft'}
          </Button>
          {previewBoardUrl ? (
            <>
              <Button variant="outline" onClick={() => void handleCopyPublicLink()}>
                <Copy className="mr-2 h-4 w-4" />
                Copy Public Link
              </Button>
              <Button asChild variant="outline">
                <a href={previewBoardUrl} target="_blank" rel="noreferrer">
                  <ExternalLink className="mr-2 h-4 w-4" />
                  Preview Public Board
                </a>
              </Button>
            </>
          ) : null}
        </div>
      </div>

      <Card className="border-slate-200 bg-gradient-to-br from-slate-950 via-slate-900 to-emerald-950 text-white">
        <CardContent className="grid gap-5 p-6 lg:grid-cols-[minmax(0,1.3fr)_minmax(300px,0.7fr)]">
          <div>
            <Badge className="mb-3 bg-white/10 text-white hover:bg-white/10">Next Best Action</Badge>
            <h2 className="text-2xl font-semibold">{nextAction}</h2>
            <p className="mt-2 text-sm leading-6 text-slate-200">
              Use the board for customer-facing updates: offers, events, before-and-after photos, announcements, or
              social proof that should also live on the website.
            </p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/10 p-4 text-sm">
            <div className="font-semibold">What improves</div>
            <p className="mt-2 text-slate-200">
              Visitors see that the business is active, current, and trustworthy before they call, book, or visit.
            </p>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-6 xl:grid-cols-[minmax(360px,0.9fr)_minmax(0,1.1fr)]">
        <Card>
          <CardHeader>
            <CardTitle>Create one public update</CardTitle>
            <CardDescription>Keep it short, useful, and visual when possible.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="board-title">Title</Label>
              <Input
                id="board-title"
                value={form.title}
                onChange={(event) => setForm((current) => ({ ...current, title: event.target.value }))}
                placeholder="Spring service slots are open"
                maxLength={160}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="board-body">Body</Label>
              <Textarea
                id="board-body"
                value={form.body}
                onChange={(event) => setForm((current) => ({ ...current, body: event.target.value }))}
                placeholder="Write the update customers should see on the website."
                rows={6}
              />
            </div>

            <div className="grid gap-3 md:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="board-location">Location</Label>
                <select
                  id="board-location"
                  className="h-10 w-full rounded-md border bg-white px-3 text-sm"
                  value={form.locationId}
                  onChange={(event) => setForm((current) => ({ ...current, locationId: event.target.value }))}
                >
                  <option value="all">All locations</option>
                  {locations.map((location) => (
                    <option key={location.id} value={location.id}>
                      {location.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="board-status">Status</Label>
                <select
                  id="board-status"
                  className="h-10 w-full rounded-md border bg-white px-3 text-sm"
                  value={form.status}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, status: event.target.value as 'draft' | 'published' }))
                  }
                >
                  <option value="published">Publish now</option>
                  <option value="draft">Save as draft</option>
                </select>
              </div>
            </div>

            <label className="flex cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed bg-slate-50 px-4 py-6 text-center hover:bg-slate-100">
              <ImagePlus className="mb-2 h-6 w-6 text-slate-500" />
              <span className="text-sm font-medium text-slate-900">Add a photo</span>
              <span className="mt-1 text-xs text-slate-500">PNG, JPG, or WebP. One clear image works best.</span>
              <input
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(event) => setImageFile(event.target.files?.[0] || null)}
              />
            </label>

            {imagePreviewUrl ? (
              <div className="overflow-hidden rounded-xl border">
                <div
                  aria-label="Selected board upload preview"
                  className="h-48 w-full bg-cover bg-center"
                  style={{ backgroundImage: `url(${imagePreviewUrl})` }}
                />
              </div>
            ) : null}

            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.isPinned}
                onChange={(event) => setForm((current) => ({ ...current, isPinned: event.target.checked }))}
              />
              Pin this update at the top
            </label>

            <Button className="w-full" onClick={handleSubmit} disabled={isSaving}>
              {isSaving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Camera className="mr-2 h-4 w-4" />}
              {form.status === 'published' ? 'Publish board update' : 'Save board draft'}
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex flex-col justify-between gap-3 md:flex-row md:items-center">
              <div>
                <CardTitle>Board updates</CardTitle>
                <CardDescription>Review what customers would see on the website board.</CardDescription>
              </div>
              <select
                className="h-10 rounded-md border bg-white px-3 text-sm"
                value={statusFilter}
                onChange={(event) => setStatusFilter(event.target.value as 'all' | 'draft' | 'published' | 'archived')}
              >
                <option value="published">Published</option>
                <option value="draft">Drafts</option>
                <option value="archived">Archived</option>
                <option value="all">All statuses</option>
              </select>
            </div>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="flex items-center justify-center rounded-xl border border-dashed py-16 text-sm text-gray-500">
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Loading board updates...
              </div>
            ) : posts.length === 0 ? (
              <div className="rounded-xl border border-dashed p-8 text-center">
                <AlertCircle className="mx-auto mb-3 h-8 w-8 text-slate-300" />
                <p className="font-medium text-slate-900">No board updates yet</p>
                <p className="mt-1 text-sm text-slate-500">Create one useful update with a photo to make the website feel alive.</p>
              </div>
            ) : (
              <div className="grid gap-4 lg:grid-cols-2">
                {posts.map((post) => (
                  <article key={post.id} className="overflow-hidden rounded-2xl border bg-white shadow-sm">
                    {post.image_url ? (
                      <div
                        className="h-40 w-full bg-cover bg-center"
                        style={{ backgroundImage: `url(${post.image_url})` }}
                      />
                    ) : (
                      <div className="flex h-28 items-center justify-center bg-slate-100 text-slate-400">
                        <ImagePlus className="h-7 w-7" />
                      </div>
                    )}
                    <div className="space-y-3 p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <h3 className="font-semibold text-slate-950">{post.title}</h3>
                          <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                            {post.location_name ? (
                              <span className="inline-flex items-center gap-1">
                                <MapPin className="h-3 w-3" />
                                {post.location_name}
                              </span>
                            ) : (
                              <span>All locations</span>
                            )}
                            <span>{new Date(post.created_at).toLocaleDateString()}</span>
                          </div>
                        </div>
                        {post.is_pinned ? (
                          <Badge className="bg-amber-100 text-amber-700 hover:bg-amber-100">Pinned</Badge>
                        ) : (
                          <Badge variant="secondary" className="capitalize">{post.status}</Badge>
                        )}
                      </div>
                      <p className="line-clamp-4 text-sm leading-6 text-slate-600">{post.body}</p>
                      <div className="flex flex-wrap gap-2">
                        <Button variant="outline" size="sm" onClick={() => void handleTogglePinned(post)}>
                          <Pin className="mr-2 h-3.5 w-3.5" />
                          {post.is_pinned ? 'Unpin' : 'Pin'}
                        </Button>
                        <Button variant="outline" size="sm" onClick={() => void handleArchive(post)}>
                          {post.status === 'archived' ? 'Restore' : 'Archive'}
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-rose-600 hover:text-rose-700"
                          onClick={() => void handleDelete(post.id)}
                          disabled={deletingId === post.id}
                        >
                          {deletingId === post.id ? (
                            <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <Trash2 className="mr-2 h-3.5 w-3.5" />
                          )}
                          Delete
                        </Button>
                      </div>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <Card className="border-emerald-200 bg-emerald-50">
        <CardContent className="flex items-start gap-3 pt-6">
          <CheckCircle className="mt-0.5 h-5 w-5 text-emerald-700" />
          <div className="text-sm text-emerald-900">
            Keep the board customer-facing. If an update is not useful to a visitor, save it as a draft or archive it.
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
