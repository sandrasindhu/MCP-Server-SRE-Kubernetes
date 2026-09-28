from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel

from app.graph import build_graph


class InvestigationRequest(BaseModel):
    query: str


graph = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global graph
    graph = await build_graph()
    yield


app = FastAPI(
    title="LangGraph AWS Ops Agent",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    return {"status": "ok", "graph_loaded": graph is not None}


@app.post("/investigate")
async def investigate(request: InvestigationRequest):
    if graph is None:
        raise RuntimeError("Graph is not initialized")

    result = await graph.ainvoke(
        {"messages": [{"role": "user", "content": request.query}]}
    )

    final_message = result["messages"][-1]

    return {
        "answer": final_message.content,
        "message_count": len(result["messages"]),
    }
