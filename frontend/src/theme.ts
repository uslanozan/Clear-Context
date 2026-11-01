import { Button, createTheme, Paper, Textarea } from '@mantine/core';

// Keep in step with the CSS tokens in styles.css: two logo blues, the gray #1f1f22 and glass.
export const theme = createTheme({
  primaryColor: 'brand',
  primaryShade: { light: 7, dark: 7 },
  colors: {
    // Mantine's dark scale on the gray #1f1f22 (index 7 is the page).
    dark: [
      '#ececef',
      '#cfcfd4',
      '#a2a2aa',
      '#76767e',
      '#4a4a52',
      '#34343a',
      '#2a2a2e',
      '#1f1f22',
      '#18181a',
      '#111113',
    ],
    // The two logo blues at the ends (shade 7 #0161dd for fills, shade 5 #047bf2 for accents).
    brand: [
      '#eaf3ff',
      '#d2e6ff',
      '#a6ccfe',
      '#78b1fb',
      '#3f95f6',
      '#047bf2',
      '#036be8',
      '#0161dd',
      '#014fb4',
      '#003a86',
    ],
  },
  black: '#111113',
  fontFamily: 'Funnel Sans Variable, Segoe UI, sans-serif',
  fontFamilyMonospace: 'JetBrains Mono Variable, ui-monospace, Consolas, monospace',
  headings: {
    fontFamily: 'Funnel Display Variable, Funnel Sans Variable, Segoe UI, sans-serif',
    fontWeight: '600',
  },
  defaultRadius: 'md',
  radius: { xs: '4px', sm: '6px', md: '10px', lg: '14px', xl: '20px' },
  components: {
    Button: Button.extend({ defaultProps: { fw: 550, radius: 'sm' } }),
    Paper: Paper.extend({ defaultProps: { radius: 'md' } }),
    Textarea: Textarea.extend({ defaultProps: { radius: 'md' } }),
  },
});
