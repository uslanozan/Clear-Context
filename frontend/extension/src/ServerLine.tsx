import { useEffect, useState } from 'react';
import { Button, TextInput } from '@mantine/core';
import type { Health } from '../../src/lib/types';
import { KNOWN_SERVERS, isLocalServer, normalizeServer } from './capture-model';
import { serverApi } from './server-api';
import { loadChosenServer, saveServer } from './storage';

export type Connection =
  | { state: 'checking' }
  | { state: 'ready'; health: Health }
  | { state: 'unreachable'; message: string };

/** The address the user picked, or the first known address that answers. */
export async function findServer(): Promise<{ origin: string; chosen: boolean }> {
  const chosen = await loadChosenServer();
  if (chosen) return { origin: chosen, chosen: true };
  const answers = await Promise.all(
    KNOWN_SERVERS.map((origin) =>
      serverApi.health(origin, AbortSignal.timeout(2000)).then(
        () => true,
        () => false,
      ),
    ),
  );
  const found = answers.indexOf(true);
  return { origin: KNOWN_SERVERS[Math.max(found, 0)], chosen: false };
}

/** The server to use and whether it answers; the user can pick another or go back to auto. */
export function useServer() {
  const [server, setServer] = useState<{ origin: string; chosen: boolean } | null>(null);
  const connection = useConnection(server?.origin ?? null);
  useEffect(() => {
    void findServer().then(setServer);
  }, []);
  async function choose(origin: string | null) {
    await saveServer(origin);
    setServer(origin ? { origin, chosen: true } : null);
    if (!origin) setServer(await findServer());
  }
  return { server, connection, choose };
}

/** Whether the server answers its health check; rechecked when the address changes. */
export function useConnection(server: string | null): Connection {
  const [connection, setConnection] = useState<Connection>({ state: 'checking' });
  useEffect(() => {
    if (!server) return;
    setConnection({ state: 'checking' });
    serverApi
      .health(server)
      .then((health) => setConnection({ state: 'ready', health }))
      .catch((error: Error) => setConnection({ state: 'unreachable', message: error.message }));
  }, [server]);
  return connection;
}

/** The server address and its status, with a way to pick another for custom setups. */
export function ServerLine({
  server,
  chosen,
  connection,
  onChoose,
}: {
  server: string;
  chosen: boolean;
  connection: Connection;
  onChoose: (origin: string | null) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(server);
  const [error, setError] = useState('');
  if (editing) {
    return (
      <form
        className="ext-server-form"
        onSubmit={async (event) => {
          event.preventDefault();
          const origin = normalizeServer(value);
          if (!origin) {
            setError('Enter an address such as http://clearcontext.localhost:8080');
            return;
          }
          // Local addresses are allowed by the manifest; others need the user's permission.
          if (!isLocalServer(origin)) {
            const granted = await chrome.permissions.request({ origins: [`${origin}/*`] });
            if (!granted) {
              setError('Access to that address was not granted.');
              return;
            }
          }
          setEditing(false);
          setError('');
          onChoose(origin);
        }}
      >
        <TextInput
          size="xs"
          aria-label="Clear Context server address"
          value={value}
          onChange={(event) => setValue(event.currentTarget.value)}
          error={error || undefined}
        />
        <Button size="xs" type="submit">
          Save
        </Button>
        <Button
          size="xs"
          variant="subtle"
          onClick={() => {
            setEditing(false);
            onChoose(null);
          }}
        >
          Detect automatically
        </Button>
      </form>
    );
  }
  const status =
    connection.state === 'checking'
      ? 'Connecting…'
      : connection.state === 'unreachable'
        ? chosen
          ? 'Not reachable'
          : 'Not running: start Clear Context'
        : connection.health.mode === 'mock'
          ? 'Preview mode: no model calls'
          : 'Connected';
  return (
    <p className="ext-server">
      <span className={`ext-dot ${connection.state}`} aria-hidden="true" />
      <span>
        {new URL(server).host} · {status}
      </span>
      <button type="button" className="text-button" onClick={() => setEditing(true)}>
        Change
      </button>
    </p>
  );
}
