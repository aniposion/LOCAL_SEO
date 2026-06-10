/**
 * Onboarding Checklist Component
 *
 * P0: Tracks user activation with 4 key steps
 * Displays progress and guides users to complete onboarding
 */

import React from 'react';
import { CheckCircle2, Circle, Sparkles } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { onboardingApi } from '@/lib/api';

interface OnboardingStep {
  step: string;
  completed: boolean;
  completed_at: string | null;
}

interface OnboardingProgress {
  completed_steps: number;
  total_steps: number;
  current_step: string | null;
  is_completed: boolean;
  completion_percentage: number;
  completed_at: string | null;
  steps: OnboardingStep[];
}

const STEP_LABELS: Record<string, { title: string; description: string }> = {
  run_audit: {
    title: 'Run SEO Audit',
    description: 'Analyze your business listing'
  },
  view_insights: {
    title: 'View Insights',
    description: 'Check your audit results'
  },
  generate_content: {
    title: 'Generate Content',
    description: 'Create your first AI post'
  },
  generate_social_card: {
    title: 'Create Social Card',
    description: 'Generate a social proof card'
  }
};

interface OnboardingChecklistProps {
  progress: OnboardingProgress | null;
  onStepClick?: (step: string) => void;
  compact?: boolean;
}

export function OnboardingChecklist({
  progress,
  onStepClick,
  compact = false
}: OnboardingChecklistProps) {
  const [showCelebration, setShowCelebration] = React.useState(false);
  const [previousCompleted, setPreviousCompleted] = React.useState(0);

  React.useEffect(() => {
    if (progress && progress.is_completed && previousCompleted < progress.total_steps) {
      setShowCelebration(true);
    }
    if (progress) {
      setPreviousCompleted(progress.completed_steps);
    }
  }, [progress, previousCompleted]);

  if (!progress) {
    return null;
  }

  if (progress.is_completed && compact) {
    return null; // Hide when completed in compact mode
  }

  return (
    <>
      <Card className="w-full">
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg font-semibold">
              {progress.is_completed ? '??Onboarding Complete!' : '?? Get Started'}
            </CardTitle>
            <span className="text-sm text-gray-500">
              {progress.completed_steps}/{progress.total_steps}
            </span>
          </div>
          <Progress value={progress.completion_percentage} className="mt-2" />
        </CardHeader>

        <CardContent>
          <div className="space-y-3">
            {progress.steps.map((step) => {
              const stepInfo = STEP_LABELS[step.step] || {
                title: step.step,
                description: ''
              };

              return (
                <div
                  key={step.step}
                  className={`
                    flex items-center gap-3 p-3 rounded-lg transition-all
                    ${step.completed ? 'bg-green-50' : 'bg-gray-50 hover:bg-gray-100'}
                    ${onStepClick && !step.completed ? 'cursor-pointer' : ''}
                  `}
                  onClick={() => {
                    if (onStepClick && !step.completed) {
                      onStepClick(step.step);
                    }
                  }}
                >
                  {step.completed ? (
                    <CheckCircle2 className="h-5 w-5 text-green-600 flex-shrink-0" />
                  ) : (
                    <Circle className="h-5 w-5 text-gray-400 flex-shrink-0" />
                  )}

                  <div className="flex-1 min-w-0">
                    <div className={`font-medium ${step.completed ? 'text-green-900' : 'text-gray-900'}`}>
                      {stepInfo.title}
                    </div>
                    {!compact && (
                      <div className="text-sm text-gray-600">
                        {stepInfo.description}
                      </div>
                    )}
                  </div>

                  {step.completed && step.completed_at && (
                    <span className="text-xs text-gray-500">
                      {new Date(step.completed_at).toLocaleDateString()}
                    </span>
                  )}
                </div>
              );
            })}
          </div>

          {!progress.is_completed && progress.current_step && (
            <div className="mt-4 p-3 bg-blue-50 rounded-lg">
              <div className="text-sm text-blue-900">
                <strong>Next step:</strong> {STEP_LABELS[progress.current_step]?.title || progress.current_step}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Celebration Modal */}
      <Dialog open={showCelebration} onOpenChange={setShowCelebration}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <div className="flex justify-center mb-4">
              <Sparkles className="h-16 w-16 text-yellow-500" />
            </div>
            <DialogTitle className="text-center text-2xl">
              ?럦 Congratulations!
            </DialogTitle>
            <DialogDescription className="text-center text-base">
              You&apos;ve completed the onboarding! You&apos;re all set to optimize your local SEO.
            </DialogDescription>
          </DialogHeader>

          <div className="flex justify-center mt-4">
            <Button onClick={() => setShowCelebration(false)}>
              Let&apos;s Go! ??
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}

/**
 * Hook to fetch and manage onboarding progress
 */
export function useOnboardingProgress() {
  const [progress, setProgress] = React.useState<OnboardingProgress | null>(null);
  const [loading, setLoading] = React.useState(true);

  const fetchProgress = React.useCallback(async () => {
    try {
      const response = await onboardingApi.getProgress();
      setProgress(response.data);
    } catch (error) {
      console.error('Failed to fetch onboarding progress:', error);
    } finally {
      setLoading(false);
    }
  }, []);

  const completeStep = React.useCallback(async (step: string) => {
    try {
      const response = await onboardingApi.completeStep(step);
      setProgress(response.data);
      return true;
    } catch (error) {
      console.error('Failed to complete step:', error);
      return false;
    }
  }, []);

  React.useEffect(() => {
    fetchProgress();
  }, [fetchProgress]);

  return { progress, loading, completeStep, refetch: fetchProgress };
}
