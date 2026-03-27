from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from .schemas import LabelScore


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


@dataclass
class PredictionResult:
    top_label: str
    scores: List[LabelScore]
    model_name: str
    inference_mode: str


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
        if self._pipeline is not None:
            scores = self._run_transformer(email_text)
            return PredictionResult(
                top_label=scores[0].label,
                scores=scores,
                model_name=self.model_name,
                inference_mode=self.inference_mode,
            )

        scores = self._run_keyword_fallback(email_text)
        return PredictionResult(
            top_label=scores[0].label,
            scores=scores,
            model_name=self.model_name,
            inference_mode=self.inference_mode,
        )

    def _prepare_text(self, subject: str, sender: str, body: str) -> str:
        return (
            f"Subject: {subject.strip()}\n"
            f"Sender: {sender.strip()}\n"
            f"Body: {body.strip()}"
        ).strip()

    def _run_transformer(self, email_text: str) -> List[LabelScore]:
        result = self._pipeline(
            sequences=email_text,
            candidate_labels=EMAIL_LABELS,
            multi_label=True,
            hypothesis_template="This email belongs to the {} category.",
        )
        pairs = [
            LabelScore(label=label, score=round(float(score), 4))
            for label, score in zip(result["labels"], result["scores"])
        ]
        return pairs

    def _run_keyword_fallback(self, email_text: str) -> List[LabelScore]:
        lowered = email_text.lower()
        raw_scores: Dict[str, float] = {label: 0.05 for label in EMAIL_LABELS}

        keyword_map: Dict[str, Tuple[str, ...]] = {
            "Work": ("meeting", "project", "client", "deadline", "team", "manager"),
            "Personal": ("family", "dinner", "weekend", "home", "friend", "mom", "dad"),
            "Promotions": ("sale", "discount", "offer", "coupon", "deal", "buy now"),
            "Finance": ("invoice", "bank", "payment", "transaction", "tax", "statement"),
            "Urgent": ("urgent", "asap", "immediately", "right away", "important"),
            "Job": ("interview", "resume", "cv", "application", "recruiter", "hiring"),
            "Events": ("event", "webinar", "conference", "invite", "registration"),
            "Social": ("follow", "like", "comment", "connection", "social", "network"),
            "Spam": ("lottery", "winner", "free money", "claim now", "guaranteed"),
            "Phishing": ("verify account", "password", "login", "suspended", "click link"),
        }

        for label, keywords in keyword_map.items():
            for keyword in keywords:
                if keyword in lowered:
                    raw_scores[label] += 0.18

        # Bias suspicious language toward phishing and spam.
        if "http://" in lowered or "https://" in lowered:
            raw_scores["Phishing"] += 0.08
        if "unsubscribe" in lowered:
            raw_scores["Promotions"] += 0.1
        if "invoice attached" in lowered:
            raw_scores["Finance"] += 0.12

        total = sum(raw_scores.values()) or 1.0
        normalized = [
            LabelScore(label=label, score=round(score / total, 4))
            for label, score in raw_scores.items()
        ]
        normalized.sort(key=lambda item: item.score, reverse=True)
        return normalized
