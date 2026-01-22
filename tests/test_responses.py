"""Tests for response helpers."""

import pytest

from kiket_sdk.responses import allow, deny, pending


class TestAllow:
    """Tests for allow() response helper."""

    def test_basic_allow(self):
        """Should return properly formatted allow response."""
        response = allow()
        assert response["status"] == "allow"
        assert response["metadata"] == {}
        assert "message" not in response

    def test_with_message(self):
        """Should include message when provided."""
        response = allow(message="Success")
        assert response["message"] == "Success"

    def test_with_data(self):
        """Should include data in metadata."""
        response = allow(data={"route_id": 123, "email": "test@example.com"})
        assert response["metadata"]["route_id"] == 123
        assert response["metadata"]["email"] == "test@example.com"

    def test_with_output_fields(self):
        """Should include output_fields in metadata."""
        response = allow(output_fields={"inbound_email": "abc@parse.example.com"})
        assert response["metadata"]["output_fields"] == {
            "inbound_email": "abc@parse.example.com"
        }

    def test_combined_data_and_output_fields(self):
        """Should combine data and output_fields in metadata."""
        response = allow(
            message="Configured successfully",
            data={"route_id": 456},
            output_fields={"webhook_url": "https://example.com/hook"},
        )
        assert response["status"] == "allow"
        assert response["message"] == "Configured successfully"
        assert response["metadata"]["route_id"] == 456
        assert response["metadata"]["output_fields"] == {
            "webhook_url": "https://example.com/hook"
        }


class TestDeny:
    """Tests for deny() response helper."""

    def test_basic_deny(self):
        """Should return properly formatted deny response."""
        response = deny(message="Access denied")
        assert response["status"] == "deny"
        assert response["message"] == "Access denied"
        assert response["metadata"] == {}

    def test_with_data(self):
        """Should include data in metadata."""
        response = deny(message="Invalid credentials", data={"error_code": "AUTH_FAILED"})
        assert response["metadata"] == {"error_code": "AUTH_FAILED"}


class TestPending:
    """Tests for pending() response helper."""

    def test_basic_pending(self):
        """Should return properly formatted pending response."""
        response = pending(message="Awaiting approval")
        assert response["status"] == "pending"
        assert response["message"] == "Awaiting approval"
        assert response["metadata"] == {}

    def test_with_data(self):
        """Should include data in metadata."""
        response = pending(message="Processing", data={"job_id": "abc123"})
        assert response["metadata"] == {"job_id": "abc123"}
