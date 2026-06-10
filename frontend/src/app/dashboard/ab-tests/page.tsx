'use client';

import { useEffect, useEffectEvent, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  AlertCircle,
  FlaskConical,
  Plus,
  Play,
  Pause,
  CheckCircle,
  TrendingUp,
  BarChart3,
  Sparkles,
  Loader2,
  Trophy,
  Target,
  Eye,
  MousePointer,
} from 'lucide-react';
import { locationsApi, abTestingApi } from '@/lib/api';
import { getApiErrorMessage } from '@/lib/api-errors';
import { toast } from 'sonner';

interface LocationOption {
  id: string;
  name: string;
}

interface Variant {
  id: string;
  name: string;
  is_control: boolean;
  impressions: number;
  clicks: number;
  conversions: number;
  click_rate: number;
  conversion_rate: number;
  engagement_score: number;
}

interface ABTest {
  id: string;
  name: string;
  description: string;
  location_id: string;
  test_type: string;
  primary_metric: string;
  status: string;
  traffic_split: number;
  total_impressions: number;
  is_significant: boolean;
  variants: Variant[];
  winner_id?: string;
  improvement_percent?: number;
  start_date?: string;
  end_date?: string;
  created_at: string;
}

interface TestSuggestion {
  type: string;
  name: string;
  description: string;
  control: string;
  variant: string;
}

export default function ABTestsPage() {
  const [isLoading, setIsLoading] = useState(true);
  const [tests, setTests] = useState<ABTest[]>([]);
  const [suggestions, setSuggestions] = useState<TestSuggestion[]>([]);
  const [locations, setLocations] = useState<LocationOption[]>([]);
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [locationId, setLocationId] = useState<string>('');
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  // Create form state
  const [newTestName, setNewTestName] = useState('');
  const [newTestDescription, setNewTestDescription] = useState('');
  const [newTestType, setNewTestType] = useState('title');
  const [newTestMetric, setNewTestMetric] = useState('engagement');
  const [controlContent, setControlContent] = useState('');
  const [variantContent, setVariantContent] = useState('');
  const hasLocations = locations.length > 0;

  useEffect(() => {
    const fetchLocations = async () => {
      try {
        const locResponse = await locationsApi.list();
        const payload = locResponse.data;
        const locs = Array.isArray(payload)
          ? (payload as LocationOption[])
          : ((payload.locations || []) as LocationOption[]);

        setLocations(locs);
        if (locs.length > 0) {
          setLocationId((current) => current || locs[0].id);
          setStatusMessage(null);
        } else {
          setTests([]);
          setSuggestions([]);
          setStatusMessage('Add a location first to create or review A/B tests.');
        }
      } catch (error) {
        console.error('Failed to fetch locations:', error);
        setStatusMessage('A/B testing is unavailable until locations can be loaded.');
        toast.error(getApiErrorMessage(error, 'Failed to load A/B tests'));
      } finally {
        setIsLoading(false);
      }
    };

    void fetchLocations();
  }, []);

  const fetchABData = useEffectEvent(async (targetLocationId: string) => {
    if (!targetLocationId) return;

    setIsLoading(true);
    try {
      const testsResponse = await abTestingApi.list({ location_id: targetLocationId });
      setTests(testsResponse.data.tests || []);

      const suggestionsResponse = await abTestingApi.getSuggestions(targetLocationId);
      setSuggestions(suggestionsResponse.data.suggestions || []);
      setStatusMessage('This page uses only live A/B tests and API-backed suggestions for the selected location.');
    } catch (error) {
      console.error('Failed to fetch data:', error);
      setTests([]);
      setSuggestions([]);
      setStatusMessage('A/B tests could not be loaded for this location.');
      toast.error(getApiErrorMessage(error, 'Failed to load A/B tests'));
    } finally {
      setIsLoading(false);
    }
  });

  useEffect(() => {
    if (!locationId) return;
    void fetchABData(locationId);
  }, [locationId]);

  const handleCreateTest = async () => {
    if (!locationId) {
      toast.error('Select a location first');
      return;
    }
    if (!newTestName.trim()) {
      toast.error('Please enter a test name');
      return;
    }

    setIsSubmitting(true);
    try {
      const response = await abTestingApi.create({
        name: newTestName,
        description: newTestDescription,
        location_id: locationId,
        test_type: newTestType,
        primary_metric: newTestMetric,
        control_content: { [newTestType]: controlContent },
        variant_content: { [newTestType]: variantContent },
        traffic_split: 50,
      });

      setTests(prev => [response.data, ...prev]);
      setIsCreateDialogOpen(false);
      resetForm();
      toast.success('A/B test created!');
    } catch (error) {
      console.error('Failed to create test:', error);
      toast.error(getApiErrorMessage(error, 'Failed to create test'));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleStartTest = async (testId: string) => {
    try {
      const response = await abTestingApi.start(testId);
      setTests(prev => prev.map(t => t.id === testId ? response.data : t));
      toast.success('Test started!');
    } catch (error) {
      console.error('Failed to start test:', error);
      toast.error(getApiErrorMessage(error, 'Failed to start test'));
    }
  };

  const handlePauseTest = async (testId: string) => {
    try {
      const response = await abTestingApi.pause(testId);
      setTests(prev => prev.map(t => t.id === testId ? response.data : t));
      toast.success('Test paused');
    } catch (error) {
      console.error('Failed to pause test:', error);
      toast.error(getApiErrorMessage(error, 'Failed to pause test'));
    }
  };

  const handleCompleteTest = async (testId: string) => {
    try {
      const response = await abTestingApi.complete(testId);
      setTests(prev => prev.map(t => t.id === testId ? response.data : t));
      toast.success('Test completed!');
    } catch (error) {
      console.error('Failed to complete test:', error);
      toast.error(getApiErrorMessage(error, 'Failed to complete test'));
    }
  };

  const resetForm = () => {
    setNewTestName('');
    setNewTestDescription('');
    setNewTestType('title');
    setNewTestMetric('engagement');
    setControlContent('');
    setVariantContent('');
  };

  const applySuggestion = (suggestion: TestSuggestion) => {
    setNewTestName(suggestion.name);
    setNewTestDescription(suggestion.description);
    setNewTestType(suggestion.type);
    setControlContent(suggestion.control);
    setVariantContent(suggestion.variant);
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'draft':
        return <Badge variant="secondary">Draft</Badge>;
      case 'running':
        return <Badge className="bg-green-100 text-green-700">Running</Badge>;
      case 'paused':
        return <Badge className="bg-yellow-100 text-yellow-700">Paused</Badge>;
      case 'completed':
        return <Badge className="bg-blue-100 text-blue-700">Completed</Badge>;
      default:
        return <Badge>{status}</Badge>;
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <div className="grid gap-4">
          {[1, 2].map((i) => (
            <Card key={i}>
              <CardContent className="pt-6">
                <Skeleton className="h-32 w-full" />
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <FlaskConical className="w-6 h-6 text-violet-600" />
            A/B Testing
          </h1>
          <p className="text-gray-500">Compare live content performance for the selected location and optimize your strategy.</p>
        </div>
        {hasLocations ? (
          <div className="flex items-center gap-2">
            <Select value={locationId || undefined} onValueChange={setLocationId}>
              <SelectTrigger className="w-[240px]">
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
            <Button onClick={() => setIsCreateDialogOpen(true)}>
              <Plus className="w-4 h-4 mr-2" />
              New Test
            </Button>
          </div>
        ) : (
          <p className="max-w-sm text-sm text-gray-500">
            Add a live location first. Test creation and suggestions only appear after a real location is connected.
          </p>
        )}
      </div>

      <Card className="border-slate-200 bg-slate-950 text-white">
        <CardContent className="flex flex-col gap-4 pt-6 md:flex-row md:items-center md:justify-between">
          <div>
            <Badge className="mb-2 bg-white/10 text-white hover:bg-white/10">Testing Next Best Action</Badge>
            <h2 className="text-xl font-semibold">
              {tests.some((test) => test.status === 'running') ? 'Let active tests collect enough signal' : 'Create one focused test'}
            </h2>
            <p className="mt-1 text-sm text-slate-300">
              Test only one meaningful difference at a time so the winner can guide future content decisions.
            </p>
          </div>
          {hasLocations ? (
            <Button className="bg-white text-slate-950 hover:bg-slate-100" onClick={() => setIsCreateDialogOpen(true)}>
              <Plus className="mr-2 h-4 w-4" />
              New test
            </Button>
          ) : null}
        </CardContent>
      </Card>

      {statusMessage && (
        <Card className="border-amber-200 bg-amber-50">
          <CardContent className="flex items-start gap-3 pt-6">
            <AlertCircle className="mt-0.5 h-5 w-5 text-amber-600" />
            <div className="text-sm text-amber-900">{statusMessage}</div>
          </CardContent>
        </Card>
      )}

      {/* Stats Overview */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <FlaskConical className="w-5 h-5 text-violet-500" />
              <span className="text-3xl font-bold">{tests.length}</span>
            </div>
            <p className="text-sm text-gray-500 mt-1">Total Tests</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <Play className="w-5 h-5 text-green-500" />
              <span className="text-3xl font-bold text-green-600">
                {tests.filter(t => t.status === 'running').length}
              </span>
            </div>
            <p className="text-sm text-gray-500 mt-1">Running</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <Trophy className="w-5 h-5 text-yellow-500" />
              <span className="text-3xl font-bold text-yellow-600">
                {tests.filter(t => t.winner_id).length}
              </span>
            </div>
            <p className="text-sm text-gray-500 mt-1">Winners Found</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-blue-500" />
              <span className="text-3xl font-bold text-blue-600">
                {tests.filter(t => t.improvement_percent && t.improvement_percent > 0).length > 0
                  ? `+${Math.round(tests.filter(t => t.improvement_percent).reduce((sum, t) => sum + (t.improvement_percent || 0), 0) / tests.filter(t => t.improvement_percent).length)}%`
                  : '0%'
                }
              </span>
            </div>
            <p className="text-sm text-gray-500 mt-1">Avg Improvement</p>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="active">
        <TabsList>
          <TabsTrigger value="active">Active Tests</TabsTrigger>
          <TabsTrigger value="completed">Completed</TabsTrigger>
          <TabsTrigger value="suggestions">Suggestions</TabsTrigger>
        </TabsList>

        {/* Active Tests */}
        <TabsContent value="active" className="mt-6 space-y-4">
          {tests.filter(t => ['running', 'paused', 'draft'].includes(t.status)).length > 0 ? (
            tests.filter(t => ['running', 'paused', 'draft'].includes(t.status)).map((test) => (
              <Card key={test.id}>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle className="flex items-center gap-2">
                        {test.name}
                        {getStatusBadge(test.status)}
                      </CardTitle>
                      <CardDescription>{test.description}</CardDescription>
                    </div>
                    <div className="flex gap-2">
                      {test.status === 'draft' && (
                        <Button size="sm" onClick={() => handleStartTest(test.id)}>
                          <Play className="w-4 h-4 mr-1" />
                          Start
                        </Button>
                      )}
                      {test.status === 'running' && (
                        <>
                          <Button size="sm" variant="outline" onClick={() => handlePauseTest(test.id)}>
                            <Pause className="w-4 h-4 mr-1" />
                            Pause
                          </Button>
                          <Button size="sm" onClick={() => handleCompleteTest(test.id)}>
                            <CheckCircle className="w-4 h-4 mr-1" />
                            Complete
                          </Button>
                        </>
                      )}
                      {test.status === 'paused' && (
                        <Button size="sm" onClick={() => handleStartTest(test.id)}>
                          <Play className="w-4 h-4 mr-1" />
                          Resume
                        </Button>
                      )}
                    </div>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="grid md:grid-cols-2 gap-6">
                    {test.variants.map((variant) => (
                      <div
                        key={variant.id}
                        className={`p-4 rounded-lg border-2 ${
                          test.winner_id === variant.id
                            ? 'border-green-500 bg-green-50'
                            : 'border-gray-200'
                        }`}
                      >
                        <div className="flex items-center justify-between mb-3">
                          <span className="font-semibold flex items-center gap-2">
                            {variant.name}
                            {test.winner_id === variant.id && (
                              <Trophy className="w-4 h-4 text-yellow-500" />
                            )}
                          </span>
                          {variant.is_control && (
                            <Badge variant="outline">Control</Badge>
                          )}
                        </div>

                        <div className="grid grid-cols-3 gap-4 text-center">
                          <div>
                            <div className="flex items-center justify-center gap-1 text-gray-500 mb-1">
                              <Eye className="w-4 h-4" />
                              <span className="text-xs">Impressions</span>
                            </div>
                            <span className="text-xl font-bold">{variant.impressions.toLocaleString()}</span>
                          </div>
                          <div>
                            <div className="flex items-center justify-center gap-1 text-gray-500 mb-1">
                              <MousePointer className="w-4 h-4" />
                              <span className="text-xs">Click Rate</span>
                            </div>
                            <span className="text-xl font-bold">{variant.click_rate}%</span>
                          </div>
                          <div>
                            <div className="flex items-center justify-center gap-1 text-gray-500 mb-1">
                              <Target className="w-4 h-4" />
                              <span className="text-xs">Conversions</span>
                            </div>
                            <span className="text-xl font-bold">{variant.conversions}</span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>

                  {test.is_significant && test.improvement_percent && (
                    <div className="mt-4 p-3 bg-green-50 rounded-lg flex items-center gap-2">
                      <TrendingUp className="w-5 h-5 text-green-600" />
                      <span className="text-green-700">
                        Variant B is performing <strong>{test.improvement_percent}% better</strong> than Control A
                      </span>
                    </div>
                  )}

                  {!test.is_significant && test.status === 'running' && (
                    <div className="mt-4 p-3 bg-yellow-50 rounded-lg flex items-center gap-2">
                      <BarChart3 className="w-5 h-5 text-yellow-600" />
                      <span className="text-yellow-700">
                        Need more data for statistical significance. Keep the test running.
                      </span>
                    </div>
                  )}
                </CardContent>
              </Card>
            ))
          ) : (
            <Card>
              <CardContent className="pt-6 text-center py-12">
                <FlaskConical className="w-12 h-12 mx-auto text-gray-300 mb-4" />
                <p className="text-gray-500 mb-4">No active tests</p>
                {hasLocations ? (
                  <Button onClick={() => setIsCreateDialogOpen(true)}>
                    <Plus className="w-4 h-4 mr-2" />
                    Create Your First Test
                  </Button>
                ) : (
                  <p className="text-sm text-gray-500">
                    Connect a location first to create your first live test.
                  </p>
                )}
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Completed Tests */}
        <TabsContent value="completed" className="mt-6 space-y-4">
          {tests.filter(t => t.status === 'completed').length > 0 ? (
            tests.filter(t => t.status === 'completed').map((test) => (
              <Card key={test.id}>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    {test.name}
                    {getStatusBadge(test.status)}
                    {test.winner_id && <Trophy className="w-5 h-5 text-yellow-500" />}
                  </CardTitle>
                  <CardDescription>{test.description}</CardDescription>
                </CardHeader>
                <CardContent>
                  <p className="text-gray-600">
                    Test completed on {test.end_date ? new Date(test.end_date).toLocaleDateString() : 'N/A'}
                  </p>
                </CardContent>
              </Card>
            ))
          ) : (
            <Card>
              <CardContent className="pt-6 text-center py-12">
                <CheckCircle className="w-12 h-12 mx-auto text-gray-300 mb-4" />
                <p className="text-gray-500">No completed tests yet</p>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Suggestions */}
        <TabsContent value="suggestions" className="mt-6">
          {suggestions.length > 0 ? (
            <div className="grid md:grid-cols-2 gap-4">
              {suggestions.map((suggestion, index) => (
                <Card key={index} className="hover:border-violet-300 transition-colors cursor-pointer">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2 text-lg">
                      <Sparkles className="w-5 h-5 text-violet-500" />
                      {suggestion.name}
                    </CardTitle>
                    <CardDescription>{suggestion.description}</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="space-y-3">
                      <div className="p-3 bg-gray-50 rounded-lg">
                        <p className="text-xs text-gray-500 mb-1">Control (A)</p>
                        <p className="font-medium">{suggestion.control}</p>
                      </div>
                      <div className="p-3 bg-violet-50 rounded-lg">
                        <p className="text-xs text-violet-600 mb-1">Variant (B)</p>
                        <p className="font-medium">{suggestion.variant}</p>
                      </div>
                    </div>
                    {hasLocations ? (
                      <Button
                        className="w-full mt-4"
                        variant="outline"
                        onClick={() => {
                          applySuggestion(suggestion);
                          setIsCreateDialogOpen(true);
                        }}
                      >
                        Use This Test
                      </Button>
                    ) : (
                      <div className="mt-4 rounded-lg border border-dashed p-3 text-sm text-gray-500">
                        Connect a location before applying this suggestion to a live test.
                      </div>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          ) : (
            <Card>
              <CardContent className="pt-6 text-center py-12">
                <Sparkles className="w-12 h-12 mx-auto text-gray-300 mb-4" />
                <p className="text-gray-500">
                  {locationId
                    ? 'No live A/B suggestions are available for this location yet.'
                    : 'Select a location first to load A/B suggestions.'}
                </p>
              </CardContent>
            </Card>
          )}
        </TabsContent>
      </Tabs>

      {/* Create Test Dialog */}
      <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Create A/B Test</DialogTitle>
            <DialogDescription>
              Set up a new test to compare content performance
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="space-y-2">
              <Label>Test Name</Label>
              <Input
                value={newTestName}
                onChange={(e) => setNewTestName(e.target.value)}
                placeholder="e.g., Emoji Title Test"
              />
            </div>

            <div className="space-y-2">
              <Label>Description</Label>
              <Input
                value={newTestDescription}
                onChange={(e) => setNewTestDescription(e.target.value)}
                placeholder="What are you testing?"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Test Type</Label>
                <Select value={newTestType} onValueChange={setNewTestType}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="title">Title</SelectItem>
                    <SelectItem value="body">Body</SelectItem>
                    <SelectItem value="image">Image</SelectItem>
                    <SelectItem value="cta">CTA Button</SelectItem>
                    <SelectItem value="posting_time">Posting Time</SelectItem>
                    <SelectItem value="hashtags">Hashtags</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label>Primary Metric</Label>
                <Select value={newTestMetric} onValueChange={setNewTestMetric}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="engagement">Engagement</SelectItem>
                    <SelectItem value="clicks">Clicks</SelectItem>
                    <SelectItem value="calls">Calls</SelectItem>
                    <SelectItem value="directions">Directions</SelectItem>
                    <SelectItem value="conversions">Conversions</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="space-y-2">
              <Label>Control (A)</Label>
              <Input
                value={controlContent}
                onChange={(e) => setControlContent(e.target.value)}
                placeholder="Original content"
              />
            </div>

            <div className="space-y-2">
              <Label>Variant (B)</Label>
              <Input
                value={variantContent}
                onChange={(e) => setVariantContent(e.target.value)}
                placeholder="New content to test"
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setIsCreateDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreateTest} disabled={isSubmitting}>
              {isSubmitting ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <Plus className="w-4 h-4 mr-2" />
              )}
              Create Test
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
