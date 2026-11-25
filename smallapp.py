from fastapi import FastAPI
from typing import Any
from fastapi import Body
app = FastAPI()

@app.get("/health")
def health():
    return {"status":"ok"}

@app.get("/hello/{name}")
def hello(name:str):
    return {"message":f"Hello,{name}!"}

@app.get("/models")
def models():
    return["1","2","3"]



