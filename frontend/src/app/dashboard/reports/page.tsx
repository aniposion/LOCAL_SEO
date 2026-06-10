'use client';

import { useEffect, useEffectEvent, useMemo, useState } from 'react';
import type { LucideIcon } from 'lucide-react';
import {
  ArrowLeft,
  CheckCircle,
  Download,
  FileText,
  Loader2,
  Mail,
  Navigation,
  Phone,
  Printer,
  RefreshCw,
  Sparkles,
  Star,
  TrendingDown,
  TrendingUp,
} from 'lucide-react';
import { toast } from 'sonner';

import { extractCollectionPayload, locationsApi, reportsApi } from '@/lib/api';
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

interface LocationOption {
  id: string;
  name: string;
}

interface WeeklyReportSummary {
  calls_total: number;
  calls_delta: number;
  calls_percent: number;
  directions_total: number;
  directions_delta: number;
  directions_percent: number;
  website_clicks_total: number;
  new_reviews: number;
  avg_rating?: number | string | null;
  estimated_revenue: number | string;
  top_day: string;
  highlights: string[];
}

interface WeeklyReport {
  id: string;
  location_id: string;
  report_week: string;
  report_type: string;
  summary: WeeklyReportSummary;
  pdf_url?: string | null;
  sent_at?: string | null;
  sent_to: string[];
  created_at: string;
}

async function fetchReportsForLocation(locationId: string): Promise<WeeklyReport[]> {
  const response = await reportsApi.list(locationId, 20);
  const data = response.data as { items?: WeeklyReport[] };
  return data.items || [];
}

function toNumber(value: number | string | null | undefined): number {
  if (typeof value === 'number') {
    return value;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function getCurrentWeekMonday(): string {
  const now = new Date();
  const day = now.getDay();
  const diff = day === 0 ? -6 : 1 - day;
  const monday = new Date(now);
  monday.setHours(0, 0, 0, 0);
  monday.setDate(now.getDate() + diff);
  return monday.toISOString().slice(0, 10);
}

function formatReportWeek(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleDateString();
}

function MetricBox({
  icon: Icon,
  label,
  value,
  change,
  iconColor,
}: {
  icon: LucideIcon;
  label: string;
  value: number | string;
  change?: number;
  iconColor: string;
}) {
  return (
    <div className="rounded-lg bg-gray-50 p-4">
      <div className="mb-2 flex items-center gap-2">
        <Icon className={`h-5 w-5 ${iconColor}`} />
        <span className="text-sm text-gray-500">{label}</span>
      </div>
      <div className="flex items-end gap-2">
        <span className="text-2xl font-bold">{value}</span>
        {change !== undefined ? (
          <span className={`flex items-center text-sm ${change >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            {change >= 0 ? <TrendingUp className="mr-1 h-3 w-3" /> : <TrendingDown className="mr-1 h-3 w-3" />}
            {Math.abs(change).toFixed(1)}%
          </span>
        ) : null}
      </div>
    </div>
  );
}

export default function ReportsPage() {
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [locations, setLocations] = useState<LocationOption[]>([]);
  const [selectedLocationId, setSelectedLocationId] = useState('');
  const [reports, setReports] = useState<WeeklyReport[]>([]);
  const [selectedReport, setSelectedReport] = useState<WeeklyReport | null>(null);

  const [sendDialogOpen, setSendDialogOpen] = useState(false);
  const [reportToSend, setReportToSend] = useState<WeeklyReport | null>(null);
  const [sendEmailAddresses, setSendEmailAddresses] = useState('');
  const activeLocationId = selectedLocationId || locations[0]?.id || '';

  const selectedLocationName = useMemo(
    () => locations.find((location) => location.id === activeLocationId)?.name || 'Selected location',
    [locations, activeLocationId]
  );
  const hasLocations = locations.length > 0;

  const loadLocations = async () => {
    const response = await locationsApi.list();
    const items = extractCollectionPayload<LocationOption>(response.data, 'locations');
    const normalized = items.map((item: { id: string; name: string }) => ({
      id: item.id,
      name: item.name,
    }));

    setLocations(normalized);
    if (normalized.length > 0) {
      setSelectedLocationId((current) => current || normalized[0].id);
    } else {
      setSelectedLocationId('');
      setReports([]);
      setSelectedReport(null);
    }
  };

  const loadOnMount = useEffectEvent(async () => {
    setIsLoading(true);
    try {
      await loadLocations();
      setLoadError(null);
    } catch (error) {
      setLoadError(getApiErrorMessage(error, 'Reports setup could not be loaded.'));
      setLocations([]);
      setSelectedLocationId('');
      setReports([]);
      setSelectedReport(null);
    } finally {
      setIsLoading(false);
    }
  });

  useEffect(() => {
    void loadOnMount();
  }, []);

  const refreshReports = async () => {
    if (!activeLocationId) {
      return;
    }

    setIsRefreshing(true);
    try {
      const items = await fetchReportsForLocation(activeLocationId);
      setReports(items);
      setSelectedReport((current) => {
        if (!current) {
          return null;
        }
        return items.find((item) => item.id === current.id) || null;
      });
      setLoadError(null);
    } catch (error) {
      setLoadError(getApiErrorMessage(error, 'Reports could not be loaded for this location.'));
      setReports([]);
      setSelectedReport(null);
    } finally {
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    if (!activeLocationId) {
      return;
    }

    let isCancelled = false;

    const syncReports = async () => {
      setIsRefreshing(true);
      try {
        const items = await fetchReportsForLocation(activeLocationId);
        if (isCancelled) {
          return;
        }

        setReports(items);
        setSelectedReport((current) => {
          if (!current) {
            return null;
          }
          return items.find((item) => item.id === current.id) || null;
        });
        setLoadError(null);
      } catch (error) {
        if (isCancelled) {
          return;
        }

        setLoadError(getApiErrorMessage(error, 'Reports could not be loaded for this location.'));
        setReports([]);
        setSelectedReport(null);
      } finally {
        if (!isCancelled) {
          setIsRefreshing(false);
        }
      }
    };

    void syncReports();

    return () => {
      isCancelled = true;
    };
  }, [activeLocationId]);

  const handleGenerateReport = async () => {
    if (!activeLocationId) {
      toast.error('Choose a location before generating a report.');
      return;
    }

    setIsGenerating(true);
    try {
      const response = await reportsApi.generate(activeLocationId, getCurrentWeekMonday());
      const report = response.data as WeeklyReport;
      setReports((current) => [report, ...current.filter((item) => item.id !== report.id)]);
      setSelectedReport(report);
      toast.success('Weekly report generated from live metrics.');
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Weekly report could not be generated.'));
    } finally {
      setIsGenerating(false);
    }
  };

  const handleDownload = (report: WeeklyReport) => {
    if (!report.pdf_url) {
      toast.error('This report does not have a generated PDF yet.');
      return;
    }
    window.open(report.pdf_url, '_blank', 'noopener,noreferrer');
  };

  const openSendDialog = (report: WeeklyReport) => {
    setReportToSend(report);
    setSendEmailAddresses(report.sent_to.join(', '));
    setSendDialogOpen(true);
  };

  const handleSendReport = async () => {
    if (!reportToSend) {
      return;
    }

    const emails = sendEmailAddresses
      .split(',')
      .map((value) => value.trim())
      .filter(Boolean);

    if (emails.length === 0) {
      toast.error('Enter at least one email address.');
      return;
    }

    setIsSending(true);
    try {
      const response = await reportsApi.send(reportToSend.id, emails);
      const updated = response.data as WeeklyReport;
      setReports((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      setSelectedReport((current) => (current?.id === updated.id ? updated : current));
      setSendDialogOpen(false);
      toast.success('Report email sent.');
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Report email could not be sent.'));
    } finally {
      setIsSending(false);
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-10 w-52" />
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Reports</h1>
          <p className="text-gray-500">Review live weekly performance reports instead of demo summaries.</p>
        </div>
        {hasLocations ? (
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => void refreshReports()} disabled={isRefreshing}>
              {isRefreshing ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCw className="mr-2 h-4 w-4" />}
              Refresh
            </Button>
            <Button onClick={handleGenerateReport} disabled={isGenerating}>
              {isGenerating ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}
              Generate Weekly Report
            </Button>
          </div>
        ) : (
          <p className="max-w-sm text-sm text-gray-500">
            Connect a location first. Refresh and weekly report generation only appear when a live location is available.
          </p>
        )}
      </div>

      <Card className="border-slate-200 bg-slate-950 text-white">
        <CardContent className="flex flex-col gap-4 pt-6 md:flex-row md:items-center md:justify-between">
          <div>
            <Badge className="mb-2 bg-white/10 text-white hover:bg-white/10">Reports Next Best Action</Badge>
            <h2 className="text-xl font-semibold">Generate one weekly report when the business needs proof</h2>
            <p className="mt-1 text-sm text-slate-300">
              Reports are for proving progress. Pick a location, generate the report, then email or download only after reviewing the summary.
            </p>
          </div>
          {hasLocations ? (
            <Button className="bg-white text-slate-950 hover:bg-slate-100" onClick={handleGenerateReport} disabled={isGenerating}>
              {isGenerating ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}
              Generate report
            </Button>
          ) : null}
        </CardContent>
      </Card>

      {loadError ? (
        <Card className="border-amber-200 bg-amber-50">
          <CardContent className="pt-6 text-sm text-amber-900">{loadError}</CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Location Scope</CardTitle>
          <CardDescription>Select a live location to load its stored weekly reports.</CardDescription>
        </CardHeader>
        <CardContent className="max-w-md">
          {locations.length ? (
            <Select value={activeLocationId} onValueChange={setSelectedLocationId}>
              <SelectTrigger>
                <SelectValue placeholder="Select location" />
              </SelectTrigger>
              <SelectContent>
                {locations.map((location) => (
                  <SelectItem key={location.id} value={location.id}>
                    {location.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          ) : (
            <div className="rounded-lg border border-dashed p-4 text-sm text-gray-500">
              No locations are available yet, so reports cannot be generated.
            </div>
          )}
        </CardContent>
      </Card>

      {selectedReport ? (
        <div className="space-y-6">
          <Button variant="ghost" onClick={() => setSelectedReport(null)}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to all reports
          </Button>

          <Card>
            <CardHeader>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <Badge className="bg-blue-100 text-blue-700">{selectedReport.report_type}</Badge>
                  <CardTitle className="mt-2">
                    Week of {formatReportWeek(selectedReport.report_week)}
                  </CardTitle>
                  <CardDescription>
                    {selectedLocationName} - generated {new Date(selectedReport.created_at).toLocaleDateString()}
                  </CardDescription>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button variant="outline" size="sm" onClick={() => window.print()}>
                    <Printer className="mr-2 h-4 w-4" />
                    Print
                  </Button>
                  <Button variant="outline" size="sm" onClick={() => openSendDialog(selectedReport)}>
                    <Mail className="mr-2 h-4 w-4" />
                    Email
                  </Button>
                  {selectedReport.pdf_url ? (
                    <Button size="sm" onClick={() => handleDownload(selectedReport)}>
                      <Download className="mr-2 h-4 w-4" />
                      PDF
                    </Button>
                  ) : (
                    <div className="flex items-center rounded-md border border-dashed px-3 py-2 text-xs text-gray-500">
                      PDF is still generating for this report.
                    </div>
                  )}
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
                <MetricBox
                  icon={Phone}
                  label="Calls"
                  value={selectedReport.summary.calls_total}
                  change={selectedReport.summary.calls_percent}
                  iconColor="text-emerald-500"
                />
                <MetricBox
                  icon={Navigation}
                  label="Directions"
                  value={selectedReport.summary.directions_total}
                  change={selectedReport.summary.directions_percent}
                  iconColor="text-blue-500"
                />
                <MetricBox
                  icon={Star}
                  label="New Reviews"
                  value={selectedReport.summary.new_reviews}
                  iconColor="text-amber-500"
                />
                <MetricBox
                  icon={FileText}
                  label="Website Clicks"
                  value={selectedReport.summary.website_clicks_total}
                  iconColor="text-violet-500"
                />
              </div>

              <div className="grid gap-4 lg:grid-cols-2">
                <Card className="border-dashed">
                  <CardHeader>
                    <CardTitle className="text-base">Highlights</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    {selectedReport.summary.highlights.length ? (
                      selectedReport.summary.highlights.map((highlight, index) => (
                        <div key={`${selectedReport.id}-highlight-${index}`} className="flex items-start gap-2 rounded-lg bg-green-50 p-3 text-sm">
                          <CheckCircle className="mt-0.5 h-4 w-4 text-green-600" />
                          <span>{highlight}</span>
                        </div>
                      ))
                    ) : (
                      <div className="rounded-lg border border-dashed p-4 text-sm text-gray-500">
                        No highlights were generated for this report.
                      </div>
                    )}
                  </CardContent>
                </Card>

                <Card className="border-dashed">
                  <CardHeader>
                    <CardTitle className="text-base">Summary</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2 text-sm text-gray-600">
                    <div>Top day: {selectedReport.summary.top_day}</div>
                    <div>Average rating: {toNumber(selectedReport.summary.avg_rating).toFixed(1)}</div>
                    <div>Estimated revenue: ${toNumber(selectedReport.summary.estimated_revenue).toFixed(2)}</div>
                    <div>Sent at: {selectedReport.sent_at ? new Date(selectedReport.sent_at).toLocaleString() : 'Not sent yet'}</div>
                    <div>Sent to: {selectedReport.sent_to.length ? selectedReport.sent_to.join(', ') : 'No recipients recorded yet'}</div>
                  </CardContent>
                </Card>
              </div>
            </CardContent>
          </Card>
        </div>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>Weekly Report History</CardTitle>
            <CardDescription>Stored reports for the selected location.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {reports.length ? (
              reports.map((report) => (
                <button
                  key={report.id}
                  type="button"
                  className="w-full rounded-lg border p-4 text-left transition hover:bg-gray-50"
                  onClick={() => setSelectedReport(report)}
                >
                  <div className="flex flex-wrap items-center justify-between gap-4">
                    <div className="space-y-1">
                      <div className="font-semibold">Week of {formatReportWeek(report.report_week)}</div>
                      <div className="text-sm text-gray-500">
                        Generated {new Date(report.created_at).toLocaleDateString()}
                      </div>
                    </div>
                    <div className="flex flex-wrap items-center gap-6 text-sm">
                      <div className="text-center">
                        <div className="font-semibold text-emerald-700">{report.summary.calls_total}</div>
                        <div className="text-gray-500">Calls</div>
                      </div>
                      <div className="text-center">
                        <div className="font-semibold text-blue-700">{report.summary.directions_total}</div>
                        <div className="text-gray-500">Directions</div>
                      </div>
                      <Badge variant="outline">{report.sent_to.length ? 'Sent' : 'Draft'}</Badge>
                    </div>
                  </div>
                </button>
              ))
            ) : (
              <div className="rounded-lg border border-dashed p-6 text-sm text-gray-500">
                No weekly reports have been generated yet for this location.
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <Dialog open={sendDialogOpen} onOpenChange={setSendDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Email Weekly Report</DialogTitle>
            <DialogDescription>
              Enter one or more email addresses separated by commas.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2 py-2">
            <Label>Recipients</Label>
            <Input
              value={sendEmailAddresses}
              onChange={(event) => setSendEmailAddresses(event.target.value)}
              placeholder="owner@example.com, manager@example.com"
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setSendDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleSendReport} disabled={isSending}>
              {isSending ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Mail className="mr-2 h-4 w-4" />}
              Send Report
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
