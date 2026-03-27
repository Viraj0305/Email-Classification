from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .classifier import EmailClassifier
from .gmail_client import GmailConfigurationError, fetch_message_batch, get_connection_status
from .schemas import (
    EmailClassificationRequest,
    EmailClassificationResponse,
    GmailClassificationResponse,
    GmailClassifiedEmail,
    GmailConnectionStatus,
)


app = FastAPI(
    title="SmartMail AI Backend",
    version="0.1.0",
    description="AI-powered email classification API for SmartMail AI.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

classifier = EmailClassifier()


@app.get("/health")
def health_check() -> dict:
    return {
        "status": "ok",
        "model_name": classifier.model_name,
        "inference_mode": classifier.inference_mode,
    }


@app.post("/api/classify", response_model=EmailClassificationResponse)
def classify_email(payload: EmailClassificationRequest) -> EmailClassificationResponse:
    result = classifier.classify_email(
        subject=payload.subject,
        sender=payload.sender,
        body=payload.body,
    )
    return EmailClassificationResponse(
        top_label=result.top_label,
        scores=result.scores,
        model_name=result.model_name,
        inference_mode=result.inference_mode,
    )


@app.get("/api/gmail/status", response_model=GmailConnectionStatus)
def gmail_status() -> GmailConnectionStatus:
    return GmailConnectionStatus(**get_connection_status())


@app.get("/api/gmail/classify", response_model=GmailClassificationResponse)
def classify_gmail_messages(max_results: int = 25, query: str = "") -> GmailClassificationResponse:
    safe_max_results = max(1, min(max_results, 100))

    try:
        messages = fetch_message_batch(max_results=safe_max_results, query=query)
    except GmailConfigurationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Gmail sync failed: {exc}",
        ) from exc

    classified_messages: list[GmailClassifiedEmail] = []
    for message in messages:
        result = classifier.classify_email(
            subject=message["subject"],
            sender=message["sender"],
            body=message["body"],
        )
        classified_messages.append(
            GmailClassifiedEmail(
                message_id=message["message_id"],
                thread_id=message["thread_id"],
                sender=message["sender"],
                subject=message["subject"],
                body=message["body"],
                snippet=message["snippet"],
                received_at=message["received_at"],
                classification=EmailClassificationResponse(
                    top_label=result.top_label,
                    scores=result.scores,
                    model_name=result.model_name,
                    inference_mode=result.inference_mode,
                ),
            )
        )

    return GmailClassificationResponse(
        total_messages=len(classified_messages),
        query=query,
        messages=classified_messages,
    )



