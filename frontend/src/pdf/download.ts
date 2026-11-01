import { createElement } from 'react';
import { Font, pdf } from '@react-pdf/renderer';
import displaySemiBold from './fonts/FunnelDisplay-SemiBold.ttf?url';
import sansRegular from './fonts/FunnelSans-Regular.ttf?url';
import sansSemiBold from './fonts/FunnelSans-SemiBold.ttf?url';
import monoRegular from './fonts/JetBrainsMono-Regular.ttf?url';
import { ReportDocument } from './ReportDocument';
import type { Investigation, Report } from '../lib/types';

// Static TTFs with the full character set: the app's web fonts are split by script.
Font.register({
  family: 'Funnel Sans',
  fonts: [
    { src: sansRegular, fontWeight: 400 },
    { src: sansSemiBold, fontWeight: 600 },
  ],
});
Font.register({ family: 'Funnel Display', src: displaySemiBold, fontWeight: 600 });
Font.register({ family: 'JetBrains Mono', src: monoRegular });
// No automatic hyphens; only very long tokens such as URLs are broken so they wrap.
Font.registerHyphenationCallback((word) =>
  word.length > 28 ? (word.match(/.{1,24}/gu) ?? [word]) : [word],
);

/** Builds the branded PDF in the browser and downloads it; no server call is made. */
export async function downloadReportPdf(
  investigation: Investigation,
  report: Report,
  researchRan: boolean,
): Promise<void> {
  const document = createElement(ReportDocument, {
    investigation,
    report,
    researchRan,
    generatedAt: new Date(),
  });
  // react-pdf's pdf() expects a Document element; ReportDocument renders one.
  const blob = await pdf(document as Parameters<typeof pdf>[0]).toBlob();
  const url = URL.createObjectURL(blob);
  const anchor = window.document.createElement('a');
  anchor.href = url;
  anchor.download = `clear-context-${report.investigation_id}.pdf`;
  anchor.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
