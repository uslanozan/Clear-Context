import React from 'react';
import ReactDOM from 'react-dom/client';
import { MantineProvider } from '@mantine/core';
import '@mantine/core/styles.css';
import '@fontsource-variable/onest';
import '@fontsource-variable/jetbrains-mono';
import { theme } from '../../src/theme';
import '../../src/styles.css';
import './extension.css';

/** Render an extension page with the web app's theme and shared styles. */
export function mount(page: React.ReactNode) {
  ReactDOM.createRoot(document.getElementById('root')!).render(
    <React.StrictMode>
      <MantineProvider theme={theme} forceColorScheme="light">
        {page}
      </MantineProvider>
    </React.StrictMode>,
  );
}
