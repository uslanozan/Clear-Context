import { useEffect, useState } from 'react';
import { Alert, Button, Drawer, Loader, Modal, Skeleton } from '@mantine/core';
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ArrowRight,
  BookOpenText,
  Check,
  FileSearch,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  RefreshCw,
  X,
} from 'lucide-react';
import { Link, Route, Routes, useLocation, useNavigate, useParams } from 'react-router-dom';
import { Composer } from './components/Composer';
import { SettingsPage } from './components/SettingsPage';
import { runningStage } from './components/ProcessTimeline';
import { Activity, ReportView } from './components/ReportView';
import { StepJolly } from './components/StepJolly';
import { Sidebar } from './components/Sidebar';
import { HelpGuide } from './components/HelpGuide';
import { api, ApiError, failureMessage } from './lib/api';
import { queueMessage } from './lib/stages';
import type { Investigation, ResearchMode } from './lib/types';

// Dialogs use the same glass surface as the settings sections.
const GLASS_MODAL = {
  content: 'glass-modal',
  header: 'glass-modal-header',
  title: 'help-title',
};

export function App() {
  return (
    <Routes>
      <Route path="/" element={<Workspace />} />
      <Route path="/settings" element={<Workspace />} />
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
  const isSettings = location.pathname === '/settings';
  const queryClient = useQueryClient();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  // The history item waiting for delete confirmation.
  const [pendingDelete, setPendingDelete] = useState<Investigation | null>(null);
  // Folding the rail is a per-browser preference; storage may be unavailable.
  const [railHidden, setRailHidden] = useState(() => {
    try {
      return localStorage.getItem('clear-context:rail-hidden') === '1';
    } catch {
      return false;
    }
  });
  const toggleRail = () =>
    setRailHidden((hidden) => {
      try {
        localStorage.setItem('clear-context:rail-hidden', hidden ? '0' : '1');
      } catch {
        // The choice simply resets next time.
      }
      return !hidden;
    });
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
  const running = runningStage(steps.data || []);
  const report = useQuery({
    queryKey: ['report', id],
    queryFn: ({ signal }) => api.report(id!, signal),
    enabled: investigation.data?.status === 'completed',
  });
  const create = useMutation({
    mutationFn: (input: { text: string; research_mode?: ResearchMode; files: File[] }) =>
      input.files.length
        ? api.upload(input)
        : // The JSON endpoint rejects unknown fields, so send only text and mode.
          api.create({ text: input.text, research_mode: input.research_mode }),
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
    document.title = isSettings
      ? 'Settings — Clear Context'
      : id
        ? 'Investigation — Clear Context'
        : 'Clear Context — Look closer';
  }, [id, isSettings]);

  const groups = useQuery({
    queryKey: ['groups'],
    queryFn: ({ signal }) => api.groups(signal),
  });
  const refreshHistory = () => {
    void queryClient.invalidateQueries({ queryKey: ['groups'] });
    void queryClient.invalidateQueries({ queryKey: ['history'] });
  };
  const createGroup = useMutation({
    mutationFn: (name: string) => api.createGroup(name),
    onSuccess: refreshHistory,
  });
  const renameGroup = useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) => api.renameGroup(id, name),
    onSuccess: refreshHistory,
  });
  const deleteGroup = useMutation({
    mutationFn: (groupId: string) => api.deleteGroup(groupId),
    onSuccess: refreshHistory,
  });
  const deleteInvestigation = useMutation({
    mutationFn: (investigationId: string) => api.deleteInvestigation(investigationId),
    onSuccess: (_, investigationId) => {
      setPendingDelete(null);
      for (const key of ['investigation', 'steps', 'report', 'research']) {
        queryClient.removeQueries({ queryKey: [key, investigationId] });
      }
      refreshHistory();
      if (investigationId === id) navigate('/');
    },
  });
  const assignGroup = useMutation({
    mutationFn: ({
      investigationId,
      groupId,
    }: {
      investigationId: string;
      groupId: string | null;
    }) => api.assignGroup(investigationId, groupId),
    onSuccess: refreshHistory,
  });

  const items = Array.from(
    new Map((history.data?.pages.flat() || []).map((item) => [item.id, item])).values(),
  );
  const sidebar = (
    <Sidebar
      items={items}
      groups={groups.data ?? []}
      onCreateGroup={(name) => createGroup.mutate(name)}
      onRenameGroup={(groupId, name) => renameGroup.mutate({ id: groupId, name })}
      onDeleteGroup={(groupId) => deleteGroup.mutate(groupId)}
      onAssign={(investigationId, groupId) => assignGroup.mutate({ investigationId, groupId })}
      onDelete={(item) => {
        deleteInvestigation.reset();
        setPendingDelete(item);
      }}
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
    <div className={`app-layout ${railHidden ? 'rail-hidden' : ''}`}>
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
            <button
              className="rail-toggle icon-button"
              aria-label={railHidden ? 'Show navigation' : 'Hide navigation'}
              aria-expanded={!railHidden}
              title={railHidden ? 'Show navigation' : 'Hide navigation'}
              onClick={toggleRail}
            >
              {railHidden ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
            </button>
            <Link to="/">Workspace</Link>
            <span className="breadcrumb-divider">/</span>
            <span>{isSettings ? 'Settings' : id ? 'Investigation' : 'New investigation'}</span>
          </div>
        </header>
        <main id="main-content" className="workspace-main">
          {health.isError && (
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
          {isSettings ? (
            <SettingsPage />
          ) : !id ? (
            <Composer
              key={location.key}
              initialText={typeof location.state?.draft === 'string' ? location.state.draft : ''}
              health={health.isError ? undefined : health.data}
              isPending={create.isPending}
              error={create.error}
              onSubmit={async (text, researchMode, files) => {
                await create.mutateAsync({ text, research_mode: researchMode, files });
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
                <StepJolly event="failed" size={200} />
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
                Edit your input
              </Button>
              <AccordionPassage text={investigation.data.text} />
              <Activity steps={steps.data || []} hasError={steps.isError} />
            </div>
          ) : active ? (
            <div className="progress-page" role="status" aria-live="polite">
              {investigation.data?.status === 'queued' ? (
                <div className="current-step">
                  <span className="current-step-glyph waiting">
                    <StepJolly event="graph_started" size={220} />
                  </span>
                  <div>
                    <h1>In the queue</h1>
                    <p>
                      {queueMessage('queued', investigation.data.queue_position)} You can return to
                      this investigation from your history.
                    </p>
                  </div>
                </div>
              ) : (
                <div className="current-step">
                  <span className="current-step-glyph">
                    <StepJolly event={running.event} size={220} />
                  </span>
                  <div>
                    <h1>{running.title}</h1>
                    <p>{running.detail} You can return to this investigation from your history.</p>
                  </div>
                </div>
              )}
              <div className="progress-activity">
                {/* A queued investigation has not started: no step is shown as running. */}
                <Activity
                  steps={steps.data || []}
                  isRunning={investigation.data?.status === 'running'}
                  hasError={steps.isError}
                />
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
      </div>
      <Modal
        opened={pendingDelete !== null}
        onClose={() => setPendingDelete(null)}
        title="Delete this investigation?"
        centered
        classNames={GLASS_MODAL}
        overlayProps={{ backgroundOpacity: 0.35, blur: 3 }}
      >
        <p className="delete-target" dir="auto">
          {pendingDelete?.text || 'Files without text'}
        </p>
        <p className="muted">
          The report, its evidence and research records, and uploaded files that no other
          investigation uses are removed from your server. This cannot be undone.
        </p>
        {deleteInvestigation.isError && (
          <p className="budget-error" role="alert">
            {deleteInvestigation.error instanceof ApiError
              ? deleteInvestigation.error.message
              : 'The investigation could not be deleted. Try again.'}
          </p>
        )}
        <div className="settings-actions">
          <Button variant="default" onClick={() => setPendingDelete(null)}>
            Cancel
          </Button>
          <Button
            color="red"
            loading={deleteInvestigation.isPending}
            onClick={() => pendingDelete && deleteInvestigation.mutate(pendingDelete.id)}
          >
            Delete
          </Button>
        </div>
      </Modal>
      <Modal
        opened={helpOpen}
        onClose={() => setHelpOpen(false)}
        title="A clearer view, one claim at a time"
        closeButtonProps={{ 'aria-label': 'Close help' }}
        centered
        size="lg"
        classNames={GLASS_MODAL}
        overlayProps={{ backgroundOpacity: 0.35, blur: 3 }}
      >
        <div className="help-content">
          <HelpGuide />
          <div className="help-footnote">
            <Check size={15} /> Opening a saved report never starts a model call. Your server keeps
            the history; Meta processes your input when Meta mode is enabled.
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
        <BookOpenText size={15} /> Your input
      </summary>
      <p>{text || 'No text was entered; this investigation started from images.'}</p>
    </details>
  );
}
