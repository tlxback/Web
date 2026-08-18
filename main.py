from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "FastAPI 跑通了！"}

@app.get("/api/test")
def test_api():
    return {"data": "这是 Vue 发来请求后，后端返回的数据"}
