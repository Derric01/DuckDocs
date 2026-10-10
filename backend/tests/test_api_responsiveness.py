import asyncio
import time

import httpx

from app.api.dependencies import get_rag, get_repository
from app.domain.models import GroundedResponse, utc_now
from app.main import app


class SlowRag:
    def ask(self, query: str, scope=None) -> GroundedResponse:  # type: ignore[no-untyped-def]
        time.sleep(0.15)
        return GroundedResponse(
            id="resp_slow",
            kind="ask",
            query=query,
            outcome="insufficient_evidence",
            answer=None,
            grounded=False,
            citations=[],
            retrieved_chunk_count=0,
            provider={"kind": "chat", "name": "test", "model": "slow"},
            refusal_reason="insufficient_evidence",
            created_at=utc_now(),
        )


class EmptyRepository:
    def list_documents(self) -> list[object]:
        return []


def test_slow_ask_does_not_block_documents_request() -> None:
    async def exercise() -> None:
        app.dependency_overrides[get_rag] = lambda: SlowRag()
        app.dependency_overrides[get_repository] = lambda: EmptyRepository()
        try:
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                ask_task = asyncio.create_task(client.post("/api/v1/ask", json={"query": "slow"}))
                await asyncio.sleep(0.02)
                started = time.perf_counter()
                documents = await client.get("/api/v1/documents")
                elapsed = time.perf_counter() - started

            assert documents.status_code == 200
            assert elapsed < 0.12
            assert ask_task.done() is False
            await ask_task
        finally:
            app.dependency_overrides.pop(get_rag, None)
            app.dependency_overrides.pop(get_repository, None)

    asyncio.run(exercise())
