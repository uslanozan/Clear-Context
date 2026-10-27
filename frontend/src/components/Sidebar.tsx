import { Button, Loader } from '@mantine/core';
import { ArrowUpRight, BookOpenText, CircleHelp, Focus, Plus, RefreshCw } from 'lucide-react';
import { Link, NavLink } from 'react-router-dom';
import type { Investigation } from '../lib/types';

interface Props {
  items: Investigation[];
  isLoading: boolean;
  hasError: boolean;
  hasMore: boolean;
  isFetchingMore: boolean;
  onLoadMore: () => void;
  onRetry: () => void;
  onHelp: () => void;
  onNavigate: () => void;
}

export function Sidebar(props: Props) {
  return (
    <aside className="sidebar" aria-label="Workspace navigation">
      <Link to="/" className="brand" onClick={props.onNavigate}>
        <span className="brand-icon">
          <Focus size={23} strokeWidth={1.7} />
        </span>
        <span>
          Clear Context<span className="brand-tagline">Investigation workspace</span>
        </span>
      </Link>
      <Button
        component={Link}
        to="/"
        className="new-button"
        leftSection={<Plus size={17} />}
        onClick={props.onNavigate}
      >
        New investigation
      </Button>
      <div className="sidebar-section-label">
        <span>YOUR INVESTIGATIONS</span>
        <span>{props.items.length || '—'}</span>
      </div>
      <nav className="history-list" aria-label="Investigation history">
        {props.isLoading && (
          <div className="history-message">
            <Loader size="xs" /> Loading your history…
          </div>
        )}
        {props.hasError && (
          <div className="history-message">
            <span>History is unavailable.</span>
            <button onClick={props.onRetry}>
              <RefreshCw size={13} /> Try again
            </button>
          </div>
        )}
        {!props.isLoading && !props.hasError && !props.items.length && (
          <p className="history-empty">
            Your investigations will live here. Start with something that made you pause.
          </p>
        )}
        {props.items.map((item) => (
          <NavLink
            key={item.id}
            to={`/investigations/${item.id}`}
            className={({ isActive }) => `history-item ${isActive ? 'active' : ''}`}
            onClick={props.onNavigate}
          >
            <BookOpenText size={15} strokeWidth={1.6} aria-hidden="true" />
            <span className="history-item-title">{item.text}</span>
            <span className={`history-dot ${item.status}`} aria-label={item.status} />
          </NavLink>
        ))}
        {props.hasMore && (
          <button className="load-more" disabled={props.isFetchingMore} onClick={props.onLoadMore}>
            {props.isFetchingMore ? 'Loading…' : 'Load earlier investigations'}
          </button>
        )}
      </nav>
      <div className="sidebar-bottom">
        <button className="help-button" onClick={props.onHelp}>
          <CircleHelp size={16} /> How Clear Context works <ArrowUpRight size={14} />
        </button>
        <div className="local-label">
          <span /> Local workspace
        </div>
      </div>
    </aside>
  );
}
