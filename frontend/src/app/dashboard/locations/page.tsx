'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  MapPin,
  Plus,
  MoreVertical,
  Phone,
  Navigation,
  Star,
  ExternalLink,
  Settings,
  Trash2,
  Loader2,
  Globe,
} from 'lucide-react';
import { extractCollectionPayload, locationsApi, metricsApi } from '@/lib/api';
import { toast } from 'sonner';
import Link from 'next/link';

interface Location {
  id: string;
  name: string;
  address?: string | null;
  city?: string | null;
  state?: string | null;
  phone?: string | null;
  website_url?: string | null;
  gbp_location_id?: string | null;
  instagram_connected?: boolean;
  instagram_status?: string | null;
  created_at: string;
  metrics?: {
    calls_7d: number;
    directions_7d: number;
    rating: number | null;
    revenue_7d: number;
  };
}

export default function LocationsPage() {
  const [isLoading, setIsLoading] = useState(true);
  const [locations, setLocations] = useState<Location[]>([]);
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const [newLocationName, setNewLocationName] = useState('');
  const [newLocationAddress, setNewLocationAddress] = useState('');
  const [newLocationPhone, setNewLocationPhone] = useState('');
  const [newLocationWebsite, setNewLocationWebsite] = useState('');

  useEffect(() => {
    fetchLocations();
  }, []);

  const fetchLocations = async () => {
    try {
      const response = await locationsApi.list();
      const baseLocations = extractCollectionPayload<Location>(response.data, 'locations');

      const metricResults = await Promise.allSettled(
        baseLocations.map(async (location: Location) => {
          const metricResponse = await metricsApi.getDashboard(location.id, 7);
          const dashboard = metricResponse.data;
          return {
            id: location.id,
            metrics: {
              calls_7d: dashboard.metrics.calls.current,
              directions_7d: dashboard.metrics.directions.current,
              rating: dashboard.metrics.avg_rating,
              revenue_7d: dashboard.metrics.estimated_revenue,
            },
          };
        })
      );

      const metricsByLocation = new Map<string, Location['metrics']>();
      for (const result of metricResults) {
        if (result.status === 'fulfilled') {
          metricsByLocation.set(result.value.id, result.value.metrics);
        }
      }

      setLocations(
        baseLocations.map((location: Location) => ({
          ...location,
          metrics: metricsByLocation.get(location.id),
        }))
      );
    } catch {
      console.error('Failed to fetch locations');
      toast.error('Failed to load locations');
      setLocations([]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleAddLocation = async () => {
    if (!newLocationName.trim() || !newLocationAddress.trim()) {
      toast.error('Please enter name and address');
      return;
    }

    setIsSubmitting(true);
    try {
      await locationsApi.create({
        name: newLocationName,
        address: newLocationAddress,
        phone: newLocationPhone || null,
        website_url: newLocationWebsite || null,
      });
      toast.success('Location added successfully');
      setIsAddDialogOpen(false);
      resetForm();
      fetchLocations();
    } catch {
      toast.error('Failed to add location');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteLocation = async (id: string) => {
    if (!confirm('Are you sure you want to archive this location?')) return;

    try {
      await locationsApi.delete(id);
      toast.success('Location deleted');
      fetchLocations();
    } catch {
      toast.error('Failed to delete location');
    }
  };

  const resetForm = () => {
    setNewLocationName('');
    setNewLocationAddress('');
    setNewLocationPhone('');
    setNewLocationWebsite('');
  };

  const formatSecondaryAddress = (location: Location) => {
    if (location.city && location.state) return `${location.city}, ${location.state}`;
    return location.city || location.state || null;
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <Skeleton className="h-8 w-32" />
          <Skeleton className="h-10 w-32" />
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          {[1, 2].map((i) => (
            <Card key={i}>
              <CardContent className="pt-6">
                <Skeleton className="mb-2 h-6 w-48" />
                <Skeleton className="h-4 w-64" />
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h1 className="text-2xl font-bold">Locations</h1>
          <p className="text-gray-500">Manage the business locations connected to the account</p>
        </div>
        <Button
          onClick={() => setIsAddDialogOpen(true)}
          className="bg-gradient-to-r from-violet-600 to-indigo-600"
        >
          <Plus className="mr-2 h-4 w-4" />
          Add Location
        </Button>
      </div>

      <Card className="border-slate-200 bg-slate-950 text-white">
        <CardContent className="flex flex-col gap-4 pt-6 md:flex-row md:items-center md:justify-between">
          <div>
            <Badge className="mb-2 bg-white/10 text-white hover:bg-white/10">Locations Next Best Action</Badge>
            <h2 className="text-xl font-semibold">
              {locations.length === 0 ? 'Add the first business location' : 'Open the location that needs setup attention'}
            </h2>
            <p className="mt-1 text-sm text-slate-300">
              Locations are the foundation for metrics, publishing, reviews, and reporting. Keep each location accurate before running workflows.
            </p>
          </div>
          <Button className="bg-white text-slate-950 hover:bg-slate-100" onClick={() => setIsAddDialogOpen(true)}>
            <Plus className="mr-2 h-4 w-4" />
            Add location
          </Button>
        </CardContent>
      </Card>

      {locations.length > 0 ? (
        <div className="grid gap-4 md:grid-cols-2">
          {locations.map((location) => {
            const secondaryAddress = formatSecondaryAddress(location);
            return (
              <Card key={location.id} className="transition-shadow hover:shadow-md">
                <CardContent className="pt-6">
                  <div className="mb-4 flex items-start justify-between">
                    <div className="flex items-start gap-3">
                      <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-violet-100">
                        <MapPin className="h-6 w-6 text-violet-600" />
                      </div>
                      <div>
                        <h3 className="text-lg font-semibold">{location.name}</h3>
                        {location.address && <p className="text-sm text-gray-500">{location.address}</p>}
                        <div className="mt-1 flex flex-wrap gap-2">
                          {secondaryAddress && (
                            <Badge variant="secondary">
                              {secondaryAddress}
                            </Badge>
                          )}
                          {location.instagram_status && (
                            <Badge
                              variant="outline"
                              className={
                                location.instagram_status === 'reconnect required'
                                  ? 'border-red-200 text-red-700'
                                  : location.instagram_status === 'token refresh needed'
                                    ? 'border-amber-200 text-amber-700'
                                    : location.instagram_connected
                                      ? 'border-green-200 text-green-700'
                                      : ''
                              }
                            >
                              Instagram: {location.instagram_status}
                            </Badge>
                          )}
                        </div>
                      </div>
                    </div>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon">
                          <MoreVertical className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem asChild>
                          <Link href={`/dashboard/locations/${location.id}`}>
                            <Settings className="mr-2 h-4 w-4" />
                            Settings
                          </Link>
                        </DropdownMenuItem>
                        {location.gbp_location_id && (
                          <DropdownMenuItem asChild>
                            <a
                              href={`https://business.google.com/locations`}
                              target="_blank"
                              rel="noopener noreferrer"
                            >
                              <ExternalLink className="mr-2 h-4 w-4" />
                              Google Business Profile
                            </a>
                          </DropdownMenuItem>
                        )}
                        <DropdownMenuItem
                          className="text-red-600"
                          onClick={() => handleDeleteLocation(location.id)}
                        >
                          <Trash2 className="mr-2 h-4 w-4" />
                          Delete
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>

                  <div className="mb-4 flex flex-wrap gap-4 text-sm text-gray-600">
                    {location.phone && (
                      <div className="flex items-center gap-1">
                        <Phone className="h-4 w-4" />
                        {location.phone}
                      </div>
                    )}
                    {location.website_url && (
                      <div className="flex items-center gap-1">
                        <Globe className="h-4 w-4" />
                        <a
                          href={location.website_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="hover:underline"
                        >
                          Website
                        </a>
                      </div>
                    )}
                  </div>

                  {location.metrics && (
                    <div className="grid grid-cols-2 gap-3 border-t pt-4 text-sm md:grid-cols-4">
                      <div>
                        <div className="flex items-center gap-1 font-semibold">
                          <Phone className="h-4 w-4 text-green-600" />
                          <span>{location.metrics.calls_7d}</span>
                        </div>
                        <p className="text-gray-500">Calls 7d</p>
                      </div>
                      <div>
                        <div className="flex items-center gap-1 font-semibold">
                          <Navigation className="h-4 w-4 text-blue-600" />
                          <span>{location.metrics.directions_7d}</span>
                        </div>
                        <p className="text-gray-500">Directions 7d</p>
                      </div>
                      <div>
                        <div className="flex items-center gap-1 font-semibold">
                          <Star className="h-4 w-4 text-amber-500" />
                          <span>{location.metrics.rating?.toFixed(1) ?? '-'}</span>
                        </div>
                        <p className="text-gray-500">Rating</p>
                      </div>
                      <div>
                        <div className="font-semibold">${location.metrics.revenue_7d.toLocaleString()}</div>
                        <p className="text-gray-500">Est. Revenue 7d</p>
                      </div>
                    </div>
                  )}

                  <div className="mt-4 flex items-center justify-between border-t pt-4">
                    <span className="text-sm text-gray-500">
                      Added {new Date(location.created_at).toLocaleDateString()}
                    </span>
                    <Link href={`/dashboard?location=${location.id}`}>
                      <Button variant="outline" size="sm">
                        View Dashboard
                      </Button>
                    </Link>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>No Locations Yet</CardTitle>
            <CardDescription>Add your first business location to start tracking revenue and automation impact.</CardDescription>
          </CardHeader>
          <CardContent>
            <Button onClick={() => setIsAddDialogOpen(true)}>
              <Plus className="mr-2 h-4 w-4" />
              Add Location
            </Button>
          </CardContent>
        </Card>
      )}

      <Dialog open={isAddDialogOpen} onOpenChange={setIsAddDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add New Location</DialogTitle>
            <DialogDescription>
              Add a new business location to track
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="name">Business Name *</Label>
              <Input
                id="name"
                placeholder="Joe's Pizza"
                value={newLocationName}
                onChange={(e) => setNewLocationName(e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="address">Address *</Label>
              <Input
                id="address"
                placeholder="123 Main St, New York, NY 10001"
                value={newLocationAddress}
                onChange={(e) => setNewLocationAddress(e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="phone">Phone Number</Label>
              <Input
                id="phone"
                type="tel"
                placeholder="+1 (555) 000-0000"
                value={newLocationPhone}
                onChange={(e) => setNewLocationPhone(e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="website">Website URL</Label>
              <Input
                id="website"
                type="url"
                placeholder="https://example.com"
                value={newLocationWebsite}
                onChange={(e) => setNewLocationWebsite(e.target.value)}
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setIsAddDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleAddLocation} disabled={isSubmitting}>
              {isSubmitting ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Plus className="mr-2 h-4 w-4" />
              )}
              Add Location
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
