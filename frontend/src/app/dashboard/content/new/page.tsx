'use client';
/* eslint-disable @next/next/no-img-element */

import { useEffect, useEffectEvent, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  ArrowLeft,
  Sparkles,
  Image as ImageIcon,
  Send,
  Loader2,
  RefreshCw,
  CheckCircle,
  Calendar,
  MapPin,
  Instagram,
  Globe,
  Upload,
  X,
  Wand2,
} from 'lucide-react';
import { contentApi, extractCollectionPayload, locationsApi, postsApi, uploadsApi } from '@/lib/api';
import { getApiErrorMessage } from '@/lib/api-errors';
import { toast } from 'sonner';
import Link from 'next/link';

type LocationOption = {
  id: string;
  name: string;
  services?: string[];
};

type ContentSuggestion = {
  id: string;
  type: string;
  emoji: string;
  title_ko: string;
  title_en: string;
  priority: number;
};

type UploadedAsset = {
  id: string;
  filename: string;
  original_filename: string;
  file_type: string;
  mime_type: string;
  size_bytes: number;
  url: string;
  thumbnail_url?: string | null;
  width?: number | null;
  height?: number | null;
  created_at?: string | null;
};

export default function NewContentPage() {
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isOneClickCreating, setIsOneClickCreating] = useState(false);

  const [locations, setLocations] = useState<LocationOption[]>([]);
  const [selectedLocation, setSelectedLocation] = useState<string>('');
  const [platform, setPlatform] = useState<'GBP' | 'INSTAGRAM'>('GBP');
  const [contentType, setContentType] = useState<string>('update');
  const [topic, setTopic] = useState<string>('');
  const [suggestions, setSuggestions] = useState<ContentSuggestion[]>([]);
  const [selectedSuggestionId, setSelectedSuggestionId] = useState<string>('');

  const [generatedTitle, setGeneratedTitle] = useState('');
  const [generatedBody, setGeneratedBody] = useState('');
  const [generatedImageUrl, setGeneratedImageUrl] = useState('');
  const [step, setStep] = useState<'setup' | 'preview'>('setup');

  const [isScheduled, setIsScheduled] = useState(false);
  const [scheduledDate, setScheduledDate] = useState('');
  const [scheduledTime, setScheduledTime] = useState('09:00');

  const [uploadMode, setUploadMode] = useState<'ai' | 'manual'>('ai');
  const [manualTitle, setManualTitle] = useState('');
  const [manualBody, setManualBody] = useState('');
  const [uploadedImagePreview, setUploadedImagePreview] = useState('');
  const [uploadedImageUrl, setUploadedImageUrl] = useState('');
  const [selectedImageAssetId, setSelectedImageAssetId] = useState('');
  const [selectedImageMode, setSelectedImageMode] = useState<'uploaded' | 'library' | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadedAssets, setUploadedAssets] = useState<UploadedAsset[]>([]);
  const [isLoadingUploadedAssets, setIsLoadingUploadedAssets] = useState(false);
  const activeLocationId = selectedLocation || locations[0]?.id || '';

  useEffect(() => {
    void fetchLocations();
  }, []);

  useEffect(() => {
    if (activeLocationId) {
      void fetchSuggestions();
    }
  }, [activeLocationId]);

  useEffect(() => {
    if (uploadMode === 'manual') {
      void fetchUploadedAssets();
    }
  }, [uploadMode]);

  const currentLocation = useMemo(
    () => locations.find((loc) => loc.id === activeLocationId),
    [locations, activeLocationId]
  );

  const fetchLocations = async () => {
    try {
      const response = await locationsApi.list();
      const locs = extractCollectionPayload<LocationOption>(response.data, 'locations');
      setLocations(locs);
      setSelectedLocation((current) =>
        current && locs.some((location) => location.id === current)
          ? current
          : (locs[0]?.id ?? '')
      );
    } catch {
      toast.error('Failed to load locations');
      setLocations([]);
    } finally {
      setIsLoading(false);
    }
  };

  const fetchSuggestions = useEffectEvent(async () => {
    try {
      const response = await contentApi.getSuggestions(activeLocationId);
      setSuggestions(response.data.suggestions || []);
    } catch {
      toast.error('Failed to load content suggestions');
      setSuggestions([]);
    }
  });

  const extractUploadedFileId = (url: string) => {
    const filename = url.split('/').pop();
    if (!filename) {
      return null;
    }
    return filename.split('.')[0] || null;
  };

  const clearUploadedImageState = () => {
    setUploadedImagePreview('');
    setUploadedImageUrl('');
    setSelectedImageAssetId('');
    setSelectedImageMode(null);
  };

  const fetchUploadedAssets = async () => {
    setIsLoadingUploadedAssets(true);
    try {
      const response = await uploadsApi.listFiles({ fileType: 'image', limit: 12, offset: 0 });
      setUploadedAssets(Array.isArray(response.data.files) ? (response.data.files as UploadedAsset[]) : []);
    } catch {
      toast.error('Failed to load uploaded images');
      setUploadedAssets([]);
    } finally {
      setIsLoadingUploadedAssets(false);
    }
  };

  const selectUploadedAsset = (asset: UploadedAsset, mode: 'uploaded' | 'library') => {
    setUploadedImagePreview(asset.thumbnail_url || asset.url);
    setUploadedImageUrl(asset.url);
    setSelectedImageAssetId(asset.id);
    setSelectedImageMode(mode);
  };

  const handleRemoveUploadedImage = async () => {
    const fileId = selectedImageAssetId || (uploadedImageUrl ? extractUploadedFileId(uploadedImageUrl) : null);

    try {
      if (fileId && selectedImageMode === 'uploaded') {
        await uploadsApi.deleteFile(fileId, 'image');
        setUploadedAssets((current) => current.filter((asset) => asset.id !== fileId));
      }
      clearUploadedImageState();
      toast.success(selectedImageMode === 'library' ? 'Image cleared from draft' : 'Image removed');
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Failed to remove image'));
    }
  };

  const handleUploadManualImage = async (file: File) => {
    setUploadedImagePreview(URL.createObjectURL(file));
    setIsUploading(true);

    try {
      const response = await uploadsApi.uploadImage(file);
      const asset = response.data as UploadedAsset;
      setUploadedAssets((current) => [asset, ...current.filter((item) => item.id !== asset.id)].slice(0, 12));
      selectUploadedAsset(asset, 'uploaded');
      toast.success('Image uploaded');
    } catch (error) {
      clearUploadedImageState();
      toast.error(getApiErrorMessage(error, 'Failed to upload image'));
    } finally {
      setIsUploading(false);
    }
  };

  const handleSelectSuggestion = (suggestion: ContentSuggestion) => {
    setSelectedSuggestionId(suggestion.id);
    setTopic(suggestion.title_en || suggestion.title_ko);
    setContentType(suggestion.type);
  };

  const resolveScheduledAt = () => {
    if (!isScheduled || !scheduledDate) {
      return null;
    }
    return new Date(`${scheduledDate}T${scheduledTime}:00`).toISOString();
  };

  const handleGenerate = async () => {
    if (!activeLocationId) {
      toast.error('Create or select a location before generating content.');
      return;
    }

    if (!topic.trim()) {
      toast.error('Please enter a topic or select a suggestion');
      return;
    }

    setIsGenerating(true);
    try {
      const response = await contentApi.generate({
        location_id: activeLocationId,
        theme: topic,
        services: currentLocation?.services || [],
        tone: 'friendly and professional',
        language: 'en',
        platform_targets: [platform],
      });

      const content = response.data.content;
      if (platform === 'GBP' && content.gbp) {
        setGeneratedTitle(content.gbp.title || topic);
        setGeneratedBody(content.gbp.body || '');
      } else if (platform === 'INSTAGRAM' && content.instagram) {
        setGeneratedTitle(topic);
        setGeneratedBody(content.instagram.caption || '');
      } else {
        throw new Error('No generated content returned for the selected platform');
      }

      setGeneratedImageUrl('');
      setStep('preview');
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Failed to generate content'));
    } finally {
      setIsGenerating(false);
    }
  };

  const handleOneClickSuggestion = async () => {
    if (!activeLocationId) {
      toast.error('Create or select a location before creating a draft.');
      return;
    }

    if (!selectedSuggestionId) {
      toast.error('Select a suggestion first');
      return;
    }

    setIsOneClickCreating(true);
    try {
      const response = await contentApi.generateFromSuggestion(selectedSuggestionId, activeLocationId);
      toast.success('Draft created from suggestion');
      router.push(`/dashboard/content/${response.data.post_id}`);
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Failed to create draft from suggestion'));
    } finally {
      setIsOneClickCreating(false);
    }
  };

  const handleRegenerate = async () => {
    await handleGenerate();
  };

  const handleSubmit = async () => {
    if (!activeLocationId) {
      toast.error('Create or select a location before sending content for approval.');
      return;
    }

    setIsSubmitting(true);
    try {
      const createResponse = await postsApi.create({
        location_id: activeLocationId,
        platform,
        title: generatedTitle || null,
        body: generatedBody || null,
        image_url: generatedImageUrl || uploadedImageUrl || null,
        scheduled_at: resolveScheduledAt(),
        status: 'draft',
      });

      await postsApi.requestApproval(createResponse.data.id);
      toast.success('Content created and sent for approval');
      router.push('/dashboard/content');
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Failed to create content'));
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="max-w-3xl space-y-6">
        <Skeleton className="h-8 w-48" />
        <Card>
          <CardContent className="space-y-4 pt-6">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-32 w-full" />
          </CardContent>
        </Card>
      </div>
    );
  }

  if (locations.length === 0) {
    return (
      <div className="max-w-3xl space-y-6">
        <div className="flex items-center gap-4">
          <Link href="/dashboard/content">
            <Button variant="ghost" size="icon">
              <ArrowLeft className="h-5 w-5" />
            </Button>
          </Link>
          <div>
            <h1 className="text-2xl font-bold">Create Content</h1>
            <p className="text-gray-500">Add a business location before generating or publishing content.</p>
          </div>
        </div>
        <Card>
          <CardHeader>
            <CardTitle>No location available</CardTitle>
            <CardDescription>
              Content drafts need a real location so generated copy, approval routing, and publishing targets stay accurate.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Link href="/onboarding">
              <Button className="bg-gradient-to-r from-violet-600 to-indigo-600">
                Add your first location
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="max-w-3xl space-y-6">
      <div className="flex items-center gap-4">
        <Link href="/dashboard/content">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="h-5 w-5" />
          </Button>
        </Link>
        <div>
          <h1 className="text-2xl font-bold">Create Content</h1>
          <p className="text-gray-500">Generate or compose content, then send it into approval.</p>
        </div>
      </div>

      <Card className="border-slate-200 bg-slate-950 text-white">
        <CardContent className="pt-6">
          <Badge className="mb-2 bg-white/10 text-white hover:bg-white/10">Create Next Best Action</Badge>
          <h2 className="text-xl font-semibold">
            {step === 'setup' ? 'Choose one channel and one message' : 'Review the draft before approval'}
          </h2>
          <p className="mt-1 text-sm text-slate-300">
            This screen should produce one clear post, not a pile of options. Pick the location, platform, and message, then approve only when it reads right.
          </p>
        </CardContent>
      </Card>

      {step === 'setup' && (
        <>
          <Card>
            <CardContent className="pt-6">
              <div className="grid grid-cols-2 gap-4">
                <button
                  type="button"
                  onClick={() => setUploadMode('ai')}
                  className={`rounded-xl border-2 p-6 text-center transition-all ${
                    uploadMode === 'ai' ? 'border-violet-500 bg-violet-50' : 'border-gray-200 hover:border-gray-300'
                  }`}
                >
                  <Sparkles className={`mx-auto mb-2 h-8 w-8 ${uploadMode === 'ai' ? 'text-violet-600' : 'text-gray-400'}`} />
                  <p className="font-semibold">AI Generate</p>
                  <p className="mt-1 text-sm text-gray-500">Use suggestions or generate from a topic</p>
                </button>
                <button
                  type="button"
                  onClick={() => setUploadMode('manual')}
                  className={`rounded-xl border-2 p-6 text-center transition-all ${
                    uploadMode === 'manual' ? 'border-violet-500 bg-violet-50' : 'border-gray-200 hover:border-gray-300'
                  }`}
                >
                  <Upload className={`mx-auto mb-2 h-8 w-8 ${uploadMode === 'manual' ? 'text-violet-600' : 'text-gray-400'}`} />
                  <p className="font-semibold">Manual Upload</p>
                  <p className="mt-1 text-sm text-gray-500">Write and review content yourself</p>
                </button>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Content Settings</CardTitle>
              <CardDescription>Choose the location, platform, and message you want to publish.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>Location</Label>
                <Select value={activeLocationId} onValueChange={setSelectedLocation}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select location" />
                  </SelectTrigger>
                  <SelectContent>
                    {locations.map((loc) => (
                      <SelectItem key={loc.id} value={loc.id}>
                        <div className="flex items-center gap-2">
                          <MapPin className="h-4 w-4" />
                          {loc.name}
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>Platform</Label>
                <div className="grid grid-cols-2 gap-3">
                  {[
                    { id: 'GBP', name: 'Google Business', icon: Globe, color: 'text-blue-600' },
                    { id: 'INSTAGRAM', name: 'Instagram', icon: Instagram, color: 'text-pink-600' },
                  ].map((p) => (
                    <button
                      key={p.id}
                      type="button"
                      onClick={() => setPlatform(p.id as 'GBP' | 'INSTAGRAM')}
                      className={`flex items-center gap-3 rounded-lg border p-4 transition-colors ${
                        platform === p.id ? 'border-violet-500 bg-violet-50' : 'hover:border-gray-300'
                      }`}
                    >
                      <p.icon className={`h-6 w-6 ${p.color}`} />
                      <span className="font-medium">{p.name}</span>
                    </button>
                  ))}
                </div>
              </div>

              <div className="space-y-2">
                <Label>Content Type</Label>
                <Select value={contentType} onValueChange={setContentType}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="update">Update / News</SelectItem>
                    <SelectItem value="offer">Offer / Promotion</SelectItem>
                    <SelectItem value="event">Event</SelectItem>
                    <SelectItem value="product">Product Highlight</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {uploadMode === 'ai' && (
                <div className="space-y-2">
                  <Label>Topic</Label>
                  <Input
                    placeholder="Weekend special, new menu item, holiday hours..."
                    value={topic}
                    onChange={(e) => setTopic(e.target.value)}
                  />
                </div>
              )}

              {uploadMode === 'manual' && (
                <>
                  <div className="space-y-2">
                    <Label>Title</Label>
                    <Input value={manualTitle} onChange={(e) => setManualTitle(e.target.value)} placeholder="Enter your post title" />
                  </div>
                  <div className="space-y-2">
                    <Label>Content</Label>
                    <textarea
                      className="h-32 w-full resize-none rounded-lg border p-3 focus:outline-none focus:ring-2 focus:ring-violet-500"
                      placeholder="Write your post content"
                      value={manualBody}
                      onChange={(e) => setManualBody(e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Image (optional)</Label>
                    {uploadedImagePreview ? (
                      <div className="relative">
                        <img src={uploadedImagePreview} alt="Preview" className="h-48 w-full rounded-lg object-cover" />
                        <div className="absolute right-2 top-2 flex gap-2">
                          <button
                            type="button"
                            onClick={() => void handleRemoveUploadedImage()}
                            className="rounded-full bg-red-500 p-1 text-white hover:bg-red-600"
                            disabled={isUploading}
                          >
                            <X className="h-4 w-4" />
                          </button>
                        </div>
                        <div className="mt-3 flex gap-2">
                          <label className="inline-flex cursor-pointer items-center rounded-md border bg-white px-3 py-2 text-sm hover:bg-gray-50">
                            <Upload className="mr-2 h-4 w-4" />
                            Replace Image
                            <input
                              type="file"
                              accept="image/jpeg,image/png,image/gif,image/webp"
                              className="hidden"
                              onChange={async (e) => {
                                const file = e.target.files?.[0];
                                if (!file) {
                                  return;
                                }
                                await handleRemoveUploadedImage();
                                await handleUploadManualImage(file);
                              }}
                            />
                          </label>
                        </div>
                      </div>
                    ) : (
                      <label className="flex h-32 w-full cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed transition-colors hover:bg-gray-50">
                        <Upload className="mb-2 h-8 w-8 text-gray-400" />
                        <span className="text-sm text-gray-500">Click to upload image</span>
                        <input
                          type="file"
                          accept="image/jpeg,image/png,image/gif,image/webp"
                          className="hidden"
                          onChange={async (e) => {
                            const file = e.target.files?.[0];
                            if (file) {
                              await handleUploadManualImage(file);
                            }
                          }}
                        />
                      </label>
                    )}
                    {isUploading && <p className="text-sm text-gray-500">Uploading image...</p>}
                    {!isUploading && uploadedImageUrl && (
                      <p className="text-sm text-green-600">Uploaded image ready for publishing</p>
                    )}
                    <div className="space-y-3 pt-2">
                      <div className="flex items-center justify-between">
                        <p className="text-sm font-medium text-gray-700">Recent uploaded images</p>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => void fetchUploadedAssets()}
                          disabled={isLoadingUploadedAssets}
                        >
                          <RefreshCw className={`mr-2 h-4 w-4 ${isLoadingUploadedAssets ? 'animate-spin' : ''}`} />
                          Refresh
                        </Button>
                      </div>
                      {isLoadingUploadedAssets ? (
                        <div className="grid grid-cols-3 gap-3">
                          {Array.from({ length: 3 }).map((_, index) => (
                            <Skeleton key={index} className="h-24 w-full rounded-lg" />
                          ))}
                        </div>
                      ) : uploadedAssets.length > 0 ? (
                        <div className="grid grid-cols-3 gap-3">
                          {uploadedAssets.map((asset) => {
                            const isSelected = selectedImageAssetId === asset.id;
                            return (
                              <button
                                key={asset.id}
                                type="button"
                                onClick={() => selectUploadedAsset(asset, 'library')}
                                className={`overflow-hidden rounded-lg border text-left transition-colors ${
                                  isSelected ? 'border-violet-500 ring-2 ring-violet-200' : 'border-gray-200 hover:border-violet-300'
                                }`}
                              >
                                <img
                                  src={asset.thumbnail_url || asset.url}
                                  alt={asset.original_filename}
                                  className="h-24 w-full object-cover"
                                />
                                <div className="p-2">
                                  <p className="truncate text-xs font-medium text-gray-700">{asset.original_filename}</p>
                                </div>
                              </button>
                            );
                          })}
                        </div>
                      ) : (
                        <p className="text-sm text-gray-500">
                          No uploaded image library yet. Upload one above and it will stay reusable for future drafts.
                        </p>
                      )}
                    </div>
                  </div>
                </>
              )}
            </CardContent>
          </Card>

          {uploadMode === 'ai' && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Sparkles className="h-5 w-5 text-violet-600" />
                  AI Suggestions
                </CardTitle>
                <CardDescription>Select a topic or use one-click draft creation.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-3 sm:grid-cols-2">
                  {suggestions.map((suggestion) => {
                    const selected = selectedSuggestionId === suggestion.id;
                    return (
                      <button
                        key={suggestion.id}
                        type="button"
                        onClick={() => handleSelectSuggestion(suggestion)}
                        className={`rounded-lg border p-4 text-left transition-colors hover:border-violet-500 hover:bg-violet-50 ${
                          selected ? 'border-violet-500 bg-violet-50' : ''
                        }`}
                      >
                        <div className="mb-2 flex items-center gap-2">
                          <span>{suggestion.emoji}</span>
                          <p className="font-medium">{suggestion.title_en || suggestion.title_ko}</p>
                        </div>
                        <p className="text-sm text-gray-500">Type: {suggestion.type}</p>
                      </button>
                    );
                  })}
                </div>

                <div className="flex justify-end">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={handleOneClickSuggestion}
                    disabled={!activeLocationId || !selectedSuggestionId || isOneClickCreating}
                  >
                    {isOneClickCreating ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Creating Draft
                      </>
                    ) : (
                      <>
                        <Wand2 className="mr-2 h-4 w-4" />
                        One-Click Create Draft
                      </>
                    )}
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}

          {uploadMode === 'ai' ? (
            <Button
              size="lg"
              className="w-full bg-gradient-to-r from-violet-600 to-indigo-600"
              onClick={handleGenerate}
              disabled={isGenerating || !activeLocationId || !topic.trim()}
            >
              {isGenerating ? (
                <>
                  <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                  Generating...
                </>
              ) : (
                <>
                  <Sparkles className="mr-2 h-5 w-5" />
                  Generate Preview
                </>
              )}
            </Button>
          ) : (
            <Button
              size="lg"
              className="w-full bg-gradient-to-r from-violet-600 to-indigo-600"
              onClick={() => {
                if (!manualTitle.trim() || !manualBody.trim()) {
                  toast.error('Please enter title and content');
                  return;
                }
                setGeneratedTitle(manualTitle);
                setGeneratedBody(manualBody);
                setGeneratedImageUrl(uploadedImagePreview);
                setStep('preview');
              }}
              disabled={!activeLocationId || !manualTitle.trim() || !manualBody.trim() || isUploading}
            >
              <CheckCircle className="mr-2 h-5 w-5" />
              Preview Content
            </Button>
          )}
        </>
      )}

      {step === 'preview' && (
        <>
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Preview</CardTitle>
                  <CardDescription>Review the content before creating the draft.</CardDescription>
                </div>
                {uploadMode === 'ai' && (
                  <Button variant="outline" size="sm" onClick={handleRegenerate} disabled={isGenerating}>
                    <RefreshCw className={`mr-2 h-4 w-4 ${isGenerating ? 'animate-spin' : ''}`} />
                    Regenerate
                  </Button>
                )}
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center gap-2">
                {platform === 'GBP' ? (
                  <Badge className="bg-blue-100 text-blue-700">
                    <Globe className="mr-1 h-3 w-3" />
                    Google Business
                  </Badge>
                ) : (
                  <Badge className="bg-pink-100 text-pink-700">
                    <Instagram className="mr-1 h-3 w-3" />
                    Instagram
                  </Badge>
                )}
                <Badge variant="secondary">{contentType}</Badge>
              </div>

              {generatedImageUrl && (
                <div className="relative aspect-video overflow-hidden rounded-lg bg-gray-100">
                  <img src={generatedImageUrl} alt="Generated content" className="h-full w-full object-cover" />
                  <div className="absolute bottom-3 right-3 rounded-full bg-white/90 px-3 py-1 text-xs font-medium text-gray-700 shadow-sm">
                    <ImageIcon className="mr-1 h-4 w-4" />
                    Generated image
                  </div>
                </div>
              )}

              <div className="space-y-2">
                <Label>Title</Label>
                <Input value={generatedTitle} onChange={(e) => setGeneratedTitle(e.target.value)} />
              </div>

              <div className="space-y-2">
                <Label>Content</Label>
                <textarea
                  className="h-48 w-full resize-none rounded-lg border p-3 focus:outline-none focus:ring-2 focus:ring-violet-500"
                  value={generatedBody}
                  onChange={(e) => setGeneratedBody(e.target.value)}
                />
              </div>

              <div className="space-y-4 rounded-lg bg-gray-50 p-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Calendar className="h-5 w-5 text-violet-600" />
                    <Label className="font-medium">Schedule for later</Label>
                  </div>
                  <button
                    type="button"
                    onClick={() => setIsScheduled(!isScheduled)}
                    className={`relative h-6 w-12 rounded-full transition-colors ${isScheduled ? 'bg-violet-600' : 'bg-gray-300'}`}
                  >
                    <span
                      className={`absolute top-1 h-4 w-4 rounded-full bg-white transition-transform ${
                        isScheduled ? 'translate-x-7' : 'translate-x-1'
                      }`}
                    />
                  </button>
                </div>

                {isScheduled && (
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>Date</Label>
                      <Input
                        type="date"
                        value={scheduledDate}
                        onChange={(e) => setScheduledDate(e.target.value)}
                        min={new Date().toISOString().split('T')[0]}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Time</Label>
                      <Input type="time" value={scheduledTime} onChange={(e) => setScheduledTime(e.target.value)} />
                    </div>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          <div className="flex gap-3">
            <Button variant="outline" onClick={() => setStep('setup')} className="flex-1">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back
            </Button>
            <Button
              onClick={handleSubmit}
              disabled={isSubmitting || !activeLocationId}
              className="flex-1 bg-gradient-to-r from-violet-600 to-indigo-600"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Creating...
                </>
              ) : (
                <>
                  <Send className="mr-2 h-4 w-4" />
                  Create & Send for Approval
                </>
              )}
            </Button>
          </div>
        </>
      )}
    </div>
  );
}
