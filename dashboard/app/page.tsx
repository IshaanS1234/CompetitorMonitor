'use client';

import { useMemo, useState } from 'react';
import {
  Activity, ArrowUpRight, Building2, Check, CheckCircle2, Clock3,
  ExternalLink, FileText, Globe2, LayoutDashboard, MessageSquareText,
  Newspaper, Radar, RefreshCw, Sparkles, TrendingUp,
} from 'lucide-react';
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from 'recharts';

import initialData from '@/public/monitor-data.json';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from '@/components/ui/chart';

type MonitorData = typeof initialData;
type Signal = {
  id: string;
  source: 'News' | 'Hacker News' | 'Website';
  company: string;
  title: string;
  summary: string;
  whyItMatters: string;
  category: string;
  importance: string;
  date: string;
  href?: string;
  detail: string;
};

function formatTime(value: string, includeTime = false) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat('en-US', {
    month: 'short', day: 'numeric',
    ...(includeTime ? { hour: 'numeric', minute: '2-digit' } : {}),
    timeZone: 'America/Los_Angeles',
  }).format(parsed);
}

function sourceIcon(source: Signal['source']) {
  if (source === 'News') return Newspaper;
  if (source === 'Hacker News') return MessageSquareText;
  return Globe2;
}

function importanceClass(importance: string) {
  if (importance.toLowerCase() === 'high') return 'signal-priority signal-priority-high';
  if (importance.toLowerCase() === 'medium') return 'signal-priority signal-priority-medium';
  return 'signal-priority';
}

const activityConfig = {
  Website: { label: 'Website changes', color: '#5b5bd6' },
  News: { label: 'Press coverage', color: '#278f63' },
  'Hacker News': { label: 'Hacker News', color: '#d26d45' },
} satisfies ChartConfig;

function dateKey(date: Date) {
  return date.toISOString().slice(0, 10);
}

function dateFromKey(value: string) {
  return new Date(`${value}T12:00:00Z`);
}

export default function Home() {
  const [data, setData] = useState<MonitorData>(initialData);
  const [refreshing, setRefreshing] = useState(false);
  const [sourceFilter, setSourceFilter] = useState<'All' | Signal['source']>('All');
  const [chartCompany, setChartCompany] = useState('All');
  const [chartTopic, setChartTopic] = useState('All');
  const [chartRange, setChartRange] = useState<7 | 30 | 90>(30);
  const [selectedBucket, setSelectedBucket] = useState<string | null>(null);

  async function refreshDashboard() {
    setRefreshing(true);
    try {
      const response = await fetch(`/monitor-data.json?time=${Date.now()}`);
      if (response.ok) setData(await response.json());
    } finally {
      setRefreshing(false);
    }
  }

  const signals = useMemo<Signal[]>(() => {
    const news: Signal[] = data.recent_news.map((item) => ({
      id: `news-${item.url}`, source: 'News', company: item.company,
      title: item.title, summary: item.summary, whyItMatters: item.why_it_matters,
      category: item.category, importance: item.importance, date: item.discovered_at,
      href: item.url, detail: item.source,
    }));
    const hackerNews: Signal[] = data.recent_hacker_news.map((item) => ({
      id: `hn-${item.discussion_url}`, source: 'Hacker News', company: item.company,
      title: item.title, summary: item.summary, whyItMatters: item.why_it_matters,
      category: item.category, importance: item.importance, date: item.discovered_at,
      href: item.discussion_url, detail: `${item.points} points · ${item.comment_count} comments`,
    }));
    const changes: Signal[] = data.recent_changes.map((item, index) => ({
      id: `change-${item.company}-${item.page}-${index}`, source: 'Website',
      company: item.company, title: item.summary,
      summary: `${item.page} page update detected by the monitor.`,
      whyItMatters: item.why_it_matters, category: item.category,
      importance: item.importance, date: item.detected_at, detail: item.page,
    }));
    return [...news, ...hackerNews, ...changes].sort(
      (a, b) => new Date(b.date).getTime() - new Date(a.date).getTime(),
    );
  }, [data]);

  const visibleSignals = sourceFilter === 'All' ? signals : signals.filter((item) => item.source === sourceFilter);
  const latestRun = data.recent_runs[0];
  const totalSignals = data.overview.change_count + data.overview.news_count + data.overview.hacker_news_count;
  const chartTopics = useMemo(
    () => ['All', ...Array.from(new Set(signals.map((signal) => signal.category))).sort()],
    [signals],
  );
  const activityChart = useMemo(() => {
    const canonicalCompany = (value: string) => data.companies.find((company) => {
      const normalized = value.toLowerCase();
      return normalized.includes(company.name.toLowerCase()) || normalized.includes(company.domain.toLowerCase());
    })?.name ?? value;
    const referenceDate = dateFromKey(data.generated_at.slice(0, 10));
    const filteredSignals = signals.filter((signal) => (
      (chartCompany === 'All' || canonicalCompany(signal.company) === chartCompany)
      && (chartTopic === 'All' || signal.category === chartTopic)
    ));
    const buckets: Array<Record<string, string | number>> = [];
    const bucketEvents: Record<string, Signal[]> = {};

    if (chartRange === 90) {
      for (let offset = 84; offset >= 0; offset -= 7) {
        const start = new Date(referenceDate);
        start.setUTCDate(start.getUTCDate() - offset);
        const bucket = dateKey(start);
        buckets.push({ bucket, label: formatTime(`${bucket}T12:00:00Z`), Website: 0, News: 0, 'Hacker News': 0, total: 0 });
        bucketEvents[bucket] = [];
      }
    } else {
      for (let offset = chartRange - 1; offset >= 0; offset -= 1) {
        const day = new Date(referenceDate);
        day.setUTCDate(day.getUTCDate() - offset);
        const bucket = dateKey(day);
        buckets.push({ bucket, label: formatTime(`${bucket}T12:00:00Z`), Website: 0, News: 0, 'Hacker News': 0, total: 0 });
        bucketEvents[bucket] = [];
      }
    }

    const firstDate = buckets[0]?.bucket;
    filteredSignals.forEach((signal) => {
      const signalKey = signal.date.slice(0, 10);
      if (!firstDate || signalKey < firstDate || signalKey > dateKey(referenceDate)) return;
      const target = chartRange === 90
        ? [...buckets].reverse().find((bucket) => String(bucket.bucket) <= signalKey)
        : buckets.find((bucket) => bucket.bucket === signalKey);
      if (!target) return;
      target[signal.source] = Number(target[signal.source]) + 1;
      target.total = Number(target.total) + 1;
      bucketEvents[String(target.bucket)].push(signal);
    });

    const fallbackBucket = [...buckets].reverse().find((bucket) => Number(bucket.total) > 0)?.bucket
      ?? buckets.at(-1)?.bucket;
    const activeBucket = selectedBucket && bucketEvents[selectedBucket] ? selectedBucket : String(fallbackBucket ?? '');
    return { buckets, bucketEvents, activeBucket };
  }, [chartCompany, chartRange, chartTopic, data, selectedBucket, signals]);

  const activeChartEvents = activityChart.bucketEvents[activityChart.activeBucket] ?? [];

  function chooseChartFilter(action: () => void) {
    setSelectedBucket(null);
    action();
  }

  function selectChartBucket(entry: unknown) {
    const point = entry as { bucket?: string; payload?: { bucket?: string } };
    const bucket = point.bucket ?? point.payload?.bucket;
    if (bucket) setSelectedBucket(bucket);
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a href="#overview" className="brand" aria-label="Competitor overview">
          <span className="brand-mark"><Radar aria-hidden="true" /></span>
          <span><strong>Competitor intelligence</strong><small>Signal monitor</small></span>
        </a>
        <nav className="sidebar-nav" aria-label="Dashboard sections">
          <a href="#overview" className="active"><LayoutDashboard /> Overview</a>
          <a href="#intelligence"><Sparkles /> Intelligence</a>
          <a href="/news"><Newspaper /> Newsroom</a>
          <a href="#companies"><Building2 /> Companies</a>
          <a href="#runs"><Clock3 /> Run history</a>
        </nav>
        <div className="sidebar-status">
          <span className="status-dot" />
          <div><strong>Monitor healthy</strong><span>Last run {latestRun ? formatTime(latestRun.run_at, true) : 'not available'}</span></div>
        </div>
      </aside>

      <main className="workspace">
        <header className="topbar">
          <span className="topbar-context">Overview</span>
          <div className="topbar-actions">
            <Button variant="outline" onClick={refreshDashboard} disabled={refreshing} className="refresh-button">
              <RefreshCw className={refreshing ? 'animate-spin' : ''} />{refreshing ? 'Refreshing' : 'Refresh'}
            </Button>
          </div>
        </header>

        <div className="dashboard-content">
          <section id="overview" className="intro">
            <div><p className="eyebrow">Overview</p><h1>Competitor activity</h1><p>The newest website changes, coverage, and conversations across {data.overview.company_count} monitored companies.</p></div>
            <div className="last-updated"><CheckCircle2 /><span><strong>Data is current</strong>Updated {formatTime(data.generated_at, true)}</span></div>
          </section>

          <section className="metrics" aria-label="Monitoring overview">
            <article className="metric-card"><div className="metric-icon violet"><Building2 /></div><div><span>Companies monitored</span><strong>{data.overview.company_count}</strong><small>active watchlist</small></div></article>
            <article className="metric-card"><div className="metric-icon blue"><Activity /></div><div><span>Pages monitored</span><strong>{data.overview.page_count}</strong><small>checked every run</small></div></article>
            <article className="metric-card"><div className="metric-icon amber"><Sparkles /></div><div><span>Signals collected</span><strong>{totalSignals}</strong><small>changes, news, and discussions</small></div></article>
            <article className="metric-card"><div className="metric-icon green"><Check /></div><div><span>System status</span><strong className="metric-status">{data.overview.latest_status}</strong><small>{latestRun ? `Last run ${formatTime(latestRun.run_at, true)}` : 'Waiting to run'}</small></div></article>
          </section>

          <section className="activity-chart-panel" aria-labelledby="activity-chart-title">
            <div className="activity-chart-header">
              <div><p className="eyebrow">Activity explorer</p><h2 id="activity-chart-title">What are competitors doing?</h2><span>Each bar counts saved signals. Select a bar to see what happened.</span></div>
              <div className="chart-legend">
                {Object.entries(activityConfig).map(([source, item]) => <span key={source}><i style={{ backgroundColor: item.color }} />{item.label}</span>)}
              </div>
            </div>
            <div className="chart-controls">
              <label><span>Company</span><select value={chartCompany} onChange={(event) => chooseChartFilter(() => setChartCompany(event.target.value))}><option value="All">All companies</option>{data.companies.map((company) => <option key={company.domain} value={company.name}>{company.name}</option>)}</select></label>
              <label><span>Topic</span><select value={chartTopic} onChange={(event) => chooseChartFilter(() => setChartTopic(event.target.value))}>{chartTopics.map((topic) => <option key={topic} value={topic}>{topic === 'All' ? 'All topics' : topic}</option>)}</select></label>
              <div className="range-control" aria-label="Chart date range"><span>Range</span><div>{([7, 30, 90] as const).map((range) => <button key={range} type="button" className={chartRange === range ? 'selected' : ''} onClick={() => chooseChartFilter(() => setChartRange(range))}>{range}d</button>)}</div></div>
            </div>
            {activityChart.buckets.length ? (
              <ChartContainer config={activityConfig} className="activity-chart" initialDimension={{ width: 900, height: 270 }}>
                <BarChart data={activityChart.buckets} margin={{ top: 14, right: 16, bottom: 0, left: -16 }}>
                  <CartesianGrid vertical={false} strokeDasharray="3 3" />
                  <XAxis dataKey="label" axisLine={false} tickLine={false} tickMargin={10} minTickGap={22} />
                  <YAxis allowDecimals={false} axisLine={false} tickLine={false} width={34} />
                  <ChartTooltip content={<ChartTooltipContent labelFormatter={(_, payload) => payload?.[0]?.payload?.bucket ? formatTime(`${payload[0].payload.bucket}T12:00:00Z`) : ''} />} />
                  <Bar dataKey="Website" stackId="activity" fill="#5b5bd6" radius={[0, 0, 3, 3]} cursor="pointer" onClick={selectChartBucket} />
                  <Bar dataKey="News" stackId="activity" fill="#278f63" cursor="pointer" onClick={selectChartBucket} />
                  <Bar dataKey="Hacker News" stackId="activity" fill="#d26d45" radius={[3, 3, 0, 0]} cursor="pointer" onClick={selectChartBucket} />
                </BarChart>
              </ChartContainer>
            ) : <div className="chart-empty"><TrendingUp /><span>Activity will appear after the first saved signal.</span></div>}
            <div className="chart-drilldown">
              <div className="drilldown-header"><div><span>{chartRange === 90 ? 'Week of' : 'Selected date'}</span><strong>{activityChart.activeBucket ? formatTime(`${activityChart.activeBucket}T12:00:00Z`) : 'No date selected'}</strong></div><Badge variant="secondary">{activeChartEvents.length} {activeChartEvents.length === 1 ? 'signal' : 'signals'}</Badge></div>
              <div className="drilldown-list">
                {activeChartEvents.length ? activeChartEvents.map((signal) => {
                  const Icon = sourceIcon(signal.source);
                  return <article key={signal.id}><span className={`drilldown-icon source-${signal.source.toLowerCase().replace(' ', '-')}`}><Icon /></span><div><p><strong>{signal.company}</strong><span>{signal.category}</span></p><h3>{signal.href ? <a href={signal.href} target="_blank" rel="noreferrer">{signal.title}<ExternalLink /></a> : signal.title}</h3></div></article>;
                }) : <p className="drilldown-empty">No saved activity in this period. Choose another bar or widen the range.</p>}
              </div>
            </div>
          </section>

          <div className="content-grid">
            <section id="intelligence" className="panel intelligence-panel">
              <div className="panel-header intelligence-header">
                <div><p className="eyebrow">Intelligence feed</p><h2>Latest signals</h2></div>
                <div className="filter-row" aria-label="Filter signals by source">
                  {(['All', 'Website', 'News', 'Hacker News'] as const).map((filter) => (
                    <button key={filter} type="button" className={sourceFilter === filter ? 'selected' : ''} onClick={() => setSourceFilter(filter)}>{filter}</button>
                  ))}
                </div>
              </div>
              <div className="signal-list">
                {visibleSignals.length ? visibleSignals.map((signal) => {
                  const Icon = sourceIcon(signal.source);
                  return (
                    <article className="signal-item" key={signal.id}>
                      <div className={`source-icon source-${signal.source.toLowerCase().replace(' ', '-')}`}><Icon /></div>
                      <div className="signal-body">
                        <div className="signal-meta"><span>{signal.company}</span><span>·</span><span>{signal.source}</span><span>·</span><time>{formatTime(signal.date)}</time></div>
                        <h3>{signal.href ? <a href={signal.href} target="_blank" rel="noreferrer">{signal.title}<ExternalLink /></a> : signal.title}</h3>
                        <p className="signal-summary">{signal.summary}</p>
                        <div className="signal-tags"><Badge variant="secondary">{signal.category}</Badge><span className={importanceClass(signal.importance)}>{signal.importance} priority</span><span>{signal.detail}</span></div>
                        <div className="why-card"><Sparkles /><p><strong>Why it matters</strong>{signal.whyItMatters}</p></div>
                      </div>
                    </article>
                  );
                }) : <div className="empty-state"><FileText /><strong>No signals in this view</strong><span>New intelligence will appear after the next relevant result.</span></div>}
              </div>
            </section>

            <div className="side-column">
              <section id="companies" className="panel">
                <div className="panel-header"><div><p className="eyebrow">Coverage</p><h2>Monitored companies</h2></div><Badge variant="secondary">{data.overview.page_count} pages</Badge></div>
                <div className="company-list">
                  {data.companies.map((company) => (
                    <article className="company-card" key={company.domain}>
                      <div className="company-heading"><span className="company-logo">{company.name.slice(0, 1)}</span><div><strong>{company.name}</strong><span>{company.domain}</span></div><span className="healthy-pill"><span /> Healthy</span></div>
                      <div className="page-tags">{company.pages.map((page) => <span key={page.name}>{page.name}</span>)}</div>
                      <div className="company-footer"><span>{company.pages.length} pages</span><span>Checked {formatTime(company.pages[0]?.last_checked ?? data.generated_at, true)}</span></div>
                    </article>
                  ))}
                </div>
              </section>

              <section id="runs" className="panel">
                <div className="panel-header"><div><p className="eyebrow">Automation</p><h2>Recent runs</h2></div><span className="live-label"><span /> Active</span></div>
                <div className="run-list">
                  {data.recent_runs.map((run, index) => (
                    <div className="run-item" key={run.report_file}><span className={index === 0 ? 'run-check latest' : 'run-check'}><Check /></span><div><strong>{run.status}</strong><span>{formatTime(run.run_at, true)}</span></div><Badge variant="outline">{run.change_count} changes</Badge></div>
                  ))}
                </div>
              </section>

              <section className="brief-card">
                <div className="brief-icon"><Radar /></div><p className="eyebrow">Your monitor</p><h2>Coverage is looking good.</h2><p>{data.overview.company_count} companies and {data.overview.page_count} pages are included in every complete run.</p><a href="#companies">Review coverage <ArrowUpRight /></a>
              </section>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
