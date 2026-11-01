import { useCallback, useEffect, useState } from 'react';
import type { Health } from '../../src/lib/types';
import { KNOWN_SERVERS } from './capture-model';
import { serverApi } from './server-api';
import { loadLastServer, saveLastServer } from './storage';

export type Connection =
  | { state: 'checking' }
  | { state: 'ready'; health: Health }
  | { state: 'unreachable'; message: string };

/** Origins of open tabs on this computer, which may be Clear Context on a custom port. */
async function openLocalOrigins(): Promise<string[]> {
  try {
    const tabs = await chrome.tabs.query({
      url: ['http://*.localhost/*', 'http://localhost/*', 'http://127.0.0.1/*'],
    });
    return tabs.flatMap((tab) => (tab.url ? [new URL(tab.url).origin] : []));
  } catch {
    return [];
  }
}

/**
 * Finds the server without any setting: the address that worked last time, Clear Context
 * tabs that are open right now (any port), then the addresses this project serves on.
 * The first candidate that answers its health check wins.
 */
export async function findServer(): Promise<string> {
  const last = await loadLastServer();
  const candidates = Array.from(
    new Set([...(last ? [last] : []), ...(await openLocalOrigins()), ...KNOWN_SERVERS]),
  ).slice(0, 8);
  const answers = await Promise.all(
    candidates.map((origin) =>
      serverApi.health(origin, AbortSignal.timeout(2000)).then(
        () => true,
        () => false,
      ),
    ),
  );
  const found = answers.indexOf(true);
  if (found >= 0) {
    void saveLastServer(candidates[found]);
    return candidates[found];
  }
  return last ?? KNOWN_SERVERS[0];
}

/** The server to use, whether it answers, and a way to look again after starting the app. */
export function useServer() {
  const [server, setServer] = useState<string | null>(null);
  const connection = useConnection(server);
  const detect = useCallback(() => {
    setServer(null);
    void findServer().then(setServer);
  }, []);
  useEffect(detect, [detect]);
  return { server, connection, detect };
}

/** Whether the server answers its health check; rechecked when the address changes. */
export function useConnection(server: string | null): Connection {
  const [connection, setConnection] = useState<Connection>({ state: 'checking' });
  useEffect(() => {
    if (!server) {
      setConnection({ state: 'checking' });
      return;
    }
    setConnection({ state: 'checking' });
    serverApi
      .health(server)
      .then((health) => setConnection({ state: 'ready', health }))
      .catch((error: Error) => setConnection({ state: 'unreachable', message: error.message }));
  }, [server]);
  return connection;
}

/** The server address and its status. Unreachable servers offer one way out: look again. */
export function ServerLine({
  server,
  connection,
  onRetry,
}: {
  server: string;
  connection: Connection;
  onRetry: () => void;
}) {
  const status =
    connection.state === 'checking'
      ? 'Connecting…'
      : connection.state === 'unreachable'
        ? 'Not running: start Clear Context'
        : connection.health.mode === 'mock'
          ? 'Preview mode: no model calls'
          : 'Connected';
  return (
    <p className="ext-server">
      <span className={`ext-dot ${connection.state}`} aria-hidden="true" />
      <span>
        {new URL(server).host} · {status}
      </span>
      {connection.state === 'unreachable' && (
        <button type="button" className="text-button" onClick={onRetry}>
          Check again
        </button>
      )}
    </p>
  );
}
