from pydantic import BaseModel


class LiveHealthResponse(BaseModel):
    status: str
    service: str
    env: str


class ReadyHealthResponse(BaseModel):
    status: str
    database: str
    redis: str
