import { useEffect, useState } from 'react';
import { Button, TextInput } from '@mantine/core';
import type { Health } from '../../src/lib/types';
import { DEFAULT_SERVER, isLocalServer, normalizeServer } from './capture-model';

import { serverApi } from './server-api';
import { saveServer } from './storage';

// The web app's development server; the default address is the Docker one.
const DEV_SERVER = 'http://clearcontext.localhost:5173';

export type Connection =
  | { state: 'checking' }
  | { state: 'ready'; health: Health }
  | { state: 'unreachable'; message: string };

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

/** The server address, its status and a way to change it. */
export function ServerLine({
  server,
  connection,
  onChange,
}: {
  server: string;
  connection: Connection;
  onChange: (origin: string) => void;
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
            setError('Enter an address such as http://clearcontext.localhost');
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
          await saveServer(origin);
          setEditing(false);
          setError('');
          onChange(origin);
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
      </form>
    );
  }
  const status =
    connection.state === 'checking'
      ? 'Checking…'
      : connection.state === 'unreachable'
        ? 'Not reachable'
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
      {/* The default is the Docker address; while developing, the app runs on port 5173. */}
      {connection.state === 'unreachable' && server === DEFAULT_SERVER && (
        <button
          type="button"
          className="text-button"
          onClick={async () => {
            await saveServer(DEV_SERVER);
            onChange(DEV_SERVER);
          }}
        >
          Use :5173
        </button>
      )}
    </p>
  );
}
