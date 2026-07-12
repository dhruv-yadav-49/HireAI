from apps.api.core.config import settings
from fastapi import FastAPI

app = FastAPI(title=settings.APP_NAME)

@app.get("/")
def read_root():
    return {"message": "Welcome to HireAI API"}
