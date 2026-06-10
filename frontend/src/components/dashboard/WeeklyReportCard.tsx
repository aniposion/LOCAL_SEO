'use client';

import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  FileText,
  Download,
  Mail,
  TrendingUp,
  Phone,
  Navigation,
  DollarSign,
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface WeeklyReportSummary {
  calls_total: number;
  calls_delta: number;
  calls_percent: number;
  directions_total: number;
  directions_delta: number;
  directions_percent: number;
  estimated_revenue: number;
  highlights: string[];
}

interface WeeklyReport {
  id: string;
  report_week: string;
  summary: WeeklyReportSummary;
  pdf_url?: string | null;
  sent_at?: string | null;
}

interface WeeklyReportCardProps {
  report?: WeeklyReport;
  isLoading?: boolean;
  onDownload?: (reportId: string) => void;
  onSendEmail?: (reportId: string) => void;
  onGenerate?: () => void;
}

export function WeeklyReportCard({
  report,
  isLoading,
  onDownload,
  onSendEmail,
  onGenerate,
}: WeeklyReportCardProps) {
  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
    });
  };

  const formatWeekRange = (weekStart: string) => {
    const start = new Date(weekStart);
    const end = new Date(start);
    end.setDate(end.getDate() + 6);

    return `${formatDate(weekStart)} - ${formatDate(end.toISOString())}`;
  };

  if (!report) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <FileText className="h-5 w-5 text-violet-600" />
            Weekly Performance Report
          </CardTitle>
          <CardDescription>No weekly report has been generated yet.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="py-8 text-center">
            <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-violet-100">
              <FileText className="h-8 w-8 text-violet-600" />
            </div>
            <p className="mb-4 text-muted-foreground">
              Generate your first weekly report to review recent performance.
            </p>
            <Button onClick={onGenerate} disabled={isLoading}>
              <TrendingUp className="mr-2 h-4 w-4" />
              Generate report
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  const { summary } = report;

  return (
    <Card className="overflow-hidden">
      <div className="bg-gradient-to-r from-violet-600 to-indigo-600 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="text-white">
            <p className="text-sm text-violet-200">Weekly performance report</p>
            <p className="text-lg font-bold">{formatWeekRange(report.report_week)}</p>
          </div>
          {report.sent_at && (
            <Badge variant="secondary" className="bg-white/20 text-white">
              <Mail className="mr-1 h-3 w-3" />
              Sent
            </Badge>
          )}
        </div>
      </div>

      <CardContent className="pt-6">
        <div className="mb-6 grid grid-cols-3 gap-4">
          <div className="text-center">
            <div className="mx-auto mb-2 flex h-10 w-10 items-center justify-center rounded-full bg-green-100">
              <Phone className="h-5 w-5 text-green-600" />
            </div>
            <p className="text-2xl font-bold">{summary.calls_total}</p>
            <p className="text-xs text-muted-foreground">Calls</p>
            <p className={cn('text-xs font-medium', summary.calls_delta >= 0 ? 'text-green-600' : 'text-red-600')}>
              {summary.calls_delta >= 0 && '+'}{summary.calls_delta}
            </p>
          </div>

          <div className="text-center">
            <div className="mx-auto mb-2 flex h-10 w-10 items-center justify-center rounded-full bg-blue-100">
              <Navigation className="h-5 w-5 text-blue-600" />
            </div>
            <p className="text-2xl font-bold">{summary.directions_total}</p>
            <p className="text-xs text-muted-foreground">Directions</p>
            <p className={cn('text-xs font-medium', summary.directions_delta >= 0 ? 'text-green-600' : 'text-red-600')}>
              {summary.directions_delta >= 0 && '+'}{summary.directions_delta}
            </p>
          </div>

          <div className="text-center">
            <div className="mx-auto mb-2 flex h-10 w-10 items-center justify-center rounded-full bg-violet-100">
              <DollarSign className="h-5 w-5 text-violet-600" />
            </div>
            <p className="text-2xl font-bold">${summary.estimated_revenue.toLocaleString()}</p>
            <p className="text-xs text-muted-foreground">Estimated revenue</p>
          </div>
        </div>

        {summary.highlights && summary.highlights.length > 0 && (
          <div className="mb-6">
            <p className="mb-2 text-sm font-medium">Key highlights</p>
            <div className="space-y-1">
              {summary.highlights.map((highlight, i) => (
                <p key={i} className="flex items-center gap-2 text-sm text-muted-foreground">
                  <span className="h-1.5 w-1.5 rounded-full bg-violet-500" />
                  {highlight}
                </p>
              ))}
            </div>
          </div>
        )}

        <div className="flex gap-2">
          {report.pdf_url && (
            <Button variant="outline" className="flex-1" onClick={() => onDownload?.(report.id)}>
              <Download className="mr-2 h-4 w-4" />
              Download PDF
            </Button>
          )}
          <Button className="flex-1 bg-gradient-to-r from-violet-600 to-indigo-600" onClick={() => onSendEmail?.(report.id)}>
            <Mail className="mr-2 h-4 w-4" />
            Send email
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
