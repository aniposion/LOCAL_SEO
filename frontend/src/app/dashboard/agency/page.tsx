'use client';
/* eslint-disable @next/next/no-img-element */

import { useEffect, useEffectEvent, useState } from 'react';
import Link from 'next/link';
import {
  Building2,
  Crown,
  Edit,
  Eye,
  Loader2,
  Mail,
  Navigation,
  Phone,
  Plus,
  Send,
  Settings,
  Shield,
  Trash2,
  Users,
} from 'lucide-react';
import { toast } from 'sonner';

import { agencyApi } from '@/lib/api';
import { getApiErrorMessage } from '@/lib/api-errors';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

interface TeamMember {
  email: string;
  name?: string;
  role: string;
  status: string;
  joined_at?: string;
  last_login?: string | null;
}

interface AgencyLocationSummary {
  id: string;
  name: string;
  address: string;
  calls_7d: number;
  directions_7d: number;
  status: string;
}

interface AgencyDashboard {
  total_locations: number;
  team_members: number;
  pending_approvals: number;
  aggregate_metrics: {
    calls_7d: number;
    directions_7d: number;
    impressions_7d: number;
    new_reviews_7d: number;
  };
  locations: AgencyLocationSummary[];
}

interface WhiteLabelSettings {
  brand_name?: string | null;
  primary_color?: string | null;
  logo_url?: string | null;
  hide_powered_by?: boolean | null;
}

function getRoleIcon(role: string) {
  switch (role) {
    case 'owner':
      return <Crown className="h-4 w-4 text-yellow-500" />;
    case 'admin':
      return <Shield className="h-4 w-4 text-violet-500" />;
    case 'manager':
      return <Settings className="h-4 w-4 text-blue-500" />;
    case 'editor':
      return <Edit className="h-4 w-4 text-emerald-500" />;
    default:
      return <Eye className="h-4 w-4 text-gray-500" />;
  }
}

export default function AgencyPage() {
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isInviteDialogOpen, setIsInviteDialogOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [dashboard, setDashboard] = useState<AgencyDashboard | null>(null);
  const [teamMembers, setTeamMembers] = useState<TeamMember[]>([]);

  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState('editor');

  const [brandName, setBrandName] = useState('');
  const [primaryColor, setPrimaryColor] = useState('#667eea');
  const [logoUrl, setLogoUrl] = useState('');
  const hasManagedLocations = (dashboard?.locations?.length ?? 0) > 0;

  const fetchData = async (manual: boolean = false) => {
    if (manual) {
      setIsRefreshing(true);
    } else {
      setIsLoading(true);
    }

    const [dashboardResult, teamResult, whiteLabelResult] = await Promise.allSettled([
      agencyApi.getDashboard(),
      agencyApi.getTeam(),
      agencyApi.getWhiteLabel(),
    ]);

    const errors: string[] = [];

    if (dashboardResult.status === 'fulfilled') {
      setDashboard(dashboardResult.value.data as AgencyDashboard);
    } else {
      setDashboard(null);
      errors.push(getApiErrorMessage(dashboardResult.reason, 'Agency dashboard could not be loaded.'));
    }

    if (teamResult.status === 'fulfilled') {
      const data = teamResult.value.data as { team_members?: TeamMember[] };
      setTeamMembers(data.team_members || []);
    } else {
      setTeamMembers([]);
      errors.push(getApiErrorMessage(teamResult.reason, 'Agency team could not be loaded.'));
    }

    if (whiteLabelResult.status === 'fulfilled') {
      const settings = whiteLabelResult.value.data as WhiteLabelSettings;
      setBrandName(settings.brand_name || '');
      setPrimaryColor(settings.primary_color || '#667eea');
      setLogoUrl(settings.logo_url || '');
    } else {
      errors.push(getApiErrorMessage(whiteLabelResult.reason, 'White-label settings could not be loaded.'));
    }

    setLoadError(errors.length > 0 ? errors.join(' ') : null);

    if (manual) {
      setIsRefreshing(false);
    } else {
      setIsLoading(false);
    }
  };

  const loadOnMount = useEffectEvent(async () => {
    await fetchData(false);
  });

  useEffect(() => {
    void loadOnMount();
  }, []);

  const handleInviteTeamMember = async () => {
    if (!inviteEmail.trim()) {
      toast.error('Enter an email address before sending the invite.');
      return;
    }

    setIsSubmitting(true);
    try {
      await agencyApi.inviteTeamMember({
        email: inviteEmail.trim(),
        role: inviteRole,
      });
      toast.success('Invitation sent.');
      setIsInviteDialogOpen(false);
      setInviteEmail('');
      await fetchData(true);
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Team invitation could not be sent.'));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRemoveTeamMember = async (email: string) => {
    if (!window.confirm(`Remove ${email} from the agency team?`)) {
      return;
    }

    setIsSubmitting(true);
    try {
      await agencyApi.removeTeamMember(email);
      toast.success('Team member removed.');
      await fetchData(true);
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Team member could not be removed.'));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSaveWhiteLabel = async () => {
    setIsSubmitting(true);
    try {
      await agencyApi.updateWhiteLabel({
        brand_name: brandName || null,
        primary_color: primaryColor || null,
        logo_url: logoUrl || null,
      });
      toast.success('White-label settings saved.');
      await fetchData(true);
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'White-label settings could not be saved.'));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSendBulkReports = async () => {
    setIsSubmitting(true);
    try {
      const response = await agencyApi.sendBulkReports(null, 'weekly');
      const data = response.data as { sent?: number; failed?: number; total?: number };
      toast.success(
        `Bulk reports completed: ${data.sent ?? 0} sent, ${data.failed ?? 0} failed, ${data.total ?? 0} total.`
      );
      await fetchData(true);
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Bulk reports could not be sent.'));
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-52" />
        <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
          {[1, 2, 3, 4].map((item) => (
            <Skeleton key={item} className="h-28 w-full" />
          ))}
        </div>
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Agency Dashboard</h1>
          <p className="text-gray-500">Manage live locations, agency team access, and white-label settings.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => void fetchData(true)} disabled={isRefreshing || isSubmitting}>
            {isRefreshing ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
            Refresh
          </Button>
          {hasManagedLocations ? (
            <Button onClick={handleSendBulkReports} disabled={isSubmitting}>
              {isSubmitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Send className="mr-2 h-4 w-4" />}
              Send Weekly Reports
            </Button>
          ) : (
            <p className="max-w-xs text-sm text-gray-500">
              Add a managed location first. Weekly report sending only appears after at least one live location is available.
            </p>
          )}
        </div>
      </div>

      <Card className="border-slate-200 bg-slate-950 text-white">
        <CardContent className="flex flex-col gap-4 pt-6 md:flex-row md:items-center md:justify-between">
          <div>
            <Badge className="mb-2 bg-white/10 text-white hover:bg-white/10">Agency Next Best Action</Badge>
            <h2 className="text-xl font-semibold">
              {hasManagedLocations ? 'Check location health before sending reports' : 'Add the first managed location'}
            </h2>
            <p className="mt-1 text-sm text-slate-300">
              Agency work should start with location status. Team and white-label settings are secondary setup areas.
            </p>
          </div>
          <Button className="bg-white text-slate-950 hover:bg-slate-100" onClick={() => void fetchData(true)} disabled={isRefreshing || isSubmitting}>
            {isRefreshing ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
            Refresh health
          </Button>
        </CardContent>
      </Card>

      {loadError ? (
        <Card className="border-amber-200 bg-amber-50">
          <CardContent className="pt-6 text-sm text-amber-900">{loadError}</CardContent>
        </Card>
      ) : null}

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <Building2 className="h-5 w-5 text-violet-500" />
              <span className="text-3xl font-bold">{dashboard?.total_locations ?? 0}</span>
            </div>
            <p className="mt-1 text-sm text-gray-500">Locations</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <Phone className="h-5 w-5 text-emerald-500" />
              <span className="text-3xl font-bold">{dashboard?.aggregate_metrics?.calls_7d ?? 0}</span>
            </div>
            <p className="mt-1 text-sm text-gray-500">Calls (7d)</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <Navigation className="h-5 w-5 text-blue-500" />
              <span className="text-3xl font-bold">{dashboard?.aggregate_metrics?.directions_7d ?? 0}</span>
            </div>
            <p className="mt-1 text-sm text-gray-500">Directions (7d)</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <Users className="h-5 w-5 text-orange-500" />
              <span className="text-3xl font-bold">{dashboard?.team_members ?? teamMembers.length}</span>
            </div>
            <p className="mt-1 text-sm text-gray-500">Team Members</p>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="locations">
        <TabsList>
          <TabsTrigger value="locations">Locations</TabsTrigger>
          <TabsTrigger value="team">Team</TabsTrigger>
          <TabsTrigger value="whitelabel">White Label</TabsTrigger>
        </TabsList>

        <TabsContent value="locations" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>Live Location Overview</CardTitle>
              <CardDescription>Current agency location performance from stored analytics and approval state.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {dashboard?.locations?.length ? (
                dashboard.locations.map((location) => (
                  <div key={location.id} className="flex flex-wrap items-center justify-between gap-4 rounded-lg border p-4">
                    <div className="space-y-1">
                      <div className="font-semibold">{location.name}</div>
                      <div className="text-sm text-gray-500">{location.address || 'Address not recorded'}</div>
                    </div>
                    <div className="flex flex-wrap items-center gap-6 text-sm">
                      <div className="text-center">
                        <div className="font-semibold text-emerald-700">{location.calls_7d}</div>
                        <div className="text-gray-500">Calls</div>
                      </div>
                      <div className="text-center">
                        <div className="font-semibold text-blue-700">{location.directions_7d}</div>
                        <div className="text-gray-500">Directions</div>
                      </div>
                      <Badge className="bg-green-100 text-green-700">{location.status}</Badge>
                      <Link href={`/dashboard/locations/${location.id}`}>
                        <Button variant="ghost" size="sm">Open location</Button>
                      </Link>
                    </div>
                  </div>
                ))
              ) : (
                <div className="rounded-lg border border-dashed p-6 text-sm text-gray-500">
                  No live agency locations are available yet.
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="team" className="mt-6">
          <Card>
            <CardHeader>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <CardTitle>Agency Team</CardTitle>
                  <CardDescription>Manage real agency collaborators and their current access roles.</CardDescription>
                </div>
                <Button onClick={() => setIsInviteDialogOpen(true)}>
                  <Plus className="mr-2 h-4 w-4" />
                  Invite Member
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              {teamMembers.length ? (
                teamMembers.map((member) => (
                  <div key={member.email} className="flex flex-wrap items-center justify-between gap-4 rounded-lg border p-4">
                    <div className="space-y-1">
                      <div className="font-semibold">{member.name || member.email}</div>
                      <div className="text-sm text-gray-500">{member.email}</div>
                      <div className="text-xs text-gray-500">
                        Joined: {member.joined_at ? new Date(member.joined_at).toLocaleDateString() : 'Pending invite'}
                      </div>
                    </div>
                    <div className="flex flex-wrap items-center gap-3">
                      <Badge className="flex items-center gap-1">
                        {getRoleIcon(member.role)}
                        {member.role}
                      </Badge>
                      <Badge variant="outline">{member.status}</Badge>
                      {member.role !== 'owner' ? (
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-red-600 hover:text-red-700"
                          onClick={() => void handleRemoveTeamMember(member.email)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      ) : null}
                    </div>
                  </div>
                ))
              ) : (
                <div className="rounded-lg border border-dashed p-6 text-sm text-gray-500">
                  No agency team members are recorded yet.
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="whitelabel" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>White-Label Settings</CardTitle>
              <CardDescription>Saved branding settings come from the live agency white-label configuration.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid gap-6 md:grid-cols-2">
                <div className="space-y-2">
                  <Label>Brand Name</Label>
                  <Input value={brandName} onChange={(event) => setBrandName(event.target.value)} placeholder="Your agency name" />
                </div>
                <div className="space-y-2">
                  <Label>Primary Color</Label>
                  <div className="flex gap-2">
                    <Input
                      type="color"
                      value={primaryColor}
                      onChange={(event) => setPrimaryColor(event.target.value)}
                      className="h-10 w-16 p-1"
                    />
                    <Input value={primaryColor} onChange={(event) => setPrimaryColor(event.target.value)} placeholder="#667eea" />
                  </div>
                </div>
                <div className="space-y-2 md:col-span-2">
                  <Label>Logo URL</Label>
                  <Input value={logoUrl} onChange={(event) => setLogoUrl(event.target.value)} placeholder="https://example.com/logo.png" />
                </div>
              </div>

              <div className="rounded-lg border p-6">
                <div className="mb-4 font-semibold">Preview</div>
                <div className="flex items-center gap-3 rounded-lg bg-gray-50 p-4">
                  <div
                    className="flex h-10 w-10 items-center justify-center rounded-lg"
                    style={{ backgroundColor: primaryColor || '#667eea' }}
                  >
                    {logoUrl ? (
                      <img src={logoUrl} alt="Agency logo" className="h-6 w-6 object-contain" />
                    ) : (
                      <Building2 className="h-5 w-5 text-white" />
                    )}
                  </div>
                  <div className="font-semibold">{brandName || 'Your brand'}</div>
                </div>
              </div>

              <Button onClick={handleSaveWhiteLabel} disabled={isSubmitting}>
                {isSubmitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                Save Settings
              </Button>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <Dialog open={isInviteDialogOpen} onOpenChange={setIsInviteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Invite Team Member</DialogTitle>
            <DialogDescription>Send a real agency invite using the current team management API.</DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Email Address</Label>
              <Input
                type="email"
                placeholder="colleague@example.com"
                value={inviteEmail}
                onChange={(event) => setInviteEmail(event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label>Role</Label>
              <Select value={inviteRole} onValueChange={setInviteRole}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="admin">Admin</SelectItem>
                  <SelectItem value="manager">Manager</SelectItem>
                  <SelectItem value="editor">Editor</SelectItem>
                  <SelectItem value="viewer">Viewer</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setIsInviteDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleInviteTeamMember} disabled={isSubmitting}>
              {isSubmitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Mail className="mr-2 h-4 w-4" />}
              Send Invitation
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
