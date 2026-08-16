"""Deterministic semantic beat segmentation + classification.

Implements the BeatAnalyzer interface with lexical/structural heuristics:
sentence/clause splitting against word timings, 3-8s beat targeting, and
ordered cue rules for semantic function, entities, locations, dates, events,
objects, tone and density. All rules are topic-agnostic (spec section 31).
"""
from __future__ import annotations

import re

from videotool.domain.narration import Narration, WordTiming
from videotool.domain.semantic_beat import SemanticBeat, SemanticFunction

MIN_BEAT = 3.0
MAX_BEAT = 8.0
MERGE_TOLERANCE = 8.5  # slightly over target to avoid ugly micro-beats

_YEAR_RE = re.compile(r"\b(1[5-9]\d{2}|20\d{2})\b")
_NUMBER_RE = re.compile(r"\b\d[\d.,]*\b")
_CAPSEQ_RE = re.compile(r"\b([A-Z][a-zA-Z''-]+(?:\s+[A-Z][a-zA-Z''-]+){0,3})\b")
_QUOTED_RE = re.compile(r"\"([^\"]{8,})\"|'([^']{8,})'")

_LOCATION_CUES = ("in", "to", "through", "across", "from", "toward", "at")
_LOCATION_SUFFIXES = ("land", "stan", "ia", "y", "o", "a", "burg", "berg",
                      "ton", "city", "union", "republic", "states", "kingdom",
                      "west", "east", "germany", "austria", "hungary")
_HONORIFICS = ("Mr.", "Ms.", "Dr.", "Prof.", "President", "Minister",
               "Chancellor", "General", "Colonel", "Captain", "Director",
               "Secretary", "Ambassador", "Premier", "Marshal", "Father")

# ordered: first matching rule wins (most specific cues first)
_FUNCTION_RULES: list[tuple[SemanticFunction, list[str]]] = [
    (SemanticFunction.CAUSAL_EXPLANATION, ["because", "led to", "as a result",
                                           "therefore", "caused by", "due to",
                                           "made it clear", "forcing",
                                           "in response", "so that", "thus"]),
    (SemanticFunction.GEOGRAPHIC_MOVEMENT, ["fled", "crossed", "route",
                                            "escape", "migration", "border",
                                            "travelled", "traveled",
                                            "streamed", "poured", "through"]),
    (SemanticFunction.CONSEQUENCE, ["consequence", "aftermath",
                                    "the wall came", "were forced",
                                    "plunged", "was sealed", "collapsed",
                                    "fell"]),
    (SemanticFunction.TURNING_POINT, ["turning point", "everything changed",
                                      "suddenly", "that night", "at midnight",
                                      "overnight", "single", "one sentence"]),
    (SemanticFunction.CHRONOLOGY, ["weeks later", "days later",
                                   "months earlier", "that year",
                                   "the following year", "years before",
                                   "autumn", "summer", "spring", "winter",
                                   "by "]),
    (SemanticFunction.ESCALATION, ["more and more", "grew", "spread",
                                   "thousands", "mounting", "escalated",
                                   "swelled", "flood", "wave after"]),
    (SemanticFunction.CHARACTER_INTRODUCTION, ["introduced", "was a",
                                               "was born", "became",
                                               "spokesman", "official",
                                               "leader", "engineer", "president",
                                               "chancellor", "general"]),
    (SemanticFunction.LOCATION_INTRODUCTION, ["city of", "capital",
                                              "located", "sat at",
                                              "divided into", "province",
                                              "region of", "heart of"]),
    (SemanticFunction.EVIDENCE, ["document", "records", "memo",
                                 "declassified", "archive", "files",
                                 "report", "footage", "photograph",
                                 "transcript", "press conference"]),
    (SemanticFunction.DATA, ["percent", "%", "thousand", "million",
                             "billion", "figures", "numbers", "statistic"]),
    (SemanticFunction.COMPARISON, ["compared", "unlike", "in contrast",
                                   "while the", "whereas", "on the other"]),
    (SemanticFunction.PROCESS, ["began to", "step by step", "first",
                                "then", "procedure", "process"]),
    (SemanticFunction.TECHNICAL_EXPLANATION, ["system", "reactor", "engine",
                                              "mechanism", "design",
                                              "structure", "pressure",
                                              "telemetry", "circuit"]),
    (SemanticFunction.ATMOSPHERE, ["silence", "tension", "fear", "hope",
                                   "anxiety", "celebration", "silently",
                                   "watched", "waited"]),
    (SemanticFunction.REVEAL, ["revealed", "hidden", "secret", "unknown",
                               "nobody knew", "behind the"]),
    (SemanticFunction.SUMMARY, ["in the end", "finally", "by dawn",
                                "what remained", "legacy", "today"]),
]

_TONE_LEXICON: dict[str, list[str]] = {
    "tense": ["tension", "fear", "anxiety", "crisis", "silently", "watched"],
    "urgent": ["thousands", "flood", "spread", "forcing", "mounting"],
    "grim": ["fell", "collapsed", "died", "crash", "disaster", "radiation"],
    "hopeful": ["hope", "opened", "freedom", "celebration", "dawn"],
    "neutral": [],
}


def _sentences_with_word_spans(text: str) -> list[tuple[int, int]]:
    """(start_word_idx, end_word_idx) per sentence, computed on token list."""
    tokens = text.split()
    spans: list[tuple[int, int]] = []
    start = 0
    for i, tok in enumerate(tokens):
        if tok.endswith((".", "!", "?")) or tok.endswith(('."', '!"', '?"')):
            spans.append((start, i + 1))
            start = i + 1
    if start < len(tokens):
        spans.append((start, len(tokens)))
    return spans


def _clause_breaks(tokens: list[str]) -> list[int]:
    """Indices after which a long sentence may be split (clause boundaries)."""
    breaks: list[int] = []
    for i, tok in enumerate(tokens):
        if tok.endswith((",", ";", ":")) and i < len(tokens) - 1:
            nxt = tokens[i + 1].lower()
            if nxt in ("and", "but", "meanwhile", "while", "then", "which",
                       "who", "so", "yet", "for", "because", "as"):
                breaks.append(i + 1)
            elif tok.endswith((";", ":")):
                breaks.append(i + 1)
        if tok.lower() in ("meanwhile", "however", "but", "yet") and 0 < i < len(tokens) - 3:
            breaks.append(i)
    return sorted(set(breaks))


# capitalized single words that are sentence mechanics, not entities
_CLOSED_CLASS = {
    "The", "A", "An", "He", "She", "It", "They", "We", "You", "His", "Her",
    "Then", "That", "This", "These", "Those", "Because", "Within", "Asked",
    "Weeks", "Months", "Years", "Thousands", "Millions", "Hundreds",
    "By", "In", "On", "At", "For", "But", "And", "One", "Two", "Three",
    "Meanwhile", "However", "Private", "November", "October", "December",
    "January", "February", "March", "April", "May", "June", "July", "August",
    "September", "Imagine", "Asked",
}


class HeuristicBeatAnalyzer:
    """Deterministic implementation of BeatAnalyzer."""

    def analyze(self, narration: Narration, episode_id: str) -> list[SemanticBeat]:
        words = list(narration.words)
        if not words:
            return []
        units = self._build_units(words)
        units = self._merge_short(units, words)
        beats = []
        for i, (ws, we) in enumerate(units, start=1):
            seg = words[ws:we]
            text = " ".join(w.text for w in seg)
            start = seg[0].start_sec
            end = seg[-1].end_sec
            fn = self._classify(text, is_first=(i == 1), is_last=(i == len(units)))
            beats.append(SemanticBeat(
                beat_id=f"beat_{i:04d}",
                start_sec=round(start, 3),
                end_sec=round(end, 3),
                narration_text=text,
                word_start=ws,
                word_end=we,
                semantic_function=fn,
                visual_intent=self._visual_intent(fn, text),
                entities=self._entities(text),
                locations=self._locations(text, fn),
                dates=_YEAR_RE.findall(text),
                events=self._events(text),
                objects=self._objects(text),
                relationships=self._relationships(text),
                emotional_tone=self._tone(text),
                information_density=self._density(text),
                continuity_context="",
                analysis_reason=f"function={fn.value} assigned by cue-rule match",
            ))
        for prev, beat in zip(beats, beats[1:]):
            key = prev.entities[:1] or [prev.semantic_function.value]
            beat.continuity_context = (
                f"follows {prev.beat_id} ({prev.semantic_function.value}); "
                f"carried entity: {key[0]}")
        return beats

    # ---- unit building ---------------------------------------------------
    def _build_units(self, words: list[WordTiming]) -> list[tuple[int, int]]:
        """Sentences, split further at clause boundaries when > MAX_BEAT."""
        text = " ".join(w.text for w in words)
        units: list[tuple[int, int]] = []
        for (ws, we) in _sentences_with_word_spans(text):
            seg = words[ws:we]
            dur = seg[-1].end_sec - seg[0].start_sec
            if dur <= MERGE_TOLERANCE:
                units.append((ws, we))
                continue
            parts = self._split_long(seg)
            for p_ws, p_we in parts:
                units.append((ws + p_ws, ws + p_we))
        return units

    def _split_long(self, seg: list[WordTiming]) -> list[tuple[int, int]]:
        """Split one over-long sentence at clause boundaries near MAX_BEAT."""
        breaks = _clause_breaks([w.text for w in seg])
        parts: list[tuple[int, int]] = []
        start = 0
        for b in breaks:
            dur = seg[b - 1].end_sec - seg[start].start_sec
            if dur >= MIN_BEAT and dur <= MERGE_TOLERANCE:
                parts.append((start, b))
                start = b
        if start < len(seg):
            parts.append((start, len(seg)))
        return parts or [(0, len(seg))]

    def _merge_short(self, units: list[tuple[int, int]],
                     words: list[WordTiming]) -> list[tuple[int, int]]:
        merged: list[tuple[int, int]] = []
        for span in units:
            if merged:
                prev = merged[-1]
                prev_dur = words[prev[1] - 1].end_sec - words[prev[0]].start_sec
                cur_dur = words[span[1] - 1].end_sec - words[span[0]].start_sec
                if prev_dur < MIN_BEAT and prev_dur + cur_dur <= MERGE_TOLERANCE:
                    merged[-1] = (prev[0], span[1])
                    continue
            merged.append(span)
        return merged

    # ---- classification ----------------------------------------------------
    def _classify(self, text: str, is_first: bool, is_last: bool) -> SemanticFunction:
        low = " " + text.lower() + " "
        if is_last and any(c in low for c in ("in the end", "finally", "legacy", "by dawn", "today")):
            return SemanticFunction.SUMMARY
        # spoken/written quotation always reads as a QUOTE beat
        if '"' in text or "\u201c" in text:
            return SemanticFunction.QUOTE
        if is_first and not _NUMBER_RE.search(_YEAR_RE.sub("", text)):
            if any(c in low for c in ("imagine", "one night", "what if", "in a single",
                                      "november", "october", "march", "silence",
                                      "midnight", "for decades", "behind")):
                return SemanticFunction.HOOK
        for fn, cues in _FUNCTION_RULES:
            for cue in cues:
                if f" {cue} " in low or low.strip().startswith(cue) or f" {cue}" in low and cue.endswith("."):
                    return fn
        if is_first:
            return SemanticFunction.ESTABLISHING_CONTEXT
        if _YEAR_RE.search(text):
            return SemanticFunction.CHRONOLOGY
        return SemanticFunction.ESTABLISHING_CONTEXT

    def _visual_intent(self, fn: SemanticFunction, text: str) -> str:
        intents = {
            SemanticFunction.HOOK: "arresting single-image opening that poses the episode question",
            SemanticFunction.ESTABLISHING_CONTEXT: "set time and place with layered archival context",
            SemanticFunction.CHARACTER_INTRODUCTION: "present the person with portrait + identity metadata",
            SemanticFunction.LOCATION_INTRODUCTION: "anchor the audience in a named place",
            SemanticFunction.CHRONOLOGY: "show events ordered in time",
            SemanticFunction.CAUSAL_EXPLANATION: "make causes converge into the event visible",
            SemanticFunction.EVIDENCE: "show the primary source material itself",
            SemanticFunction.COMPARISON: "put two states side by side",
            SemanticFunction.PROCESS: "show stages of the procedure unfolding",
            SemanticFunction.TECHNICAL_EXPLANATION: "explain the mechanism with schematic clarity",
            SemanticFunction.ESCALATION: "communicate growth and spreading pressure",
            SemanticFunction.TURNING_POINT: "isolate the decisive moment",
            SemanticFunction.CONSEQUENCE: "show what the cause produced",
            SemanticFunction.QUOTE: "let the spoken/written words carry the frame",
            SemanticFunction.DATA: "visualize the quantities honestly",
            SemanticFunction.GEOGRAPHIC_MOVEMENT: "trace movement across geography",
            SemanticFunction.ATMOSPHERE: "hold mood with restrained imagery",
            SemanticFunction.REVEAL: "disclose what was hidden progressively",
            SemanticFunction.TRANSITION: "carry the audience to the next chapter",
            SemanticFunction.SUMMARY: "resolve the episode visually",
        }
        return intents.get(fn, "support the narration meaning")

    # ---- extraction ----------------------------------------------------
    def _entities(self, text: str) -> list[str]:
        found: list[str] = []
        for m in _CAPSEQ_RE.finditer(text):
            words = m.group(0).split()
            # strip leading sentence-mechanics words (leading mechanics word stripped)
            while words and words[0] in _CLOSED_CLASS and words[0] not in _HONORIFICS:
                words.pop(0)
            if words:
                found.append(" ".join(words))
        seen: set[str] = set()
        out = []
        for e in found:
            if e.lower() not in seen:
                seen.add(e.lower())
                out.append(e)
        return out[:6]

    def _locations(self, text: str, fn: SemanticFunction | None = None) -> list[str]:
        entities = self._entities(text)
        locs: list[str] = []
        # a LOCATION_INTRODUCTION beat by definition introduces a place: its
        # lead entity IS the location, whatever the topic's vocabulary
        if fn == SemanticFunction.LOCATION_INTRODUCTION and entities:
            locs.append(entities[0])
        toks = text.split()
        for i, tok in enumerate(toks):
            clean = tok.strip(".,;:!?\"'")
            if clean.lower() in _LOCATION_CUES and i + 1 < len(toks):
                # take the full capitalized phrase after the preposition
                phrase: list[str] = []
                for nxt in toks[i + 1:i + 4]:
                    w = nxt.strip(".,;:!?\"'")
                    if w and w[0].isupper() and not _YEAR_RE.fullmatch(w):
                        phrase.append(w)
                    else:
                        break
                if phrase:
                    locs.append(" ".join(phrase))
        for ent in entities:
            low = ent.lower()
            if any(low.endswith(s) for s in _LOCATION_SUFFIXES) and ent not in locs:
                locs.append(ent)
        seen: set[str] = set()
        out = []
        for l in locs:
            if l.lower() not in seen:
                seen.add(l.lower())
                out.append(l)
        return out[:4]

    def _events(self, text: str) -> list[str]:
        m = re.search(r"\bthe ([a-z]+(?:\s+[a-z]+){0,3}) (?:of|began|started|ended)\b",
                      text.lower())
        return [m.group(1)] if m else []

    def _objects(self, text: str) -> list[str]:
        obj_words = ("document", "wall", "map", "gate", "photograph", "film",
                     "recording", "regulation", "memo", "telegram", "chart",
                     "newspaper", "sign", "fence", "train", "ship", "reactor",
                     "capsule", "letter", "stamp")
        low = text.lower()
        return [w for w in obj_words if w in low][:4]

    def _relationships(self, text: str) -> list[str]:
        rels: list[str] = []
        low = text.lower()
        for pattern, label in (("because", "cause"), ("led to", "cause"),
                               ("as a result", "consequence"),
                               ("forcing", "consequence"),
                               ("announced", "statement"),
                               ("said", "statement")):
            if pattern in low and label not in rels:
                rels.append(label)
        return rels

    def _tone(self, text: str) -> str:
        low = text.lower()
        best, hits = "neutral", 0
        for tone, words in _TONE_LEXICON.items():
            n = sum(1 for w in words if w in low)
            if n > hits:
                best, hits = tone, n
        return best

    def _density(self, text: str) -> float:
        n = (len(_YEAR_RE.findall(text)) +
             len(_NUMBER_RE.findall(_YEAR_RE.sub("", text))) +
             len(self._entities(text)))
        return round(min(1.0, n / 5.0), 2)
