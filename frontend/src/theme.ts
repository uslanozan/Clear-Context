import { Button, createTheme, Paper, Textarea } from '@mantine/core';

export const theme = createTheme({
  primaryColor: 'ember',
  primaryShade: 7,
  colors: {
    ember: [
      '#fff5ed',
      '#ffe7d2',
      '#ffcca3',
      '#f9ad75',
      '#ed8e4f',
      '#dc7330',
      '#ca5d1e',
      '#b44c14',
      '#963e12',
      '#78330f',
    ],
  },
  fontFamily: 'Source Sans 3 Variable, sans-serif',
  headings: { fontFamily: 'Source Sans 3 Variable, sans-serif', fontWeight: '600' },
  defaultRadius: 'md',
  radius: { xs: '4px', sm: '6px', md: '10px', lg: '14px', xl: '24px' },
  components: {
    Button: Button.extend({ defaultProps: { fw: 550, radius: 'sm' } }),
    Paper: Paper.extend({ defaultProps: { radius: 'md' } }),
    Textarea: Textarea.extend({ defaultProps: { radius: 'md' } }),
  },
});
