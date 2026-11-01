import { DetailTag, VerdictLabel } from './VerdictTag';
import { CLAIM_SUMMARY, type ClaimSummaryKey, type ComponentStatus } from '../lib/labels';

const STEPS = [
  {
    title: 'Bring your input',
    text: 'Paste text, attach images or video, or include links. The browser extension can send a selection from any page.',
  },
  {
    title: 'Claims are separated',
    text: 'Each checkable statement keeps its original wording. “Highlight in your input” shows where it came from. Claims are split into details that sources can settle.',
  },
  {
    title: 'Sources are researched',
    text: 'Searches run within the depth you choose: Fast, Balanced or Deep. Evidence is quoted word for word from pages that were actually read.',
  },
  {
    title: 'Each detail is judged',
    text: 'Only against those quotes. Open any investigation step in a report to see what was recorded there.',
  },
];

const DETAIL_RESULTS: { status: ComponentStatus; text: string }[] = [
  { status: 'supported', text: 'Quoted sources back this detail.' },
  { status: 'contradicted', text: 'Quoted sources state otherwise.' },
  { status: 'conflicting', text: 'Some quoted sources back it and others contradict it.' },
  {
    status: 'insufficient',
    text: 'It was checked, but the sources read do not settle it. This is not the same as false.',
  },
  {
    status: 'not_assessed',
    text: 'It was never judged, for example because the research budget ran out or a call failed.',
  },
];

export function HelpGuide() {
  return (
    <div className="help-guide">
      <ol className="help-steps">
        {STEPS.map((step, index) => (
          <li key={step.title}>
            <span className="help-step-number">{String(index + 1).padStart(2, '0')}</span>
            <div>
              <h3>{step.title}</h3>
              <p>{step.text}</p>
            </div>
          </li>
        ))}
      </ol>
      <section className="help-results" aria-labelledby="help-results-title">
        <h3 id="help-results-title">Reading the results</h3>
        <p className="help-results-intro">Every detail of a claim gets one of these results.</p>
        <dl>
          {DETAIL_RESULTS.map((item) => (
            <div key={item.status}>
              <dt>
                <DetailTag status={item.status} />
              </dt>
              <dd>{item.text}</dd>
            </div>
          ))}
        </dl>
      </section>
      <section className="help-results" aria-labelledby="help-claims-title">
        <h3 id="help-claims-title">The result of a claim</h3>
        <p className="help-results-intro">
          The tag at the top of a claim is counted from its details; no model decides it. A claim
          with one detail shows that detail's result. It describes the details that were checked,
          not parts of the claim that no detail covers.
        </p>
        <dl>
          {(Object.keys(CLAIM_SUMMARY) as ClaimSummaryKey[]).map((key) => (
            <div key={key}>
              <dt>
                <VerdictLabel tone={CLAIM_SUMMARY[key].tone} label={CLAIM_SUMMARY[key].label} />
              </dt>
              <dd>{CLAIM_SUMMARY[key].rule}</dd>
            </div>
          ))}
        </dl>
      </section>
    </div>
  );
}
