"""
French Learning Material Generator API
----------------------------------------
A minimal FastAPI backend that generates French learning content
(grammar explanations, reading passages, or vocabulary lists) using
the Anthropic Claude API.

Run locally:
    uvicorn main:app --reload

Requires ANTHROPIC_API_KEY to be set in the environment (see .env.example).
"""

import os
import logging
from enum import Enum

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import anthropic

# --------------------------------------------------------------------------
# Setup
# --------------------------------------------------------------------------

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("french_lesson_api")

app = FastAPI(
    title="French Learning Material Generator",
    description="Generates grammar, reading, and vocabulary content for French learners.",
    version="1.0.0",
)

# Comma-separated list of allowed origins, e.g.
# "http://localhost:4200,https://your-frontend.onrender.com"
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("ALLOWED_ORIGINS", "http://localhost:4200").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")

# The client is created lazily inside the endpoint so the app can still
# start (and e.g. serve /health) even if the key isn't set yet.
_client = None


def get_client() -> anthropic.Anthropic:
    global _client
    if not ANTHROPIC_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server misconfiguration: ANTHROPIC_API_KEY is not set.",
        )
    if _client is None:
        _client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    return _client


# --------------------------------------------------------------------------
# Request / Response models
# --------------------------------------------------------------------------

class CEFRLevel(str, Enum):
    A1 = "A1"
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"
    C1 = "C1"
    C2 = "C2"


class ContentType(str, Enum):
    grammar = "grammar"
    reading = "reading"
    vocab = "vocab"


class LessonRequest(BaseModel):
    level: CEFRLevel = Field(..., description="CEFR level, e.g. A1, B2, C1")
    topic: str = Field(
        ..., min_length=2, max_length=200,
        description="Topic for the lesson, e.g. 'ordering food at a restaurant'"
    )
    content_type: ContentType = Field(
        ..., description="Type of content to generate: grammar, reading, or vocab"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "level": "B1",
                "topic": "talking about your weekend",
                "content_type": "reading",
            }
        }


class LessonResponse(BaseModel):
    level: CEFRLevel
    topic: str
    content_type: ContentType
    content: str


# --------------------------------------------------------------------------
# Prompt construction
# --------------------------------------------------------------------------

def build_prompt(req: LessonRequest) -> str:
    base = (
        f"You are an expert French-language teacher creating material for a "
        f"student at CEFR level {req.level.value}. The topic is: \"{req.topic}\". "
        f"Write entirely in a way that's appropriate for a {req.level.value} learner "
        f"(vocabulary, grammar complexity, sentence length)."
    )

    if req.content_type == ContentType.grammar:
        instructions = (
            "Produce a grammar lesson. Include: 1) a clear explanation of one "
            "grammar point relevant to the topic, appropriate for this level, "
            "2) 3-5 example sentences in French with English translations, "
            "3) a short set of 5 practice exercises (fill-in-the-blank or "
            "transformation), with an answer key at the end."
        )
    elif req.content_type == ContentType.reading:
        instructions = (
            "Produce a short reading passage in French on the topic, sized "
            "appropriately for the level (roughly 100-150 words for A1/A2, "
            "150-300 for B1/B2, 300-450 for C1/C2). Follow it with a French "
            "vocabulary glossary for tricky words, and 4-5 comprehension "
            "questions in French with an answer key."
        )
    else:  # vocab
        instructions = (
            "Produce a vocabulary list of 15-20 words/phrases in French related "
            "to the topic, appropriate for the level. For each entry include: "
            "the French word/phrase, its English translation, its gender/type "
            "if relevant (e.g. nm/nf/verb), and one example sentence in French "
            "with an English translation. End with a short 5-question quiz."
        )

    return f"{base}\n\n{instructions}\n\nFormat the response in clean Markdown."


# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------

@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.post("/generate-lesson", response_model=LessonResponse)
def generate_lesson(req: LessonRequest):
    client = get_client()
    prompt = build_prompt(req)

    try:
        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.AuthenticationError:
        logger.exception("Authentication with Claude API failed.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication with the AI provider failed. Check server API key.",
        )
    except anthropic.RateLimitError:
        logger.exception("Rate limit hit calling Claude API.")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded. Please try again shortly.",
        )
    except anthropic.APIConnectionError:
        logger.exception("Could not connect to Claude API.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Could not reach the AI provider. Please try again later.",
        )
    except anthropic.APIStatusError as e:
        logger.exception("Claude API returned an error status.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI provider error: {e.status_code}",
        )
    except Exception:
        logger.exception("Unexpected error while generating lesson.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while generating the lesson.",
        )

    # Extract text content from the response
    try:
        text_blocks = [block.text for block in message.content if block.type == "text"]
        content = "\n".join(text_blocks).strip()
    except (AttributeError, IndexError):
        logger.exception("Unexpected response shape from Claude API.")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Received an unexpected response format from the AI provider.",
        )

    if not content:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The AI provider returned an empty response.",
        )

    return LessonResponse(
        level=req.level,
        topic=req.topic,
        content_type=req.content_type,
        content=content,
    )


# --------------------------------------------------------------------------
# Generic validation error handler (cleaner error payloads than FastAPI default)
# --------------------------------------------------------------------------

@app.exception_handler(ValueError)
async def value_error_handler(request, exc: ValueError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc)},
    )
