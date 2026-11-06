from fastapi import FastAPI

app = FastAPI(title="Contest Platform")

@app.get("/health")
async def health():
    return {"status": "ok"}
