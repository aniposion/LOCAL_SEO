'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { Bell, ExternalLink, KeyRound, Loader2, Mail, MessageSquare, Shield, Smartphone, User } from 'lucide-react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { getApiErrorMessage } from '@/lib/api-errors';
import { api } from '@/lib/api';
import { useAuthStore } from '@/store/auth';

type ApprovalChannel = 'email' | 'sms' | 'both';

export default function SettingsPage() {
  const { user, setUser } = useAuthStore();

  const [profileSaving, setProfileSaving] = useState(false);
  const [notificationSaving, setNotificationSaving] = useState(false);
  const [passwordSaving, setPasswordSaving] = useState(false);

  const [fullName, setFullName] = useState(user?.full_name || '');
  const [companyName, setCompanyName] = useState(user?.company_name || '');
  const [phone, setPhone] = useState(user?.phone || '');
  const [notificationChannel, setNotificationChannel] = useState<ApprovalChannel>(
    (user?.notification_channel as ApprovalChannel) || 'email'
  );

  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');

  useEffect(() => {
    setFullName(user?.full_name || '');
    setCompanyName(user?.company_name || '');
    setPhone(user?.phone || '');
    setNotificationChannel((user?.notification_channel as ApprovalChannel) || 'email');
  }, [user]);

  const handleUpdateProfile = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setProfileSaving(true);

    try {
      const response = await api.patch('/auth/me', {
        full_name: fullName.trim() || null,
        company_name: companyName.trim() || null,
        phone: phone.trim() || null,
      });

      setUser({
        id: response.data.id,
        email: response.data.email,
        full_name: response.data.full_name || undefined,
        company_name: response.data.company_name || undefined,
        role: response.data.role,
        notification_channel: user?.notification_channel || notificationChannel,
        phone: response.data.phone || undefined,
      });
      toast.success('Profile updated successfully.');
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Failed to update profile.'));
    } finally {
      setProfileSaving(false);
    }
  };

  const handleUpdateNotifications = async () => {
    setNotificationSaving(true);

    try {
      const response = await api.put('/approval/notification-preferences', {
        channel: notificationChannel,
        phone_number: phone.trim() || undefined,
      });

      setUser(
        user
          ? {
              ...user,
              notification_channel: response.data.notification_channel,
              phone: response.data.phone || user.phone,
            }
          : null
      );
      toast.success('Approval notification preferences updated.');
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Failed to update notification preferences.'));
    } finally {
      setNotificationSaving(false);
    }
  };

  const handleChangePassword = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    if (!currentPassword || !newPassword || !confirmPassword) {
      toast.error('Fill in all password fields.');
      return;
    }
    if (newPassword !== confirmPassword) {
      toast.error('New password and confirmation do not match.');
      return;
    }

    setPasswordSaving(true);
    try {
      await api.post('/auth/change-password', {
        current_password: currentPassword,
        new_password: newPassword,
      });
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      toast.success('Password updated successfully.');
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Failed to update password.'));
    } finally {
      setPasswordSaving(false);
    }
  };

  return (
    <div className="max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Settings</h1>
        <p className="text-gray-500">Manage your account details and approval workflow defaults.</p>
      </div>

      <Card className="border-slate-200 bg-gradient-to-br from-slate-50 to-white">
        <CardContent className="space-y-4 p-6">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Next Best Action</p>
            <h2 className="mt-2 text-xl font-semibold text-slate-950">Confirm who receives approval alerts</h2>
            <p className="mt-2 text-sm text-slate-600">
              Keeping your name, company, phone, and approval channel current prevents publish delays when content needs
              a quick yes or no.
            </p>
          </div>
          <div className="flex flex-col gap-3 sm:flex-row">
            <Button asChild>
              <a href="#profile-settings">Update Profile</a>
            </Button>
            <Button asChild variant="outline">
              <a href="#notification-settings">Set Approval Alerts</a>
            </Button>
          </div>
        </CardContent>
      </Card>

      <Tabs defaultValue="profile">
        <TabsList>
          <TabsTrigger value="profile">
            <User className="mr-2 h-4 w-4" />
            Profile
          </TabsTrigger>
          <TabsTrigger value="notifications">
            <Bell className="mr-2 h-4 w-4" />
            Notifications
          </TabsTrigger>
          <TabsTrigger value="security">
            <Shield className="mr-2 h-4 w-4" />
            Security
          </TabsTrigger>
        </TabsList>

        <TabsContent value="profile" className="mt-6">
          <Card id="profile-settings">
            <CardHeader>
              <CardTitle>Profile Information</CardTitle>
              <CardDescription>
                Update the contact details used for approvals, billing context, and missed-call workflows.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleUpdateProfile} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="email">Email</Label>
                  <Input id="email" type="email" value={user?.email || ''} disabled className="bg-gray-50" />
                  <p className="text-xs text-gray-500">Email changes are not self-serve in this build.</p>
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="full-name">Full Name</Label>
                    <Input
                      id="full-name"
                      value={fullName}
                      onChange={(event) => setFullName(event.target.value)}
                      placeholder="Jordan Lee"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="company-name">Company Name</Label>
                    <Input
                      id="company-name"
                      value={companyName}
                      onChange={(event) => setCompanyName(event.target.value)}
                      placeholder="North Shore Dental"
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="phone">Phone Number</Label>
                  <Input
                    id="phone"
                    type="tel"
                    value={phone}
                    onChange={(event) => setPhone(event.target.value)}
                    placeholder="+1 (555) 000-0000"
                  />
                  <p className="text-xs text-gray-500">
                    Used for SMS approval requests and missed-call text back flows.
                  </p>
                </div>

                <Button type="submit" disabled={profileSaving}>
                  {profileSaving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                  Save Changes
                </Button>
              </form>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="notifications" className="mt-6 space-y-6">
          <Card id="notification-settings">
            <CardHeader>
              <CardTitle>Approval Notifications</CardTitle>
              <CardDescription>
                Set the default channel for content approval requests and reminders.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {[
                {
                  id: 'email' as const,
                  icon: Mail,
                  title: 'Email Only',
                  description: 'Send approval requests by email.',
                },
                {
                  id: 'sms' as const,
                  icon: Smartphone,
                  title: 'SMS Only',
                  description: 'Send approval requests by text message.',
                },
                {
                  id: 'both' as const,
                  icon: MessageSquare,
                  title: 'Email + SMS',
                  description: 'Send approval requests through both channels.',
                },
              ].map((option) => (
                <button
                  key={option.id}
                  type="button"
                  onClick={() => setNotificationChannel(option.id)}
                  className={`flex w-full items-center gap-4 rounded-lg border-2 p-4 text-left transition-colors ${
                    notificationChannel === option.id
                      ? 'border-violet-500 bg-violet-50'
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                >
                  <div
                    className={`flex h-10 w-10 items-center justify-center rounded-lg ${
                      notificationChannel === option.id ? 'bg-violet-100' : 'bg-gray-100'
                    }`}
                  >
                    <option.icon
                      className={`h-5 w-5 ${
                        notificationChannel === option.id ? 'text-violet-600' : 'text-gray-500'
                      }`}
                    />
                  </div>
                  <div className="flex-1">
                    <p className="font-medium">{option.title}</p>
                    <p className="text-sm text-gray-500">{option.description}</p>
                  </div>
                </button>
              ))}

              {(notificationChannel === 'sms' || notificationChannel === 'both') && !phone.trim() ? (
                <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
                  Add a phone number in the Profile tab before using SMS approvals.
                </div>
              ) : null}

              <Button onClick={handleUpdateNotifications} disabled={notificationSaving}>
                {notificationSaving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                Save Approval Defaults
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Notification Center</CardTitle>
              <CardDescription>
                Detailed inbox preferences, push subscriptions, quiet hours, and delivery audit live in the Notifications page.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="text-sm text-gray-600">
                Use the dedicated page for performance alerts, push setup, inbox history, and notification delivery audit.
              </div>
              <Button asChild variant="outline">
                <Link href="/dashboard/notifications">
                  Open Notifications
                  <ExternalLink className="h-4 w-4" />
                </Link>
              </Button>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="security" className="mt-6 space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Change Password</CardTitle>
              <CardDescription>
                Update your password using the live authenticated account endpoint.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleChangePassword} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="current-password">Current Password</Label>
                  <Input
                    id="current-password"
                    type="password"
                    value={currentPassword}
                    onChange={(event) => setCurrentPassword(event.target.value)}
                    placeholder="Current password"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="new-password">New Password</Label>
                  <Input
                    id="new-password"
                    type="password"
                    value={newPassword}
                    onChange={(event) => setNewPassword(event.target.value)}
                    placeholder="New password"
                  />
                  <p className="text-xs text-gray-500">
                    Use at least 8 characters with uppercase, lowercase, and a number.
                  </p>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="confirm-password">Confirm New Password</Label>
                  <Input
                    id="confirm-password"
                    type="password"
                    value={confirmPassword}
                    onChange={(event) => setConfirmPassword(event.target.value)}
                    placeholder="Confirm new password"
                  />
                </div>
                <Button type="submit" disabled={passwordSaving}>
                  {passwordSaving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <KeyRound className="mr-2 h-4 w-4" />}
                  Update Password
                </Button>
              </form>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Connected Apps</CardTitle>
              <CardDescription>
                OAuth and publishing connections are managed from the dedicated Integrations workspace.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="text-sm text-gray-600">
                This page no longer shows static connected/disconnected placeholders. Open Integrations for live Google and social connection status.
              </div>
              <Button asChild variant="outline">
                <Link href="/dashboard/integrations">
                  Open Integrations
                  <ExternalLink className="h-4 w-4" />
                </Link>
              </Button>
            </CardContent>
          </Card>

          <Card className="border-amber-200">
            <CardHeader>
              <CardTitle>Account Lifecycle</CardTitle>
              <CardDescription>
                Destructive account actions are intentionally not presented as self-serve controls here.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="text-sm text-gray-600">
                If you need an account closure or billing review, use the contact workflow so support can verify subscription and refund state first.
              </div>
              <Button asChild variant="outline">
                <Link href="/contact">
                  Contact Support
                  <ExternalLink className="h-4 w-4" />
                </Link>
              </Button>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
