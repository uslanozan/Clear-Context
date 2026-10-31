// The Clear Context mark: two stacked letters C, the upper one's tail running into the
// lower one's crown. Paths share a 128-unit grid with public/brand/clear-context-mark.svg.
const UPPER = 'M75.4 18.6 A24 24 0 1 0 66.2 60.2';
const LOWER = 'M76.7 69.1 A26 26 0 1 0 76.7 108.9';

const TONES = {
  light: { upper: '#3b81e0', lower: '#0064e0' },
  dark: { upper: '#f3e6d6', lower: '#8db8ff' },
};

interface Props {
  size?: number;
  tone?: keyof typeof TONES;
}

export function LogoMark({ size = 28, tone = 'light' }: Props) {
  const colors = TONES[tone];
  return (
    <svg
      width={size}
      height={size}
      viewBox="-2 4 120 120"
      fill="none"
      strokeWidth={13}
      strokeLinecap="round"
      aria-hidden="true"
    >
      <path d={LOWER} stroke={colors.lower} />
      <path d={UPPER} stroke={colors.upper} />
    </svg>
  );
}
