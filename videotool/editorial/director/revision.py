"""Feedback-driven revision loop service (Phase 3A / AI Editorial Director).

Interprets free-text human editorial feedback, validates proposed changes
against domain invariants and anti-hallucination grounding rules, creates
reproducible RevisionProposal objects, and persists approved overrides
to editorial_overrides.json.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from videotool.artifacts import ArtifactStore
from videotool.editorial.director.caption_validator import validate_caption
from videotool.editorial.director.providers.gemini import _extract_json_block
from videotool.providers.env import get_gemini_api_key


@dataclass
class RevisionProposal:
    """Structured proposal for an editorial override generated from human feedback."""
    proposal_id: str
    episode_id: str
    beat_id: str
    target_id: str
    target_type: str  # "node_caption" | "beat_strategy"
    field: str        # "caption" | "strategy"
    old_value: str
    new_value: str
    feedback: str
    reason: str
    is_valid: bool
    rejection_reason: str = ""
    created_at: str = field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "RevisionProposal":
        return cls(**d)


class RevisionService:
    """Service coordinating human feedback interpretation and override committing."""

    def __init__(self, provider_name: str = "mock"):
        self.provider_name = provider_name

    def propose_revision(
        self,
        episode_id: str,
        feedback_text: str,
        store: ArtifactStore,
    ) -> RevisionProposal:
        """Interpret feedback text and generate a structured before/after proposal."""
        # 1. Check for explicitly unsupported change types (Timing / Duration / Narration re-writing)
        lower_fb = feedback_text.lower()
        if any(w in lower_fb for w in ["kéo dài", "rút ngắn", "thời lượng", "duration", "timing", "tăng giây", "giảm giây", "thời gian"]):
            prop_id = f"prop_err_{hashlib.sha256(feedback_text.encode()).hexdigest()[:8]}"
            return RevisionProposal(
                proposal_id=prop_id,
                episode_id=episode_id,
                beat_id="",
                target_id="",
                target_type="unsupported",
                field="timing",
                old_value="",
                new_value="",
                feedback=feedback_text,
                reason="timing changes aren't supported yet",
                is_valid=False,
                rejection_reason="timing changes aren't supported yet: Beat duration is derived from narration word-timing",
            )

        # 2. Load current plan context to validate targets
        semantic_beats = store.load(episode_id, "semantic_beats") or []
        geo_plans = store.load(episode_id, "semantic_geometry") or []
        visual_comps = store.load(episode_id, "visual_compositions") or []
        editorial_intents = store.load(episode_id, "editorial_intents") or {}

        if not semantic_beats:
            raise ValueError(f"No semantic beats found for episode '{episode_id}'. Please run planning pipeline first.")

        # 3. Interpret feedback
        if self.provider_name == "gemini":
            proposal = self._interpret_gemini(
                episode_id=episode_id,
                feedback_text=feedback_text,
                beats=semantic_beats,
                geo_plans=geo_plans,
                comps=visual_comps,
                intents=editorial_intents,
            )
        else:
            proposal = self._interpret_mock(
                episode_id=episode_id,
                feedback_text=feedback_text,
                beats=semantic_beats,
                geo_plans=geo_plans,
                comps=visual_comps,
                intents=editorial_intents,
            )

        # 4. Save proposal to disk for two-step apply
        prop_dir = store.episode_dir(episode_id) / "proposals"
        prop_dir.mkdir(parents=True, exist_ok=True)
        prop_file = prop_dir / f"{proposal.proposal_id}.json"
        with open(prop_file, "w", encoding="utf-8") as f:
            json.dump(proposal.to_dict(), f, indent=2, ensure_ascii=False)

        return proposal

    def apply_revision(
        self,
        episode_id: str,
        proposal_id: str,
        store: ArtifactStore,
    ) -> list[dict[str, Any]]:
        """Commit an approved proposal into editorial_overrides.json."""
        prop_file = store.episode_dir(episode_id) / "proposals" / f"{proposal_id}.json"
        if not prop_file.is_file():
            raise FileNotFoundError(f"Revision proposal '{proposal_id}' not found at {prop_file}")

        with open(prop_file, "r", encoding="utf-8") as f:
            proposal_dict = json.load(f)

        proposal = RevisionProposal.from_dict(proposal_dict)
        if not proposal.is_valid:
            raise ValueError(f"Cannot apply invalid proposal: {proposal.rejection_reason}")

        # Load existing overrides
        overrides = store.load(episode_id, "editorial_overrides") or []
        if not isinstance(overrides, list):
            overrides = []

        # Remove previous override for the exact same target if present, then append
        overrides = [ovr for ovr in overrides if ovr.get("target_id") != proposal.target_id]
        overrides.append({
            "override_id": f"ovr_{proposal.proposal_id}",
            "beat_id": proposal.beat_id,
            "target_id": proposal.target_id,
            "target_type": proposal.target_type,
            "field": proposal.field,
            "old_value": proposal.old_value,
            "new_value": proposal.new_value,
            "feedback": proposal.feedback,
            "applied_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        })

        store.save(episode_id, "editorial_overrides", overrides)
        return overrides

    def _interpret_mock(
        self,
        episode_id: str,
        feedback_text: str,
        beats: list[dict[str, Any]],
        geo_plans: list[dict[str, Any]],
        comps: list[dict[str, Any]],
        intents: dict[str, Any],
    ) -> RevisionProposal:
        """Deterministic mock interpreter supporting test patterns and declining non-trivial text."""
        prop_id = f"prop_{hashlib.sha256(feedback_text.encode('utf-8')).hexdigest()[:8]}"

        # Identify target beat (e.g. "Beat 4", "beat_0004", "Beat 04")
        beat_match = re.search(r"beat[\s_]*0*([1-9]|1[0-2])\b", feedback_text, re.IGNORECASE)
        if not beat_match:
            return RevisionProposal(
                proposal_id=prop_id,
                episode_id=episode_id,
                beat_id="",
                target_id="",
                target_type="unknown",
                field="unknown",
                old_value="",
                new_value="",
                feedback=feedback_text,
                reason="No valid beat reference found in feedback",
                is_valid=False,
                rejection_reason="Target beat could not be identified in feedback (e.g. 'Beat 4: ...')",
            )

        beat_num = int(beat_match.group(1))
        beat_id = f"beat_{beat_num:04d}"

        # Verify beat exists in current plan
        beat_data = next((b for b in beats if b["beat_id"] == beat_id), None)
        if not beat_data:
            return RevisionProposal(
                proposal_id=prop_id,
                episode_id=episode_id,
                beat_id=beat_id,
                target_id=beat_id,
                target_type="beat",
                field="unknown",
                old_value="",
                new_value="",
                feedback=feedback_text,
                reason=f"Beat '{beat_id}' does not exist in episode",
                is_valid=False,
                rejection_reason=f"Target '{beat_id}' not found in current plan",
            )

        geo_data = next((g for g in geo_plans if g["beat_id"] == beat_id), {})
        nodes = geo_data.get("nodes", [])

        # Structured pattern matching: extract `<target> -> <new_value>` or `<target> to <new_value>`
        remainder = re.sub(r"^.*?beat[\s_]*0*([1-9]|1[0-2])\s*[:,-]?\s*", "", feedback_text, flags=re.IGNORECASE).strip()

        old_str = None
        new_str = None

        # Pattern 1: Arrow delimiters (->, =>, →) or Vietnamese 'thành'
        arrow_match = re.search(
            r"^(?:(?:set|change)\s+)?(?:caption\s+|label\s+)?['\"]?(.*?)['\"]?\s*(?:->|=>|→|\bthành\b)\s*['\"]?(.*?)['\"]?$",
            remainder,
            flags=re.IGNORECASE,
        )
        if arrow_match and arrow_match.group(1).strip() and arrow_match.group(2).strip():
            old_str = arrow_match.group(1).strip().strip("'\"")
            new_str = arrow_match.group(2).strip().strip("'\"")
        else:
            # Pattern 2: Quoted 'A' to 'B'
            quoted_match = re.search(
                r"['\"]([^'\"]+)['\"]\s+(?:to|thành)\s+['\"]([^'\"]+)['\"]",
                remainder,
                flags=re.IGNORECASE,
            )
            if quoted_match and quoted_match.group(1).strip() and quoted_match.group(2).strip():
                old_str = quoted_match.group(1).strip()
                new_str = quoted_match.group(2).strip()
            else:
                # Pattern 3: Explicit 'caption A to B' or 'set A to B'
                explicit_match = re.search(
                    r"^(?:set\s+|caption\s+|change\s+)(?:caption\s+)?['\"]?(\S+?)['\"]?\s+to\s+['\"]?(.+?)['\"]?$",
                    remainder,
                    flags=re.IGNORECASE,
                )
                if explicit_match and explicit_match.group(1).strip() and explicit_match.group(2).strip():
                    old_str = explicit_match.group(1).strip().strip("'\"")
                    new_str = explicit_match.group(2).strip().strip("'\"")

        if old_str and new_str:
            text_nodes = [
                n for n in nodes
                if n.get("text_role") or n.get("role") not in ("MAP", "HERO", "PORTRAIT", "DOCUMENT", "ARCHIVAL_IMAGE")
            ]
            target_node = next(
                (n for n in text_nodes if old_str.lower() in [r.lower() for r in n.get("semantic_refs", [])]),
                None,
            )
            if not target_node:
                target_node = next(
                    (n for n in text_nodes if old_str.lower() in n.get("node_id", "").lower()),
                    None,
                )
            if not target_node:
                target_node = next(
                    (n for n in nodes if old_str.lower() in [r.lower() for r in n.get("semantic_refs", [])] or old_str.lower() in n.get("node_id", "").lower()),
                    None,
                )
            target_id = target_node["node_id"] if target_node else f"semantic:{beat_id}:label:00"

            is_valid, reason = validate_caption(
                caption=new_str,
                narration_text=beat_data.get("narration_text", ""),
                entities=beat_data.get("entities", []),
                locations=beat_data.get("locations", []),
                dates=beat_data.get("dates", []),
            )

            return RevisionProposal(
                proposal_id=prop_id,
                episode_id=episode_id,
                beat_id=beat_id,
                target_id=target_id,
                target_type="node_caption",
                field="caption",
                old_value=old_str,
                new_value=new_str,
                feedback=feedback_text,
                reason=f"Structured revision: '{old_str}' -> '{new_str}'",
                is_valid=is_valid,
                rejection_reason="" if is_valid else reason,
            )

        # For general unstructured free-text feedback that requires natural language comprehension:
        # Gracefully decline with clear error per User Clarification 2
        return RevisionProposal(
            proposal_id=prop_id,
            episode_id=episode_id,
            beat_id=beat_id,
            target_id="",
            target_type="unsupported_mock",
            field="unknown",
            old_value="",
            new_value="",
            feedback=feedback_text,
            reason="Mock provider cannot interpret arbitrary free-text feedback",
            is_valid=False,
            rejection_reason=(
                "Mock provider cannot interpret arbitrary free-text feedback. "
                "Please run with --provider gemini (or an active LLM provider) for natural language feedback interpretation."
            ),
        )

    def _interpret_gemini(
        self,
        episode_id: str,
        feedback_text: str,
        beats: list[dict[str, Any]],
        geo_plans: list[dict[str, Any]],
        comps: list[dict[str, Any]],
        intents: dict[str, Any],
    ) -> RevisionProposal:
        """Query Gemini API to interpret free-text feedback and extract structured patch."""
        import urllib.request

        api_key = get_gemini_api_key()
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key={api_key}"

        prompt = (
            "You are an AI Editorial Revision Assistant for a documentary production pipeline.\n"
            "A human director has provided free-text feedback requesting a revision to the current shooting plan.\n\n"
            f"FEEDBACK:\n\"{feedback_text}\"\n\n"
            f"AVAILABLE BEATS AND NODES:\n"
            f"{json.dumps([{'beat_id': b['beat_id'], 'narration': b.get('narration_text'), 'entities': b.get('entities')} for b in beats], indent=2, ensure_ascii=False)}\n\n"
            "INSTRUCTIONS:\n"
            "1. Extract the target beat_id and target_id (node_id or strategy).\n"
            "2. Determine the field ('caption' or 'strategy') and propose a concise new_value (2-6 words for captions).\n"
            "3. The proposed caption MUST be strictly factually grounded in that beat's narration and entities.\n"
            "4. Return ONLY a JSON object conforming to:\n"
            "{\n"
            '  "beat_id": "beat_0004",\n'
            '  "target_id": "semantic:beat_0004:connector_endpoint:01",\n'
            '  "target_type": "node_caption",\n'
            '  "field": "caption",\n'
            '  "old_value": "Hungary",\n'
            '  "new_value": "Hungary opens border",\n'
            '  "reason": "Clear narrative summary of the border event"\n'
            "}"
        )

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.1},
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=15.0) as resp:
            resp_data = json.loads(resp.read().decode("utf-8"))

        raw_text = resp_data["candidates"][0]["content"]["parts"][0]["text"]
        parsed = _extract_json_block(raw_text)

        beat_id = parsed.get("beat_id", "")
        beat_data = next((b for b in beats if b["beat_id"] == beat_id), None)
        if not beat_data:
            raise ValueError(f"Gemini proposed invalid beat_id '{beat_id}'")

        new_val = parsed.get("new_value", "")
        is_valid, reason = validate_caption(
            caption=new_val,
            narration_text=beat_data.get("narration_text", ""),
            entities=beat_data.get("entities", []),
            locations=beat_data.get("locations", []),
            dates=beat_data.get("dates", []),
        )

        prop_id = f"prop_{hashlib.sha256(feedback_text.encode('utf-8')).hexdigest()[:8]}"
        return RevisionProposal(
            proposal_id=prop_id,
            episode_id=episode_id,
            beat_id=beat_id,
            target_id=parsed.get("target_id", ""),
            target_type=parsed.get("target_type", "node_caption"),
            field=parsed.get("field", "caption"),
            old_value=parsed.get("old_value", ""),
            new_value=new_val,
            feedback=feedback_text,
            reason=parsed.get("reason", ""),
            is_valid=is_valid,
            rejection_reason="" if is_valid else reason,
        )
