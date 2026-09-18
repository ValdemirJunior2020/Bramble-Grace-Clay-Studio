import uvicorn
from app.config import DEFAULT_BACKEND_HOST, DEFAULT_BACKEND_PORT
if __name__ == "__main__":
    uvicorn.run("app.main:app", host=DEFAULT_BACKEND_HOST, port=DEFAULT_BACKEND_PORT, reload=False)
