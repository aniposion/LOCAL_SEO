'use client';

import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  DollarSign,
  Clock,
  TrendingUp,
  RefreshCw,
  Calendar,
  Sparkles,
  PhoneCall,
  MessageSquareQuote,
  MapPinned,
  Save,
} from 'lucide-react';
import { revenueApi, roiApi } from '@/lib/api/ai-features';
import { extractCollectionPayload, locationsApi } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Progress } from '@/components/ui/progress';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { toast } from 'sonner';

type LocationOption = {
  id: string;
  name: string;
};

type RevenueFormState = {
  business_type: string;
  currency: string;
  average_order_value: string;
  gross_margin_percent: string;
  call_to_booking_rate: string;
  booking_to_visit_rate: string;
  visit_to_sale_rate: string;
  missed_call_recovery_rate: string;
  review_to_conversion_lift_percent: string;
  owner_hourly_value: string;
};

type RevenuePreset = {
  id: string;
  label: string;
  description: string;
  guidance: string;
  values: RevenueFormState;
};

const revenuePresets: RevenuePreset[] = [
  {
    id: 'restaurant',
    label: 'Restaurant',
    description: 'High call volume, fast booking cycles, and repeat visits.',
    guidance: 'Good for restaurants, cafes, and other appointment-light local businesses.',
    values: {
      business_type: 'restaurant',
      currency: 'USD',
      average_order_value: '45',
      gross_margin_percent: '65',
      call_to_booking_rate: '30',
      booking_to_visit_rate: '85',
      visit_to_sale_rate: '70',
      missed_call_recovery_rate: '30',
      review_to_conversion_lift_percent: '2',
      owner_hourly_value: '40',
    },
  },
  {
    id: 'med_spa',
    label: 'Med Spa',
    description: 'Higher ticket, lead-driven, and sensitive to follow-up speed.',
    guidance: 'Good for med spas, aesthetics, and premium wellness services.',
    values: {
      business_type: 'med spa',
      currency: 'USD',
      average_order_value: '220',
      gross_margin_percent: '70',
      call_to_booking_rate: '45',
      booking_to_visit_rate: '80',
      visit_to_sale_rate: '55',
      missed_call_recovery_rate: '20',
      review_to_conversion_lift_percent: '4',
      owner_hourly_value: '60',
    },
  },
  {
    id: 'dental',
    label: 'Dental',
    description: 'High trust, high value, and strong return from missed-call recovery.',
    guidance: 'Good for dental offices, orthodontics, and general clinics.',
    values: {
      business_type: 'dental',
      currency: 'USD',
      average_order_value: '450',
      gross_margin_percent: '65',
      call_to_booking_rate: '55',
      booking_to_visit_rate: '85',
      visit_to_sale_rate: '70',
      missed_call_recovery_rate: '25',
      review_to_conversion_lift_percent: '3',
      owner_hourly_value: '75',
    },
  },
  {
    id: 'auto_shop',
    label: 'Auto Shop',
    description: 'Service-heavy, phone-first, and driven by call follow-up.',
    guidance: 'Good for repair shops, tire shops, and maintenance businesses.',
    values: {
      business_type: 'auto shop',
      currency: 'USD',
      average_order_value: '180',
      gross_margin_percent: '50',
      call_to_booking_rate: '40',
      booking_to_visit_rate: '75',
      visit_to_sale_rate: '65',
      missed_call_recovery_rate: '30',
      review_to_conversion_lift_percent: '2',
      owner_hourly_value: '55',
    },
  },
  {
    id: 'salon',
    label: 'Salon',
    description: 'Appointment-based with repeat customers and review sensitivity.',
    guidance: 'Good for salons, barbers, and beauty service businesses.',
    values: {
      business_type: 'salon',
      currency: 'USD',
      average_order_value: '95',
      gross_margin_percent: '60',
      call_to_booking_rate: '50',
      booking_to_visit_rate: '85',
      visit_to_sale_rate: '60',
      missed_call_recovery_rate: '30',
      review_to_conversion_lift_percent: '3',
      owner_hourly_value: '35',
    },
  },
  {
    id: 'clinic',
    label: 'Clinic',
    description: 'High trust, high volume, and dependent on quick response and reviews.',
    guidance: 'Good for urgent care, family practice, and specialty clinics.',
    values: {
      business_type: 'clinic',
      currency: 'USD',
      average_order_value: '260',
      gross_margin_percent: '55',
      call_to_booking_rate: '55',
      booking_to_visit_rate: '90',
      visit_to_sale_rate: '65',
      missed_call_recovery_rate: '25',
      review_to_conversion_lift_percent: '3',
      owner_hourly_value: '65',
    },
  },
];

export default function ROIPage() {
  const queryClient = useQueryClient();
  const [locationId, setLocationId] = useState<string | null>(null);
  const [locations, setLocations] = useState<LocationOption[]>([]);
  const [timeRange] = useState<'week' | 'month' | 'quarter'>('month');
  const [locationsLoading, setLocationsLoading] = useState(true);
  const [selectedPresetId, setSelectedPresetId] = useState<string | null>(null);
  const [formState, setFormState] = useState<RevenueFormState>({
    business_type: '',
    currency: 'USD',
    average_order_value: '150',
    gross_margin_percent: '30',
    call_to_booking_rate: '35',
    booking_to_visit_rate: '80',
    visit_to_sale_rate: '90',
    missed_call_recovery_rate: '20',
    review_to_conversion_lift_percent: '3',
    owner_hourly_value: '50',
  });

  useEffect(() => {
    const loadLocations = async () => {
      try {
        const response = await locationsApi.list();
        const items = extractCollectionPayload<LocationOption>(response.data, 'locations');
        setLocations(items);
        setLocationId((current) =>
          current && items.some((location) => location.id === current)
            ? current
            : (items[0]?.id ?? null)
        );
      } catch (error) {
        console.error('Failed to load locations for ROI dashboard:', error);
        setLocations([]);
        setLocationId(null);
      } finally {
        setLocationsLoading(false);
      }
    };

    void loadLocations();
  }, []);

  const activeLocationId = locationId || locations[0]?.id || null;

  const { data: report, isLoading } = useQuery({
    queryKey: ['roi-report', activeLocationId, timeRange],
    queryFn: () => roiApi.getReport({ location_id: activeLocationId || '' }),
    enabled: !!activeLocationId,
    refetchInterval: 60000,
  });

  const { data: revenueProfile, isLoading: profileLoading } = useQuery({
    queryKey: ['revenue-profile', activeLocationId],
    queryFn: () => revenueApi.getProfile(activeLocationId || ''),
    enabled: !!activeLocationId,
  });

  const { data: timeSavedData } = useQuery({
    queryKey: ['roi-time-series', activeLocationId, 'time_saved'],
    queryFn: () =>
      roiApi.getTimeSeries({
        location_id: activeLocationId || '',
        metric: 'time_saved',
        days_back: 30,
      }),
    enabled: !!activeLocationId,
  });

  const { data: reviewResponsesData } = useQuery({
    queryKey: ['roi-time-series', activeLocationId, 'review_responses'],
    queryFn: () =>
      roiApi.getTimeSeries({
        location_id: activeLocationId || '',
        metric: 'review_responses',
        days_back: 30,
      }),
    enabled: !!activeLocationId,
  });

  useEffect(() => {
    if (!revenueProfile) {
      return;
    }

    setFormState({
      business_type: revenueProfile.business_type || '',
      currency: revenueProfile.currency || 'USD',
      average_order_value: String(revenueProfile.average_order_value ?? 150),
      gross_margin_percent: String(revenueProfile.gross_margin_percent ?? 30),
      call_to_booking_rate: String(revenueProfile.call_to_booking_rate ?? 35),
      booking_to_visit_rate: String(revenueProfile.booking_to_visit_rate ?? 80),
      visit_to_sale_rate: String(revenueProfile.visit_to_sale_rate ?? 90),
      missed_call_recovery_rate: String(revenueProfile.missed_call_recovery_rate ?? 20),
      review_to_conversion_lift_percent: String(revenueProfile.review_to_conversion_lift_percent ?? 3),
      owner_hourly_value: String(revenueProfile.owner_hourly_value ?? 50),
    });
    const matchedPreset = revenuePresets.find(
      (preset) => preset.id === (revenueProfile.business_type || '').trim().toLowerCase().replace(/\s+/g, '_')
    );
    setSelectedPresetId(matchedPreset?.id ?? null);
  }, [revenueProfile]);

  const updateRevenueProfile = useMutation({
    mutationFn: async () => {
      if (!activeLocationId) {
        throw new Error('Location is required');
      }

      return revenueApi.updateProfile(activeLocationId, {
        business_type: formState.business_type || undefined,
        currency: formState.currency,
        average_order_value: Number(formState.average_order_value),
        gross_margin_percent: Number(formState.gross_margin_percent),
        call_to_booking_rate: Number(formState.call_to_booking_rate),
        booking_to_visit_rate: Number(formState.booking_to_visit_rate),
        visit_to_sale_rate: Number(formState.visit_to_sale_rate),
        missed_call_recovery_rate: Number(formState.missed_call_recovery_rate),
        review_to_conversion_lift_percent: Number(formState.review_to_conversion_lift_percent),
        owner_hourly_value: Number(formState.owner_hourly_value),
      });
    },
    onSuccess: async () => {
      toast.success('Revenue assumptions updated');
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['revenue-profile', activeLocationId] }),
        queryClient.invalidateQueries({ queryKey: ['roi-report', activeLocationId, timeRange] }),
      ]);
    },
    onError: () => {
      toast.error('Failed to update revenue assumptions');
    },
  });

  const locationName = useMemo(
    () => locations.find((location) => location.id === activeLocationId)?.name,
    [activeLocationId, locations]
  );

  const updateField = (field: keyof typeof formState, value: string) => {
    setSelectedPresetId(null);
    setFormState((current) => ({ ...current, [field]: value }));
  };

  const applyPreset = (preset: RevenuePreset) => {
    setFormState(preset.values);
    setSelectedPresetId(preset.id);
    toast.success(`${preset.label} preset applied`);
  };

  const selectedPreset = revenuePresets.find((preset) => preset.id === selectedPresetId) ?? null;

  if (locationsLoading || (activeLocationId && isLoading)) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <RefreshCw className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  if (!activeLocationId) {
    return (
      <div className="container mx-auto py-8">
        <Card>
          <CardHeader>
            <CardTitle>No location available</CardTitle>
            <CardDescription>
              Create or connect a business location before viewing ROI.
            </CardDescription>
          </CardHeader>
        </Card>
      </div>
    );
  }

  const chartData =
    timeSavedData?.dates.map((date, index) => ({
      date: new Date(date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
      hours: timeSavedData.values[index],
      responses: reviewResponsesData?.values[index] || 0,
    })) || [];

  const activityData = [
    {
      name: 'Review Responses',
      count: report?.breakdown.time_saved.review_responses.count || 0,
      hours: Math.round(((report?.breakdown.time_saved.review_responses.minutes_saved || 0) / 60) * 10) / 10,
      money: Math.round(((report?.breakdown.time_saved.review_responses.minutes_saved || 0) / 60) * (report?.hourly_value || 50)),
    },
    {
      name: 'Auto Posts',
      count: report?.breakdown.time_saved.automated_posts.count || 0,
      hours: Math.round(((report?.breakdown.time_saved.automated_posts.minutes_saved || 0) / 60) * 10) / 10,
      money: Math.round(((report?.breakdown.time_saved.automated_posts.minutes_saved || 0) / 60) * (report?.hourly_value || 50)),
    },
    {
      name: 'Competitor Analysis',
      count: report?.breakdown.time_saved.competitor_analyses.count || 0,
      hours: Math.round(((report?.breakdown.time_saved.competitor_analyses.minutes_saved || 0) / 60) * 10) / 10,
      money: Math.round(((report?.breakdown.time_saved.competitor_analyses.minutes_saved || 0) / 60) * (report?.hourly_value || 50)),
    },
    {
      name: 'Social Cards',
      count: report?.breakdown.time_saved.social_cards.count || 0,
      hours: Math.round(((report?.breakdown.time_saved.social_cards.minutes_saved || 0) / 60) * 10) / 10,
      money: Math.round(((report?.breakdown.time_saved.social_cards.minutes_saved || 0) / 60) * (report?.hourly_value || 50)),
    },
  ];

  const grossProfitTotal =
    (report?.revenue_projection.estimated_gross_profit_from_calls || 0) +
    (report?.revenue_projection.missed_call_recovery_gross_profit || 0) +
    (report?.revenue_projection.review_uplift_gross_profit || 0);

  const totalRevenueInfluenced =
    (report?.revenue_projection.estimated_revenue_from_calls || 0) +
    (report?.revenue_projection.missed_call_recovery_revenue || 0) +
    (report?.revenue_projection.review_uplift_revenue || 0);

  return (
    <div className="container mx-auto py-8 space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">ROI Dashboard</h1>
          <p className="text-muted-foreground mt-2">
            Track your return on investment from AI automation{locationName ? ` for ${locationName}` : ''}
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm">
            <Calendar className="h-4 w-4 mr-2" />
            This Month
          </Button>
        </div>
      </div>

      <Card className="border-slate-200 bg-slate-950 text-white">
        <CardContent className="flex flex-col gap-4 pt-6 md:flex-row md:items-center md:justify-between">
          <div>
            <Badge className="mb-2 bg-white/10 text-white hover:bg-white/10">ROI Next Best Action</Badge>
            <h2 className="text-xl font-semibold">Confirm the revenue assumptions before trusting ROI</h2>
            <p className="mt-1 text-sm text-slate-300">
              The charts are only useful after lead value, conversion rate, and owner time assumptions match the business.
            </p>
          </div>
          <Badge className="w-fit bg-white/10 text-white hover:bg-white/10">
            {locationName || 'Selected location'}
          </Badge>
        </CardContent>
      </Card>

      {locations.length > 1 && (
        <div className="flex flex-wrap gap-2">
          {locations.map((location) => (
            <Button
              key={location.id}
              type="button"
              variant={location.id === activeLocationId ? 'default' : 'outline'}
              size="sm"
              onClick={() => setLocationId(location.id)}
            >
              {location.name}
            </Button>
          ))}
        </div>
      )}

      <Card className="bg-gradient-to-r from-primary/10 to-primary/5 border-primary/20">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-primary" />
            AI Impact Summary
          </CardTitle>
          <CardDescription>
            Measured activity comes from connected logs. Revenue, ROI, and lift are estimated from the assumptions below.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-lg leading-relaxed">{report?.summary_message}</p>
        </CardContent>
      </Card>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <div className="space-y-1">
              <CardTitle className="text-sm font-medium">Time Saved</CardTitle>
              <Badge variant="outline" className="text-[10px] uppercase tracking-wide">
                Estimated
              </Badge>
            </div>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{report?.total_hours_saved.toFixed(1)} hrs</div>
            <p className="text-xs text-muted-foreground mt-2">This month</p>
            <Progress value={Math.min((report?.total_hours_saved || 0) * 5, 100)} className="mt-2 h-2" />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <div className="space-y-1">
              <CardTitle className="text-sm font-medium">Money Saved</CardTitle>
              <Badge variant="outline" className="text-[10px] uppercase tracking-wide">
                Estimated
              </Badge>
            </div>
            <DollarSign className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">${report?.total_money_saved.toFixed(0)}</div>
            <p className="text-xs text-muted-foreground mt-2">At ${report?.hourly_value.toFixed(0)}/hour</p>
            <Progress value={Math.min((report?.total_money_saved || 0) / 10, 100)} className="mt-2 h-2" />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <div className="space-y-1">
              <CardTitle className="text-sm font-medium">ROI</CardTitle>
              <Badge variant="outline" className="text-[10px] uppercase tracking-wide">
                Estimated
              </Badge>
            </div>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">{report?.roi_percentage.toFixed(0)}%</div>
            <p className="text-xs text-muted-foreground mt-2">Return on investment</p>
            <Progress value={Math.min(report?.roi_percentage || 0, 100)} className="mt-2 h-2" />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <div className="space-y-1">
              <CardTitle className="text-sm font-medium">Revenue Influenced</CardTitle>
              <Badge variant="outline" className="text-[10px] uppercase tracking-wide">
                Estimated
              </Badge>
            </div>
            <DollarSign className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-emerald-600">${totalRevenueInfluenced.toFixed(0)}</div>
            <p className="text-xs text-muted-foreground mt-2">Calls, recovery, and review uplift</p>
            <Progress value={Math.min(totalRevenueInfluenced / 10, 100)} className="mt-2 h-2" />
          </CardContent>
        </Card>
      </div>

      <Card className="border-dashed">
        <CardHeader>
          <CardTitle>Start with a preset</CardTitle>
          <CardDescription>
            Pick an industry starting point, then adjust the assumptions with your own numbers before saving.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-2">
            <Badge variant="secondary">Assumptions</Badge>
            <Badge variant="outline">Measured inputs come from connected activity logs</Badge>
            <Badge variant="outline">Outputs below are estimated</Badge>
          </div>
          {selectedPreset && (
            <div className="rounded-lg border border-primary/20 bg-primary/5 px-4 py-3 text-sm text-muted-foreground">
              <span className="font-medium text-foreground">Applied preset:</span> {selectedPreset.label}. {selectedPreset.guidance}
            </div>
          )}
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {revenuePresets.map((preset) => {
              const isSelected = selectedPresetId === preset.id;

              return (
                <button
                  key={preset.id}
                  type="button"
                  onClick={() => applyPreset(preset)}
                  className={`rounded-xl border p-4 text-left transition-all hover:-translate-y-0.5 hover:shadow-md ${
                    isSelected
                      ? 'border-primary bg-primary/5 shadow-sm'
                      : 'border-border bg-background'
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="font-semibold">{preset.label}</h3>
                        <Badge variant={isSelected ? 'default' : 'outline'} className="text-[10px] uppercase tracking-wide">
                          Start here
                        </Badge>
                      </div>
                      <p className="mt-2 text-sm text-muted-foreground">{preset.description}</p>
                    </div>
                  </div>
                  <p className="mt-3 text-xs text-muted-foreground">{preset.guidance}</p>
                </button>
              );
            })}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Revenue Assumptions</CardTitle>
          <CardDescription>
            Adjust the inputs used to estimate bookings, sales, margin, and owner time value. These are assumptions, not measured values.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="rounded-lg border bg-muted/30 p-4 text-sm text-muted-foreground">
            <p className="font-medium text-foreground">How to read this section</p>
            <p className="mt-1">
              Assumption fields are editable starting points. Connected activity logs provide measured counts, and the ROI numbers below are estimated from both.
            </p>
          </div>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <Label htmlFor="business_type">Business Type</Label>
                <Badge variant="outline" className="text-[10px] uppercase tracking-wide">
                  Preset
                </Badge>
              </div>
              <Input
                id="business_type"
                value={formState.business_type}
                onChange={(event) => updateField('business_type', event.target.value)}
                placeholder="Cafe, salon, dental clinic"
              />
            </div>
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <Label htmlFor="currency">Currency</Label>
                <Badge variant="outline" className="text-[10px] uppercase tracking-wide">
                  Assumption
                </Badge>
              </div>
              <Input
                id="currency"
                value={formState.currency}
                onChange={(event) => updateField('currency', event.target.value.toUpperCase())}
                maxLength={10}
              />
            </div>
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <Label htmlFor="owner_hourly_value">Owner Hourly Value</Label>
                <Badge variant="outline" className="text-[10px] uppercase tracking-wide">
                  Assumption
                </Badge>
              </div>
              <Input
                id="owner_hourly_value"
                type="number"
                min="0"
                step="0.01"
                value={formState.owner_hourly_value}
                onChange={(event) => updateField('owner_hourly_value', event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <Label htmlFor="average_order_value">Average Order Value</Label>
                <Badge variant="outline" className="text-[10px] uppercase tracking-wide">
                  Assumption
                </Badge>
              </div>
              <Input
                id="average_order_value"
                type="number"
                min="0"
                step="0.01"
                value={formState.average_order_value}
                onChange={(event) => updateField('average_order_value', event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <Label htmlFor="gross_margin_percent">Gross Margin %</Label>
                <Badge variant="outline" className="text-[10px] uppercase tracking-wide">
                  Assumption
                </Badge>
              </div>
              <Input
                id="gross_margin_percent"
                type="number"
                min="0"
                max="100"
                step="0.01"
                value={formState.gross_margin_percent}
                onChange={(event) => updateField('gross_margin_percent', event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <Label htmlFor="call_to_booking_rate">Call to Booking %</Label>
                <Badge variant="outline" className="text-[10px] uppercase tracking-wide">
                  Assumption
                </Badge>
              </div>
              <Input
                id="call_to_booking_rate"
                type="number"
                min="0"
                max="100"
                step="0.01"
                value={formState.call_to_booking_rate}
                onChange={(event) => updateField('call_to_booking_rate', event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <Label htmlFor="booking_to_visit_rate">Booking to Visit %</Label>
                <Badge variant="outline" className="text-[10px] uppercase tracking-wide">
                  Assumption
                </Badge>
              </div>
              <Input
                id="booking_to_visit_rate"
                type="number"
                min="0"
                max="100"
                step="0.01"
                value={formState.booking_to_visit_rate}
                onChange={(event) => updateField('booking_to_visit_rate', event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <Label htmlFor="visit_to_sale_rate">Visit to Sale %</Label>
                <Badge variant="outline" className="text-[10px] uppercase tracking-wide">
                  Assumption
                </Badge>
              </div>
              <Input
                id="visit_to_sale_rate"
                type="number"
                min="0"
                max="100"
                step="0.01"
                value={formState.visit_to_sale_rate}
                onChange={(event) => updateField('visit_to_sale_rate', event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <Label htmlFor="missed_call_recovery_rate">Missed Call Recovery %</Label>
                <Badge variant="outline" className="text-[10px] uppercase tracking-wide">
                  Assumption
                </Badge>
              </div>
              <Input
                id="missed_call_recovery_rate"
                type="number"
                min="0"
                max="100"
                step="0.01"
                value={formState.missed_call_recovery_rate}
                onChange={(event) => updateField('missed_call_recovery_rate', event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <Label htmlFor="review_to_conversion_lift_percent">Review Conversion Lift %</Label>
                <Badge variant="outline" className="text-[10px] uppercase tracking-wide">
                  Assumption
                </Badge>
              </div>
              <Input
                id="review_to_conversion_lift_percent"
                type="number"
                min="0"
                max="100"
                step="0.01"
                value={formState.review_to_conversion_lift_percent}
                onChange={(event) => updateField('review_to_conversion_lift_percent', event.target.value)}
              />
            </div>
          </div>

          <div className="flex items-center justify-between border-t pt-4">
            <p className="text-sm text-muted-foreground">
              {profileLoading ? 'Loading current assumptions...' : 'Changes are applied to ROI after save.'}
            </p>
            <Button
              type="button"
              onClick={() => updateRevenueProfile.mutate()}
              disabled={!activeLocationId || profileLoading || updateRevenueProfile.isPending}
            >
              {updateRevenueProfile.isPending ? (
                <>
                  <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                  Saving
                </>
              ) : (
                <>
                  <Save className="mr-2 h-4 w-4" />
                  Save Assumptions
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <div className="space-y-1">
              <CardTitle className="text-sm font-medium">Call Funnel</CardTitle>
              <Badge variant="outline" className="text-[10px] uppercase tracking-wide">
                Mixed
              </Badge>
            </div>
            <PhoneCall className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="text-2xl font-bold">{report?.revenue_projection.calls.total_calls || 0}</div>
            <p className="text-xs text-muted-foreground">
              {report?.revenue_projection.estimated_bookings_from_calls || 0} bookings, {report?.revenue_projection.estimated_sales_from_calls || 0} sales
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <div className="space-y-1">
              <CardTitle className="text-sm font-medium">Digital Intent</CardTitle>
              <Badge variant="outline" className="text-[10px] uppercase tracking-wide">
                Mixed
              </Badge>
            </div>
            <MapPinned className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="text-2xl font-bold">{report?.revenue_projection.digital_intent.digital_intent_events || 0}</div>
            <p className="text-xs text-muted-foreground">
              ${(report?.revenue_projection.digital_intent.estimated_digital_revenue || 0).toFixed(0)} estimated from directions and website clicks
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <div className="space-y-1">
              <CardTitle className="text-sm font-medium">Review Uplift</CardTitle>
              <Badge variant="outline" className="text-[10px] uppercase tracking-wide">
                Mixed
              </Badge>
            </div>
            <MessageSquareQuote className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="text-2xl font-bold">${(report?.revenue_projection.review_uplift_revenue || 0).toFixed(0)}</div>
            <p className="text-xs text-muted-foreground">
              {report?.revenue_projection.reviews.review_activity_count || 0} review signals with +{report?.revenue_projection.inputs.review_to_conversion_lift_percent || 0}% lift
            </p>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="overview" className="space-y-4">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="breakdown">Activity Breakdown</TabsTrigger>
          <TabsTrigger value="trends">Trends</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Cost vs Savings</CardTitle>
                <CardDescription>Your subscription cost vs saved time and projected gross profit</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">Subscription Cost</span>
                    <span className="text-lg font-bold text-red-600">-${report?.subscription_cost.toFixed(0)}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">Money Saved</span>
                    <span className="text-lg font-bold text-green-600">+${report?.total_money_saved.toFixed(0)}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">Projected Gross Profit</span>
                    <span className="text-lg font-bold text-emerald-600">+${grossProfitTotal.toFixed(0)}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">Review Uplift Gross Profit</span>
                    <span className="text-lg font-bold text-blue-600">
                      +${(report?.revenue_projection.review_uplift_gross_profit || 0).toFixed(0)}
                    </span>
                  </div>
                  <div className="border-t pt-4">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-semibold">Net Benefit</span>
                      <span className="text-2xl font-bold text-green-600">
                        +${(((report?.total_money_saved || 0) + grossProfitTotal) - (report?.subscription_cost || 0)).toFixed(0)}
                      </span>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Call Revenue Projection</CardTitle>
                <CardDescription>Estimated revenue from calls, recovery, and digital intent</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">Bookings from Calls</span>
                    <span className="font-semibold">{report?.revenue_projection.estimated_bookings_from_calls}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">Visits from Calls</span>
                    <span className="font-semibold">{report?.revenue_projection.estimated_visits_from_calls}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">Projected Revenue</span>
                    <span className="font-semibold text-emerald-600">
                      ${report?.revenue_projection.estimated_revenue_from_calls.toFixed(0)}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">Missed Call Recovery</span>
                    <span className="font-semibold text-blue-600">
                      ${report?.revenue_projection.missed_call_recovery_revenue.toFixed(0)}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">Digital Intent Revenue</span>
                    <span className="font-semibold text-violet-600">
                      ${report?.revenue_projection.digital_intent.estimated_digital_revenue.toFixed(0)}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">Review Uplift Revenue</span>
                    <span className="font-semibold text-emerald-600">
                      ${report?.revenue_projection.review_uplift_revenue.toFixed(0)}
                    </span>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="breakdown" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Activity Breakdown</CardTitle>
              <CardDescription>Detailed breakdown of AI automation activities</CardDescription>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={activityData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" />
                  <YAxis yAxisId="left" orientation="left" stroke="#8884d8" />
                  <YAxis yAxisId="right" orientation="right" stroke="#82ca9d" />
                  <Tooltip />
                  <Legend />
                  <Bar yAxisId="left" dataKey="count" fill="#8884d8" name="Count" />
                  <Bar yAxisId="right" dataKey="hours" fill="#82ca9d" name="Hours Saved" />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            {activityData.map((activity) => (
              <Card key={activity.name}>
                <CardHeader>
                  <CardTitle className="text-base">{activity.name}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Count</span>
                    <span className="font-semibold">{activity.count}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Time Saved</span>
                    <span className="font-semibold">{activity.hours}h</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">Value</span>
                    <span className="font-semibold text-green-600">${activity.money}</span>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        </TabsContent>

        <TabsContent value="trends" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Time Saved Over Time</CardTitle>
              <CardDescription>Daily time savings from AI automation (last 30 days)</CardDescription>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  <Line type="monotone" dataKey="hours" stroke="#8884d8" strokeWidth={2} name="Hours Saved" />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Activity Trends</CardTitle>
              <CardDescription>AI automation activity over time</CardDescription>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  <Line type="monotone" dataKey="responses" stroke="#82ca9d" strokeWidth={2} name="Review Responses" />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
