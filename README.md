# French Learning Material Generator API

A minimal FastAPI backend that generates French learning content (grammar
explanations, reading passages, or vocabulary lists) via the Claude API.

## Setup

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# then edit .env and add your ANTHROPIC_API_KEY
```

Load the `.env` file however you prefer (e.g. `python-dotenv`, or just
`export $(cat .env | xargs)` on Mac/Linux before starting the server).

## Run (without Docker)

```bash
uvicorn main:app --reload
```

Docs available at `http://127.0.0.1:8000/docs`.

## Run with Docker

Make sure you have `.env` set up (see above), then:

```bash
docker compose up --build
```

The API will be available at `http://localhost:8000` (docs at `/docs`).
Stop it with `docker compose down`.

The container includes a `/health` check that Docker uses automatically —
you can also hit it manually:

```bash
curl http://localhost:8000/health
```

### Deploying to the cloud later

The image builds for your host's native architecture by default, which is
fine for local testing. When you're ready to push to a cloud provider that
expects `linux/amd64` (common on most managed container platforms), build
explicitly for that platform — especially if you're on Apple Silicon:

```bash
docker build --platform linux/amd64 -t french-lesson-api .
```

Then tag and push to your registry of choice (ECR, GCR, Docker Hub, etc.):

```bash
docker tag french-lesson-api your-registry/french-lesson-api:latest
docker push your-registry/french-lesson-api:latest
```

Remember to set `ANTHROPIC_API_KEY` as a secret/environment variable on
the cloud platform itself — don't bake it into the image or commit `.env`.

## Endpoint

### `POST /generate-lesson`

**Request body:**

```json
{
  "level": "B1",
  "topic": "talking about your weekend",
  "content_type": "reading"
}
```

- `level`: one of `A1, A2, B1, B2, C1, C2`
- `content_type`: one of `grammar, reading, vocab`
- `topic`: free text, 2–200 characters

**Response:**

```json
{
  "level": "B1",
  "topic": "talking about your weekend",
  "content_type": "reading",
  "content": "## Le week-end de Claire\n\n..."
}
```

**Error responses:**

| Status | Meaning |
|--------|---------|
| 422 | Invalid input (bad level/content_type, missing/too-long topic) |
| 429 | Rate limited by the AI provider |
| 500 | Server misconfiguration or unexpected error |
| 502 | Bad/empty response from the AI provider |
| 503 | Could not reach the AI provider |

## Swapping in OpenAI instead

This implementation calls Claude via the `anthropic` SDK. To use OpenAI
instead, swap the `anthropic.Anthropic` client for `openai.OpenAI`, replace
the `client.messages.create(...)` call with `client.chat.completions.create(...)`,
and adjust the exception types you catch (`openai.AuthenticationError`,
`openai.RateLimitError`, etc.) — the rest of the app (models, prompt
building, error-handling structure) stays the same.
