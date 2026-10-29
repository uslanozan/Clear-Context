"""Generate the evidence-relative assessment flow in the approved visual style."""

from pathlib import Path

from generate import ACCENT, INK, MUTED, OUT, PAPER, node, text


def main():
    nodes = ''.join([
        node(50,210,280,170,'Claims + needs',['Explicit case and IDs','Needs stay separate']),
        node(355,210,280,170,'Saved evidence',['V1 receipt + context','Same source offsets']),
        node(660,210,280,170,'Muse assessment',['Relation + short quotes','Joint coverage + time'],focal=True),
        node(965,210,280,170,'Code validation',['Need IDs + exact text','Resolve source offsets']),
        node(1270,210,280,170,'Need result',['Status + source links','Saved judge receipt']),
    ])
    arrows=''.join(f'<path d="M{x} 295H{x+25}"/>' for x in [330,635,940,1245])
    svg=f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 900" role="img" aria-labelledby="judge-title judge-desc">
<title id="judge-title">From saved evidence to need-level assessment</title>
<desc id="judge-desc">An implemented standalone evaluation flow. Claims and needs reference V1 selection receipts and source contexts. Muse assesses evidence relations. Code validates IDs and exact quotations, resolves source offsets, derives need statuses, and stores a receipt. No evidence needs are insufficient without inference; errors stay errors. No global truth or source-trust score is produced.</desc>
<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10Z" fill="{MUTED}"/></marker></defs>
<rect width="1600" height="900" fill="{PAPER}"/>
{text(50,75,'Judge the evidence, preserve the boundaries',size=36,weight=600)}
{text(50,120,'Working evaluation service · Not connected to application graph or UI',size=22,color=MUTED)}
<g fill="none" stroke="{MUTED}" stroke-width="2" marker-end="url(#arrow)">{arrows}</g>{nodes}
{text(50,475,'A source relation is not a global truth verdict',size=28,weight=600)}
{text(50,530,['Synthetic example: a source gives 8 km between city centers.','That can address distance; it does not establish urban adjacency.'],size=23,line_height=38)}
{text(50,640,'Reconcile gaps across excerpts · Record the temporal basis and its assumptions',size=23,color=ACCENT)}
{text(50,700,'No selected evidence → insufficient without a model call · Invalid output → explicit error',size=22,color=MUTED)}
{text(50,755,'Publication time is not an effective period · Repeated excerpts are not independent sources',size=22,color=MUTED)}
{text(50,825,'Bounded calls · No automatic retries · Source reliability unassessed · No full-claim verdict',size=20,color=MUTED)}
</svg>'''
    (OUT/'svg/11-evidence-judgment.svg').write_text(svg,encoding='utf-8')
    page=f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Evidence assessment | Clear Context</title><style>body{{margin:0;padding:24px;background:{PAPER};color:{INK};font:18px/1.6 'Source Sans 3',sans-serif}}main{{max-width:1600px;margin:auto}}svg{{width:100%;height:auto}}</style></head><body><main>{svg}<p>Implemented code: <code>services/evidence_judgment.py</code>, <code>repositories/judgment.py</code>, and <code>schemas/evidence_judgment.py</code>. Statuses describe only supplied evidence. The example is explanatory, not a measured inference result.</p></main></body></html>'''
    (OUT/'html/11-evidence-judgment.html').write_text(page,encoding='utf-8')
    return {'slug':'11-evidence-judgment','title':'Saved evidence to need-level assessment',
            'status':'EVALUATION SERVICE','notes':'Validated need-bound quotations and persisted assessment receipts. Source reliability and global claim verification are not implemented.'}


if __name__=='__main__':
    main()
