from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from .schemas import EmailSummary


SUMMARIZER_MODEL = "sshleifer/distilbart-cnn-12-6"
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "we",
    "will",
    "with",
    "you",
    "your",
}

TIME_PATTERNS = (
    r"\b\d{1,2}:\d{2}\s?(am|pm)?\b",
    r"\b\d{1,2}\s?(am|pm)\b",
    r"\b(today|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
    r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\b",
)

ACTION_TERMS = {
    "please",
    "review",
    "confirm",
    "join",
    "reply",
    "submit",
    "approve",
    "verify",
    "click",
    "meeting",
    "agenda",
    "scheduled",
    "deadline",
    "payment",
    "invoice",
}


@dataclass
class SummaryResult:
    text: str
    model_name: str
    summary_method: str


class EmailSummarizer:
    def __init__(self) -> None:
        self._pipeline = None
        self.model_name = SUMMARIZER_MODEL
        self.summary_method = "transformer"
        self._initialize_pipeline()

    def _initialize_pipeline(self) -> None:
        try:
            from transformers import pipeline

            self._pipeline = pipeline("summarization", model=SUMMARIZER_MODEL)
        except Exception:
            self._pipeline = None
            self.model_name = "extractive-fallback"
            self.summary_method = "extractive"

    def summarize_email(self, subject: str, body: str) -> SummaryResult:
        text = self._prepare_text(subject=subject, body=body)
        if self._pipeline is not None:
            try:
                summary = self._pipeline(
                    text,
                    max_length=60,
                    min_length=12,
                    do_sample=False,
                )[0]["summary_text"].strip()
                if summary:
                    return SummaryResult(
                        text=summary,
                        model_name=self.model_name,
                        summary_method=self.summary_method,
                    )
            except Exception:
                pass

        return SummaryResult(
            text=self._extractive_summary(subject=subject, body=body),
            model_name=self.model_name,
            summary_method=self.summary_method,
        )

    def _prepare_text(self, subject: str, body: str) -> str:
        subject = subject.strip()
        body = body.strip()
        if subject:
            return f"Subject: {subject}\n\n{body}".strip()
        return body

    def _extractive_summary(self, subject: str, body: str) -> str:
        cleaned_subject = re.sub(r"\s+", " ", subject).strip()
        cleaned_body = re.sub(r"\s+", " ", body).strip()
        if not cleaned_body:
            return cleaned_subject or "No summary available."

        sentences = [
            sentence.strip()
            for sentence in re.split(r"(?<=[.!?])\s+", cleaned_body)
            if sentence.strip()
        ]
        if not sentences:
            sentences = [cleaned_body]

        word_counts = Counter(
            word
            for word in re.findall(r"[a-zA-Z0-9']+", cleaned_body.lower())
            if word not in STOPWORDS and len(word) > 2
        )
        subject_tokens = set(
            token
            for token in re.findall(r"[a-zA-Z0-9']+", cleaned_subject.lower())
            if token not in STOPWORDS and len(token) > 2
        )

        ranked = []
        for index, sentence in enumerate(sentences):
            tokens = re.findall(r"[a-zA-Z0-9']+", sentence.lower())
            token_set = set(tokens)
            score = sum(word_counts.get(token, 0) for token in tokens)
            score += max(0, 4 - index)
            score += len(token_set.intersection(subject_tokens)) * 1.5
            score += self._sentence_bonus(sentence, token_set)
            ranked.append((score, index, sentence))

        ranked.sort(key=lambda item: (item[0], -item[1]), reverse=True)

        chosen_sentences = []
        for _, _, sentence in ranked:
            if len(chosen_sentences) >= 2:
                break
            if self._is_redundant(sentence, chosen_sentences):
                continue
            chosen_sentences.append(sentence)

        if not chosen_sentences:
            chosen_sentences = [sentences[0]]

        summary = self._compose_summary(cleaned_subject, chosen_sentences)
        return summary[:280].rstrip(" ,;")

    def _sentence_bonus(self, sentence: str, token_set: set[str]) -> float:
        bonus = 0.0
        lowered = sentence.lower()

        if any(re.search(pattern, lowered) for pattern in TIME_PATTERNS):
            bonus += 6.0
        if token_set.intersection(ACTION_TERMS):
            bonus += 4.0
        if lowered.endswith(":") or "agenda" in lowered:
            bonus += 3.0
        if any(marker in lowered for marker in ("please", "kindly", "action required", "fyi")):
            bonus += 2.5
        if any(marker in lowered for marker in ("http://", "https://", "attach", "attached")):
            bonus += 1.5
        return bonus

    def _is_redundant(self, sentence: str, existing: list[str]) -> bool:
        new_tokens = set(re.findall(r"[a-zA-Z0-9']+", sentence.lower()))
        for current in existing:
            current_tokens = set(re.findall(r"[a-zA-Z0-9']+", current.lower()))
            overlap = len(new_tokens.intersection(current_tokens))
            if current_tokens and overlap / max(1, len(current_tokens)) > 0.7:
                return True
        return False

    def _compose_summary(self, subject: str, sentences: list[str]) -> str:
        first_sentence = sentences[0].rstrip()
        pieces = []

        if subject and not self._subject_repeated_in_sentence(subject, first_sentence):
            pieces.append(subject)

        cleaned_sentences = [self._trim_sentence(sentence) for sentence in sentences if sentence.strip()]
        pieces.extend(cleaned_sentences)

        summary = " ".join(piece for piece in pieces if piece)
        summary = re.sub(r"\s+", " ", summary)
        return summary

    def _subject_repeated_in_sentence(self, subject: str, sentence: str) -> bool:
        subject_tokens = set(re.findall(r"[a-zA-Z0-9']+", subject.lower())) - STOPWORDS
        sentence_tokens = set(re.findall(r"[a-zA-Z0-9']+", sentence.lower())) - STOPWORDS
        if not subject_tokens:
            return False
        overlap_ratio = len(subject_tokens.intersection(sentence_tokens)) / len(subject_tokens)
        return overlap_ratio >= 0.6

    def _trim_sentence(self, sentence: str) -> str:
        sentence = sentence.strip()
        if len(sentence) <= 160:
            return sentence
        cutoff = sentence[:157].rsplit(" ", 1)[0]
        return f"{cutoff}..."


def to_summary_schema(result: SummaryResult) -> EmailSummary:
    return EmailSummary(
        text=result.text,
        model_name=result.model_name,
        summary_method=result.summary_method,
    )
