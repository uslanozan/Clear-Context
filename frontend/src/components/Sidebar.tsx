import { useState } from 'react';
import { Button, Loader, Menu } from '@mantine/core';
import {
  ArrowUpRight,
  BookOpenText,
  ChevronRight,
  CircleHelp,
  Ellipsis,
  FolderPlus,
  Plus,
  RefreshCw,
  FlaskConical,
  Settings,
} from 'lucide-react';
import { Link, NavLink } from 'react-router-dom';
import type { HistoryGroup, Investigation } from '../lib/types';
import { LogoMark } from './Logo';

interface Props {
  items: Investigation[];
  groups: HistoryGroup[];
  isLoading: boolean;
  hasError: boolean;
  hasMore: boolean;
  isFetchingMore: boolean;
  onLoadMore: () => void;
  onRetry: () => void;
  onHelp: () => void;
  onNavigate: () => void;
  onCreateGroup: (name: string) => void;
  onRenameGroup: (id: string, name: string) => void;
  onDeleteGroup: (id: string) => void;
  onAssign: (investigationId: string, groupId: string | null) => void;
}

// Finished investigations need no label; only the exceptions are named.
const HISTORY_STATE: Record<string, string> = {
  queued: 'Queued',
  running: 'Running',
  failed: 'Failed',
};

const COLLAPSED_KEY = 'clear-context:collapsed-groups';

// Which groups are folded is a per-browser convenience, so it lives in the browser only.
function readCollapsed(): Set<string> {
  try {
    const stored = JSON.parse(localStorage.getItem(COLLAPSED_KEY) || '[]');
    return new Set(Array.isArray(stored) ? stored.filter((v) => typeof v === 'string') : []);
  } catch {
    return new Set();
  }
}

function writeCollapsed(ids: Set<string>) {
  try {
    localStorage.setItem(COLLAPSED_KEY, JSON.stringify([...ids]));
  } catch {
    // Storage can be unavailable; the groups simply open again next time.
  }
}

/** A small text field that saves on Enter or blur and cancels on Escape. */
function NameField({
  initial = '',
  label,
  onSave,
  onCancel,
}: {
  initial?: string;
  label: string;
  onSave: (name: string) => void;
  onCancel: () => void;
}) {
  const [value, setValue] = useState(initial);
  const finish = () => {
    const name = value.trim();
    if (name && name !== initial) onSave(name);
    else onCancel();
  };
  return (
    <input
      className="group-name-field"
      aria-label={label}
      value={value}
      maxLength={60}
      autoFocus
      onChange={(event) => setValue(event.currentTarget.value)}
      onBlur={finish}
      onKeyDown={(event) => {
        if (event.key === 'Enter') finish();
        if (event.key === 'Escape') onCancel();
      }}
    />
  );
}

function HistoryItem({
  item,
  groups,
  onNavigate,
  onAssign,
}: {
  item: Investigation;
  groups: HistoryGroup[];
  onNavigate: () => void;
  onAssign: Props['onAssign'];
}) {
  return (
    <div className="history-row">
      <NavLink
        to={`/investigations/${item.id}`}
        className={({ isActive }) => `history-item ${isActive ? 'active' : ''}`}
        onClick={onNavigate}
      >
        <BookOpenText size={15} strokeWidth={1.6} aria-hidden="true" />
        <span className="history-item-title">
          {item.text || <em className="muted">Files without text</em>}
        </span>
        {item.status !== 'completed' && (
          <span className={`history-state ${item.status}`}>{HISTORY_STATE[item.status]}</span>
        )}
      </NavLink>
      {groups.length > 0 && (
        <Menu position="right-start" withinPortal shadow="md" width={200}>
          <Menu.Target>
            <button type="button" className="history-menu" aria-label="Move to a group">
              <Ellipsis size={15} />
            </button>
          </Menu.Target>
          <Menu.Dropdown>
            <Menu.Label>Move to group</Menu.Label>
            {groups.map((group) => (
              <Menu.Item
                key={group.id}
                disabled={item.group_id === group.id}
                onClick={() => onAssign(item.id, group.id)}
              >
                {group.name}
              </Menu.Item>
            ))}
            {item.group_id && (
              <Menu.Item onClick={() => onAssign(item.id, null)}>Remove from group</Menu.Item>
            )}
          </Menu.Dropdown>
        </Menu>
      )}
    </div>
  );
}

export function Sidebar(props: Props) {
  const [collapsed, setCollapsed] = useState(readCollapsed);
  const [creating, setCreating] = useState(false);
  const [renaming, setRenaming] = useState<string | null>(null);

  const known = new Set(props.groups.map((group) => group.id));
  const ungrouped = props.items.filter((item) => !item.group_id || !known.has(item.group_id));
  const toggle = (id: string) => {
    const next = new Set(collapsed);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setCollapsed(next);
    writeCollapsed(next);
  };
  const row = (item: Investigation) => (
    <HistoryItem
      key={item.id}
      item={item}
      groups={props.groups}
      onNavigate={props.onNavigate}
      onAssign={props.onAssign}
    />
  );

  return (
    <aside className="sidebar" aria-label="Workspace navigation">
      <Link to="/" className="brand" onClick={props.onNavigate}>
        <span className="brand-icon">
          <LogoMark size={36} />
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
      <NavLink
        to="/evaluations"
        className={({ isActive }) => `evaluation-nav ${isActive ? 'active' : ''}`}
        onClick={props.onNavigate}
      >
        <FlaskConical size={16} /> Extraction review
      </NavLink>
      <NavLink
        to="/settings"
        className={({ isActive }) => `evaluation-nav settings-nav ${isActive ? 'active' : ''}`}
        onClick={props.onNavigate}
      >
        <Settings size={16} /> Settings
      </NavLink>
      <div className="sidebar-section-label">
        <span>History</span>
        <span className="sidebar-section-tools">
          <button
            type="button"
            className="sidebar-tool"
            aria-label="New group"
            title="New group"
            onClick={() => setCreating(true)}
          >
            <FolderPlus size={15} />
          </button>
          <span>{props.items.length || '—'}</span>
        </span>
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
        {!props.isLoading && !props.hasError && !props.items.length && !props.groups.length && (
          <p className="history-empty">
            Your investigations will live here. Start with something that made you pause.
          </p>
        )}
        {creating && (
          <NameField
            label="Name of the new group"
            onSave={(name) => {
              props.onCreateGroup(name);
              setCreating(false);
            }}
            onCancel={() => setCreating(false)}
          />
        )}
        {props.groups.map((group) => {
          const members = props.items.filter((item) => item.group_id === group.id);
          const open = !collapsed.has(group.id);
          return (
            <section key={group.id} className="history-group">
              <div className="group-head">
                {renaming === group.id ? (
                  <NameField
                    initial={group.name}
                    label={`Rename ${group.name}`}
                    onSave={(name) => {
                      props.onRenameGroup(group.id, name);
                      setRenaming(null);
                    }}
                    onCancel={() => setRenaming(null)}
                  />
                ) : (
                  <button
                    type="button"
                    className="group-toggle"
                    aria-expanded={open}
                    onClick={() => toggle(group.id)}
                  >
                    <ChevronRight size={14} className={open ? 'is-open' : ''} />
                    <span className="group-name">{group.name}</span>
                    <span className="group-count">{members.length}</span>
                  </button>
                )}
                <Menu position="right-start" withinPortal shadow="md" width={180}>
                  <Menu.Target>
                    <button
                      type="button"
                      className="history-menu"
                      aria-label={`${group.name} options`}
                    >
                      <Ellipsis size={15} />
                    </button>
                  </Menu.Target>
                  <Menu.Dropdown>
                    <Menu.Item onClick={() => setRenaming(group.id)}>Rename</Menu.Item>
                    <Menu.Item color="red" onClick={() => props.onDeleteGroup(group.id)}>
                      Delete group
                    </Menu.Item>
                  </Menu.Dropdown>
                </Menu>
              </div>
              {open && (
                <div className="group-items">
                  {members.map(row)}
                  {!members.length && <p className="group-empty">Empty</p>}
                </div>
              )}
            </section>
          );
        })}
        {props.groups.length > 0 && ungrouped.length > 0 && (
          <p className="group-label">Not in a group</p>
        )}
        {ungrouped.map(row)}
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
      </div>
    </aside>
  );
}
