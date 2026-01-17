"""Tests for the IntakeFormsClient."""
from __future__ import annotations

from datetime import datetime

import httpx
import pytest

from kiket_sdk.client import KiketClient
from kiket_sdk.intake_forms import IntakeFormsClient


class MockTransport(httpx.MockTransport):
    pass


@pytest.fixture
def mock_client():
    """Create a KiketClient with mock transport."""

    async def default_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=200, json={"data": []})

    client = KiketClient(
        base_url="https://api.kiket.dev",
        workspace_token=None,
        runtime_token="rt_123",
    )
    client._client = httpx.AsyncClient(
        transport=MockTransport(default_handler), base_url=client.base_url
    )
    return client


@pytest.mark.asyncio
async def test_list_intake_forms_includes_project_id():
    """Test that list includes project_id in query params."""
    captured: dict[str, httpx.Request] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(status_code=200, json={"data": []})

    client = KiketClient(
        base_url="https://api.kiket.dev",
        workspace_token=None,
        runtime_token="rt_123",
    )
    client._client = httpx.AsyncClient(
        transport=MockTransport(handler), base_url=client.base_url
    )

    intake_forms = IntakeFormsClient(client, project_id=42)
    async with client:
        await intake_forms.list()

    request = captured["request"]
    assert request.url.path.endswith("/api/v1/ext/intake_forms")
    assert request.url.params["project_id"] == "42"
    assert request.headers["X-Kiket-Runtime-Token"] == "rt_123"


@pytest.mark.asyncio
async def test_list_intake_forms_with_filters():
    """Test that list includes optional filters."""
    captured: dict[str, httpx.Request] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(status_code=200, json={"data": []})

    client = KiketClient(
        base_url="https://api.kiket.dev",
        workspace_token=None,
        runtime_token="rt_123",
    )
    client._client = httpx.AsyncClient(
        transport=MockTransport(handler), base_url=client.base_url
    )

    intake_forms = IntakeFormsClient(client, project_id=42)
    async with client:
        await intake_forms.list(active=True, public_only=True, limit=10)

    request = captured["request"]
    assert request.url.params["active"] == "true"
    assert request.url.params["public"] == "true"
    assert request.url.params["limit"] == "10"


@pytest.mark.asyncio
async def test_get_intake_form():
    """Test getting a specific intake form."""
    captured: dict[str, httpx.Request] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(
            status_code=200,
            json={
                "id": 1,
                "key": "feedback",
                "name": "Feedback Form",
                "active": True,
                "public": True,
            },
        )

    client = KiketClient(
        base_url="https://api.kiket.dev",
        workspace_token=None,
        runtime_token="rt_123",
    )
    client._client = httpx.AsyncClient(
        transport=MockTransport(handler), base_url=client.base_url
    )

    intake_forms = IntakeFormsClient(client, project_id=42)
    async with client:
        result = await intake_forms.get("feedback")

    request = captured["request"]
    assert request.url.path.endswith("/api/v1/ext/intake_forms/feedback")
    assert result["key"] == "feedback"


@pytest.mark.asyncio
async def test_list_submissions():
    """Test listing submissions for an intake form."""
    captured: dict[str, httpx.Request] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(status_code=200, json={"data": []})

    client = KiketClient(
        base_url="https://api.kiket.dev",
        workspace_token=None,
        runtime_token="rt_123",
    )
    client._client = httpx.AsyncClient(
        transport=MockTransport(handler), base_url=client.base_url
    )

    intake_forms = IntakeFormsClient(client, project_id=42)
    async with client:
        await intake_forms.list_submissions("feedback", status="pending", limit=25)

    request = captured["request"]
    assert request.url.path.endswith("/api/v1/ext/intake_forms/feedback/submissions")
    assert request.url.params["status"] == "pending"
    assert request.url.params["limit"] == "25"


@pytest.mark.asyncio
async def test_list_submissions_with_since():
    """Test listing submissions with since filter."""
    captured: dict[str, httpx.Request] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(status_code=200, json={"data": []})

    client = KiketClient(
        base_url="https://api.kiket.dev",
        workspace_token=None,
        runtime_token="rt_123",
    )
    client._client = httpx.AsyncClient(
        transport=MockTransport(handler), base_url=client.base_url
    )

    intake_forms = IntakeFormsClient(client, project_id=42)
    since_time = datetime(2025, 1, 1, 12, 0, 0)
    async with client:
        await intake_forms.list_submissions("feedback", since=since_time)

    request = captured["request"]
    assert "since" in request.url.params
    assert request.url.params["since"] == "2025-01-01T12:00:00"


@pytest.mark.asyncio
async def test_create_submission():
    """Test creating a submission."""
    captured: dict[str, httpx.Request] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(
            status_code=201,
            json={"id": 1, "status": "pending", "data": {"email": "test@example.com"}},
        )

    client = KiketClient(
        base_url="https://api.kiket.dev",
        workspace_token=None,
        runtime_token="rt_123",
    )
    client._client = httpx.AsyncClient(
        transport=MockTransport(handler), base_url=client.base_url
    )

    intake_forms = IntakeFormsClient(client, project_id=42)
    async with client:
        result = await intake_forms.create_submission(
            "feedback",
            data={"email": "test@example.com", "message": "Hello"},
            metadata={"source": "api"},
        )

    request = captured["request"]
    assert request.method == "POST"
    assert request.url.path.endswith("/api/v1/ext/intake_forms/feedback/submissions")
    assert result["status"] == "pending"


@pytest.mark.asyncio
async def test_approve_submission():
    """Test approving a submission."""
    captured: dict[str, httpx.Request] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(
            status_code=200,
            json={"id": 1, "status": "approved"},
        )

    client = KiketClient(
        base_url="https://api.kiket.dev",
        workspace_token=None,
        runtime_token="rt_123",
    )
    client._client = httpx.AsyncClient(
        transport=MockTransport(handler), base_url=client.base_url
    )

    intake_forms = IntakeFormsClient(client, project_id=42)
    async with client:
        result = await intake_forms.approve_submission("feedback", 1, notes="Looks good!")

    request = captured["request"]
    assert request.method == "POST"
    assert request.url.path.endswith("/api/v1/ext/intake_forms/feedback/submissions/1/approve")
    assert result["status"] == "approved"


@pytest.mark.asyncio
async def test_reject_submission():
    """Test rejecting a submission."""
    captured: dict[str, httpx.Request] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(
            status_code=200,
            json={"id": 1, "status": "rejected"},
        )

    client = KiketClient(
        base_url="https://api.kiket.dev",
        workspace_token=None,
        runtime_token="rt_123",
    )
    client._client = httpx.AsyncClient(
        transport=MockTransport(handler), base_url=client.base_url
    )

    intake_forms = IntakeFormsClient(client, project_id=42)
    async with client:
        result = await intake_forms.reject_submission("feedback", 1, notes="Invalid data")

    request = captured["request"]
    assert request.method == "POST"
    assert request.url.path.endswith("/api/v1/ext/intake_forms/feedback/submissions/1/reject")
    assert result["status"] == "rejected"


@pytest.mark.asyncio
async def test_stats():
    """Test getting submission statistics."""
    captured: dict[str, httpx.Request] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["request"] = request
        return httpx.Response(
            status_code=200,
            json={
                "total_submissions": 100,
                "pending": 10,
                "approved": 80,
                "rejected": 5,
                "converted": 5,
            },
        )

    client = KiketClient(
        base_url="https://api.kiket.dev",
        workspace_token=None,
        runtime_token="rt_123",
    )
    client._client = httpx.AsyncClient(
        transport=MockTransport(handler), base_url=client.base_url
    )

    intake_forms = IntakeFormsClient(client, project_id=42)
    async with client:
        result = await intake_forms.stats("feedback", period="month")

    request = captured["request"]
    assert request.url.path.endswith("/api/v1/ext/intake_forms/feedback/stats")
    assert request.url.params["period"] == "month"
    assert result["total_submissions"] == 100


def test_requires_project_id():
    """Test that project_id is required."""
    client = KiketClient(
        base_url="https://api.kiket.dev",
        workspace_token=None,
        runtime_token="rt_123",
    )

    with pytest.raises(ValueError, match="project_id is required"):
        IntakeFormsClient(client, project_id=None)


@pytest.mark.asyncio
async def test_get_requires_form_key():
    """Test that form_key is required for get."""
    client = KiketClient(
        base_url="https://api.kiket.dev",
        workspace_token=None,
        runtime_token="rt_123",
    )
    intake_forms = IntakeFormsClient(client, project_id=42)

    with pytest.raises(ValueError, match="form_key is required"):
        await intake_forms.get("")


def test_public_url_returns_url_for_public_form():
    """Test that public_url returns URL for public forms."""
    client = KiketClient(
        base_url="https://api.kiket.dev",
        workspace_token=None,
        runtime_token="rt_123",
    )
    intake_forms = IntakeFormsClient(client, project_id=42)

    form = {
        "id": 1,
        "key": "feedback",
        "public": True,
        "form_url": "https://app.kiket.dev/forms/feedback",
    }
    assert intake_forms.public_url(form) == "https://app.kiket.dev/forms/feedback"


def test_public_url_returns_none_for_private_form():
    """Test that public_url returns None for private forms."""
    client = KiketClient(
        base_url="https://api.kiket.dev",
        workspace_token=None,
        runtime_token="rt_123",
    )
    intake_forms = IntakeFormsClient(client, project_id=42)

    form = {
        "id": 1,
        "key": "internal",
        "public": False,
        "form_url": None,
    }
    assert intake_forms.public_url(form) is None
