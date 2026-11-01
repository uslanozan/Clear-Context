import type { ExtractedClaim } from '../lib/types';

export function ClaimSource({ claim, input }: { claim: ExtractedClaim; input: string }) {
  const span = claim.source_span;
  if (!span) return null;
  const characters = Array.from(input);
  const matches = characters.slice(span.start, span.end).join('') === claim.text;
  if (!matches) return <p className="muted">The saved source location could not be matched.</p>;

  return (
    <details className="claim-provenance">
      <summary>Highlight in your input</summary>
      <p className="source-location">
        Original characters {span.start + 1}–{span.end}
      </p>
      <p className="source-context" dir="auto">
        {span.start > 100 ? '…' : ''}
        {characters.slice(Math.max(0, span.start - 100), span.start).join('')}
        <mark>{claim.text}</mark>
        {characters.slice(span.end, span.end + 100).join('')}
        {span.end + 100 < characters.length ? '…' : ''}
      </p>
      {!!claim.context_spans?.length && (
        <div>
          <p className="source-location">Context used to interpret this statement</p>
          {claim.context_spans.map((context, index) => (
            <p className="source-context" key={`${context.start}-${index}`} dir="auto">
              {context.text}
            </p>
          ))}
        </div>
      )}
      <p className="source-location">
        The statement is a model interpretation, not a verified fact.
      </p>
    </details>
  );
}
