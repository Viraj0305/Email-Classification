from typing import List

from pydantic import BaseModel, Field


class EmailClassificationRequest(BaseModel):
    subject: str = Field(default="", max_length=500)
    sender: str = Field(default="", max_length=250)
    body: str = Field(min_length=1, max_length=20000)


class LabelScore(BaseModel):
    label: str
    score: float


class EmailClassificationResponse(BaseModel):
    top_label: str
    scores: List[LabelScore]
    model_name: str
    inference_mode: str


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
    snippet: str
    received_at: str
    classification: EmailClassificationResponse


class GmailClassificationResponse(BaseModel):
    total_messages: int
    query: str
    messages: List[GmailClassifiedEmail]

