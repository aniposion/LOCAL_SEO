'use client';

import { useEffect, useEffectEvent, useMemo, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Skeleton } from '@/components/ui/skeleton';
import {
  AlertCircle,
  Bell,
  BellRing,
  BarChart3,
  CheckCircle,
  Clock,
  FileText,
  Loader2,
  Mail,
  MessageCircle,
  Phone,
  Settings,
  Smartphone,
  Star,
  ShieldAlert,
  Trash2,
} from 'lucide-react';
import { notificationsApi } from '@/lib/api';
import { getApiErrorMessage } from '@/lib/api-errors';
import { toast } from 'sonner';

interface NotificationItem {
  id: string;
  type: string;
  title: string;
  body: string;
  url?: string;
  read: boolean;
  created_at: string;
}

interface DeliveryLogItem {
  id: string;
  notification_event_id?: string | null;
  channel: string;
  delivery_status: string;
  failure_reason?: string | null;
  attempted_at: string;
  delivered_at?: string | null;
  created_at: string;
}

interface DeliveryAuditResponse {
  logs: DeliveryLogItem[];
  total: number;
  source: string;
}

interface NotificationPreferencesState {
  new_reviews: boolean;
  content_ready: boolean;
  approval_reminders: boolean;
  weekly_reports: boolean;
  missed_calls: boolean;
  new_messages: boolean;
  performance_alerts: boolean;
  email_notifications: boolean;
  push_notifications: boolean;
  quiet_hours_start?: string | null;
  quiet_hours_end?: string | null;
  persisted: boolean;
  storage_available: boolean;
  source: string;
  note?: string | null;
}

interface NotificationHistoryResponse {
  notifications: NotificationItem[];
  unread_count: number;
  storage_available: boolean;
  source: string;
  note?: string | null;
}

interface PushAvailability {
  supported: boolean;
  configured: boolean;
  reason?: string;
}

interface PushSubscriptionInfo {
  id: string;
  device_type: string;
  created_at: string;
}

interface PushSubscriptionsResponse {
  subscriptions: PushSubscriptionInfo[];
  count: number;
}

interface DeliveryAuditPreset {
  id: string;
  name: string;
  channel: string;
  delivery_status: string;
  start_date: string;
  end_date: string;
}

const STALE_SUBSCRIPTION_DAYS = 30;
const formatDateInput = (date: Date) => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
};

const BUILT_IN_DELIVERY_AUDIT_PRESETS: DeliveryAuditPreset[] = [
  {
    id: 'last-7-days',
    name: 'Last 7 days',
    channel: 'all',
    delivery_status: 'all',
    start_date: formatDateInput(new Date(Date.now() - 6 * 24 * 60 * 60 * 1000)),
    end_date: formatDateInput(new Date()),
  },
  {
    id: 'recent-failures',
    name: 'Recent failures',
    channel: 'all',
    delivery_status: 'failed',
    start_date: formatDateInput(new Date(Date.now() - 13 * 24 * 60 * 60 * 1000)),
    end_date: formatDateInput(new Date()),
  },
  {
    id: 'push-health',
    name: 'Push health',
    channel: 'push',
    delivery_status: 'all',
    start_date: formatDateInput(new Date(Date.now() - 13 * 24 * 60 * 60 * 1000)),
    end_date: formatDateInput(new Date()),
  },
];

const DEFAULT_PREFERENCES: NotificationPreferencesState = {
  new_reviews: true,
  content_ready: true,
  approval_reminders: true,
  weekly_reports: true,
  missed_calls: true,
  new_messages: true,
  performance_alerts: true,
  email_notifications: true,
  push_notifications: true,
  quiet_hours_start: null,
  quiet_hours_end: null,
  persisted: false,
  storage_available: true,
  source: 'defaults',
  note: null,
};

const PREFERENCE_KEYS: Array<keyof Omit<NotificationPreferencesState, 'persisted' | 'storage_available' | 'source' | 'note'>> = [
  'new_reviews',
  'content_ready',
  'approval_reminders',
  'weekly_reports',
  'missed_calls',
  'new_messages',
  'performance_alerts',
  'email_notifications',
  'push_notifications',
  'quiet_hours_start',
  'quiet_hours_end',
];

export default function NotificationsPage() {
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [deletingNotificationId, setDeletingNotificationId] = useState<string | null>(null);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [historySource, setHistorySource] = useState('not_persisted');
  const [preferences, setPreferences] = useState<NotificationPreferencesState>(DEFAULT_PREFERENCES);
  const [pushAvailability, setPushAvailability] = useState<PushAvailability>({
    supported: false,
    configured: false,
  });
  const [loadError, setLoadError] = useState<string | null>(null);
  const [deliveryLogs, setDeliveryLogs] = useState<DeliveryLogItem[]>([]);
  const [deliveryTotal, setDeliveryTotal] = useState(0);
  const [deliveryAuditLoading, setDeliveryAuditLoading] = useState(false);
  const [deliveryChannelFilter, setDeliveryChannelFilter] = useState('all');
  const [deliveryStatusFilter, setDeliveryStatusFilter] = useState('all');
  const [deliveryStartDate, setDeliveryStartDate] = useState('');
  const [deliveryEndDate, setDeliveryEndDate] = useState('');
  const [savedDeliveryPresets, setSavedDeliveryPresets] = useState<DeliveryAuditPreset[]>([]);
  const [deliveryPresetName, setDeliveryPresetName] = useState('');
  const [activeDeliveryPresetId, setActiveDeliveryPresetId] = useState<string | null>(null);
  const [storedSubscriptions, setStoredSubscriptions] = useState<PushSubscriptionInfo[]>([]);
  const [subscriptionsLoading, setSubscriptionsLoading] = useState(false);
  const [removingSubscriptionId, setRemovingSubscriptionId] = useState<string | null>(null);

  useEffect(() => {
    void fetchData();
    void fetchSubscriptions();
    void fetchDeliveryAuditPresets();
  }, []);

  useEffect(() => {
    void fetchDeliveryAudit();
  }, [deliveryChannelFilter, deliveryStatusFilter, deliveryStartDate, deliveryEndDate]);

  const fetchData = async () => {
    setIsLoading(true);
    setLoadError(null);

    try {
      const [historyResult, prefsResult, vapidResult] = await Promise.allSettled([
        notificationsApi.getHistory({ limit: 50, offset: 0 }),
        notificationsApi.getPreferences(),
        notificationsApi.getVapidKey(),
      ]);

      if (historyResult.status === 'fulfilled') {
        const history = historyResult.value.data as NotificationHistoryResponse;
        setNotifications(history.notifications || []);
        setUnreadCount(history.unread_count || 0);
        setHistorySource(history.source || 'not_persisted');
      } else {
        setLoadError('Notification history could not be loaded.');
      }

      if (prefsResult.status === 'fulfilled') {
        const prefs = prefsResult.value.data as Partial<NotificationPreferencesState>;
        setPreferences({
          ...DEFAULT_PREFERENCES,
          ...prefs,
          persisted: Boolean(prefs.persisted),
          storage_available: Boolean(prefs.storage_available ?? true),
          source: prefs.source || 'defaults',
          note: prefs.note || null,
        });
      } else {
        setLoadError((prev) => prev || 'Notification preferences could not be loaded.');
      }

      if (vapidResult.status === 'fulfilled') {
        setPushAvailability({
          supported: 'Notification' in window && 'serviceWorker' in navigator,
          configured: true,
          reason: undefined,
        });
      } else {
        const detail =
          (vapidResult.reason?.response?.data?.detail as string | undefined) ||
          vapidResult.reason?.message ||
          'Push notifications are not configured on the server yet.';
        setPushAvailability({
          supported: 'Notification' in window && 'serviceWorker' in navigator,
          configured: false,
          reason: detail,
        });
      }
    } catch {
      setLoadError('Notifications could not be loaded.');
    } finally {
      setIsLoading(false);
    }
  };

  const fetchDeliveryAudit = useEffectEvent(async () => {
    setDeliveryAuditLoading(true);
    try {
      const res = await notificationsApi.getDeliveryAudit({
        limit: 100,
        offset: 0,
        channel: deliveryChannelFilter === 'all' ? undefined : deliveryChannelFilter,
        delivery_status: deliveryStatusFilter === 'all' ? undefined : deliveryStatusFilter,
        start_date: deliveryStartDate || undefined,
        end_date: deliveryEndDate || undefined,
      });
      const data = res.data as DeliveryAuditResponse;
      setDeliveryLogs(data.logs || []);
      setDeliveryTotal(data.total || 0);
    } catch {
      // Non-fatal: audit tab will show empty state
    } finally {
      setDeliveryAuditLoading(false);
    }
  });

  const fetchSubscriptions = async () => {
    setSubscriptionsLoading(true);
    try {
      const res = await notificationsApi.getSubscriptions();
      const data = res.data as PushSubscriptionsResponse;
      setStoredSubscriptions(data.subscriptions || []);
    } catch {
      // Non-fatal: subscription count will show 0
    } finally {
      setSubscriptionsLoading(false);
    }
  };

  const fetchDeliveryAuditPresets = async () => {
    try {
      const res = await notificationsApi.getDeliveryAuditPresets();
      setSavedDeliveryPresets(res.data.presets || []);
    } catch {
      setSavedDeliveryPresets([]);
    }
  };

  const pushBlockedReason = useMemo(() => {
    if (!pushAvailability.supported) {
      return 'This browser does not support push notifications.';
    }
    if (!pushAvailability.configured) {
      return pushAvailability.reason || 'Push notifications are not configured yet.';
    }
    return null;
  }, [pushAvailability]);

  const staleSubscriptions = useMemo(
    () =>
      storedSubscriptions.filter((subscription) => {
        const ageMs = Date.now() - new Date(subscription.created_at).getTime();
        return ageMs >= STALE_SUBSCRIPTION_DAYS * 24 * 60 * 60 * 1000;
      }),
    [storedSubscriptions]
  );

  const persistDeliveryPresets = (presets: DeliveryAuditPreset[]) => {
    setSavedDeliveryPresets(presets);
  };

  const applyDeliveryPreset = (preset: DeliveryAuditPreset) => {
    setActiveDeliveryPresetId(preset.id);
    setDeliveryChannelFilter(preset.channel);
    setDeliveryStatusFilter(preset.delivery_status);
    setDeliveryStartDate(preset.start_date || '');
    setDeliveryEndDate(preset.end_date || '');
  };

  const handleSaveDeliveryPreset = async () => {
    const name = deliveryPresetName.trim();
    if (!name) {
      toast.error('Enter a preset name first.');
      return;
    }
    const preset: DeliveryAuditPreset = {
      id: `custom-${Date.now()}`,
      name,
      channel: deliveryChannelFilter,
      delivery_status: deliveryStatusFilter,
      start_date: deliveryStartDate,
      end_date: deliveryEndDate,
    };
    const nextPresets = [preset, ...savedDeliveryPresets];
    try {
      const res = await notificationsApi.saveDeliveryAuditPresets(nextPresets);
      persistDeliveryPresets(res.data.presets || nextPresets);
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Failed to save delivery audit preset.'));
      return;
    }
    setActiveDeliveryPresetId(preset.id);
    setDeliveryPresetName('');
    toast.success('Delivery audit preset saved to your account.');
  };

  const handleDeleteDeliveryPreset = async (presetId: string) => {
    const nextPresets = savedDeliveryPresets.filter((preset) => preset.id !== presetId);
    try {
      const res = await notificationsApi.saveDeliveryAuditPresets(nextPresets);
      persistDeliveryPresets(res.data.presets || nextPresets);
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Failed to delete saved preset.'));
      return;
    }
    if (activeDeliveryPresetId === presetId) {
      setActiveDeliveryPresetId(null);
    }
    toast.success('Saved preset removed.');
  };

  const handleMarkAsRead = async (id: string) => {
    try {
      await notificationsApi.markAsRead(id);
      setNotifications((prev) => prev.map((n) => (n.id === id ? { ...n, read: true } : n)));
      setUnreadCount((prev) => Math.max(0, prev - 1));
      toast.success('Marked as read');
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Failed to mark notification as read'));
    }
  };

  const handleMarkAllAsRead = async () => {
    try {
      await notificationsApi.markAllAsRead();
      setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
      setUnreadCount(0);
      toast.success('All notifications marked as read');
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Failed to mark notifications as read'));
    }
  };

  const handleDeleteNotification = async (id: string) => {
    setDeletingNotificationId(id);
    try {
      await notificationsApi.delete(id);
      const removedNotification = notifications.find((notification) => notification.id === id);
      setNotifications((prev) => prev.filter((notification) => notification.id !== id));
      if (removedNotification && !removedNotification.read) {
        setUnreadCount((prev) => Math.max(0, prev - 1));
      }
      toast.success('Notification removed from inbox');
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Failed to delete notification'));
    } finally {
      setDeletingNotificationId(null);
    }
  };

  const updatePreference = <K extends keyof NotificationPreferencesState>(key: K, value: NotificationPreferencesState[K]) => {
    setPreferences((prev) => ({ ...prev, [key]: value }));
  };

  const handleSavePreferences = async () => {
    setIsSaving(true);
    try {
      const payload = Object.fromEntries(PREFERENCE_KEYS.map((key) => [key, preferences[key]]));
      const response = await notificationsApi.updatePreferences(payload);
      const saved = response.data as Partial<NotificationPreferencesState>;
      setPreferences({
        ...DEFAULT_PREFERENCES,
        ...saved,
        persisted: Boolean(saved.persisted),
        storage_available: Boolean(saved.storage_available ?? true),
        source: saved.source || 'account.settings',
        note: saved.note || null,
      });
      toast.success('Notification preferences saved');
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Failed to save notification preferences'));
    } finally {
      setIsSaving(false);
    }
  };

  const handleRequestPushPermission = async () => {
    if (pushBlockedReason) {
      toast.error(pushBlockedReason);
      return;
    }

    try {
      const permission = await Notification.requestPermission();
      if (permission !== 'granted') {
        toast.error('Push notifications were not granted by the browser');
        return;
      }

      // Fetch VAPID public key and register the push subscription.
      const vapidRes = await notificationsApi.getVapidKey();
      const vapidKey = (vapidRes.data as { public_key: string }).public_key;

      const swReg = await navigator.serviceWorker.ready;
      const pushSub = await swReg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: vapidKey,
      });

      const rawKey = pushSub.getKey('p256dh');
      const rawAuth = pushSub.getKey('auth');
      if (!rawKey || !rawAuth) {
        toast.error('Could not extract push subscription keys from browser');
        return;
      }

      const p256dh = btoa(String.fromCharCode(...new Uint8Array(rawKey)));
      const auth = btoa(String.fromCharCode(...new Uint8Array(rawAuth)));

      await notificationsApi.subscribePush({
        endpoint: pushSub.endpoint,
        p256dh_key: p256dh,
        auth_key: auth,
        device_type: 'web',
      });

      toast.success('Push subscription registered. Notifications will be delivered to this browser.');
      void fetchSubscriptions();
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Failed to enable push notifications'));
    }
  };

  const handleUnsubscribeAll = async () => {
    try {
      if ('serviceWorker' in navigator) {
        const reg = await navigator.serviceWorker.ready;
        const existing = await reg.pushManager.getSubscription();
        if (existing) {
          await existing.unsubscribe();
          await notificationsApi.unsubscribePush(existing.endpoint);
          toast.success('Unsubscribed this browser from push notifications.');
        } else {
          toast.message('This browser does not have an active push subscription right now.');
        }
      }
      void fetchSubscriptions();
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Failed to unsubscribe'));
    }
  };

  const handleRemoveStoredSubscription = async (subscriptionId: string) => {
    setRemovingSubscriptionId(subscriptionId);
    try {
      await notificationsApi.removeSubscription(subscriptionId);
      setStoredSubscriptions((prev) => prev.filter((subscription) => subscription.id !== subscriptionId));
      toast.success('Stored device removed.');
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Failed to remove stored device'));
    } finally {
      setRemovingSubscriptionId(null);
    }
  };

  const handleExportDeliveryAudit = async () => {
    try {
      const response = await notificationsApi.exportDeliveryAudit({
        channel: deliveryChannelFilter === 'all' ? undefined : deliveryChannelFilter,
        delivery_status: deliveryStatusFilter === 'all' ? undefined : deliveryStatusFilter,
        start_date: deliveryStartDate || undefined,
        end_date: deliveryEndDate || undefined,
      });
      const blob = new Blob([response.data], { type: 'text/csv' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'notification-delivery-audit.csv';
      link.click();
      window.URL.revokeObjectURL(url);
      toast.success('Delivery audit export downloaded.');
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Failed to export delivery audit.'));
    }
  };

  const getNotificationIcon = (type: string) => {
    switch (type) {
      case 'new_review': return <Star className="w-5 h-5 text-yellow-500" />;
      case 'content_ready': return <FileText className="w-5 h-5 text-violet-500" />;
      case 'weekly_report': return <BarChart3 className="w-5 h-5 text-blue-500" />;
      case 'missed_call': return <Phone className="w-5 h-5 text-green-500" />;
      case 'new_message': return <MessageCircle className="w-5 h-5 text-pink-500" />;
      default: return <Bell className="w-5 h-5 text-gray-500" />;
    }
  };

  const formatTime = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    return `${diffDays}d ago`;
  };

  const formatDateTime = (dateString: string) =>
    new Date(dateString).toLocaleString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    });

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <Card key={i}>
              <CardContent className="pt-6">
                <Skeleton className="h-16 w-full" />
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Bell className="w-6 h-6 text-violet-600" />
            Notifications
            {unreadCount > 0 && <Badge className="bg-red-500">{unreadCount}</Badge>}
          </h1>
          <p className="text-gray-500">Notification preferences and inbox history are persisted to your account.</p>
        </div>
        {unreadCount > 0 && (
          <Button variant="outline" onClick={handleMarkAllAsRead}>
            <CheckCircle className="w-4 h-4 mr-2" />
            Mark All Read
          </Button>
        )}
      </div>

      <Card className="border-slate-200 bg-slate-950 text-white">
        <CardContent className="flex flex-col gap-4 pt-6 md:flex-row md:items-center md:justify-between">
          <div>
            <Badge className="mb-2 bg-white/10 text-white hover:bg-white/10">Notification Next Best Action</Badge>
            <h2 className="text-xl font-semibold">
              {unreadCount > 0 ? `Review ${unreadCount} unread alert${unreadCount === 1 ? '' : 's'}` : 'Keep notification delivery healthy'}
            </h2>
            <p className="mt-1 text-sm text-slate-300">
              Start with Inbox. Delivery audit and settings are available in tabs when you need troubleshooting detail.
            </p>
          </div>
          {unreadCount > 0 ? (
            <Button className="bg-white text-slate-950 hover:bg-slate-100" onClick={handleMarkAllAsRead}>
              Mark all read
            </Button>
          ) : (
            <Badge className="w-fit bg-emerald-100 text-emerald-700 hover:bg-emerald-100">Inbox clear</Badge>
          )}
        </CardContent>
      </Card>

      {loadError && (
        <Card className="border-yellow-200 bg-yellow-50">
          <CardContent className="pt-6 flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-yellow-700 mt-0.5" />
            <div>
              <p className="font-medium text-yellow-900">Partial load</p>
              <p className="text-sm text-yellow-800">{loadError}</p>
            </div>
          </CardContent>
        </Card>
      )}

      <Tabs defaultValue="inbox">
        <TabsList>
          <TabsTrigger value="inbox">
            Inbox
            {unreadCount > 0 && <Badge variant="secondary" className="ml-2">{unreadCount}</Badge>}
          </TabsTrigger>
          <TabsTrigger value="delivery-audit">Delivery Audit</TabsTrigger>
          <TabsTrigger value="settings">Settings</TabsTrigger>
        </TabsList>

        <TabsContent value="inbox" className="mt-6 space-y-4">
          <Card className="border-dashed border-gray-200">
            <CardContent className="pt-6">
              <div className="flex items-start gap-3">
                <BellRing className="w-5 h-5 text-gray-400 mt-0.5" />
                <div className="space-y-1">
                  <p className="font-medium">Inbox storage status</p>
                  <p className="text-sm text-gray-600">
                    Notification history is stored for reference. You can mark items as read or remove stale inbox entries here. Delivery audit history stays separate.
                  </p>
                  <div className="flex flex-wrap items-center gap-2 pt-1">
                    <Badge variant="default">History storage available</Badge>
                    <Badge variant="secondary">Inbox items removable</Badge>
                    <Badge variant="outline">Source: {historySource}</Badge>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {notifications.length > 0 ? (
            notifications.map((notification) => (
              <Card
                key={notification.id}
                className={`transition-colors ${!notification.read ? 'bg-violet-50 border-violet-200' : ''}`}
              >
                <CardContent className="pt-4">
                  <div className="flex items-start gap-4">
                    <div className="p-2 bg-white rounded-lg shadow-sm">
                      {getNotificationIcon(notification.type)}
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <h3 className="font-semibold">{notification.title}</h3>
                        {!notification.read && <div className="w-2 h-2 bg-violet-500 rounded-full" />}
                      </div>
                      <p className="text-gray-600 text-sm mt-1">{notification.body}</p>
                      <p className="text-gray-400 text-xs mt-2 flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {formatTime(notification.created_at)}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      {notification.read ? (
                        <Badge variant="outline">Read</Badge>
                      ) : (
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleMarkAsRead(notification.id)}
                        >
                          Mark Read
                        </Button>
                      )}
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => void handleDeleteNotification(notification.id)}
                        disabled={deletingNotificationId === notification.id}
                        aria-label="Delete notification"
                      >
                        {deletingNotificationId === notification.id ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <Trash2 className="h-4 w-4" />
                        )}
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))
          ) : (
            <Card>
              <CardContent className="pt-6 text-center py-12">
                <BellRing className="w-12 h-12 mx-auto text-gray-300 mb-4" />
                <p className="text-gray-500">No notifications stored yet</p>
                <p className="text-sm text-gray-400 mt-2">
                  Once notifications are created, they will appear here.
                </p>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="delivery-audit" className="mt-6 space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <ShieldAlert className="w-5 h-5" />
                Delivery Audit Log
              </CardTitle>
              <CardDescription>
                Every delivery attempt — inbox, push, email, SMS, Slack — is recorded here with its outcome and any failure reason. No fabricated successes.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap items-center gap-2 mb-4">
                <Badge variant="outline">Filtered attempts: {deliveryTotal}</Badge>
                <Badge variant="outline">Source: database</Badge>
                {(deliveryStartDate || deliveryEndDate) && (
                  <Badge variant="outline">
                    Range: {deliveryStartDate || '...'} to {deliveryEndDate || '...'}
                  </Badge>
                )}
              </div>
              <div className="mb-4 space-y-3 rounded-lg border bg-gray-50 p-4">
                <div className="text-sm font-medium text-gray-700">Filter delivery attempts</div>
                <div className="space-y-2">
                  <div className="text-xs font-medium uppercase tracking-wide text-gray-500">Channel</div>
                  <div className="flex flex-wrap gap-2">
                    {['all', 'inbox', 'push', 'email', 'sms', 'slack'].map((channel) => (
                      <Button
                        key={channel}
                        type="button"
                        size="sm"
                        variant={deliveryChannelFilter === channel ? 'default' : 'outline'}
                        onClick={() => {
                          setActiveDeliveryPresetId(null);
                          setDeliveryChannelFilter(channel);
                        }}
                        className="capitalize"
                      >
                        {channel === 'all' ? 'All channels' : channel}
                      </Button>
                    ))}
                  </div>
                </div>
                <div className="space-y-2">
                  <div className="text-xs font-medium uppercase tracking-wide text-gray-500">Status</div>
                  <div className="flex flex-wrap gap-2">
                    {['all', 'delivered', 'failed', 'unavailable', 'skipped'].map((status) => (
                      <Button
                        key={status}
                        type="button"
                        size="sm"
                        variant={deliveryStatusFilter === status ? 'default' : 'outline'}
                        onClick={() => {
                          setActiveDeliveryPresetId(null);
                          setDeliveryStatusFilter(status);
                        }}
                        className="capitalize"
                      >
                        {status === 'all' ? 'All statuses' : status}
                      </Button>
                    ))}
                  </div>
                </div>
                <div className="grid gap-3 md:grid-cols-2">
                  <div className="space-y-2">
                    <div className="text-xs font-medium uppercase tracking-wide text-gray-500">Start date</div>
                    <input
                      type="date"
                      value={deliveryStartDate}
                      onChange={(event) => {
                        setActiveDeliveryPresetId(null);
                        setDeliveryStartDate(event.target.value);
                      }}
                      className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm"
                    />
                  </div>
                  <div className="space-y-2">
                    <div className="text-xs font-medium uppercase tracking-wide text-gray-500">End date</div>
                    <input
                      type="date"
                      value={deliveryEndDate}
                      onChange={(event) => {
                        setActiveDeliveryPresetId(null);
                        setDeliveryEndDate(event.target.value);
                      }}
                      className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm"
                    />
                  </div>
                </div>
                <div className="space-y-3 rounded-lg border bg-white p-4">
                  <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                    <div>
                      <div className="text-xs font-medium uppercase tracking-wide text-gray-500">Saved presets</div>
                      <p className="mt-1 text-sm text-gray-600">
                        Reuse common audit views. Saved presets follow your account settings.
                      </p>
                    </div>
                    <div className="flex w-full flex-col gap-2 md:w-auto md:flex-row">
                      <input
                        type="text"
                        value={deliveryPresetName}
                        onChange={(event) => setDeliveryPresetName(event.target.value)}
                        placeholder="Preset name"
                        className="w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm md:w-48"
                      />
                      <Button type="button" variant="outline" onClick={handleSaveDeliveryPreset}>
                        Save current preset
                      </Button>
                    </div>
                  </div>
                  <div className="space-y-2">
                    <div className="text-xs font-medium uppercase tracking-wide text-gray-500">Built-in</div>
                    <div className="flex flex-wrap gap-2">
                      {BUILT_IN_DELIVERY_AUDIT_PRESETS.map((preset) => (
                        <Button
                          key={preset.id}
                          type="button"
                          size="sm"
                          variant={activeDeliveryPresetId === preset.id ? 'default' : 'outline'}
                          onClick={() => applyDeliveryPreset(preset)}
                        >
                          {preset.name}
                        </Button>
                      ))}
                    </div>
                  </div>
                  {savedDeliveryPresets.length > 0 && (
                    <div className="space-y-2">
                      <div className="text-xs font-medium uppercase tracking-wide text-gray-500">Saved by you</div>
                      <div className="flex flex-wrap gap-2">
                        {savedDeliveryPresets.map((preset) => (
                          <div key={preset.id} className="flex items-center gap-2 rounded-md border bg-slate-50 px-2 py-2">
                            <Button
                              type="button"
                              size="sm"
                              variant={activeDeliveryPresetId === preset.id ? 'default' : 'ghost'}
                              onClick={() => applyDeliveryPreset(preset)}
                            >
                              {preset.name}
                            </Button>
                            <Button
                              type="button"
                              size="sm"
                              variant="ghost"
                              onClick={() => handleDeleteDeliveryPreset(preset.id)}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button type="button" variant="outline" onClick={handleExportDeliveryAudit}>
                    Export CSV
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => {
                      setActiveDeliveryPresetId(null);
                      setDeliveryChannelFilter('all');
                      setDeliveryStatusFilter('all');
                      setDeliveryStartDate('');
                      setDeliveryEndDate('');
                    }}
                  >
                    Reset filters
                  </Button>
                </div>
              </div>
              {deliveryAuditLoading ? (
                <div className="space-y-2">
                  {[1, 2, 3].map((i) => <Skeleton key={i} className="h-10 w-full" />)}
                </div>
              ) : deliveryLogs.length === 0 ? (
                <p className="text-sm text-gray-500 py-4 text-center">
                  No delivery attempts recorded yet. Send a test notification to generate audit entries.
                </p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b text-left text-gray-500">
                        <th className="pb-2 pr-4 font-medium">Channel</th>
                        <th className="pb-2 pr-4 font-medium">Status</th>
                        <th className="pb-2 pr-4 font-medium">Attempted</th>
                        <th className="pb-2 font-medium">Failure reason</th>
                      </tr>
                    </thead>
                    <tbody>
                      {deliveryLogs.map((log) => (
                        <tr key={log.id} className="border-b last:border-0">
                          <td className="py-2 pr-4">
                            <Badge variant="outline" className="capitalize">{log.channel}</Badge>
                          </td>
                          <td className="py-2 pr-4">
                            <Badge
                              variant={
                                log.delivery_status === 'delivered'
                                  ? 'default'
                                  : log.delivery_status === 'unavailable'
                                  ? 'secondary'
                                  : 'destructive'
                              }
                              className="capitalize"
                            >
                              {log.delivery_status}
                            </Badge>
                          </td>
                          <td className="py-2 pr-4 text-gray-500 whitespace-nowrap">
                            {formatTime(log.attempted_at)}
                          </td>
                          <td className="py-2 text-gray-500 text-xs max-w-xs truncate">
                            {log.failure_reason || <span className="text-gray-300">—</span>}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="settings" className="mt-6 space-y-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Smartphone className="w-5 h-5" />
                Browser Push
              </CardTitle>
              <CardDescription>
                Push notifications are only available when the backend is configured for delivery.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                <div>
                  <p className="font-medium">Browser support</p>
                  <p className="text-sm text-gray-500">
                    {pushAvailability.supported
                      ? 'This browser supports notifications.'
                      : 'This browser does not support notifications.'}
                  </p>
                </div>
                <Badge variant={pushAvailability.supported ? 'default' : 'secondary'}>
                  {pushAvailability.supported ? 'Supported' : 'Unsupported'}
                </Badge>
              </div>
              <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                <div>
                  <p className="font-medium">Backend push availability</p>
                  <p className="text-sm text-gray-500">
                    {pushAvailability.configured
                      ? 'Push credentials are configured.'
                      : pushBlockedReason || 'Push delivery is not configured yet.'}
                  </p>
                </div>
                <Badge variant={pushAvailability.configured ? 'default' : 'destructive'}>
                  {pushAvailability.configured ? 'Configured' : 'Unavailable'}
                </Badge>
              </div>
              <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
                <div>
                  <p className="font-medium">Stored subscriptions</p>
                  <p className="text-sm text-gray-500">
                    {subscriptionsLoading
                      ? 'Loading…'
                      : storedSubscriptions.length === 0
                      ? 'No push subscriptions registered yet.'
                      : `${storedSubscriptions.length} device${storedSubscriptions.length > 1 ? 's' : ''} registered.`}
                  </p>
                </div>
                <Badge variant={storedSubscriptions.length > 0 ? 'default' : 'secondary'}>
                  {storedSubscriptions.length} registered
                </Badge>
              </div>
              {staleSubscriptions.length > 0 && (
                <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
                  {staleSubscriptions.length} device{staleSubscriptions.length > 1 ? 's look' : ' looks'} older than{' '}
                  {STALE_SUBSCRIPTION_DAYS} days. Review older devices if teammates changed laptops or browsers.
                </div>
              )}
              <div className="flex gap-3 flex-wrap">
                {pushAvailability.supported && pushAvailability.configured ? (
                  <Button onClick={handleRequestPushPermission}>
                    Enable Push for This Browser
                  </Button>
                ) : (
                  <div className="rounded-lg border border-dashed border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                    {!pushAvailability.supported
                      ? 'This browser cannot register push subscriptions.'
                      : 'Server push setup is still pending. Enable Push will appear here after VAPID credentials are configured.'}
                  </div>
                )}
                {storedSubscriptions.length > 0 && (
                  <Button variant="outline" onClick={handleUnsubscribeAll}>
                    Unsubscribe This Browser
                  </Button>
                )}
              </div>
              {!pushAvailability.configured && (
                <div className="rounded-lg border border-yellow-200 bg-yellow-50 p-4 text-sm text-yellow-800">
                  VAPID credentials are not configured on the server yet. This browser cannot register a push subscription until push is configured.
                </div>
              )}
              {storedSubscriptions.length > 0 && (
                <div className="rounded-lg border border-gray-200 bg-white">
                  <div className="flex items-center justify-between border-b px-4 py-3">
                    <div>
                      <p className="font-medium">Registered devices</p>
                      <p className="text-sm text-gray-500">
                        Remove stale browsers or old laptops if they should no longer receive push.
                      </p>
                    </div>
                    <Badge variant="outline">{storedSubscriptions.length} devices</Badge>
                  </div>
                  <div className="divide-y">
                    {storedSubscriptions.map((subscription) => {
                      const isStale = staleSubscriptions.some((item) => item.id === subscription.id);
                      return (
                        <div
                          key={subscription.id}
                          className="flex flex-col gap-3 px-4 py-3 md:flex-row md:items-center md:justify-between"
                        >
                          <div>
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="font-medium capitalize">{subscription.device_type || 'web'}</span>
                              {isStale && (
                                <Badge variant="secondary">Older device to review</Badge>
                              )}
                            </div>
                            <p className="text-sm text-gray-500">
                              Registered {formatDateTime(subscription.created_at)}
                            </p>
                          </div>
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={removingSubscriptionId === subscription.id}
                            onClick={() => handleRemoveStoredSubscription(subscription.id)}
                          >
                            {removingSubscriptionId === subscription.id ? (
                              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                            ) : (
                              <Trash2 className="mr-2 h-4 w-4" />
                            )}
                            Remove device
                          </Button>
                        </div>
                      );
                    })}
                  </div>
                  <div className="border-t bg-gray-50 px-4 py-3 text-xs text-gray-500">
                    Stale push endpoints are also cleaned up automatically when delivery returns an expired endpoint response.
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Mail className="w-5 h-5" />
                Email Notifications
              </CardTitle>
              <CardDescription>
                Choose which emails you want to receive.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <Label>Email Notifications</Label>
                  <p className="text-sm text-gray-500">Receive notifications via email</p>
                </div>
                <button
                  type="button"
                  onClick={() => updatePreference('email_notifications', !preferences.email_notifications)}
                  className={`relative w-12 h-6 rounded-full transition-colors ${
                    preferences.email_notifications ? 'bg-violet-600' : 'bg-gray-300'
                  }`}
                >
                  <span
                    className={`absolute top-1 w-4 h-4 bg-white rounded-full transition-transform ${
                      preferences.email_notifications ? 'translate-x-7' : 'translate-x-1'
                    }`}
                  />
                </button>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Settings className="w-5 h-5" />
                Notification Types
              </CardTitle>
              <CardDescription>
                These preferences are saved in your account settings.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {[
                { key: 'new_reviews', label: 'New Reviews', desc: 'When customers leave reviews', icon: Star },
                { key: 'content_ready', label: 'Content Ready', desc: 'When AI generates new content', icon: FileText },
                { key: 'approval_reminders', label: 'Approval Reminders', desc: 'Reminders for pending approvals', icon: CheckCircle },
                { key: 'weekly_reports', label: 'Weekly Reports', desc: 'Weekly performance summaries', icon: BarChart3 },
                { key: 'missed_calls', label: 'Missed Calls', desc: 'When calls are missed', icon: Phone },
                { key: 'new_messages', label: 'New Messages', desc: 'Instagram DMs and comments', icon: MessageCircle },
                { key: 'performance_alerts', label: 'Performance Alerts', desc: 'Significant metric changes', icon: BarChart3 },
              ].map((item) => (
                <div key={item.key} className="flex items-center justify-between py-2">
                  <div className="flex items-center gap-3">
                    <item.icon className="w-5 h-5 text-gray-400" />
                    <div>
                      <Label>{item.label}</Label>
                      <p className="text-sm text-gray-500">{item.desc}</p>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => updatePreference(item.key as keyof NotificationPreferencesState, !preferences[item.key as keyof NotificationPreferencesState] as boolean)}
                    className={`relative w-12 h-6 rounded-full transition-colors ${
                      preferences[item.key as keyof NotificationPreferencesState] ? 'bg-violet-600' : 'bg-gray-300'
                    }`}
                  >
                    <span
                      className={`absolute top-1 w-4 h-4 bg-white rounded-full transition-transform ${
                        preferences[item.key as keyof NotificationPreferencesState] ? 'translate-x-7' : 'translate-x-1'
                      }`}
                    />
                  </button>
                </div>
              ))}

              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <Label htmlFor="quiet-hours-start">Quiet hours start</Label>
                  <input
                    id="quiet-hours-start"
                    type="time"
                    value={preferences.quiet_hours_start || ''}
                    onChange={(event) => updatePreference('quiet_hours_start', event.target.value || null)}
                    className="mt-2 w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <Label htmlFor="quiet-hours-end">Quiet hours end</Label>
                  <input
                    id="quiet-hours-end"
                    type="time"
                    value={preferences.quiet_hours_end || ''}
                    onChange={(event) => updatePreference('quiet_hours_end', event.target.value || null)}
                    className="mt-2 w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                  />
                </div>
              </div>

              <div className="rounded-lg border border-gray-200 bg-gray-50 p-4 text-sm text-gray-600">
                <div className="flex items-center gap-2">
                  <ShieldAlert className="w-4 h-4 text-gray-500" />
                  <span>
                    Preferences are stored in account settings and can be edited later.
                  </span>
                </div>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <Badge variant={preferences.persisted ? 'default' : 'secondary'}>
                    {preferences.persisted ? 'Saved' : 'Unsaved defaults'}
                  </Badge>
                  <Badge variant="outline">Source: {preferences.source}</Badge>
                </div>
                {preferences.note && <p className="mt-2 text-xs text-gray-500">{preferences.note}</p>}
              </div>
            </CardContent>
          </Card>

          <Button onClick={handleSavePreferences} disabled={isSaving}>
            {isSaving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <CheckCircle className="w-4 h-4 mr-2" />}
            Save Preferences
          </Button>
        </TabsContent>
      </Tabs>
    </div>
  );
}
