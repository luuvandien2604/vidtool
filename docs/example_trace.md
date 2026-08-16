# Example trace: narration drives visual editing

## Narration (beat beat_0007)

> Then Schabowski held the travel regulation document in his hands, shuffling his notes at the live press conference.

- window: 35.6s - 42.8s (7.1s)
- entities: Schabowski | objects: document, regulation | tone: neutral

## Semantic beat

- semantic function: **EVIDENCE**
- visual intent: show the primary source material itself
- information density: 0.2

## Candidate visual strategies (scored)

| strategy | family | total | semantic | storytelling | novelty |
|---|---|---|---|---|---|
| document_plus_quote | document_evidence | 0.960 | 1.00 | 0.90 | 1.00 |
| single_document_focus | document_evidence | 0.948 | 1.00 | 0.85 | 1.00 |
| document_stack | document_evidence | 0.748 | 1.00 | 0.85 | 1.00 |
| clip_plus_annotation | document_evidence | 0.735 | 1.00 | 0.80 | 1.00 |
| evidence_board | causal_network | 0.523 | 1.00 | 0.90 | 0.92 |

**Selected:** `document_plus_quote` (family `document_evidence`, novelty 1.00)

**Why:** Beat intends to show the primary source material itself. 'document_plus_quote' fits EVIDENCE because: Document shown alongside the sentence that matters. Runner-up 'single_document_focus' scored lower on novelty/fit (novelty=1.00).

## Composition

- variant reasoning: variant=single_focus; docs=1 quote=False
- signature: `document_evidence|DOCUMENTx1,LINEx1|hero=LINE@01|none|rel=0:flat|asset_type=none...`
- focus target: comp_beat_0007_doc
- entrance sequence:

  - +0.00s  comp_beat_0007_doc                 DOCUMENT_UNFOLD
  - +4.98s  comp_beat_0007_mark                MARKER_LINE

## Motion plan

- camera: stable (Documentary restraint: camera fixed; motion comes from editorial elements.)
  -  35.64- 36.34s ENTRANCE comp_beat_0007_doc                 DOCUMENT_UNFOLD
  -  41.90- 42.75s EXIT     comp_beat_0007_doc                 SLIDE_OUT
  -  40.62- 41.32s ENTRANCE comp_beat_0007_mark                MARKER_LINE
  -  41.90- 42.75s EXIT     comp_beat_0007_mark                DISSOLVE
  -  35.64- 36.44s ENTRANCE comp_beat_0007_paper_texture       DISSOLVE

(same structure generated for all 12 beats)
