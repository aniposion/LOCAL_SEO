'use client';

import axios from 'axios';
import { useEffect, useEffectEvent, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Skeleton } from '@/components/ui/skeleton';
import {
  ArrowLeft,
  Save,
  Trash2,
  Loader2,
  AlertCircle,
  MapPin,
  Phone,
  Star,
  Navigation,
  Eye,
  DollarSign,
  TrendingUp,
  TrendingDown,
  Edit,
  ExternalLink,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { locationsApi, metricsApi } from '@/lib/api';
import { toast } from 'sonner';

interface LocationDetail {
  id: string;
  name: string;
  address: string;
  phone?: string;
  website_url?: string;
  category?: string;
  gbp_location_id?: string;
  rating?: number;
  review_count?: number;
  status: string;
  created_at: string;
}

interface MetricDelta {
  current: number;
  previous: number;
  delta: number;
  percent_change: number;
}

interface DashboardMetrics {
  calls: MetricDelta;
  directions: MetricDelta;
  profile_views: MetricDelta;
  new_reviews: MetricDelta;
  estimated_revenue: number | string;
}

export default function LocationDetailPage() {
  const params = useParams();
  const router = useRouter();
  const locationId = params.id as string;

  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [location, setLocation] = useState<LocationDetail | null>(null);
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [metricsError, setMetricsError] = useState<string | null>(null);

  // Edit form state
  const [editName, setEditName] = useState('');
  const [editPhone, setEditPhone] = useState('');
  const [editWebsite, setEditWebsite] = useState('');

  const fetchLocationData = async () => {
    setIsLoading(true);
    setLoadError(null);
    setMetricsError(null);
    try {
      const [locationResult, metricsResult] = await Promise.allSettled([
        locationsApi.get(locationId),
        metricsApi.getDashboard(locationId, 7),
      ]);

      if (locationResult.status === 'rejected') {
        const detail =
          axios.isAxiosError(locationResult.reason) && locationResult.reason.response?.status === 404
            ? 'Location not found'
            : 'Failed to load location details';
        setLoadError(detail);
        setLocation(null);
        setMetrics(null);
        return;
      }

      const locationData = locationResult.value.data as LocationDetail;
      setLocation(locationData);
      setEditName(locationData.name);
      setEditPhone(locationData.phone || '');
      setEditWebsite(locationData.website_url || '');

      if (metricsResult.status === 'fulfilled') {
        setMetrics(metricsResult.value.data.metrics as DashboardMetrics);
      } else {
        setMetrics(null);
        setMetricsError('Failed to load metrics for this location');
      }
    } catch {
      setLoadError('Failed to load location details');
      setLocation(null);
      setMetrics(null);
    } finally {
      setIsLoading(false);
    }
  };

  const loadLocationOnMount = useEffectEvent(async () => {
    await fetchLocationData();
  });

  useEffect(() => {
    void loadLocationOnMount();
  }, [locationId]);

  const handleSave = async () => {
    if (!editName.trim()) {
      toast.error('Name is required');
      return;
    }

    setIsSaving(true);
    try {
      const response = await locationsApi.update(locationId, {
        name: editName,
        phone: editPhone || null,
        website_url: editWebsite || null,
      });
      setLocation(response.data);
      setEditName(response.data.name);
      setEditPhone(response.data.phone || '');
      setEditWebsite(response.data.website_url || '');
      setIsEditing(false);
      toast.success('Location updated!');
    } catch {
      toast.error('Failed to update location');
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async () => {
    setIsDeleting(true);
    try {
      await locationsApi.delete(locationId);
      toast.success('Location deleted');
      router.push('/dashboard/locations');
    } catch {
      toast.error('Failed to delete location');
    } finally {
      setIsDeleting(false);
    }
  };

  const MetricCard = ({
    icon: Icon,
    label,
    value,
    change,
    iconColor
  }: {
    icon: LucideIcon;
    label: string;
    value: number | string;
    change?: number;
    iconColor: string;
  }) => (
    <Card>
      <CardContent className="pt-6">
        <div className="flex items-center gap-2 mb-2">
          <Icon className={`w-5 h-5 ${iconColor}`} />
          <span className="text-sm text-gray-500">{label}</span>
        </div>
        <div className="flex items-end gap-2">
          <span className="text-2xl font-bold">{value}</span>
          {change !== undefined && (
            <span className={`text-sm flex items-center ${change >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {change >= 0 ? <TrendingUp className="w-3 h-3 mr-1" /> : <TrendingDown className="w-3 h-3 mr-1" />}
              {Math.abs(change)}%
            </span>
          )}
        </div>
      </CardContent>
    </Card>
  );

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <Card key={i}>
              <CardContent className="pt-6">
                <Skeleton className="h-6 w-24 mb-2" />
                <Skeleton className="h-8 w-16" />
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="container mx-auto py-8">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <AlertCircle className="h-5 w-5 text-destructive" />
              Could not load location
            </CardTitle>
            <CardDescription>{loadError}</CardDescription>
          </CardHeader>
          <CardContent className="flex gap-3">
            <Button onClick={() => void fetchLocationData()}>Retry</Button>
            <Link href="/dashboard/locations">
              <Button variant="outline">Back to Locations</Button>
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!location) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500">Location not found</p>
        <Link href="/dashboard/locations">
          <Button variant="link">Back to Locations</Button>
        </Link>
      </div>
    );
  }

  const isMissingCoreDetails = !location.phone || !location.website_url;
  const locationNextAction = isEditing
    ? {
        title: 'Save this location profile',
        description: 'Accurate phone and website details make every automation safer and keep customers from hitting dead ends.',
      }
    : isMissingCoreDetails
      ? {
          title: 'Complete the phone and website first',
          description: 'This improves trust, call conversion, and the quality of content, reports, and customer follow-up.',
        }
      : metricsError
        ? {
            title: 'Refresh this location snapshot',
            description: 'Metrics are temporarily unavailable. Refresh before making decisions from this location page.',
          }
        : {
            title: 'Publish a local update for this location',
            description: 'Fresh location-specific content helps customers see that this business is active and ready to help.',
          };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href="/dashboard/locations">
            <Button variant="ghost" size="sm">
              <ArrowLeft className="w-4 h-4 mr-1" />
              Back
            </Button>
          </Link>
          <div>
            <h1 className="text-2xl font-bold">{location.name}</h1>
            <p className="text-gray-500 flex items-center gap-1">
              <MapPin className="w-4 h-4" />
              {location.address}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Badge className="bg-green-100 text-green-700">{location.status}</Badge>
          {location.rating && (
            <Badge variant="secondary" className="flex items-center gap-1">
              <Star className="w-3 h-3 fill-yellow-400 text-yellow-400" />
              {location.rating} ({location.review_count} reviews)
            </Badge>
          )}
        </div>
      </div>

      <Card className="border-sky-200 bg-gradient-to-br from-sky-50 to-white">
        <CardContent className="space-y-4 p-6">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-sky-700">Next Best Action</p>
            <h2 className="mt-2 text-xl font-semibold text-slate-950">{locationNextAction.title}</h2>
            <p className="mt-2 text-sm text-slate-600">{locationNextAction.description}</p>
          </div>
          <div className="flex flex-col gap-3 sm:flex-row">
            {isEditing ? (
              <Button onClick={handleSave} disabled={isSaving}>
                {isSaving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Save className="w-4 h-4 mr-2" />}
                Save Location
              </Button>
            ) : isMissingCoreDetails ? (
              <Button onClick={() => setIsEditing(true)}>
                <Edit className="w-4 h-4 mr-2" />
                Complete Details
              </Button>
            ) : metricsError ? (
              <Button onClick={() => void fetchLocationData()}>Refresh Snapshot</Button>
            ) : (
              <Button asChild>
                <Link href="/dashboard/content/new">Create Local Post</Link>
              </Button>
            )}
            {!isEditing && (
              <Button asChild variant="outline">
                <Link href="/dashboard/reviews">Check Reviews</Link>
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Metrics */}
      {metrics ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <MetricCard
            icon={Phone}
            label="Calls (7d)"
            value={metrics.calls.current}
            change={metrics.calls.percent_change}
            iconColor="text-green-500"
          />
          <MetricCard
            icon={Navigation}
            label="Directions (7d)"
            value={metrics.directions.current}
            change={metrics.directions.percent_change}
            iconColor="text-blue-500"
          />
          <MetricCard
            icon={Eye}
            label="Profile Views (7d)"
            value={metrics.profile_views.current.toLocaleString()}
            change={metrics.profile_views.percent_change}
            iconColor="text-purple-500"
          />
          <MetricCard
            icon={DollarSign}
            label="Estimated Revenue"
            value={`$${Number(metrics.estimated_revenue || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}`}
            iconColor="text-orange-500"
          />
        </div>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <AlertCircle className="h-5 w-5 text-amber-500" />
              Metrics unavailable
            </CardTitle>
            <CardDescription>
              {metricsError || 'We could not load metrics for this location right now.'}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button variant="outline" onClick={() => void fetchLocationData()}>
              Retry metrics
            </Button>
          </CardContent>
        </Card>
      )}

      <Tabs defaultValue="details">
        <TabsList>
          <TabsTrigger value="details">Details</TabsTrigger>
          <TabsTrigger value="settings">Settings</TabsTrigger>
        </TabsList>

        {/* Details Tab */}
        <TabsContent value="details" className="mt-6">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>Location Details</CardTitle>
                  <CardDescription>Basic information about this location</CardDescription>
                </div>
                {!isEditing && (
                  <Button variant="outline" size="sm" onClick={() => setIsEditing(true)}>
                    <Edit className="w-4 h-4 mr-1" />
                    Edit
                  </Button>
                )}
              </div>
            </CardHeader>
            <CardContent className="space-y-6">
              {isEditing ? (
                /* Edit Mode */
                <>
                  <div className="grid md:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>Business Name</Label>
                      <Input
                        value={editName}
                        onChange={(e) => setEditName(e.target.value)}
                        placeholder="Business name"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label>Phone Number</Label>
                      <Input
                        value={editPhone}
                        onChange={(e) => setEditPhone(e.target.value)}
                        placeholder="+1 (555) 000-0000"
                      />
                    </div>
                    <div className="space-y-2 md:col-span-2">
                      <Label>Website</Label>
                      <Input
                        value={editWebsite}
                        onChange={(e) => setEditWebsite(e.target.value)}
                        placeholder="https://example.com"
                      />
                    </div>
                  </div>

                  <div className="flex gap-3">
                    <Button variant="outline" onClick={() => setIsEditing(false)}>
                      Cancel
                    </Button>
                    <Button onClick={handleSave} disabled={isSaving}>
                      {isSaving ? (
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      ) : (
                        <Save className="w-4 h-4 mr-2" />
                      )}
                      Save Changes
                    </Button>
                  </div>
                </>
              ) : (
                /* View Mode */
                <div className="grid md:grid-cols-2 gap-6">
                  <div>
                    <p className="text-sm text-gray-500 mb-1">Business Name</p>
                    <p className="font-medium">{location.name}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500 mb-1">Category</p>
                    <p className="font-medium">{location.category || 'Not set'}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500 mb-1">Address</p>
                    <p className="font-medium">{location.address}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500 mb-1">Phone</p>
                    <p className="font-medium flex items-center gap-2">
                      {location.phone || 'Not set'}
                      {location.phone && (
                        <a href={`tel:${location.phone}`} className="text-violet-600">
                          <Phone className="w-4 h-4" />
                        </a>
                      )}
                    </p>
                  </div>
                  <div className="md:col-span-2">
                    <p className="text-sm text-gray-500 mb-1">Website</p>
                    <p className="font-medium flex items-center gap-2">
                      {location.website_url || 'Not set'}
                      {location.website_url && (
                        <a href={location.website_url} target="_blank" rel="noopener noreferrer" className="text-violet-600">
                          <ExternalLink className="w-4 h-4" />
                        </a>
                      )}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500 mb-1">Added</p>
                    <p className="font-medium">{new Date(location.created_at).toLocaleDateString()}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-500 mb-1">Google Business ID</p>
                    <p className="font-medium font-mono text-sm">{location.gbp_location_id || 'Not connected'}</p>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Settings Tab */}
        <TabsContent value="settings" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>Location Settings</CardTitle>
              <CardDescription>Manage settings for this location</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="p-4 border rounded-lg">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">Auto-publish content</p>
                    <p className="text-sm text-gray-500">Automatically publish approved content</p>
                  </div>
                  <Badge className="bg-green-100 text-green-700">Enabled</Badge>
                </div>
              </div>

              <div className="p-4 border rounded-lg">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">Review notifications</p>
                    <p className="text-sm text-gray-500">Get notified when new reviews are posted</p>
                  </div>
                  <Badge className="bg-green-100 text-green-700">Enabled</Badge>
                </div>
              </div>

              <div className="p-4 border rounded-lg">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">Missed call text back</p>
                    <p className="text-sm text-gray-500">Automatically text customers when calls are missed</p>
                  </div>
                  <Badge className="bg-green-100 text-green-700">Enabled</Badge>
                </div>
              </div>

              <div className="border-t pt-6">
                <h4 className="font-medium text-red-600 mb-2">Danger Zone</h4>
                <p className="text-sm text-gray-500 mb-4">
                  Deleting this location will remove all associated data including content, analytics, and settings.
                </p>
                <Button
                  variant="destructive"
                  disabled={isDeleting}
                  onClick={() => setIsDeleteDialogOpen(true)}
                >
                  <Trash2 className="w-4 h-4 mr-2" />
                  Delete Location
                </Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Delete Dialog */}
      <Dialog open={isDeleteDialogOpen} onOpenChange={setIsDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Location</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete &quot;{location.name}&quot;? This will permanently remove all associated data.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsDeleteDialogOpen(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDelete}>
              {isDeleting ? 'Deleting...' : 'Delete Location'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
