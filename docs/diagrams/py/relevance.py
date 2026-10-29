"""Generate an evidence relevance flow in the approved project theme."""

from generate import ACCENT, INK, MUTED, OUT, PAPER, text
from retrieval import node


def example_row(y, passage, relevance, relation):
    return f'''<rect x="60" y="{y}" width="650" height="74" rx="8" fill="white" stroke="#bfc0c0" stroke-width="2"/>
{text(82, y+45, passage, size=22)}
<path d="M710 {y+37} H850" fill="none" stroke="{MUTED}" stroke-width="2" marker-end="url(#arrow)"/>
<rect x="850" y="{y}" width="690" height="74" rx="8" fill="white" stroke="#bfc0c0" stroke-width="2"/>
{text(872, y+30, relevance, size=20, weight=600)}
{text(872, y+57, relation, size=19, color=MUTED)}'''


def main():
    nodes = node(60, 180, "Saved evidence", "Passages + source URLs", "Stable E1 / E2 / E3")
    nodes += node(430, 180, "Muse assessment", "Relevance + relation", "Direct / inferred basis", True)
    nodes += node(800, 180, "Code validation", "Check IDs and quotes", "Restore source URLs")
    nodes += node(1170, 180, "Need result", "Combine the evidence", "Record remaining gaps")
    arrows = '<path d="M330 246H430"/><path d="M700 246H800"/><path d="M1070 246H1170"/>'
    examples = example_row(410, "E1: North Bridge opened in 2019", "Relevant", "Directly contradicts the 2017 opening year")
    examples += example_row(505, "E2: North Bridge is 200 metres long", "Relevant", "Insufficient to determine the opening year")
    examples += example_row(600, "E3: South Museum opened in 2017", "Irrelevant", "Different entity; no material coverage")
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 900" role="img" aria-labelledby="relevance-title relevance-desc">
<title id="relevance-title">Relevance and evidence relations in a verification workflow</title>
<desc id="relevance-desc">An experimental flow from saved source passages through Muse assessment, code validation and a need-level result. Three synthetic passages about a bridge show direct contradiction, relevant but insufficient information, and irrelevant information. The default judge remains V1.2 and the workflow is not integrated into the application.</desc>
<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10Z" fill="{MUTED}"/></marker></defs>
<rect width="1600" height="900" fill="{PAPER}"/>
<g font-family="Source Sans 3, sans-serif" fill="{INK}">
{text(60, 76, "Separate relevance from evidence relations", size=36, weight=600)}
{text(60, 122, "Selectable evaluation candidate · Default V1.2 · Not connected to the application", size=22, color=MUTED)}
<g fill="none" stroke="{MUTED}" stroke-width="2" marker-end="url(#arrow)">{arrows}</g>{nodes}
{text(60, 374, "Synthetic target: North Bridge opened in 2017", size=25, weight=600)}
{examples}
{text(60, 760, "Each arrow connects an original passage to its assessment; URLs stay linked through IDs.", size=22, color=ACCENT)}
{text(60, 812, "Exact quotations and valid IDs do not prove semantic accuracy or source reliability.", size=20, color=MUTED)}
{text(60, 854, "Synthetic illustration · Need-level results only · Errors remain separate", size=18, color=MUTED)}
</g></svg>'''
    (OUT / 'svg/12-evidence-relevance.svg').write_text(svg, encoding='utf-8')
    page = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Evidence relevance | Clear Context</title><style>body{{margin:0;padding:24px;background:{PAPER};color:{INK};font:18px/1.6 'Source Sans 3',sans-serif}}main{{max-width:1600px;margin:auto}}svg{{width:100%;height:auto}}</style></head><body><main>{svg}<p>The arrows show the evaluation flow and the relation between each synthetic passage and its assessment. Source URLs remain bound to recorded evidence IDs. This selectable candidate is not connected to application routes or UI. Implemented in <code>schemas/evidence_judgment.py</code>, <code>providers/meta_judgment.py</code> and <code>services/evidence_judgment.py</code>.</p></main></body></html>'''
    (OUT / 'html/12-evidence-relevance.html').write_text(page, encoding='utf-8')
    return {'slug': '12-evidence-relevance', 'title': 'Relevance and evidence relations',
            'status': 'EVALUATION CANDIDATE', 'notes': 'Passage relevance, evidence relation and source URLs flow into a validated need-level assessment. Default remains V1.2.'}


if __name__ == '__main__':
    main()
