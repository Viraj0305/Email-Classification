from typing import List

from pydantic import BaseModel, Field


class EmailClassificationRequest(BaseModel):
    subject: str = Field(default="", max_length=500)
    sender: str = Field(default="", max_length=250)
    body: str = Field(min_length=1, max_length=20000)


class LabelScore(BaseModel):
    label: str
    score: float


class ExplanationKeyword(BaseModel):
    term: str
    field: str
    occurrences: int
    weight: float


class ClassificationExplanation(BaseModel):
    summary: str
    rationale: List[str]
    matched_keywords: List[ExplanationKeyword]
    explanation_method: str


class PriorityAssessment(BaseModel):
    level: str
    score: float
    color: str
    reasons: List[str]


class EmailSummary(BaseModel):
    text: str
    model_name: str
    summary_method: str


class LanguageInfo(BaseModel):
    code: str
    name: str
    detection_method: str


class EmailClassificationResponse(BaseModel):
    top_label: str
    scores: List[LabelScore]
    model_name: str
    inference_mode: str
    explanation: ClassificationExplanation
    priority: PriorityAssessment
    summary: EmailSummary
    language: LanguageInfo


class GmailConnectionStatus(BaseModel):
    connected: bool
    credentials_file_configured: bool
    credentials_file_path: str
    token_file_path: str
    scope: str


class GmailClassifiedEmail(BaseModel):
    message_id: str
    thread_id: str
    sender: str
    subject: str
    body: str
    snippet: str
    received_at: str
    classification: EmailClassificationResponse


class GmailClassificationResponse(BaseModel):
    total_messages: int
    query: str
    messages: List[GmailClassifiedEmail]
