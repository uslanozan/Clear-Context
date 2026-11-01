import { withoutEmoji } from '../pdf/ReportDocument';

it('leaves emoji out of PDF text but keeps every other character', () => {
  expect(withoutEmoji('Çok şaşırdım 😮 ama doğru değil 👀👀')).toBe(
    'Çok şaşırdım ama doğru değil ',
  );
  expect(withoutEmoji('“Quoted” — 3 months…')).toBe('“Quoted” — 3 months…');
});
