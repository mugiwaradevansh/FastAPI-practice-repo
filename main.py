import os
from typing import Any, Literal

import httpx
from dotenv import load_dotenv
from fastapi import Body, FastAPI, HTTPException
from pydantic import BaseModel, Field, model_validator

load_dotenv()
app = FastAPI(title="AI Engineer Practice API")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/hello/{name}")
def hello(name: str):
    return {"message": f"Hello, {name}!"}


@app.get("/models")
def models():
    return ["gemini-3.8-flash", "gemini-2.5-flash"]


@app.post("/echo")
def echo(payload: Any = Body(default=None)):
    return payload


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1)
    model: str = Field(default="gemini-3.8-flash", pattern=r"^gemini-[a-zA-Z0-9.-]+$")
    temperature: float = Field(default=1.0, ge=0.0, le=2.0)

    @model_validator(mode="after")
    def validate_history(self):
        for index, message in enumerate(self.messages):
            expected = "user" if index % 2 == 0 else "assistant"
            if message.role != expected or not message.content.strip():
                raise ValueError("Messages must be nonblank and alternate user/assistant, starting with user.")
        if self.messages[-1].role != "user":
            raise ValueError("The last message must be from the user.")
        return self


class ChatResponse(BaseModel):
    reply: str
    model_used: str
    tokens_used: int = Field(ge=0)


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GEMINI_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="Gemini API key is not configured.")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{request.model}:generateContent"
    headers = {"x-goog-api-key": api_key}

    contents = []
    for message in request.messages:
        role = "model" if message.role == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": message.content}]})

    payload = {
        "contents": contents,
        "generationConfig": {"temperature": request.temperature},
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Gemini request timed out.")
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 429:
            raise HTTPException(status_code=429, detail="Gemini quota or rate limit reached.")
        raise HTTPException(status_code=502, detail=f"Gemini returned HTTP {exc.response.status_code}. Check model, key and access.")
    except httpx.RequestError:
        raise HTTPException(status_code=502, detail="Could not connect to Gemini.")

    try:
        data = response.json()
        parts = data["candidates"][0]["content"]["parts"]
        reply = "".join(part.get("text", "") for part in parts if not part.get("thought", False))
        if not reply.strip():
            raise ValueError("No answer text")
        return ChatResponse(
            reply=reply,
            model_used=data.get("modelVersion", request.model),
            tokens_used=data["usageMetadata"]["totalTokenCount"],
        )
    except (ValueError, KeyError, IndexError, TypeError, AttributeError):
        raise HTTPException(status_code=502, detail="Gemini returned no usable text or token metadata.")
