"""Helpers for blockchain audit verification via the Kiket API."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

from .exceptions import AuditVerificationError, OutboundRequestError

if TYPE_CHECKING:  # pragma: no cover - import for typing only
    from .client import KiketClient


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        sanitized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(sanitized)
    except ValueError:
        return None


@dataclass(slots=True)
class BlockchainAnchor:
    """Represents a blockchain anchor containing a batch of audit records."""

    id: int
    merkle_root: str
    leaf_count: int
    first_record_at: datetime | None
    last_record_at: datetime | None
    network: str
    status: str
    tx_hash: str | None
    block_number: int | None
    block_timestamp: datetime | None
    confirmed_at: datetime | None
    explorer_url: str | None
    created_at: datetime | None


@dataclass(slots=True)
class BlockchainProof:
    """Represents a Merkle proof for an audit record."""

    record_id: int
    record_type: str
    content_hash: str
    anchor_id: int
    merkle_root: str
    leaf_index: int
    leaf_count: int
    proof: list[str]
    network: str
    tx_hash: str | None
    block_number: int | None
    block_timestamp: datetime | None
    verified: bool
    verification_url: str | None


@dataclass(slots=True)
class VerificationResult:
    """Result of a blockchain verification."""

    verified: bool
    proof_valid: bool
    blockchain_verified: bool
    content_hash: str
    merkle_root: str
    leaf_index: int
    block_number: int | None
    block_timestamp: datetime | None
    network: str | None
    explorer_url: str | None
    error: str | None = None


class AuditClient:
    """Client for blockchain audit verification operations."""

    def __init__(self, client: KiketClient) -> None:
        self._client = client

    async def list_anchors(
        self,
        *,
        status: str | None = None,
        network: str | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        page: int = 1,
        per_page: int = 25,
    ) -> tuple[list[BlockchainAnchor], dict[str, Any]]:
        """List blockchain anchors for the organization.

        Args:
            status: Filter by status (pending, submitted, confirmed, failed)
            network: Filter by network (polygon_amoy, polygon_mainnet)
            from_date: Filter anchors created after this date
            to_date: Filter anchors created before this date
            page: Page number (1-indexed)
            per_page: Results per page (max 100)

        Returns:
            Tuple of (list of anchors, pagination info)
        """
        params: dict[str, Any] = {"page": page, "per_page": per_page}
        if status:
            params["status"] = status
        if network:
            params["network"] = network
        if from_date:
            params["from"] = from_date.isoformat()
        if to_date:
            params["to"] = to_date.isoformat()

        try:
            response = await self._client.get("/api/v1/audit/anchors", params=params)
        except OutboundRequestError as exc:
            raise AuditVerificationError("Failed to list anchors") from exc

        data = response.json()
        anchors = [self._parse_anchor(a) for a in data.get("anchors", [])]
        pagination = data.get("pagination", {})

        return anchors, pagination

    async def get_anchor(self, merkle_root: str, *, include_records: bool = False) -> BlockchainAnchor:
        """Get details of a specific anchor by merkle root.

        Args:
            merkle_root: The merkle root (hex string with 0x prefix)
            include_records: Whether to include the list of records

        Returns:
            BlockchainAnchor instance
        """
        params = {"include_records": "true"} if include_records else {}

        try:
            response = await self._client.get(f"/api/v1/audit/anchors/{merkle_root}", params=params)
        except OutboundRequestError as exc:
            raise AuditVerificationError(f"Failed to get anchor {merkle_root}") from exc

        return self._parse_anchor(response.json())

    async def get_proof(self, record_id: int) -> BlockchainProof:
        """Get the blockchain proof for a specific audit record.

        Args:
            record_id: The ID of the audit record

        Returns:
            BlockchainProof instance
        """
        try:
            response = await self._client.get(f"/api/v1/audit/records/{record_id}/proof")
        except OutboundRequestError as exc:
            raise AuditVerificationError(f"Failed to get proof for record {record_id}") from exc

        return self._parse_proof(response.json())

    async def verify(self, proof: BlockchainProof | dict[str, Any]) -> VerificationResult:
        """Verify a blockchain proof.

        Args:
            proof: BlockchainProof instance or dict with proof data

        Returns:
            VerificationResult instance
        """
        if isinstance(proof, BlockchainProof):
            payload = {
                "content_hash": proof.content_hash,
                "merkle_root": proof.merkle_root,
                "proof": proof.proof,
                "leaf_index": proof.leaf_index,
                "tx_hash": proof.tx_hash,
            }
        else:
            payload = proof

        try:
            response = await self._client.post("/api/v1/audit/verify", json=payload)
        except OutboundRequestError as exc:
            raise AuditVerificationError("Verification request failed") from exc

        data = response.json()
        return VerificationResult(
            verified=data.get("verified", False),
            proof_valid=data.get("proof_valid", False),
            blockchain_verified=data.get("blockchain_verified", False),
            content_hash=data.get("content_hash", ""),
            merkle_root=data.get("merkle_root", ""),
            leaf_index=data.get("leaf_index", 0),
            block_number=data.get("block_number"),
            block_timestamp=_parse_timestamp(data.get("block_timestamp")),
            network=data.get("network"),
            explorer_url=data.get("explorer_url"),
            error=data.get("error"),
        )

    @staticmethod
    def compute_content_hash(data: dict[str, Any]) -> str:
        """Compute the content hash for a record (for local verification).

        Args:
            data: Record data dict

        Returns:
            Hex string with 0x prefix
        """
        canonical = json.dumps(dict(sorted(data.items())), separators=(",", ":"), sort_keys=True)
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return f"0x{digest}"

    @staticmethod
    def verify_proof_locally(
        content_hash: str,
        proof_path: list[str],
        leaf_index: int,
        merkle_root: str,
    ) -> bool:
        """Verify a Merkle proof locally without making an API call.

        Args:
            content_hash: Hash of the record content
            proof_path: Array of sibling hashes
            leaf_index: Position of the leaf in the tree
            merkle_root: Expected root hash

        Returns:
            True if the proof is valid
        """

        def normalize_hash(h: str) -> bytes:
            hex_str = h[2:] if h.startswith("0x") else h
            return bytes.fromhex(hex_str)

        def hash_pair(left: bytes, right: bytes) -> bytes:
            if left > right:
                left, right = right, left
            return hashlib.sha256(left + right).digest()

        current = normalize_hash(content_hash)
        idx = leaf_index

        for sibling_hex in proof_path:
            sibling = normalize_hash(sibling_hex)
            if idx % 2 == 0:
                current = hash_pair(current, sibling)
            else:
                current = hash_pair(sibling, current)
            idx //= 2

        expected = normalize_hash(merkle_root)
        return current == expected

    def _parse_anchor(self, data: dict[str, Any]) -> BlockchainAnchor:
        return BlockchainAnchor(
            id=data.get("id", 0),
            merkle_root=data.get("merkle_root", ""),
            leaf_count=data.get("leaf_count", 0),
            first_record_at=_parse_timestamp(data.get("first_record_at")),
            last_record_at=_parse_timestamp(data.get("last_record_at")),
            network=data.get("network", ""),
            status=data.get("status", ""),
            tx_hash=data.get("tx_hash"),
            block_number=data.get("block_number"),
            block_timestamp=_parse_timestamp(data.get("block_timestamp")),
            confirmed_at=_parse_timestamp(data.get("confirmed_at")),
            explorer_url=data.get("explorer_url"),
            created_at=_parse_timestamp(data.get("created_at")),
        )

    def _parse_proof(self, data: dict[str, Any]) -> BlockchainProof:
        return BlockchainProof(
            record_id=data.get("record_id", 0),
            record_type=data.get("record_type", ""),
            content_hash=data.get("content_hash", ""),
            anchor_id=data.get("anchor_id", 0),
            merkle_root=data.get("merkle_root", ""),
            leaf_index=data.get("leaf_index", 0),
            leaf_count=data.get("leaf_count", 0),
            proof=data.get("proof", []),
            network=data.get("network", ""),
            tx_hash=data.get("tx_hash"),
            block_number=data.get("block_number"),
            block_timestamp=_parse_timestamp(data.get("block_timestamp")),
            verified=data.get("verified", False),
            verification_url=data.get("verification_url"),
        )
