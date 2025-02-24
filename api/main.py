from fastapi import FastAPI
from config import logger
from api.Routers import router as api_router

app = FastAPI()
app.include_router(api_router)

if __name__ == "__main__":
    import uvicorn

    logger.info("Starting server...")
    uvicorn.run(app, host="0.0.0.0", port=8855)
