import os
import secrets
from contextlib import asynccontextmanager
from typing import Any, Literal

import httpx
from dotenv import load_dotenv
from fastapi import Body, Depends, FastAPI, HTTPException, Request
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field, model_validator

load_dotenv()

# 1. Authentication: incoming client -> our FastAPI application.
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str | None = Depends(api_key_header)):
    expected = os.getenv("APP_API_KEY")
    if not expected or not expected.strip():
        raise HTTPException(503, "Application API key is not configured.")
    if api_key is None or not secrets.compare_digest(
        api_key.encode("utf-8"), expected.encode("utf-8")
    ):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid API key.",
            headers={"WWW-Authenticate": "APIKey"},
        )


# 2. Resource lifecycle: one HTTP client per application worker.
@asynccontextmanager
async def lifespan(app: FastAPI):
    async with httpx.AsyncClient(timeout=60.0) as client:
        app.state.http_client = client
        yield


async def get_client(request: Request) -> httpx.AsyncClient:
    return request.app.state.http_client


app = FastAPI(
    title="AI Engineer Practice API",
    lifespan=lifespan,
    dependencies=[Depends(verify_api_key)],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/hello/{name}")
async def hello(name: str):
    return {"message": f"Hello, {name}!"}


@app.get("/models")
async def models():
    return ["gpt-4o-mini", "gpt-4.1-mini"]


@app.post("/echo")
async def echo(payload: Any = Body(default=None)):
    return payload


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1)
    model: Literal["gpt-4o-mini", "gpt-4.1-mini"] = "gpt-4o-mini"
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
