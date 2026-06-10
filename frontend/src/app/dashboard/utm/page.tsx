'use client';

import { useEffect, useState } from 'react';
import { Link2, Plus, Copy, ExternalLink, MousePointer, TrendingUp, BarChart3, Loader2, Trash2, RefreshCw, AlertCircle } from 'lucide-react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { extractCollectionPayload, locationsApi, utmApi } from '@/lib/api';
import { getApiErrorMessage } from '@/lib/api-errors';

type Location = {
  id: string;
  name: string;
  address?: string;
};

type UTMLink = {
  id: string;
  original_url: string;
  utm_campaign: string;
  utm_source: string;
  utm_medium: string;
  utm_content?: string | null;
  clicks: number;
  created_at: string;
  utm_url: string;
};

type UTMStatsResponse = {
  total_links: number;
  total_clicks: number;
  links: UTMLink[];
};

const formatDate = (dateString: string) => {
  const date = new Date(dateString);
  return `${date.getFullYear()}.${String(date.getMonth() + 1).padStart(2, '0')}.${String(date.getDate()).padStart(2, '0')}`;
};

export default function UTMPage() {
  const [isLoadingLocations, setIsLoadingLocations] = useState(true);
  const [isLoadingLinks, setIsLoadingLinks] = useState(false);
  const [locationError, setLocationError] = useState<string | null>(null);
  const [linksError, setLinksError] = useState<string | null>(null);
  const [locations, setLocations] = useState<Location[]>([]);
  const [selectedLocation, setSelectedLocation] = useState<string>('');
  const [links, setLinks] = useState<UTMLink[]>([]);
  const [totalClicks, setTotalClicks] = useState(0);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newLink, setNewLink] = useState({
    original_url: '',
    campaign: '',
    utm_source: 'google',
    utm_medium: 'business_profile',
  });
  const activeLocationId = selectedLocation || locations[0]?.id || '';

  useEffect(() => {
    void fetchLocations();
  }, []);

  useEffect(() => {
    if (activeLocationId) {
      void fetchLinks(activeLocationId);
    } else {
      setLinks([]);
      setTotalClicks(0);
    }
  }, [activeLocationId]);

  const fetchLocations = async () => {
    setIsLoadingLocations(true);
    setLocationError(null);
    try {
      const response = await locationsApi.list();
      const locs = extractCollectionPayload<Location>(response.data, 'locations');
      setLocations(locs);
      setSelectedLocation((current) =>
        current && locs.some((location) => location.id === current)
          ? current
          : (locs[0]?.id ?? '')
      );
    } catch (error) {
      setLocationError(getApiErrorMessage(error, 'Failed to load locations'));
      setLocations([]);
      setSelectedLocation('');
    } finally {
      setIsLoadingLocations(false);
    }
  };

  const fetchLinks = async (locationId: string) => {
    if (!locationId) return;

    setIsLoadingLinks(true);
    setLinksError(null);
    try {
      const response = await utmApi.list(locationId);
      const data: UTMStatsResponse = response.data;
      setLinks(data.links || []);
      setTotalClicks(data.total_clicks || 0);
    } catch (error) {
      setLinks([]);
      setTotalClicks(0);
      setLinksError(getApiErrorMessage(error, 'Failed to load UTM links'));
    } finally {
      setIsLoadingLinks(false);
    }
  };

  const handleCreate = async () => {
    if (!activeLocationId) {
      toast.error('Create a location before generating UTM links.');
      return;
    }
    if (!newLink.original_url || !newLink.campaign) {
      toast.error('Please enter both a destination URL and a campaign name.');
      return;
    }

    setCreating(true);
    try {
      await utmApi.create(activeLocationId, {
        original_url: newLink.original_url,
        campaign: newLink.campaign,
        utm_source: newLink.utm_source,
        utm_medium: newLink.utm_medium,
      });
      toast.success('UTM link created');
      setShowCreateModal(false);
      setNewLink({
        original_url: '',
        campaign: '',
        utm_source: 'google',
        utm_medium: 'business_profile',
      });
      await fetchLinks(activeLocationId);
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Failed to create UTM link'));
    } finally {
      setCreating(false);
    }
  };

  const handleCopy = async (url: string) => {
    await navigator.clipboard.writeText(url);
    toast.success('Copied to clipboard');
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this UTM link?')) return;

    try {
      await utmApi.delete(id);
      toast.success('UTM link deleted');
      if (selectedLocation) {
        await fetchLinks(selectedLocation);
      }
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Failed to delete link'));
    }
  };

  const buildPreviewUrl = () => {
    if (!newLink.original_url) return '';
    try {
      const url = new URL(newLink.original_url);
      const params = new URLSearchParams();
      if (newLink.utm_source) params.set('utm_source', newLink.utm_source);
      if (newLink.utm_medium) params.set('utm_medium', newLink.utm_medium);
      if (newLink.campaign) params.set('utm_campaign', newLink.campaign);
      url.search = params.toString();
      return url.toString();
    } catch {
      return '';
    }
  };

  if (isLoadingLocations) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-64" />
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
        </div>
        <Skeleton className="h-80" />
      </div>
    );
  }

  if (locationError && locations.length === 0) {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center text-center">
        <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-red-100">
          <AlertCircle className="h-8 w-8 text-red-600" />
        </div>
        <h2 className="mb-2 text-2xl font-bold">UTM links could not be loaded</h2>
        <p className="mb-6 max-w-md text-gray-500">{locationError}</p>
        <Button onClick={() => void fetchLocations()}>
          <RefreshCw className="mr-2 h-4 w-4" />
          Retry
        </Button>
      </div>
    );
  }

  if (locations.length === 0) {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center text-center">
        <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-violet-100">
          <AlertCircle className="h-8 w-8 text-violet-600" />
        </div>
        <h2 className="mb-2 text-2xl font-bold">Add your first location</h2>
        <p className="mb-6 max-w-md text-gray-500">
          Create a business location first so UTM links can be tracked against real activity.
        </p>
        <Button asChild className="bg-gradient-to-r from-violet-600 to-indigo-600">
          <a href="/onboarding">
            Start onboarding
          </a>
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">UTM Link Tracking</h1>
          <p className="text-gray-600">Track campaign clicks and see which links are actually getting used.</p>
        </div>
        <div className="flex items-center gap-3">
          {locations.length > 1 && (
            <Select value={activeLocationId} onValueChange={setSelectedLocation}>
              <SelectTrigger className="w-[220px]">
                <SelectValue placeholder="Select location" />
              </SelectTrigger>
              <SelectContent>
                {locations.map((loc) => (
                  <SelectItem key={loc.id} value={loc.id}>
                    {loc.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
          <Button variant="outline" onClick={() => void fetchLinks(activeLocationId)} disabled={isLoadingLinks}>
            <RefreshCw className="mr-2 h-4 w-4" />
            Refresh
          </Button>
          <Dialog open={showCreateModal} onOpenChange={setShowCreateModal}>
            <DialogTrigger asChild>
              <Button>
                <Plus className="mr-2 h-4 w-4" />
                Create link
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-lg">
              <DialogHeader>
                <DialogTitle>Create UTM link</DialogTitle>
                <DialogDescription>
                  Add a destination URL and campaign name. We will generate the tracking link from the real data you enter.
                </DialogDescription>
              </DialogHeader>

              <div className="space-y-4 py-4">
                <div className="space-y-2">
                  <Label htmlFor="original_url">Destination URL *</Label>
                  <Input
                    id="original_url"
                    placeholder="https://example.com/page"
                    value={newLink.original_url}
                    onChange={(event) => setNewLink({ ...newLink, original_url: event.target.value })}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="campaign">Campaign name *</Label>
                  <Input
                    id="campaign"
                    placeholder="summer_promo_2026"
                    value={newLink.campaign}
                    onChange={(event) =>
                      setNewLink({ ...newLink, campaign: event.target.value.toLowerCase().replace(/\s+/g, '_') })
                    }
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="utm_source">Source</Label>
                    <Select
                      value={newLink.utm_source}
                      onValueChange={(value) => setNewLink({ ...newLink, utm_source: value })}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="google">Google</SelectItem>
                        <SelectItem value="facebook">Facebook</SelectItem>
                        <SelectItem value="instagram">Instagram</SelectItem>
                        <SelectItem value="email">Email</SelectItem>
                        <SelectItem value="sms">SMS</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="utm_medium">Medium</Label>
                    <Select
                      value={newLink.utm_medium}
                      onValueChange={(value) => setNewLink({ ...newLink, utm_medium: value })}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="business_profile">Business Profile</SelectItem>
                        <SelectItem value="gbp_post">GBP Post</SelectItem>
                        <SelectItem value="social">Social</SelectItem>
                        <SelectItem value="email">Email</SelectItem>
                        <SelectItem value="sms">SMS</SelectItem>
                        <SelectItem value="cpc">CPC</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                {buildPreviewUrl() ? (
                  <div className="space-y-1 rounded-lg bg-gray-50 p-3">
                    <p className="text-xs font-medium text-gray-500">Preview</p>
                    <p className="break-all font-mono text-sm text-gray-700">{buildPreviewUrl()}</p>
                  </div>
                ) : null}
              </div>

              <DialogFooter>
                <Button variant="outline" onClick={() => setShowCreateModal(false)}>
                  Cancel
                </Button>
                <Button onClick={handleCreate} disabled={creating}>
                  {creating ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                  Create
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      <Card className="border-slate-200 bg-slate-950 text-white">
        <CardContent className="flex flex-col gap-4 pt-6 md:flex-row md:items-center md:justify-between">
          <div>
            <Badge className="mb-2 bg-white/10 text-white hover:bg-white/10">UTM Next Best Action</Badge>
            <h2 className="text-xl font-semibold">Create a trackable link before launching a campaign</h2>
            <p className="mt-1 text-sm text-slate-300">
              One clear campaign link makes it easier to prove which posts, emails, texts, or ads drove traffic.
            </p>
          </div>
          <Button className="bg-white text-slate-950 hover:bg-slate-100" onClick={() => setShowCreateModal(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Create link
          </Button>
        </CardContent>
      </Card>

      {linksError ? (
        <Card className="border-amber-200 bg-amber-50">
          <CardContent className="flex items-center justify-between gap-4 pt-6">
            <div className="flex items-start gap-3">
              <AlertCircle className="mt-0.5 h-5 w-5 text-amber-600" />
              <div>
                <p className="font-medium text-amber-900">UTM links need attention</p>
                <p className="text-sm text-amber-800">{linksError}</p>
              </div>
            </div>
            <Button variant="outline" onClick={() => void fetchLinks(activeLocationId)} disabled={isLoadingLinks}>
              Retry
            </Button>
          </CardContent>
        </Card>
      ) : null}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-violet-100">
                <Link2 className="h-6 w-6 text-violet-600" />
              </div>
              <div>
                <p className="text-sm text-gray-500">Total links</p>
                <p className="text-2xl font-bold">{links.length}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-green-100">
                <MousePointer className="h-6 w-6 text-green-600" />
              </div>
              <div>
                <p className="text-sm text-gray-500">Total clicks</p>
                <p className="text-2xl font-bold">{totalClicks.toLocaleString()}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-amber-100">
                <TrendingUp className="h-6 w-6 text-amber-600" />
              </div>
              <div>
                <p className="text-sm text-gray-500">Average clicks per link</p>
                <p className="text-2xl font-bold">{links.length > 0 ? Math.round(totalClicks / links.length) : 0}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <BarChart3 className="h-5 w-5" />
            UTM links
          </CardTitle>
          <CardDescription>Track created links and total clicks for the selected location.</CardDescription>
        </CardHeader>
        <CardContent>
          {isLoadingLinks ? (
            <div className="space-y-3">
              {[1, 2, 3].map((item) => (
                <Skeleton key={item} className="h-16 w-full" />
              ))}
            </div>
          ) : links.length === 0 ? (
            <div className="rounded-lg border border-dashed p-10 text-center">
              <Link2 className="mx-auto mb-3 h-12 w-12 text-gray-300" />
              <p className="font-medium text-gray-500">No UTM links yet</p>
              <p className="mt-1 text-sm text-gray-400">
                Create the first tracked link for this location and the clicks will appear here.
              </p>
              <Button className="mt-4" onClick={() => setShowCreateModal(true)}>
                <Plus className="mr-2 h-4 w-4" />
                Create link
              </Button>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Campaign</TableHead>
                  <TableHead>Destination</TableHead>
                  <TableHead className="text-center">Clicks</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {links.map((link) => (
                  <TableRow key={link.id}>
                    <TableCell>
                      <div>
                        <p className="font-medium">{link.utm_campaign}</p>
                        <div className="mt-1 flex items-center gap-1">
                          <Badge variant="outline" className="text-xs">
                            {link.utm_source}
                          </Badge>
                          <Badge variant="outline" className="text-xs">
                            {link.utm_medium}
                          </Badge>
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="max-w-xs">
                        <p className="truncate font-mono text-sm text-violet-600">{link.utm_url}</p>
                        <p className="mt-0.5 truncate text-xs text-gray-400">{link.original_url}</p>
                      </div>
                    </TableCell>
                    <TableCell className="text-center">
                      <Badge className="bg-green-100 text-green-700">{link.clicks.toLocaleString()}</Badge>
                    </TableCell>
                    <TableCell className="text-sm text-gray-500">{formatDate(link.created_at)}</TableCell>
                    <TableCell>
                      <div className="flex items-center justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => void handleCopy(link.utm_url)}
                          title="Copy tracking URL"
                        >
                          <Copy className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => window.open(link.utm_url, '_blank')}
                          title="Open tracking URL"
                        >
                          <ExternalLink className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="text-red-600 hover:bg-red-50 hover:text-red-700"
                          onClick={() => void handleDelete(link.id)}
                          title="Delete link"
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
