from fastapi import FastAPI

from .database import Base, engine
from . import models
from .routes import router


Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="E-Commerce Recommendation System"
)


app.include_router(router)


@app.get("/")
def root():
    return {
        "message": "E-Commerce Recommendation API is running"
    }