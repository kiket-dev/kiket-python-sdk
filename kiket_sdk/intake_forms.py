"""Helpers for managing intake forms and submissions via the Kiket API."""
from __future__ import annotations

from datetime import datetime
from typing import Any, TypedDict
from urllib.parse import quote

from .client import KiketClient


class IntakeFormField(TypedDict, total=False):
    """Shape of an intake form field."""
    key: str
    label: str
    field_type: str
    required: bool
    options: list[str] | None
    placeholder: str | None
    help_text: str | None


class IntakeForm(TypedDict, total=False):
    """Shape of an intake form response."""
    id: int
    key: str
    name: str
    description: str | None
    active: bool
    public: bool
    fields: list[IntakeFormField]
    form_url: str | None
    embed_allowed: bool
    submissions_count: int
    created_at: str
    updated_at: str


class IntakeSubmission(TypedDict, total=False):
    """Shape of an intake submission response."""
    id: int
    intake_form_id: int
    status: str
    data: dict[str, Any]
    metadata: dict[str, Any] | None
    submitted_by_email: str | None
    reviewed_by: str | None
    reviewed_at: str | None
    notes: str | None
    created_at: str
    updated_at: str


class IntakeFormStats(TypedDict, total=False):
    """Shape of intake form statistics."""
    total_submissions: int
    pending: int
    approved: int
    rejected: int
    converted: int
    period: str | None


class IntakeFormListResponse(TypedDict):
    """Response from listing intake forms."""
    data: list[IntakeForm]


class IntakeSubmissionListResponse(TypedDict):
    """Response from listing submissions."""
    data: list[IntakeSubmission]


class IntakeFormsClient:
    """Client for managing intake forms and submissions."""

    def __init__(self, client: KiketClient, project_id: str | int) -> None:
        if project_id is None:
            raise ValueError("project_id is required for intake form operations")

        self._client = client
        self._project_id = str(project_id)

    async def list(
        self,
        *,
        active: bool | None = None,
        public_only: bool | None = None,
        limit: int | None = None,
    ) -> IntakeFormListResponse:
        """
        List all intake forms for the project.

        Args:
            active: Filter by active status
            public_only: Filter by public forms only
            limit: Maximum number of forms to return

        Returns:
            Response with forms array
        """
        params = self._base_params()
        if active is not None:
            params["active"] = str(active).lower()
        if public_only is not None:
            params["public"] = str(public_only).lower()
        if limit is not None:
            params["limit"] = str(limit)

        response = await self._client.get("/api/v1/ext/intake_forms", params=params)
        return response.json()

    async def get(self, form_key: str) -> IntakeForm:
        """
        Get a specific intake form by key or ID.

        Args:
            form_key: The form key or ID

        Returns:
            The intake form details
        """
        if not form_key:
            raise ValueError("form_key is required")

        response = await self._client.get(
            f"/api/v1/ext/intake_forms/{quote(str(form_key), safe='')}",
            params=self._base_params(),
        )
        return response.json()

    def public_url(self, form: IntakeForm) -> str | None:
        """
        Get the public URL for a form if it's public.

        Args:
            form: The intake form object

        Returns:
            The public URL if the form is public, None otherwise
        """
        if form.get("public"):
            return form.get("form_url")
        return None

    async def list_submissions(
        self,
        form_key: str,
        *,
        status: str | None = None,
        limit: int | None = None,
        since: datetime | str | None = None,
    ) -> IntakeSubmissionListResponse:
        """
        List submissions for an intake form.

        Args:
            form_key: The form key or ID
            status: Filter by status (pending, approved, rejected, converted)
            limit: Maximum number of submissions to return
            since: Only return submissions after this time

        Returns:
            Response with submissions array
        """
        if not form_key:
            raise ValueError("form_key is required")

        params = self._base_params()
        if status is not None:
            params["status"] = status
        if limit is not None:
            params["limit"] = str(limit)
        if since is not None:
            params["since"] = self._format_timestamp(since)

        response = await self._client.get(
            f"/api/v1/ext/intake_forms/{quote(str(form_key), safe='')}/submissions",
            params=params,
        )
        return response.json()

    async def get_submission(self, form_key: str, submission_id: str | int) -> IntakeSubmission:
        """
        Get a specific submission by ID.

        Args:
            form_key: The form key or ID
            submission_id: The submission ID

        Returns:
            The submission details
        """
        if not form_key:
            raise ValueError("form_key is required")
        if submission_id is None:
            raise ValueError("submission_id is required")

        response = await self._client.get(
            f"/api/v1/ext/intake_forms/{quote(str(form_key), safe='')}/submissions/{submission_id}",
            params=self._base_params(),
        )
        return response.json()

    async def create_submission(
        self,
        form_key: str,
        data: dict[str, Any],
        *,
        metadata: dict[str, Any] | None = None,
    ) -> IntakeSubmission:
        """
        Create a new submission for an intake form.
        This is typically used for internal/programmatic submissions.

        Args:
            form_key: The form key or ID
            data: The submission data (field values)
            metadata: Optional metadata

        Returns:
            The created submission
        """
        if not form_key:
            raise ValueError("form_key is required")
        if data is None:
            raise ValueError("data is required")

        payload: dict[str, Any] = {
            "project_id": self._project_id,
            "data": data,
        }
        if metadata is not None:
            payload["metadata"] = metadata

        response = await self._client.post(
            f"/api/v1/ext/intake_forms/{quote(str(form_key), safe='')}/submissions",
            json=payload,
        )
        return response.json()

    async def approve_submission(
        self,
        form_key: str,
        submission_id: str | int,
        *,
        notes: str | None = None,
    ) -> IntakeSubmission:
        """
        Approve a pending submission.

        Args:
            form_key: The form key or ID
            submission_id: The submission ID
            notes: Optional approval notes

        Returns:
            The updated submission
        """
        if not form_key:
            raise ValueError("form_key is required")
        if submission_id is None:
            raise ValueError("submission_id is required")

        payload: dict[str, Any] = {"project_id": self._project_id}
        if notes is not None:
            payload["notes"] = notes

        response = await self._client.post(
            f"/api/v1/ext/intake_forms/{quote(str(form_key), safe='')}/submissions/{submission_id}/approve",
            json=payload,
        )
        return response.json()

    async def reject_submission(
        self,
        form_key: str,
        submission_id: str | int,
        *,
        notes: str | None = None,
    ) -> IntakeSubmission:
        """
        Reject a pending submission.

        Args:
            form_key: The form key or ID
            submission_id: The submission ID
            notes: Optional rejection notes

        Returns:
            The updated submission
        """
        if not form_key:
            raise ValueError("form_key is required")
        if submission_id is None:
            raise ValueError("submission_id is required")

        payload: dict[str, Any] = {"project_id": self._project_id}
        if notes is not None:
            payload["notes"] = notes

        response = await self._client.post(
            f"/api/v1/ext/intake_forms/{quote(str(form_key), safe='')}/submissions/{submission_id}/reject",
            json=payload,
        )
        return response.json()

    async def stats(
        self,
        form_key: str,
        *,
        period: str | None = None,
    ) -> IntakeFormStats:
        """
        Get submission statistics for an intake form.

        Args:
            form_key: The form key or ID
            period: Time period for stats (day, week, month)

        Returns:
            Statistics including counts by status
        """
        if not form_key:
            raise ValueError("form_key is required")

        params = self._base_params()
        if period is not None:
            params["period"] = period

        response = await self._client.get(
            f"/api/v1/ext/intake_forms/{quote(str(form_key), safe='')}/stats",
            params=params,
        )
        return response.json()

    def _base_params(self) -> dict[str, str]:
        return {"project_id": self._project_id}

    @staticmethod
    def _format_timestamp(time: datetime | str) -> str:
        if isinstance(time, datetime):
            return time.isoformat()
        return str(time)
