from fastapi import FastAPI
from pydantic import BaseModel
from typing import Any
from fastapi import Body
app = FastAPI()

class Item(BaseModel):
    name: str
    description: str | None = None
    price: float
    tax: float | None = None

@app.post("/items/")
async def create_item(item:Item):
    return item

@app.get("/health")
def health():
    return {"status":"ok"}

@app.get("/hello/{name}")
def hello(name:str):
    return {"message":f"Hello,{name}!"}

@app.get("/models")
def models():
    return["1","2","3"]

@app.post("/echo")
def echo(payload: Any = Body(default=None)):
    return payload

