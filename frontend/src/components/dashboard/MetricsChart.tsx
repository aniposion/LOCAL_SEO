'use client';

import { useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts';

interface ChartDataPoint {
  date: string;
  calls: number;
  directions: number;
  website_clicks: number;
}

interface MetricsChartProps {
  data: ChartDataPoint[];
  title?: string;
}

interface TooltipPayloadItem {
  color?: string;
  name?: string;
  value?: number | string;
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: TooltipPayloadItem[];
  label?: string;
}

function CustomTooltip({ active, payload, label }: CustomTooltipProps) {
  if (active && payload && payload.length) {
    return (
      <div className="rounded-lg border bg-white p-3 shadow-lg">
        <p className="mb-2 text-sm font-medium">{label}</p>
        {payload.map((entry, index) => (
          <div key={`${entry.name || 'metric'}-${index}`} className="flex items-center gap-2 text-sm">
            <div className="h-3 w-3 rounded-full" style={{ backgroundColor: entry.color }} />
            <span className="text-muted-foreground">{entry.name}:</span>
            <span className="font-medium">{entry.value}</span>
          </div>
        ))}
      </div>
    );
  }

  return null;
}

export function MetricsChart({ data, title = 'Performance Trend' }: MetricsChartProps) {
  const formattedData = useMemo(() => {
    return data.map((point) => ({
      ...point,
      displayDate: new Date(point.date).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
      }),
    }));
  }, [data]);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="h-[300px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={formattedData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis
                dataKey="displayDate"
                tick={{ fontSize: 12 }}
                tickLine={false}
                axisLine={{ stroke: '#e5e5e5' }}
              />
              <YAxis
                tick={{ fontSize: 12 }}
                tickLine={false}
                axisLine={{ stroke: '#e5e5e5' }}
                width={40}
              />
              <Tooltip content={<CustomTooltip />} />
              <Legend
                wrapperStyle={{ paddingTop: '20px' }}
                formatter={(value) => <span className="text-sm">{value}</span>}
              />
              <Line
                type="monotone"
                dataKey="calls"
                name="Calls"
                stroke="#22c55e"
                strokeWidth={2}
                dot={{ r: 4 }}
                activeDot={{ r: 6 }}
              />
              <Line
                type="monotone"
                dataKey="directions"
                name="Directions"
                stroke="#3b82f6"
                strokeWidth={2}
                dot={{ r: 4 }}
                activeDot={{ r: 6 }}
              />
              <Line
                type="monotone"
                dataKey="website_clicks"
                name="Website Clicks"
                stroke="#a855f7"
                strokeWidth={2}
                dot={{ r: 4 }}
                activeDot={{ r: 6 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
