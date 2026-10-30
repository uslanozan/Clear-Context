import { useEffect, useState } from 'react';
import { Alert, Badge, Button, Drawer, Loader, Modal, Skeleton } from '@mantine/core';
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ArrowRight,
  BookOpenText,
  Check,
  CircleHelp,
  FileSearch,
  Menu,
  RefreshCw,
  Search,
  X,
} from 'lucide-react';
import { Link, Route, Routes, useLocation, useNavigate, useParams } from 'react-router-dom';
import { EvaluationView } from './components/EvaluationView';
import { Composer } from './components/Composer';
import { Activity, ReportView } from './components/ReportView';
import { Sidebar } from './components/Sidebar';
import { api, ApiError, failureMessage } from './lib/api';
import type { Investigation } from './lib/types';

export function App() {
  return (
    <Routes>
      <Route path="/" element={<Workspace />} />
      <Route path="/evaluations" element={<Workspace />} />
      <Route path="/investigations/:id" element={<Workspace />} />
      <Route
        path="*"
        element={
          <div className="not-found">
            <h1>This page isn’t here</h1>
            <Link to="/">Return to your workspace</Link>
          </div>
        }
      />
    </Routes>
  );
}

function Workspace() {
  const { id } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const isEvaluations = location.pathname === '/evaluations';
  const queryClient = useQueryClient();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const health = useQuery({
    queryKey: ['health'],
    queryFn: ({ signal }) => api.health(signal),
    refetchInterval: 15000,
  });
  const history = useInfiniteQuery({
    queryKey: ['history'],
    queryFn: ({ pageParam, signal }) => api.history(pageParam, signal),
    initialPageParam: 0,
    getNextPageParam: (last, pages) => (last.length === 20 ? pages.length * 20 : undefined),
  });
  const investigation = useQuery({
    queryKey: ['investigation', id],
    queryFn: ({ signal }) => api.investigation(id!, signal),
    enabled: Boolean(id),
    refetchInterval: (query) =>
      query.state.error || ['completed', 'failed'].includes(query.state.data?.status || '')
        ? false
        : 800,
  });
  const active = Boolean(
    investigation.data && ['queued', 'running'].includes(investigation.data.status),
  );
  const steps = useQuery({
    queryKey: ['steps', id],
    queryFn: ({ signal }) => api.steps(id!, signal),
    enabled: Boolean(investigation.data),
    refetchInterval: active ? 800 : false,
  });
  const report = useQuery({
    queryKey: ['report', id],
    queryFn: ({ signal }) => api.report(id!, signal),
    enabled: investigation.data?.status === 'completed',
  });
  const create = useMutation({
    mutationFn: api.create,
    retry: false,
    onSuccess: (created: Investigation) => {
      queryClient.setQueryData(['investigation', created.id], created);
      void queryClient.invalidateQueries({ queryKey: ['history'] });
      navigate(`/investigations/${created.id}`);
    },
  });
  useEffect(() => {
    if (investigation.data?.status === 'completed' || investigation.data?.status === 'failed') {
      void queryClient.invalidateQueries({ queryKey: ['history'] });
      void queryClient.invalidateQueries({ queryKey: ['steps', id] });
    }
  }, [investigation.data?.status, id, queryClient]);
  useEffect(() => {
    document.title = id ? 'Investigation — Clear Context' : 'Clear Context — Look closer';
  }, [id]);

  const items = Array.from(
    new Map((history.data?.pages.flat() || []).map((item) => [item.id, item])).values(),
  );
  const sidebar = (
    <Sidebar
      items={items}
      isLoading={history.isPending}
      hasError={history.isError}
      hasMore={Boolean(history.hasNextPage)}
      isFetchingMore={history.isFetchingNextPage}
      onLoadMore={() => void history.fetchNextPage()}
      onRetry={() => void history.refetch()}
      onHelp={() => {
        setMobileOpen(false);
        setHelpOpen(true);
      }}
      onNavigate={() => setMobileOpen(false)}
    />
  );

  return (
    <div className="app-layout">
      <a href="#main-content" className="skip-link">
        Skip to content
      </a>
      <div className="desktop-sidebar">{sidebar}</div>
      <Drawer
        opened={mobileOpen}
        onClose={() => setMobileOpen(false)}
        title="Your workspace"
        closeButtonProps={{ 'aria-label': 'Close navigation' }}
        padding={0}
        size={290}
        classNames={{ body: 'mobile-sidebar-body' }}
      >
        {sidebar}
      </Drawer>
      <div className="workspace-shell">
        <header className="topbar">
          <div className="topbar-left">
            <button
              className="mobile-menu icon-button"
              aria-label="Open navigation"
              onClick={() => setMobileOpen(true)}
            >
              <Menu size={20} />
            </button>
            <Link to="/">Workspace</Link>
            <span className="breadcrumb-divider">/</span>
            <span>
              {isEvaluations ? 'Extraction review' : id ? 'Investigation' : 'New investigation'}
            </span>
          </div>
          <div className="topbar-right">
            <button
              className="icon-button"
              aria-label="How Clear Context works"
              onClick={() => setHelpOpen(true)}
            >
              <CircleHelp size={17} />
            </button>
          </div>
        </header>
        <main id="main-content" className="workspace-main">
          {health.isError && !isEvaluations && (
            <Alert
              color="orange"
              title="Your investigation service is unavailable"
              className="connection-alert"
              icon={<RefreshCw size={17} />}
            >
              Your saved workspace will be available when the backend reconnects.{' '}
              <button
                className="text-button"
                onClick={() => {
                  void health.refetch();
                  void history.refetch();
                }}
              >
                Check connection
              </button>
            </Alert>
          )}
          {isEvaluations ? (
            <EvaluationView />
          ) : !id ? (
            <Composer
              key={location.key}
              initialText={typeof location.state?.draft === 'string' ? location.state.draft : ''}
              health={health.isError ? undefined : health.data}
              isPending={create.isPending}
              error={create.error}
              onSubmit={async (text, researchMode) => {
                await create.mutateAsync({ text, research_mode: researchMode });
              }}
            />
          ) : investigation.isPending ? (
            <div className="report-loading" aria-label="Loading investigation">
              <Skeleton height={22} width="25%" mb={28} />
              <Skeleton height={54} width="70%" mb={35} />
              <Skeleton height={100} mb={24} />
              <Skeleton height={220} />
            </div>
          ) : investigation.isError ? (
            <div className="error-state">
              <FileSearch size={35} strokeWidth={1.3} />
              <h1>
                {investigation.error instanceof ApiError && investigation.error.status === 404
                  ? 'This investigation wasn’t found'
                  : 'We couldn’t open this investigation'}
              </h1>
              <p>Your other investigations are available in the sidebar.</p>
              <Button
                variant="default"
                onClick={() => void investigation.refetch()}
                leftSection={<RefreshCw size={14} />}
              >
                Try loading again
              </Button>
            </div>
          ) : investigation.data?.status === 'failed' ? (
            <div className="failure-page">
              <span className="failure-icon">
                <X size={23} />
              </span>

              <h1>We couldn’t finish this one</h1>
              <p>{failureMessage(investigation.data.error_code)}</p>
              <p className="muted">
                We haven’t automatically retried this request. Failed model calls may still use
                credits.
              </p>
              <Button
                onClick={() => navigate('/', { state: { draft: investigation.data!.text } })}
                rightSection={<ArrowRight size={15} />}
              >
                Edit original passage
              </Button>
              <AccordionPassage text={investigation.data.text} />
              <Activity steps={steps.data || []} hasError={steps.isError} />
            </div>
          ) : active ? (
            <div className="progress-page" role="status" aria-live="polite">
              <div className="progress-symbol">
                <Search size={35} strokeWidth={1.2} />
                <span />
              </div>
              <Badge variant="light" color="ember">
                INVESTIGATION IN PROGRESS
              </Badge>
              <h1>Investigation running</h1>
              <p>
                We’re separating the claims and checking the report.
                <br />
                You can return to this investigation from your history.
              </p>
              <div className="progress-activity">
                <Activity steps={steps.data || []} isRunning hasError={steps.isError} />
              </div>
            </div>
          ) : report.isError ? (
            <div className="error-state">
              <h1>Your report couldn’t be loaded</h1>
              <p>The investigation is saved. Loading it again won’t start another model call.</p>
              <Button variant="default" onClick={() => void report.refetch()}>
                Reload report
              </Button>
            </div>
          ) : report.data && investigation.data ? (
            <ReportView
              key={id}
              investigation={investigation.data}
              report={report.data}
              steps={steps.data || []}
            />
          ) : (
            <div className="report-loading">
              <Loader size="sm" /> Loading your report…
            </div>
          )}
        </main>
        <footer className="workspace-footer">
          <span>Clear Context</span>
          <span>Self-hosted · Clear Context</span>
        </footer>
      </div>
      <Modal
        opened={helpOpen}
        onClose={() => setHelpOpen(false)}
        title="A clearer view, one claim at a time"
        closeButtonProps={{ 'aria-label': 'Close help' }}
        centered
        size="lg"
        classNames={{ title: 'help-title' }}
      >
        <div className="help-content">
          <div>
            <span>01</span>
            <section>
              <h3>Start with the words</h3>
              <p>
                Paste a statement or passage. Clear Context separates it into claims, keeping their
                original wording.
              </p>
            </section>
          </div>
          <div>
            <span>02</span>
            <section>
              <h3>Look for the evidence</h3>
              <p>
                Source research is the next stage. It isn’t connected yet. Extracted claims stay
                unresolved until there’s evidence to assess.
              </p>
            </section>
          </div>
          <div>
            <span>03</span>
            <section>
              <h3>Keep the context</h3>
              <p>
                Open an investigation from your history, inspect each claim, and export the report.
                Your server stores the history; Meta processes your text when Meta mode is enabled.
              </p>
            </section>
          </div>
          <div className="help-footnote">
            <Check size={15} /> Selecting an example or opening a saved report never starts a model
            call.
          </div>
          <Button
            fullWidth
            onClick={() => setHelpOpen(false)}
            rightSection={<ArrowRight size={15} />}
          >
            Back to the workspace
          </Button>
        </div>
      </Modal>
    </div>
  );
}

function AccordionPassage({ text }: { text: string }) {
  return (
    <details className="failed-passage">
      <summary>
        <BookOpenText size={15} /> Original passage
      </summary>
      <p>{text}</p>
    </details>
  );
}
