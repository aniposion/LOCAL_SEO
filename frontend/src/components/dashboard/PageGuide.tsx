'use client';

import { HelpCircle, Lightbulb, MousePointerClick, TrendingUp } from 'lucide-react';

import { Card, CardContent } from '@/components/ui/card';
import { getDashboardPageGuide } from '@/lib/page-guides';

interface PageGuideProps {
  pathname: string;
}

export function PageGuide({ pathname }: PageGuideProps) {
  const guide = getDashboardPageGuide(pathname);
  const normalizedPath = pathname.replace(/\/$/, '') || '/dashboard';

  if (!guide) {
    return null;
  }

  return (
    <details
      open={normalizedPath === '/dashboard' ? true : undefined}
      className="group rounded-xl border border-sky-100 bg-gradient-to-r from-sky-50 via-white to-emerald-50 shadow-sm"
    >
      <summary className="flex cursor-pointer list-none items-center gap-3 px-5 py-4">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-sky-100 text-sky-700">
          <HelpCircle className="h-5 w-5" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="text-sm font-semibold text-slate-900">Page help: {guide.title}</div>
          <div className="mt-1 text-sm text-slate-600">{guide.summary}</div>
        </div>
        <span className="text-xs font-medium text-sky-700 group-open:hidden">Open</span>
        <span className="hidden text-xs font-medium text-sky-700 group-open:inline">Collapse</span>
      </summary>
      <Card className="mx-4 mb-4 border-sky-100 bg-white/80 py-0 shadow-none">
        <CardContent className="grid gap-4 p-4 xl:grid-cols-[1.3fr_1fr_1fr]">
          <div>
            <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-slate-900">
              <MousePointerClick className="h-4 w-4 text-sky-600" />
              Workflow
            </div>
            <ol className="space-y-2 text-sm text-slate-700">
              {guide.steps.map((step, index) => (
                <li key={step} className="flex gap-2">
                  <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-sky-100 text-xs font-semibold text-sky-700">
                    {index + 1}
                  </span>
                  <span>{step}</span>
                </li>
              ))}
            </ol>
          </div>
          <div className="rounded-lg border border-blue-100 bg-blue-50/70 p-3">
            <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-blue-950">
              <TrendingUp className="h-4 w-4 text-blue-600" />
              What improves
            </div>
            <p className="text-sm text-blue-950">{guide.benefit}</p>
          </div>
          <div className="rounded-lg border border-emerald-100 bg-emerald-50/70 p-3">
            <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-emerald-900">
              <Lightbulb className="h-4 w-4 text-emerald-600" />
              Keep in mind
            </div>
            <ul className="space-y-2 text-sm text-emerald-900">
              {(guide.tips?.length ? guide.tips : ['Start at the top, then handle red or amber items first.']).map(
                (tip) => (
                  <li key={tip}>{tip}</li>
                )
              )}
            </ul>
          </div>
        </CardContent>
      </Card>
    </details>
  );
}
