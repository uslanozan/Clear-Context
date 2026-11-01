import { claimSummary, STATUS_ORDER, type ComponentStatus } from '../../src/lib/labels';
import type { Report } from '../../src/lib/types';

/** A short view of a report for the capture window; the evidence stays in the web report. */
export interface ReportSummary {
  claims: {
    text: string;
    counts: [ComponentStatus, number][];
    // Counted from the detail results, as in the web report.
    result: { label: string; tone: ComponentStatus } | null;
  }[];
  hiddenClaims: number;
  media: { kind: 'image' | 'video'; earliest: string | null; mismatches: string[] }[];
  unreadableLinks: number;
  budgetLimited: number;
}

const SHOWN_CLAIMS = 5;

export function summarize(report: Report): ReportSummary {
  const texts = new Map(report.claims.map((claim) => [claim.id, claim.text]));
  const claims = report.findings.map((finding) => {
    const counts = new Map<ComponentStatus, number>();
    for (const component of finding.components ?? []) {
      counts.set(component.status, (counts.get(component.status) ?? 0) + 1);
    }
    return {
      text: texts.get(finding.claim_id) ?? '',
      counts: STATUS_ORDER.filter((status) => counts.has(status)).map(
        (status) => [status, counts.get(status)!] as [ComponentStatus, number],
      ),
      result: claimSummary(finding.components ?? []),
    };
  });
  return {
    claims: claims.slice(0, SHOWN_CLAIMS),
    hiddenClaims: Math.max(0, claims.length - SHOWN_CLAIMS),
    media: (report.media ?? []).map((item) => {
      // Same-image matches with a usable date, earliest first (the server orders them).
      const dated = item.origin.matches.find(
        (match) => match.match !== 'similar' && match.published_on,
      );
      return {
        kind: item.kind,
        earliest: dated
          ? [dated.date_text ?? dated.published_on, dated.source].filter(Boolean).join(', ')
          : null,
        mismatches: (item.analysis.caption_checks ?? [])
          .filter((check) => check.assessment === 'inconsistent')
          .map((check) => check.caption_detail),
      };
    }),
    unreadableLinks: (report.links ?? []).filter((link) => link.status === 'failed').length,
    budgetLimited: report.research_summary?.budget_limited_claim_ids.length ?? 0,
  };
}
