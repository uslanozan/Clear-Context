import {
  Circle,
  Document,
  Image,
  Line,
  Link,
  LinearGradient,
  Page,
  Path,
  Rect,
  Stop,
  StyleSheet,
  Svg,
  Text,
  View,
  Defs,
} from '@react-pdf/renderer';
import { excerptParts, sourceDisplayName, sourceTypeText } from '../components/EvidenceExcerpt';
import { ASSESSMENT_LABEL } from '../components/VerdictTag';
import { claimSummary, COMPONENT_STATUS, detailSummary, type ComponentStatus } from '../lib/labels';
import { modeLabel } from '../lib/modes';
import type { Assessment, Investigation, Report } from '../lib/types';

// Brand colors from the app theme; the body is light so the report prints and reads on paper.
const BRAND = {
  gray: '#1f1f22',
  blue1: '#0161dd',
  blue2: '#047bf2',
  ink: '#16161a',
  muted: '#5b5b66',
  line: '#e2e2e8',
  soft: '#f5f6f8',
  highlight: '#d9e8fd',
};

type Tone = 'supported' | 'contradicted' | 'conflicting' | 'open' | 'muted';
const TONE: Record<Tone, { color: string; background: string }> = {
  supported: { color: '#12794a', background: '#e6f5ed' },
  contradicted: { color: '#c0352a', background: '#fbe9e7' },
  conflicting: { color: '#b45f06', background: '#fdf0e1' },
  open: { color: '#4f5b6e', background: '#eef1f5' },
  muted: { color: '#6b6b75', background: '#f1f1f3' },
};
const COMPONENT_TONE: Record<ComponentStatus, Tone> = {
  supported: 'supported',
  contradicted: 'contradicted',
  conflicting: 'conflicting',
  insufficient: 'open',
  not_assessed: 'muted',
};
const ASSESSMENT_TONE: Record<Assessment, Tone> = {
  supported: 'supported',
  contradicted: 'contradicted',
  mixed: 'conflicting',
  unresolved: 'open',
};
const LINK_STATUS: Record<string, string> = {
  read: 'Read',
  not_read: 'Not read',
  failed: 'Could not be read',
};

// Fonts embed only the glyphs they have; emoji are left out and the report says so.
const EMOJI = /[\p{Extended_Pictographic}\u{FE0F}\u{200D}\u{1F3FB}-\u{1F3FF}]/gu;
export function withoutEmoji(text: string): string {
  return text.replace(EMOJI, '').replace(/ {2,}/g, ' ');
}

/** Source text as a browser shows it inline: runs of spaces and line breaks become one space. */
function inline(text: string): string {
  return withoutEmoji(text).replace(/\s+/g, ' ');
}

const styles = StyleSheet.create({
  // lineHeight lives on the body, not the page: react-pdf drops fixed absolute text that has one.
  page: {
    paddingTop: 0,
    paddingBottom: 56,
    paddingHorizontal: 0,
    fontFamily: 'Funnel Sans',
    fontSize: 9.5,
    color: BRAND.ink,
  },
  body: { paddingHorizontal: 40 },
  continuationSpace: { height: 36 },
  band: {
    backgroundColor: BRAND.gray,
    paddingHorizontal: 40,
    paddingTop: 26,
    paddingBottom: 22,
  },
  bandRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  brand: { flexDirection: 'row', alignItems: 'center' },
  mark: { width: 26, height: 26, marginRight: 9 },
  wordmark: { fontFamily: 'Funnel Display', fontSize: 15, color: '#ffffff' },
  bandLabel: { fontSize: 8.5, color: '#a2a2aa', textAlign: 'right' },
  title: {
    fontFamily: 'Funnel Display',
    fontSize: 24,
    lineHeight: 1.2,
    color: '#ffffff',
    marginTop: 22,
  },
  subtitle: { fontSize: 9.5, lineHeight: 1.4, color: '#c4c4cc', marginTop: 6 },
  sectionTitle: {
    fontFamily: 'Funnel Display',
    fontSize: 13,
    marginTop: 22,
    marginBottom: 8,
  },
  inputBox: {
    backgroundColor: BRAND.soft,
    borderLeftWidth: 3,
    borderLeftColor: BRAND.blue2,
    borderRadius: 4,
    padding: 12,
    fontSize: 10,
    lineHeight: 1.5,
  },
  inputLabel: {
    fontSize: 7,
    fontWeight: 600,
    letterSpacing: 0.6,
    color: BRAND.muted,
    marginBottom: 3,
  },
  inputPart: {
    marginTop: 10,
    paddingTop: 8,
    borderTopWidth: 1,
    borderTopColor: BRAND.line,
  },
  inputItem: { marginTop: 4 },
  glance: { flexDirection: 'row', flexWrap: 'wrap', marginTop: 2 },
  stat: {
    borderWidth: 1,
    borderColor: BRAND.line,
    borderRadius: 6,
    paddingVertical: 8,
    paddingHorizontal: 12,
    marginRight: 8,
    marginBottom: 8,
    minWidth: 90,
  },
  statValue: { fontFamily: 'Funnel Display', fontSize: 16, lineHeight: 1.25, color: BRAND.blue1 },
  statLabel: { fontSize: 8, color: BRAND.muted, marginTop: 2 },
  row: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap' },
  muted: { color: BRAND.muted },
  small: { fontSize: 8.5 },
  listItem: {
    paddingVertical: 6,
    borderBottomWidth: 1,
    borderBottomColor: BRAND.line,
  },
  claim: {
    borderWidth: 1,
    borderColor: BRAND.line,
    borderRadius: 8,
    padding: 14,
    marginBottom: 12,
  },
  claimHead: { flexDirection: 'row', justifyContent: 'space-between' },
  claimNumber: {
    fontFamily: 'JetBrains Mono',
    fontSize: 11,
    color: BRAND.blue1,
    marginRight: 8,
  },
  claimStatement: { fontFamily: 'Funnel Display', fontSize: 12.5, lineHeight: 1.35, flex: 1 },
  verdictColumn: { alignItems: 'flex-end', marginLeft: 12, maxWidth: 160 },
  verdictSummary: { fontSize: 7.5, color: BRAND.muted, marginTop: 4, textAlign: 'right' },
  tag: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    borderRadius: 9,
    borderWidth: 1,
    paddingVertical: 2,
    paddingLeft: 5,
    paddingRight: 8,
  },
  tagText: { fontFamily: 'Funnel Sans', fontWeight: 600, fontSize: 8, lineHeight: 1.2 },
  detail: {
    backgroundColor: '#fafafb',
    borderWidth: 1,
    borderColor: BRAND.line,
    borderRadius: 6,
    padding: 11,
    marginTop: 9,
  },
  detailTitle: { fontFamily: 'Funnel Display', fontSize: 11, lineHeight: 1.35, marginTop: 6 },
  detailNote: { fontSize: 8.8, lineHeight: 1.5, color: BRAND.muted, marginTop: 3 },
  groupLabel: {
    fontSize: 7,
    fontWeight: 600,
    letterSpacing: 0.6,
    color: BRAND.muted,
    marginTop: 9,
    marginBottom: 3,
  },
  sourceName: { fontWeight: 600, fontSize: 8.8, color: BRAND.blue1, textDecoration: 'none' },
  quote: {
    borderLeftWidth: 2,
    borderLeftColor: '#c9cbd3',
    paddingLeft: 8,
    marginTop: 4,
    fontSize: 9,
    lineHeight: 1.5,
  },
  excerpt: { backgroundColor: BRAND.highlight, color: BRAND.ink },
  budget: {
    backgroundColor: '#fdf6e7',
    borderWidth: 1,
    borderColor: '#efd9a8',
    borderRadius: 6,
    padding: 11,
    marginTop: 4,
  },
  facts: { flexDirection: 'row', paddingVertical: 3 },
  factLabel: { width: 110, color: BRAND.muted },
  factValue: { flex: 1 },
  bullet: { flexDirection: 'row', marginBottom: 4 },
  bulletDot: { width: 10, color: BRAND.blue2 },
  closing: {
    marginTop: 18,
    paddingTop: 10,
    borderTopWidth: 1,
    borderTopColor: BRAND.line,
    fontSize: 8.5,
    lineHeight: 1.5,
    color: BRAND.muted,
  },
  footerLine: {
    position: 'absolute',
    bottom: 36,
    left: 40,
    right: 40,
    borderTopWidth: 1,
    borderTopColor: BRAND.line,
  },
  footerMark: { position: 'absolute', bottom: 21, left: 40, width: 10, height: 10 },
  footerLeft: {
    position: 'absolute',
    bottom: 20,
    left: 55,
    fontSize: 7.5,
    color: BRAND.muted,
  },
  footerRight: {
    position: 'absolute',
    bottom: 20,
    right: 40,
    fontSize: 7.5,
    color: BRAND.muted,
  },
});

function ToneIcon({ tone, color }: { tone: Tone; color: string }) {
  const stroke = { stroke: color, strokeWidth: 2.2, fill: 'none' } as const;
  return (
    <Svg width={9} height={9} viewBox="0 0 24 24" style={{ marginRight: 4 }}>
      {tone === 'open' ? (
        <Circle cx="12" cy="12" r="10" {...stroke} strokeDasharray="3.2 2.6" />
      ) : (
        <Circle cx="12" cy="12" r="10" {...stroke} />
      )}
      {tone === 'supported' && <Path d="m8.5 12 2.5 2.5 4.5-5" {...stroke} />}
      {tone === 'contradicted' && <Path d="m15 9-6 6M9 9l6 6" {...stroke} />}
      {tone === 'conflicting' && <Path d="M7 9.5h10M7 14.5h10" {...stroke} />}
      {tone === 'muted' && <Line x1="8" y1="12" x2="16" y2="12" {...stroke} />}
    </Svg>
  );
}

function Tag({ tone, label }: { tone: Tone; label: string }) {
  const colors = TONE[tone];
  return (
    <View
      style={[
        styles.tag,
        {
          backgroundColor: colors.background,
          borderColor: colors.color,
          borderStyle: tone === 'open' ? 'dashed' : 'solid',
        },
      ]}
    >
      <ToneIcon tone={tone} color={colors.color} />
      <Text style={[styles.tagText, { color: colors.color }]}>{label}</Text>
    </View>
  );
}

function Bullets({ items }: { items: string[] }) {
  return (
    <View>
      {items.map((item, index) => (
        <View style={styles.bullet} key={index} wrap={false}>
          <Text style={styles.bulletDot}>•</Text>
          <Text style={{ flex: 1 }}>{item}</Text>
        </View>
      ))}
    </View>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.facts} wrap={false}>
      <Text style={styles.factLabel}>{label}</Text>
      <Text style={styles.factValue}>{value}</Text>
    </View>
  );
}

type Evidence = Report['evidence'][number];
type Source = Report['sources'][number];

function Quote({ evidence, source }: { evidence: Evidence; source?: Source }) {
  const parts = excerptParts(evidence, source);
  return (
    <View style={styles.quote} minPresenceAhead={30}>
      {parts.unique ? (
        <Text>
          <Text style={styles.muted}>
            {parts.hasMoreBefore ? '… ' : ''}
            {inline(parts.before)}
            {parts.before ? ' ' : ''}
          </Text>
          <Text style={styles.excerpt}>{inline(evidence.excerpt)}</Text>
          <Text style={styles.muted}>
            {parts.after ? ' ' : ''}
            {inline(parts.after)}
            {parts.hasMoreAfter && parts.after ? ' …' : ''}
          </Text>
        </Text>
      ) : (
        <Text style={styles.excerpt}>{inline(evidence.excerpt)}</Text>
      )}
    </View>
  );
}

function EvidenceGroups({
  ids,
  evidence,
  sources,
  labelFor,
}: {
  ids: string[];
  evidence: Evidence[];
  sources: Source[];
  labelFor: (id: string) => string;
}) {
  const groups: { key: string; label: string; source?: Source; items: Evidence[] }[] = [];
  for (const id of ids) {
    const item = evidence.find((entry) => entry.id === id);
    if (!item) continue;
    const label = labelFor(id);
    const key = `${label}|${item.source_id}`;
    const group = groups.find((entry) => entry.key === key);
    if (group) group.items.push(item);
    else
      groups.push({
        key,
        label,
        source: sources.find((source) => source.id === item.source_id),
        items: [item],
      });
  }
  return (
    <>
      {groups.map((group) => {
        const parts = group.items[0] && excerptParts(group.items[0], group.source);
        const type = sourceTypeText(group.source?.source_type);
        return (
          <View key={group.key}>
            <Text style={styles.groupLabel}>{group.label.toUpperCase()}</Text>
            <View style={styles.row}>
              {parts?.url ? (
                <Link src={parts.url.href} style={styles.sourceName}>
                  {sourceDisplayName(group.source)}
                </Link>
              ) : (
                <Text style={styles.sourceName}>{sourceDisplayName(group.source)}</Text>
              )}
              {type && (
                <Text style={[styles.muted, styles.small, { marginLeft: 4 }]}>· {type}</Text>
              )}
            </View>
            {group.items.map((item) => (
              <Quote key={item.id} evidence={item} source={group.source} />
            ))}
          </View>
        );
      })}
    </>
  );
}

// Each footer part is its own fixed, absolutely positioned element, the layout react-pdf repeats
// reliably on every page.
function MediaList({ items, label }: { items: Report['media']; label: string }) {
  if (!items?.length) return null;
  return (
    <View style={styles.inputPart}>
      <Text style={styles.inputLabel}>{label}</Text>
      {items.map((item) => (
        <View style={styles.inputItem} key={item.id} wrap={false}>
          <Text style={{ fontWeight: 600 }}>{item.filename}</Text>
          <Text style={[styles.muted, styles.small]}>
            {[
              item.kind,
              item.analysis.status.replace('_', ' '),
              item.origin.matches.length ? `found on ${item.origin.matches.length} pages` : null,
              item.prior_checks?.reviews.length
                ? `${item.prior_checks.reviews.length} published fact checks`
                : null,
            ]
              .filter(Boolean)
              .join(' · ')}
          </Text>
        </View>
      ))}
    </View>
  );
}

function Footer({ id }: { id: string }) {
  return (
    <>
      <View style={styles.footerLine} fixed />
      <Image src="/brand/clear-context-mark.png" style={styles.footerMark} fixed />
      <Text style={styles.footerLeft} fixed>
        Clear Context · Investigation report · {id.slice(0, 8)}
      </Text>
      <Text
        style={styles.footerRight}
        fixed
        render={({ pageNumber, totalPages }) => `Page ${pageNumber} of ${totalPages}`}
      />
    </>
  );
}

export function ReportDocument({
  investigation,
  report,
  researchRan,
  generatedAt,
}: {
  investigation: Investigation;
  report: Report;
  researchRan: boolean;
  generatedAt: Date;
}) {
  const created = new Date(investigation.created_at).toLocaleDateString('en-GB', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  });
  const research = researchRan
    ? `${modeLabel(investigation.research_mode ?? 'balanced')} research`
    : null;
  const components = report.findings.flatMap((finding) => finding.components ?? []);
  const limited = report.research_summary?.budget_limited ?? 0;
  const strippedEmoji = [
    investigation.text,
    ...report.evidence.map((item) => item.excerpt),
    ...report.sources.map((source) => source.content),
  ].some((text) => withoutEmoji(text) !== text.replace(/ {2,}/g, ' '));
  const uploadedMedia = (report.media ?? []).filter((item) => !item.source_url);
  const linkMedia = (report.media ?? []).filter((item) => item.source_url);
  const coverage = report.extraction_coverage;
  const ranges = coverage?.chunks.filter((chunk) => chunk.status !== 'split') ?? [];

  return (
    <Document
      title={`Clear Context report ${report.investigation_id}`}
      author="Clear Context"
      creator="Clear Context"
      producer="Clear Context"
      subject="Investigation report"
    >
      <Page size="A4" style={styles.page}>
        {/* Fixed elements repeat on every page; declared first so they render reliably. */}
        <Footer id={report.investigation_id} />
        {/* Pages after the first start below a top margin; the first page starts with the band. */}
        <View
          fixed
          render={({ pageNumber }) =>
            pageNumber > 1 ? <View style={styles.continuationSpace} /> : null
          }
        />
        <View style={styles.band}>
          <View style={styles.bandRow}>
            <View style={styles.brand}>
              <Image src="/brand/clear-context-mark.png" style={styles.mark} />
              <Text style={styles.wordmark}>Clear Context</Text>
            </View>
            <Text style={styles.bandLabel}>
              Generated{' '}
              {generatedAt.toLocaleString('en-GB', { dateStyle: 'medium', timeStyle: 'short' })}
            </Text>
          </View>
          <Text style={styles.title}>Investigation report</Text>
          <Text style={styles.subtitle}>
            {[
              created,
              `${report.claims.length} ${report.claims.length === 1 ? 'claim' : 'claims'} extracted`,
              research,
              report.mode === 'mock' ? 'Development preview' : null,
            ]
              .filter(Boolean)
              .join('  ·  ')}
          </Text>
        </View>
        <Svg height={4} width="100%" viewBox="0 0 100 4" preserveAspectRatio="none">
          <Defs>
            <LinearGradient id="brandLine" x1="0" y1="0" x2="1" y2="0">
              <Stop offset="0" stopColor={BRAND.blue1} />
              <Stop offset="1" stopColor={BRAND.blue2} />
            </LinearGradient>
          </Defs>
          <Rect x="0" y="0" width="100" height="4" fill="url(#brandLine)" />
        </Svg>

        <View style={styles.body}>
          <Text style={styles.sectionTitle} minPresenceAhead={90}>
            At a glance
          </Text>
          <View style={styles.glance}>
            <View style={styles.stat}>
              <Text style={styles.statValue}>{report.claims.length}</Text>
              <Text style={styles.statLabel}>Claims</Text>
            </View>
            <View style={styles.stat}>
              <Text style={styles.statValue}>{components.length}</Text>
              <Text style={styles.statLabel}>Details judged</Text>
            </View>
            <View style={styles.stat}>
              <Text style={styles.statValue}>{report.sources.length}</Text>
              <Text style={styles.statLabel}>Sources cited</Text>
            </View>
            <View style={styles.stat}>
              <Text style={styles.statValue}>{report.evidence.length}</Text>
              <Text style={styles.statLabel}>Quoted passages</Text>
            </View>
          </View>
          {components.length > 0 && (
            <Text style={[styles.muted, styles.small]}>
              Detail results: {detailSummary(components)}
            </Text>
          )}

          <Text style={styles.sectionTitle} minPresenceAhead={90}>
            Your input
          </Text>
          {/* Everything the user sent, in one box: text, links in it and attached files. */}
          <View style={styles.inputBox}>
            <Text style={styles.inputLabel}>TEXT YOU ENTERED</Text>
            <Text>
              {withoutEmoji(
                investigation.text ||
                  'No text was entered. Claims come from text read from the files.',
              )}
            </Text>
            {!!report.links?.length && (
              <View style={styles.inputPart}>
                <Text style={styles.inputLabel}>LINKS IN YOUR TEXT</Text>
                {report.links.map((link) => (
                  <View style={styles.inputItem} key={link.url} wrap={false}>
                    <Text>
                      <Text style={{ fontWeight: 600 }}>{link.title || link.site || link.url}</Text>
                      <Text style={styles.muted}> · {LINK_STATUS[link.status] ?? link.status}</Text>
                    </Text>
                    <Text style={[styles.muted, styles.small]}>{link.url}</Text>
                    {link.reason && <Text style={[styles.muted, styles.small]}>{link.reason}</Text>}
                  </View>
                ))}
                <MediaList items={linkMedia} label="IMAGES FROM LINKED PAGES" />
              </View>
            )}
            <MediaList items={uploadedMedia} label="FILES YOU ATTACHED" />
          </View>

          <Text style={styles.sectionTitle} minPresenceAhead={90}>
            Claim by claim
          </Text>
          {report.claims.map((claim, index) => {
            const finding = report.findings.find((item) => item.claim_id === claim.id);
            const parts = finding?.components ?? [];
            const evidence = report.evidence.filter((item) =>
              finding?.evidence_ids.includes(item.id),
            );
            const perDetail = parts.length > 0;
            // Counted from detail results, exactly as in the web report.
            const summary = claimSummary(parts);
            const verdictTone: Tone = summary
              ? COMPONENT_TONE[summary.tone]
              : finding
                ? ASSESSMENT_TONE[finding.assessment]
                : 'muted';
            const verdictLabel =
              summary?.label ?? (finding ? ASSESSMENT_LABEL[finding.assessment] : 'No finding');
            return (
              <View style={styles.claim} key={claim.id}>
                <View style={styles.claimHead} wrap={false}>
                  <Text style={styles.claimNumber}>{index + 1}</Text>
                  <Text style={styles.claimStatement}>
                    {withoutEmoji(claim.statement || claim.text)}
                  </Text>
                  <View style={styles.verdictColumn}>
                    <Tag tone={verdictTone} label={verdictLabel} />
                    {perDetail && <Text style={styles.verdictSummary}>{detailSummary(parts)}</Text>}
                  </View>
                </View>
                {!perDetail && finding?.explanation && (
                  <Text style={[styles.detailNote, { marginTop: 8 }]}>{finding.explanation}</Text>
                )}
                {parts.map((component, componentIndex) => (
                  <View style={styles.detail} key={`${component.description}-${componentIndex}`}>
                    <View wrap={false}>
                      <Tag
                        tone={COMPONENT_TONE[component.status]}
                        label={COMPONENT_STATUS[component.status].label}
                      />
                      <Text style={styles.detailTitle}>{withoutEmoji(component.description)}</Text>
                      <Text style={styles.detailNote}>{withoutEmoji(component.explanation)}</Text>
                    </View>
                    <EvidenceGroups
                      ids={component.evidence_ids}
                      evidence={evidence}
                      sources={report.sources}
                      labelFor={(id) =>
                        component.evidence_relations?.[id] === 'contradicts'
                          ? 'Contradicting source'
                          : 'Supporting source'
                      }
                    />
                    <EvidenceGroups
                      ids={component.context_evidence_ids ?? []}
                      evidence={evidence}
                      sources={report.sources}
                      labelFor={() =>
                        'Reviewed for this research question; not cited for this detail'
                      }
                    />
                  </View>
                ))}
                {!perDetail && (
                  <EvidenceGroups
                    ids={evidence.map((item) => item.id)}
                    evidence={evidence}
                    sources={report.sources}
                    labelFor={() => 'Source'}
                  />
                )}
              </View>
            );
          })}

          {limited > 0 && (
            <View style={styles.budget} wrap={false}>
              <Text style={{ fontWeight: 600, color: '#8a5a00' }}>
                {limited} {limited === 1 ? 'detail' : 'details'} did not fit the{' '}
                {modeLabel(investigation.research_mode ?? 'balanced')} research budget
              </Text>
              <Text style={{ marginTop: 3 }}>
                These details were not researched. A Deep run or a continuation can research them
                from the app.
              </Text>
            </View>
          )}

          {report.sources.length > 0 && (
            <>
              <Text style={styles.sectionTitle} minPresenceAhead={90}>
                Sources
              </Text>
              {report.sources.map((source) => {
                const type = sourceTypeText(source.source_type);
                return (
                  <View style={styles.listItem} key={source.id} wrap={false}>
                    <Text>
                      <Text style={{ fontWeight: 600 }}>{sourceDisplayName(source)}</Text>
                      {type && <Text style={styles.muted}> · {type}</Text>}
                    </Text>
                    <Link src={source.url} style={[styles.small, { color: BRAND.blue1 }]}>
                      {source.url}
                    </Link>
                  </View>
                );
              })}
            </>
          )}

          <Text style={styles.sectionTitle} minPresenceAhead={90}>
            Technical details
          </Text>
          <Fact label="Report" value={`${report.investigation_id} · revision ${report.revision}`} />
          <Fact
            label="Mode"
            value={[report.mode === 'mock' ? 'Development preview' : 'Meta models', research]
              .filter(Boolean)
              .join(' · ')}
          />
          {coverage && (
            <Fact
              label="Claim extraction"
              value={`${ranges.filter((chunk) => chunk.status === 'processed').length} of ${ranges.length} input ${ranges.length === 1 ? 'range' : 'ranges'} processed in ${coverage.model_calls} model ${coverage.model_calls === 1 ? 'call' : 'calls'}. Processing every range does not guarantee that every claim was found.`}
            />
          )}
          {report.limitations.length > 0 && (
            <>
              <Text style={[styles.groupLabel, { marginTop: 12 }]}>SCOPE AND LIMITATIONS</Text>
              <Bullets items={report.limitations} />
            </>
          )}

          <View style={styles.closing} wrap={false}>
            <Text>
              No supporting evidence is not the same as evidence that a claim is false. Quotes are
              copied word for word from pages read during the investigation.
              {strippedEmoji
                ? ' Emoji are left out of this PDF; the JSON export keeps the exact text.'
                : ''}
            </Text>
          </View>
        </View>
      </Page>
    </Document>
  );
}
