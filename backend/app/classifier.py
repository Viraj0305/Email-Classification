from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Tuple

from .schemas import (
    ClassificationExplanation,
    ExplanationKeyword,
    LabelScore,
    LanguageInfo,
    PriorityAssessment,
)


EMAIL_LABELS = [
    "Work",
    "Personal",
    "Promotions",
    "Finance",
    "Urgent",
    "Job",
    "Events",
    "Social",
    "Spam",
    "Phishing",
]

ZERO_SHOT_MODEL = "typeform/distilbert-base-uncased-mnli"
BASE_SCORE = 0.05
KEYWORD_WEIGHT = 0.18

LANGUAGE_LABELS = {
    "en": "English",
    "hi": "Hindi",
    "mr": "Marathi",
}

LABEL_KEYWORDS: Dict[str, Tuple[str, ...]] = {
    "Work": (
        "meeting", "project", "client", "deadline", "team", "manager",
        "????", "?????????", "???", "??????", "??????",
        "????", "???????", "???", "??????????",
    ),
    "Personal": (
        "family", "dinner", "weekend", "home", "friend", "mom", "dad",
        "??????", "?????", "??", "?????", "??", "????",
        "??????", "?????", "???", "??", "????",
    ),
    "Promotions": (
        "sale", "discount", "offer", "coupon", "deal", "buy now",
        "???", "???", "????", "???",
        "????", "???", "????", "?????",
    ),
    "Finance": (
        "invoice", "bank", "payment", "transaction", "tax", "statement",
        "????", "??????", "?????", "??????", "??",
        "???", "??????", "???", "???????", "??",
    ),
    "Urgent": (
        "urgent", "asap", "immediately", "right away", "important", "deadline",
        "?????", "??????", "??? ??????", "????",
        "???????", "????????", "???????", "????",
    ),
    "Job": (
        "interview", "resume", "cv", "application", "recruiter", "hiring",
        "????????", "????????", "?????", "?????",
        "??????????", "????????", "?????", "????",
    ),
    "Events": (
        "event", "webinar", "conference", "invite", "registration",
        "?????????", "???????", "???????", "????????",
        "?????????", "???????", "?????", "???????", "??????",
    ),
    "Social": (
        "follow", "like", "comment", "connection", "social", "network",
        "????", "????", "?????", "????",
        "????", "????", "?????", "????",
    ),
    "Spam": (
        "lottery", "winner", "free money", "claim now", "guaranteed",
        "?????", "????", "?????", "??? ??",
        "?????", "??????", "????", "???????",
    ),
    "Phishing": (
        "verify account", "password", "login", "suspended", "click link",
        "???? ????????", "???????", "?????", "???????", "???? ?? ?????",
        "???? ????????", "???????", "?????", "???????", "?????? ?????",
    ),
}

SPECIAL_SIGNALS: Dict[str, Tuple[Tuple[str, float, Tuple[str, ...]], ...]] = {
    "Phishing": (
        ("http://", 0.08, ("body",)),
        ("https://", 0.08, ("body",)),
        ("otp", 0.08, ("subject", "body")),
    ),
    "Promotions": (("unsubscribe", 0.10, ("body",)),),
    "Finance": (("invoice attached", 0.12, ("subject", "body")),),
}

PRIORITY_SIGNAL_WEIGHTS: Dict[str, float] = {
    "urgent": 0.22,
    "asap": 0.18,
    "immediately": 0.18,
    "deadline": 0.18,
    "verify account": 0.18,
    "password": 0.14,
    "invoice": 0.12,
    "payment": 0.12,
    "interview": 0.1,
    "meeting": 0.08,
    "?????": 0.22,
    "???????": 0.22,
    "??????": 0.12,
    "??????": 0.12,
}

PRIORITY_LABEL_WEIGHTS: Dict[str, float] = {
    "Urgent": 0.95,
    "Phishing": 0.9,
    "Finance": 0.6,
    "Work": 0.45,
    "Job": 0.35,
    "Events": 0.25,
    "Personal": 0.15,
    "Promotions": -0.2,
    "Social": -0.18,
    "Spam": -0.12,
}

HINDI_MARKERS = {"??", "?????", "?????", "??????", "????", "??????", "????"}
MARATHI_MARKERS = {"???", "?????", "???????", "????????", "?????", "??????", "????", "????"}


@dataclass
class PredictionResult:
    top_label: str
    scores: List[LabelScore]
    model_name: str
    inference_mode: str
    explanation: ClassificationExplanation
    priority: PriorityAssessment
    language: LanguageInfo


@dataclass
class EvidenceMatch:
    label: str
    term: str
    field: str
    occurrences: int
    weight: float


class EmailClassifier:
    def __init__(self) -> None:
        self._pipeline = None
        self._load_error = None
        self.model_name = ZERO_SHOT_MODEL
        self.inference_mode = "transformer"
        self._initialize_pipeline()

    def _initialize_pipeline(self) -> None:
        try:
            from transformers import pipeline

            self._pipeline = pipeline(
                "zero-shot-classification",
                model=ZERO_SHOT_MODEL,
            )
        except Exception as exc:
            self._pipeline = None
            self._load_error = str(exc)
            self.model_name = "keyword-fallback"
            self.inference_mode = "fallback"

    def classify_email(self, subject: str, sender: str, body: str) -> PredictionResult:
        email_text = self._prepare_text(subject=subject, sender=sender, body=body)
        evidence = self._collect_evidence(subject=subject, sender=sender, body=body)
        language = self._detect_language(email_text)

        if self._pipeline is not None and language.code == "en":
            scores = self._run_transformer(email_text)
            inference_mode = self.inference_mode
            model_name = self.model_name
        else:
            scores = self._run_keyword_fallback(evidence)
            inference_mode = "fallback"
            model_name = "keyword-fallback"

        explanation = self._build_explanation(scores=scores, evidence=evidence, language=language)
        priority = self._build_priority(scores=scores, evidence=evidence, language=language)
        return PredictionResult(
            top_label=scores[0].label,
            scores=scores,
            model_name=model_name,
            inference_mode=inference_mode,
            explanation=explanation,
            priority=priority,
            language=language,
        )

    def _prepare_text(self, subject: str, sender: str, body: str) -> str:
        return (
            f"Subject: {subject.strip()}\n"
            f"Sender: {sender.strip()}\n"
            f"Body: {body.strip()}"
        ).strip()

    def _detect_language(self, text: str) -> LanguageInfo:
        lowered = text.lower()
        devanagari_chars = re.findall(r"[\u0900-\u097F]", text)
        if not devanagari_chars:
            return LanguageInfo(code="en", name=LANGUAGE_LABELS["en"], detection_method="latin-script heuristic")

        tokens = set(re.findall(r"[\u0900-\u097F]+", text))
        hindi_hits = sum(1 for marker in HINDI_MARKERS if marker in tokens or marker in lowered)
        marathi_hits = sum(1 for marker in MARATHI_MARKERS if marker in tokens or marker in lowered)

        if marathi_hits > hindi_hits:
            code = "mr"
        else:
            code = "hi"

        return LanguageInfo(code=code, name=LANGUAGE_LABELS[code], detection_method="devanagari keyword heuristic")

    def _run_transformer(self, email_text: str) -> List[LabelScore]:
        result = self._pipeline(
            sequences=email_text,
            candidate_labels=EMAIL_LABELS,
            multi_label=True,
            hypothesis_template="This email belongs to the {} category.",
        )
        return [
            LabelScore(label=label, score=round(float(score), 4))
            for label, score in zip(result["labels"], result["scores"])
        ]

    def _run_keyword_fallback(self, evidence: List[EvidenceMatch]) -> List[LabelScore]:
        raw_scores: Dict[str, float] = {label: BASE_SCORE for label in EMAIL_LABELS}
        for match in evidence:
            raw_scores[match.label] += match.weight * match.occurrences
        total = sum(raw_scores.values()) or 1.0
        normalized = [
            LabelScore(label=label, score=round(score / total, 4))
            for label, score in raw_scores.items()
        ]
        normalized.sort(key=lambda item: item.score, reverse=True)
        return normalized

    def _collect_evidence(self, subject: str, sender: str, body: str) -> List[EvidenceMatch]:
        fields = {
            "subject": subject.lower(),
            "sender": sender.lower(),
            "body": body.lower(),
        }
        matches: List[EvidenceMatch] = []

        for label, keywords in LABEL_KEYWORDS.items():
            for term in keywords:
                for field, text in fields.items():
                    occurrences = text.count(term.lower())
                    if occurrences:
                        matches.append(EvidenceMatch(label=label, term=term, field=field, occurrences=occurrences, weight=KEYWORD_WEIGHT))

        for label, signals in SPECIAL_SIGNALS.items():
            for term, weight, signal_fields in signals:
                for field in signal_fields:
                    occurrences = fields[field].count(term)
                    if occurrences:
                        matches.append(EvidenceMatch(label=label, term=term, field=field, occurrences=occurrences, weight=weight))

        return matches

    def _build_explanation(self, scores: List[LabelScore], evidence: List[EvidenceMatch], language: LanguageInfo) -> ClassificationExplanation:
        top_label = scores[0].label
        top_matches = [match for match in evidence if match.label == top_label]
        top_matches.sort(key=lambda item: (item.weight * item.occurrences), reverse=True)
        fallback_terms = [ExplanationKeyword(term="general context", field="body", occurrences=1, weight=0.0)]
        matched_keywords = [
            ExplanationKeyword(term=match.term, field=match.field, occurrences=match.occurrences, weight=round(match.weight * match.occurrences, 3))
            for match in top_matches[:5]
        ] or fallback_terms

        prominent_terms = [item.term for item in matched_keywords if item.term != "general context"]
        if prominent_terms:
            keyword_text = ", ".join(f"'{term}'" for term in prominent_terms[:3])
            summary = f"This email is marked as {top_label.lower()} because it contains signals like {keyword_text}."
        else:
            summary = f"This email is marked as {top_label.lower()} based on the overall wording and message context."

        rationale = [
            f"Detected language: {language.name}.",
            f"Top prediction: {scores[0].label} ({scores[0].score:.1%} confidence).",
            f"Runner-up: {scores[1].label} ({scores[1].score:.1%} confidence).",
        ]
        if top_matches:
            rationale.append(f"Strongest evidence came from the {top_matches[0].field} field via '{top_matches[0].term}'.")
        else:
            rationale.append("No predefined alert phrase matched exactly, so the explanation is based on broader wording patterns.")

        method = "keyword-attribution over transformer prediction" if self._pipeline is not None and language.code == "en" else "multilingual keyword attribution fallback"
        return ClassificationExplanation(summary=summary, rationale=rationale, matched_keywords=matched_keywords, explanation_method=method)

    def _build_priority(self, scores: List[LabelScore], evidence: List[EvidenceMatch], language: LanguageInfo) -> PriorityAssessment:
        score_map = {item.label: item.score for item in scores}
        priority_score = 0.12
        for label, weight in PRIORITY_LABEL_WEIGHTS.items():
            priority_score += score_map.get(label, 0.0) * weight

        reasons: List[str] = [f"Language: {language.name}."]
        seen_terms: set[str] = set()
        sorted_evidence = sorted(evidence, key=lambda item: item.weight * item.occurrences, reverse=True)
        for match in sorted_evidence:
            if match.term.lower() in PRIORITY_SIGNAL_WEIGHTS:
                priority_score += PRIORITY_SIGNAL_WEIGHTS[match.term.lower()] * min(match.occurrences, 2)
            if match.term not in seen_terms and len(reasons) < 4:
                reasons.append(f"Detected '{match.term}' in the {match.field}.")
                seen_terms.add(match.term)

        priority_score = max(0.0, min(priority_score, 1.0))
        if priority_score >= 0.62:
            level, color = "Urgent", "red"
        elif priority_score >= 0.33:
            level, color = "Medium", "yellow"
        else:
            level, color = "Low", "green"

        if len(reasons) == 1:
            reasons.append("No strong urgency or risk signals were detected.")
        reasons.append(f"Priority score: {priority_score:.0%}.")
        return PriorityAssessment(level=level, score=round(priority_score, 4), color=color, reasons=reasons)
