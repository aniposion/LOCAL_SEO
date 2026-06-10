'use client';

import { useEffect, useEffectEvent, useMemo, useState } from 'react';
import { AlertCircle, Building2, CheckCircle, Clock, Loader2, MessageCircleQuestion, Send, Sparkles, User } from 'lucide-react';
import { toast } from 'sonner';

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
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { extractCollectionPayload, locationsApi, qaApi } from '@/lib/api';
import { getApiErrorMessage } from '@/lib/api-errors';

interface LocationOption {
  id: string;
  name: string;
}

interface Question {
  id: string;
  question_text: string;
  author_name: string;
  created_at: string;
  answer?: string;
  answer_status: 'pending' | 'answered';
  draft_answer?: string | null;
  draft_status?: string | null;
  last_error?: string | null;
}

interface Draft {
  id: string;
  question_id: string;
  question_text: string;
  author_name?: string | null;
  suggested_answer?: string | null;
  posted_answer?: string | null;
  draft_status: string;
  last_error?: string | null;
  feedback_rating?: 'good' | 'needs_edit' | 'wrong' | null;
  feedback_notes?: string | null;
  feedback_at?: string | null;
  answered_at?: string | null;
  updated_at?: string | null;
}

interface DraftHistoryPayload {
  items: Draft[];
  total: number;
  limit: number;
  offset: number;
  feedback_good_count: number;
  feedback_needs_edit_count: number;
  feedback_wrong_count: number;
}

interface QuestionsPayload {
  questions: Question[];
  total: number;
  pending_count: number;
  integration_status: string;
  warning?: string | null;
  last_sync_at?: string | null;
  last_sync_error?: string | null;
}

const EMPTY_PAYLOAD: QuestionsPayload = {
  questions: [],
  total: 0,
  pending_count: 0,
  integration_status: 'ok',
  warning: null,
  last_sync_at: null,
  last_sync_error: null,
};

export default function QAPage() {
  const [isBootLoading, setIsBootLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [locations, setLocations] = useState<LocationOption[]>([]);
  const [locationId, setLocationId] = useState<string>('');
  const [payload, setPayload] = useState<QuestionsPayload>(EMPTY_PAYLOAD);
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [draftHistory, setDraftHistory] = useState<DraftHistoryPayload>({
    items: [],
    total: 0,
    limit: 10,
    offset: 0,
    feedback_good_count: 0,
    feedback_needs_edit_count: 0,
    feedback_wrong_count: 0,
  });
  const [draftStatusFilter, setDraftStatusFilter] = useState<string>('all');
  const [draftSearch, setDraftSearch] = useState('');
  const [historyView, setHistoryView] = useState<'all' | 'failed'>('all');
  const [selectedQuestion, setSelectedQuestion] = useState<Question | null>(null);
  const [selectedDraftId, setSelectedDraftId] = useState<string | undefined>(undefined);
  const [isAnswerDialogOpen, setIsAnswerDialogOpen] = useState(false);
  const [feedbackDraft, setFeedbackDraft] = useState<Draft | null>(null);
  const [feedbackRating, setFeedbackRating] = useState<'good' | 'needs_edit' | 'wrong'>('good');
  const [feedbackNotes, setFeedbackNotes] = useState('');
  const [isSavingFeedback, setIsSavingFeedback] = useState(false);
  const [answerText, setAnswerText] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const loadLocations = async () => {
    try {
      const response = await locationsApi.list();
      const locationItems = extractCollectionPayload<LocationOption>(response.data, 'locations');
      setLocations(locationItems);
      if (locationItems.length > 0) {
        setLocationId(locationItems[0].id);
      }
    } catch (error) {
      console.error('Failed to load locations:', error);
      toast.error('Failed to load locations');
    } finally {
      setIsBootLoading(false);
    }
  };

  const loadLocationData = async (currentLocationId: string, silent: boolean) => {
    if (!silent) {
      setIsRefreshing(true);
    }
    try {
      const [questionsResponse, draftsResponse] = await Promise.all([
        qaApi.list(currentLocationId),
        qaApi.listDrafts(currentLocationId, {
          status_filter: historyView === 'failed' ? 'failed' : draftStatusFilter !== 'all' ? draftStatusFilter : undefined,
          search: draftSearch || undefined,
          limit: draftHistory.limit,
          offset: draftHistory.offset,
        }),
      ]);
      setPayload(questionsResponse.data);
      setDrafts(draftsResponse.data.items || []);
      setDraftHistory(draftsResponse.data);
    } catch (error) {
      console.error('Failed to load Q&A data:', error);
      toast.error('Q&A sync is unavailable until Google Business Profile is connected. Open Integrations to reconnect and try again.');
      setPayload(EMPTY_PAYLOAD);
      setDrafts([]);
      setDraftHistory({
        items: [],
        total: 0,
        limit: draftHistory.limit,
        offset: 0,
        feedback_good_count: 0,
        feedback_needs_edit_count: 0,
        feedback_wrong_count: 0,
      });
    } finally {
      setIsRefreshing(false);
    }
  };

  const loadDrafts = async (currentLocationId: string, silent: boolean) => {
    if (!silent) {
      setIsRefreshing(true);
    }
    try {
      const draftsResponse = await qaApi.listDrafts(currentLocationId, {
        status_filter: historyView === 'failed' ? 'failed' : draftStatusFilter !== 'all' ? draftStatusFilter : undefined,
        search: draftSearch || undefined,
        limit: draftHistory.limit,
        offset: draftHistory.offset,
      });
      setDrafts(draftsResponse.data.items || []);
      setDraftHistory(draftsResponse.data);
    } catch (error) {
      console.error('Failed to load Q&A drafts:', error);
      toast.error('Q&A draft history could not be loaded. Open Integrations to reconnect Google Business Profile and try again.');
    } finally {
      setIsRefreshing(false);
    }
  };

  const loadLocationsOnMount = useEffectEvent(async () => {
    await loadLocations();
  });

  const loadSelectedLocationData = useEffectEvent(async (currentLocationId: string) => {
    await loadLocationData(currentLocationId, false);
  });

  const loadDraftHistory = useEffectEvent(async (currentLocationId: string) => {
    await loadDrafts(currentLocationId, true);
  });

  useEffect(() => {
    void loadLocationsOnMount();
  }, []);

  useEffect(() => {
    if (!locationId) {
      return;
    }
    void loadSelectedLocationData(locationId);
  }, [locationId]);

  useEffect(() => {
    if (!locationId) {
      return;
    }
    void loadDraftHistory(locationId);
  }, [locationId, draftStatusFilter, draftSearch, historyView, draftHistory.offset]);

  const openAnswerDialog = (question: Question) => {
    setSelectedQuestion(question);
    const matchingDraft = drafts.find((draft) => draft.question_id === question.id);
    setSelectedDraftId(matchingDraft?.id);
    setAnswerText(question.draft_answer || matchingDraft?.suggested_answer || question.answer || '');
    setIsAnswerDialogOpen(true);
  };

  const openDraftRetry = (draft: Draft) => {
    setSelectedQuestion({
      id: draft.question_id,
      question_text: draft.question_text,
      author_name: draft.author_name || 'Unknown',
      created_at: draft.answered_at || draft.updated_at || new Date().toISOString(),
      answer_status: 'pending',
      answer: draft.posted_answer || undefined,
      draft_answer: draft.suggested_answer,
      draft_status: draft.draft_status,
      last_error: draft.last_error,
    });
    setSelectedDraftId(draft.id);
    setAnswerText(draft.suggested_answer || draft.posted_answer || '');
    setIsAnswerDialogOpen(true);
  };

  const handleGenerateAnswer = async () => {
    if (!selectedQuestion || !locationId) {
      return;
    }

    setIsSubmitting(true);
    try {
      const response = await qaApi.generateAnswer(
        locationId,
        selectedQuestion.id,
        selectedQuestion.question_text
      );
      setAnswerText(response.data.suggested_answer);
      setSelectedDraftId(response.data.draft_id);
      await loadLocationData(locationId, true);
      toast.success('Draft answer generated');
    } catch (error) {
      console.error('Failed to generate answer:', error);
      toast.error(getApiErrorMessage(error, 'Failed to generate AI draft'));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSubmitAnswer = async () => {
    if (!selectedQuestion || !locationId) {
      return;
    }
    if (!answerText.trim()) {
      toast.error('Please enter an answer');
      return;
    }

    setIsSubmitting(true);
    try {
      await qaApi.answer(locationId, selectedQuestion.id, answerText, selectedDraftId);
      toast.success('Answer posted successfully');
      setIsAnswerDialogOpen(false);
      setAnswerText('');
      setSelectedDraftId(undefined);
      await loadLocationData(locationId, true);
    } catch (error) {
      console.error('Failed to post answer:', error);
      toast.error('Failed to post answer');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleManualSync = async () => {
    if (!locationId) {
      return;
    }

    setIsSyncing(true);
    try {
      const response = await qaApi.sync(locationId);
      const synced = response.data?.synced_questions ?? 0;
      const pending = response.data?.pending_count ?? 0;
      toast.success(`Synced ${synced} questions. ${pending} still need an answer.`);
      await loadLocationData(locationId, true);
    } catch (error) {
      toast.error(getApiErrorMessage(error, 'Failed to sync Q&A questions'));
    } finally {
      setIsSyncing(false);
    }
  };

  const openFeedbackDialog = (draft: Draft, rating: 'good' | 'needs_edit' | 'wrong') => {
    setFeedbackDraft(draft);
    setFeedbackRating(rating);
    setFeedbackNotes(draft.feedback_notes || '');
  };

  const handleSaveFeedback = async () => {
    if (!locationId || !feedbackDraft) return;
    setIsSavingFeedback(true);
    try {
      await qaApi.saveDraftFeedback(locationId, feedbackDraft.id, {
        rating: feedbackRating,
        notes: feedbackNotes.trim() || undefined,
      });
      toast.success('Draft feedback saved');
      setFeedbackDraft(null);
      setFeedbackNotes('');
      await loadDrafts(locationId, true);
    } catch (error) {
      console.error('Failed to save draft feedback:', error);
      toast.error('Failed to save draft feedback');
    } finally {
      setIsSavingFeedback(false);
    }
  };

  const filteredQuestions = useMemo(() => {
    return {
      all: payload.questions,
      pending: payload.questions.filter((question) => question.answer_status === 'pending'),
      answered: payload.questions.filter((question) => question.answer_status === 'answered'),
    };
  }, [payload.questions]);

  const canGoPrevious = draftHistory.offset > 0;
  const canGoNext = draftHistory.offset + draftHistory.limit < draftHistory.total;

  if (isBootLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[1, 2, 3].map((item) => (
            <Card key={item}>
              <CardContent className="pt-6">
                <Skeleton className="h-8 w-20 mb-2" />
                <Skeleton className="h-4 w-28" />
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  if (locations.length === 0) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold">Q&A Response Drafts</h1>
          <p className="text-muted-foreground">Draft and post answers for Google Business Profile questions.</p>
        </div>
        <Card>
          <CardContent className="pt-6 text-center text-muted-foreground">
            Add a location before using Q&A drafts.
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="text-2xl font-bold">Q&A Response Drafts</h1>
          <p className="text-muted-foreground">Review live Google questions, generate draft answers, and post them from one screen.</p>
        </div>
        <div className="flex items-center gap-3">
          <select
            className="h-10 rounded-md border border-input bg-background px-3 text-sm"
            value={locationId}
            onChange={(event) => setLocationId(event.target.value)}
          >
            {locations.map((location) => (
              <option key={location.id} value={location.id}>
                {location.name}
              </option>
            ))}
          </select>
          <Button variant="outline" onClick={handleManualSync} disabled={isSyncing || isRefreshing}>
            {isSyncing ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
            Sync now
          </Button>
          <Button variant="outline" onClick={() => void loadLocationData(locationId, false)} disabled={isRefreshing}>
            {isRefreshing ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
            Refresh
          </Button>
        </div>
      </div>

      <Card className="border-slate-200 bg-slate-950 text-white">
        <CardContent className="flex flex-col gap-4 pt-6 md:flex-row md:items-center md:justify-between">
          <div>
            <Badge className="mb-2 bg-white/10 text-white hover:bg-white/10">Q&A Next Best Action</Badge>
            <h2 className="text-xl font-semibold">
              {payload.pending_count > 0 ? 'Answer live customer questions first' : 'Sync Google Q&A to catch new questions'}
            </h2>
            <p className="mt-1 text-sm text-slate-300">
              Public answers reduce repeated calls and remove buyer hesitation. History and feedback counts are secondary.
            </p>
          </div>
          <Button className="bg-white text-slate-950 hover:bg-slate-100" onClick={handleManualSync} disabled={isSyncing || isRefreshing}>
            {isSyncing ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
            Sync Q&A
          </Button>
        </CardContent>
      </Card>

      {payload.warning ? (
        <Card className="border-amber-200 bg-amber-50">
          <CardContent className="flex items-start gap-3 pt-6">
            <AlertCircle className="mt-0.5 h-5 w-5 text-amber-600" />
            <div>
              <p className="font-medium text-amber-900">Integration attention needed</p>
              <p className="text-sm text-amber-800">{payload.warning}</p>
              {payload.last_sync_at ? (
                <p className="mt-1 text-xs text-amber-700">
                  Last sync attempt: {new Date(payload.last_sync_at).toLocaleString()}
                </p>
              ) : null}
              {payload.last_sync_error ? (
                <p className="mt-1 text-xs text-red-700">Last sync error: {payload.last_sync_error}</p>
              ) : null}
            </div>
          </CardContent>
        </Card>
      ) : null}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <MessageCircleQuestion className="h-5 w-5 text-blue-500" />
              <span className="text-3xl font-bold">{payload.total}</span>
            </div>
            <p className="mt-1 text-sm text-muted-foreground">Live questions</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <AlertCircle className="h-5 w-5 text-orange-500" />
              <span className="text-3xl font-bold text-orange-600">{payload.pending_count}</span>
            </div>
            <p className="mt-1 text-sm text-muted-foreground">Need an answer</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <CheckCircle className="h-5 w-5 text-green-500" />
              <span className="text-3xl font-bold text-green-600">
                {drafts.filter((draft) => draft.draft_status === 'draft').length}
              </span>
            </div>
            <p className="mt-1 text-sm text-muted-foreground">Saved answer drafts</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <Card className="border-green-200 bg-green-50">
          <CardContent className="pt-6">
            <div className="text-sm text-green-700">Drafts rated good</div>
            <div className="mt-2 text-3xl font-bold text-green-900">{draftHistory.feedback_good_count}</div>
          </CardContent>
        </Card>
        <Card className="border-amber-200 bg-amber-50">
          <CardContent className="pt-6">
            <div className="text-sm text-amber-700">Need edits</div>
            <div className="mt-2 text-3xl font-bold text-amber-900">{draftHistory.feedback_needs_edit_count}</div>
          </CardContent>
        </Card>
        <Card className="border-red-200 bg-red-50">
          <CardContent className="pt-6">
            <div className="text-sm text-red-700">Marked wrong</div>
            <div className="mt-2 text-3xl font-bold text-red-900">{draftHistory.feedback_wrong_count}</div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(0,2fr)_minmax(320px,1fr)]">
        <Card>
          <CardHeader>
            <CardTitle>Questions</CardTitle>
            <CardDescription>Only live Google Business Profile questions for the selected location are shown here.</CardDescription>
          </CardHeader>
          <CardContent>
            <Tabs defaultValue="all">
              <TabsList>
                <TabsTrigger value="all">All ({filteredQuestions.all.length})</TabsTrigger>
                <TabsTrigger value="pending">Needs Answer ({filteredQuestions.pending.length})</TabsTrigger>
                <TabsTrigger value="answered">Answered ({filteredQuestions.answered.length})</TabsTrigger>
              </TabsList>

              {(['all', 'pending', 'answered'] as const).map((tab) => (
                <TabsContent key={tab} value={tab} className="mt-4 space-y-4">
                  {filteredQuestions[tab].length > 0 ? (
                    filteredQuestions[tab].map((question) => (
                      <div key={question.id} className="rounded-lg border p-4">
                        <div className="flex items-start justify-between gap-4">
                          <div className="min-w-0 flex-1">
                            <div className="mb-2 flex items-center gap-3">
                              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-100">
                                <User className="h-5 w-5 text-blue-600" />
                              </div>
                              <div>
                                <p className="font-semibold">{question.author_name}</p>
                                <p className="text-sm text-muted-foreground">
                                  {new Date(question.created_at).toLocaleString()}
                                </p>
                              </div>
                            </div>

                            <p className="mb-3 font-medium text-foreground">Q: {question.question_text}</p>

                            {question.draft_answer ? (
                              <div className="mb-3 rounded-lg border border-violet-200 bg-violet-50 p-3">
                                <div className="mb-1 flex items-center gap-2">
                                  <Sparkles className="h-4 w-4 text-violet-600" />
                                  <p className="text-sm font-medium text-violet-700">Saved draft</p>
                                  {question.draft_status ? <Badge variant="secondary">{question.draft_status}</Badge> : null}
                                </div>
                                <p className="text-sm text-slate-700">{question.draft_answer}</p>
                              </div>
                            ) : null}

                            {question.answer ? (
                              <div className="rounded-lg border-l-2 border-green-500 bg-green-50 p-3">
                                <div className="mb-1 flex items-center gap-2">
                                  <Building2 className="h-4 w-4 text-green-600" />
                                  <p className="text-sm font-medium text-green-700">Posted answer</p>
                                </div>
                                <p className="text-sm text-slate-700">{question.answer}</p>
                              </div>
                            ) : null}

                            {question.last_error ? (
                              <p className="mt-2 text-sm text-red-600">Last error: {question.last_error}</p>
                            ) : null}
                          </div>

                          <div className="flex flex-col gap-2">
                            {question.answer_status === 'answered' ? (
                              <Badge className="bg-green-100 text-green-700">
                                <CheckCircle className="mr-1 h-3 w-3" />
                                Answered
                              </Badge>
                            ) : (
                              <>
                                <Badge className="bg-orange-100 text-orange-700">
                                  <Clock className="mr-1 h-3 w-3" />
                                  Pending
                                </Badge>
                                <Button size="sm" onClick={() => openAnswerDialog(question)}>
                                  <Send className="mr-1 h-4 w-4" />
                                  Draft Answer
                                </Button>
                              </>
                            )}
                          </div>
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="py-10 text-center text-muted-foreground">
                      <MessageCircleQuestion className="mx-auto mb-2 h-12 w-12 text-slate-300" />
                      <p>No questions in this view.</p>
                    </div>
                  )}
                </TabsContent>
              ))}
            </Tabs>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Recent Draft Activity</CardTitle>
            <CardDescription>Saved Q&A drafts and posting results for this location.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3">
              <div className="flex gap-2">
                <Button
                  variant={historyView === 'all' ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => {
                    setHistoryView('all');
                    setDraftHistory((current) => ({ ...current, offset: 0 }));
                  }}
                >
                  All history
                </Button>
                <Button
                  variant={historyView === 'failed' ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => {
                    setHistoryView('failed');
                    setDraftHistory((current) => ({ ...current, offset: 0 }));
                  }}
                >
                  Failed only
                </Button>
              </div>
              <select
                className="h-10 rounded-md border border-input bg-background px-3 text-sm"
                value={draftStatusFilter}
                onChange={(event) => setDraftStatusFilter(event.target.value)}
                disabled={historyView === 'failed'}
              >
                <option value="all">All draft statuses</option>
                <option value="draft">Drafts</option>
                <option value="posted">Posted</option>
                <option value="failed">Failed</option>
                <option value="pending">Pending</option>
              </select>
              <input
                className="h-10 rounded-md border border-input bg-background px-3 text-sm"
                placeholder="Search question, answer, or error"
                value={draftSearch}
                onChange={(event) => setDraftSearch(event.target.value)}
              />
            </div>
            {drafts.length > 0 ? (
              drafts.map((draft) => (
                <div key={draft.id} className="rounded-lg border p-3">
                  <div className="mb-2 flex items-center justify-between gap-2">
                    <Badge variant="secondary">{draft.draft_status}</Badge>
                    {draft.answered_at || draft.updated_at ? (
                      <span className="text-xs text-muted-foreground">
                        {new Date(draft.answered_at || draft.updated_at || '').toLocaleString()}
                      </span>
                    ) : null}
                  </div>
                  <p className="mb-1 line-clamp-2 text-sm font-medium">{draft.question_text}</p>
                  <p className="line-clamp-3 text-sm text-muted-foreground">
                    {draft.posted_answer || draft.suggested_answer || 'No saved answer text yet.'}
                  </p>
                  {draft.author_name ? (
                    <p className="mt-2 text-xs text-muted-foreground">Author: {draft.author_name}</p>
                  ) : null}
                  {draft.last_error ? (
                    <p className="mt-2 text-xs text-red-600">Last error: {draft.last_error}</p>
                  ) : null}
                  {draft.feedback_rating ? (
                    <p className="mt-2 text-xs text-muted-foreground">
                      Quality feedback: <span className="font-medium">{draft.feedback_rating.replace('_', ' ')}</span>
                      {draft.feedback_at ? ` 쨌 ${new Date(draft.feedback_at).toLocaleString()}` : ''}
                    </p>
                  ) : null}
                  <div className="mt-3 flex gap-2">
                    <Button variant="outline" size="sm" onClick={() => openDraftRetry(draft)}>
                      {draft.draft_status === 'failed' ? 'Retry answer' : 'Open draft'}
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => openFeedbackDialog(draft, 'good')}>
                      Good
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => openFeedbackDialog(draft, 'needs_edit')}>
                      Needs edit
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => openFeedbackDialog(draft, 'wrong')}>
                      Wrong
                    </Button>
                  </div>
                </div>
              ))
            ) : (
              <div className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
                No saved Q&A drafts yet.
              </div>
            )}
            <div className="flex items-center justify-between border-t pt-3">
              <p className="text-xs text-muted-foreground">
                Showing {draftHistory.total === 0 ? 0 : draftHistory.offset + 1}-
                {Math.min(draftHistory.offset + draftHistory.limit, draftHistory.total)} of {draftHistory.total}
              </p>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={!canGoPrevious}
                  onClick={() =>
                    setDraftHistory((current) => ({ ...current, offset: Math.max(current.offset - current.limit, 0) }))
                  }
                >
                  Previous
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={!canGoNext}
                  onClick={() =>
                    setDraftHistory((current) => ({ ...current, offset: current.offset + current.limit }))
                  }
                >
                  Next
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <Dialog open={isAnswerDialogOpen} onOpenChange={setIsAnswerDialogOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Draft an Answer</DialogTitle>
            <DialogDescription>Generate a draft, edit it, and post it back to Google Business Profile.</DialogDescription>
          </DialogHeader>

          {selectedQuestion ? (
            <div className="space-y-4">
              <div className="rounded-lg bg-blue-50 p-3">
                <p className="mb-1 text-sm font-medium text-blue-700">Question from {selectedQuestion.author_name}</p>
                <p className="text-sm text-slate-800">{selectedQuestion.question_text}</p>
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <label className="text-sm font-medium">Answer</label>
                  <Button variant="ghost" size="sm" onClick={handleGenerateAnswer} disabled={isSubmitting}>
                    <Sparkles className="mr-1 h-4 w-4" />
                    Generate Draft
                  </Button>
                </div>
                <textarea
                  className="h-32 w-full resize-none rounded-lg border p-3 focus:outline-none focus:ring-2 focus:ring-violet-500"
                  placeholder="Write your answer..."
                  value={answerText}
                  onChange={(event) => setAnswerText(event.target.value)}
                />
              </div>
            </div>
          ) : null}

          <DialogFooter>
            <Button variant="outline" onClick={() => setIsAnswerDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleSubmitAnswer} disabled={isSubmitting}>
              {isSubmitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Send className="mr-2 h-4 w-4" />}
              Post Answer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!feedbackDraft} onOpenChange={(open) => !open && setFeedbackDraft(null)}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Rate this draft</DialogTitle>
            <DialogDescription>
              Save quick feedback so we can track which Q&amp;A drafts are useful and which ones still need work.
            </DialogDescription>
          </DialogHeader>
          {feedbackDraft ? (
            <div className="space-y-4">
              <div className="rounded-lg bg-slate-50 p-3 text-sm text-slate-700">
                <p className="font-medium text-slate-900">{feedbackDraft.question_text}</p>
                <p className="mt-2 line-clamp-4">{feedbackDraft.posted_answer || feedbackDraft.suggested_answer || 'No answer text yet.'}</p>
              </div>
              <div className="grid grid-cols-3 gap-2">
                {(['good', 'needs_edit', 'wrong'] as const).map((option) => (
                  <Button
                    key={option}
                    type="button"
                    variant={feedbackRating === option ? 'default' : 'outline'}
                    onClick={() => setFeedbackRating(option)}
                  >
                    {option === 'good' ? 'Good' : option === 'needs_edit' ? 'Needs edit' : 'Wrong'}
                  </Button>
                ))}
              </div>
              <textarea
                className="h-28 w-full resize-none rounded-lg border p-3 focus:outline-none focus:ring-2 focus:ring-violet-500"
                placeholder="Optional note: what should improve?"
                value={feedbackNotes}
                onChange={(event) => setFeedbackNotes(event.target.value)}
              />
            </div>
          ) : null}
          <DialogFooter>
            <Button variant="outline" onClick={() => setFeedbackDraft(null)}>
              Cancel
            </Button>
            <Button onClick={handleSaveFeedback} disabled={isSavingFeedback}>
              {isSavingFeedback ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              Save feedback
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
