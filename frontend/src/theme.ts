import { Button, createTheme, Paper, Textarea } from '@mantine/core';

// Keep in step with the CSS tokens in styles.css.
export const theme = createTheme({
  primaryColor: 'brand',
  primaryShade: { light: 7, dark: 7 },
  colors: {
    // Mantine's dark scale, mapped to the page, surface and line tokens in styles.css.
    dark: [
      '#e8eef7',
      '#c9d5e5',
      '#98a9bf',
      '#6f819a',
      '#2d4264',
      '#1b2a42',
      '#0d1726',
      '#0a1322',
      '#060b14',
      '#03060c',
    ],
    // Meta blue; shade 7 (#0064e0) is the action color and passes AA on white.
    brand: [
      '#eaf2ff',
      '#d4e4ff',
      '#a8c8ff',
      '#78a9fd',
      '#4f8ef8',
      '#2f7cf2',
      '#146ee9',
      '#0064e0',
      '#0050b5',
      '#003f8f',
    ],
    // Jolly cream, for the few places the brand warmth appears.
    cream: [
      '#fdfaf6',
      '#fbf5ee',
      '#f6ebdf',
      '#f3e6d6',
      '#ecd7bd',
      '#e6c8a7',
      '#d2ae86',
      '#a98762',
      '#7d6346',
      '#54412d',
    ],
  },
  black: '#060b14',
  fontFamily: 'Onest Variable, Segoe UI, sans-serif',
  fontFamilyMonospace: 'JetBrains Mono Variable, ui-monospace, Consolas, monospace',
  headings: { fontFamily: 'Onest Variable, Segoe UI, sans-serif', fontWeight: '600' },
  defaultRadius: 'md',
  radius: { xs: '4px', sm: '6px', md: '10px', lg: '14px', xl: '20px' },
  components: {
    Button: Button.extend({ defaultProps: { fw: 550, radius: 'sm' } }),
    Paper: Paper.extend({ defaultProps: { radius: 'md' } }),
    Textarea: Textarea.extend({ defaultProps: { radius: 'md' } }),
  },
});
