"""Organization-scoped policy retrieval API for IAM_GATEWAY.

This is a lightweight lexical retrieval baseline (BM25-style ranking) over the
active, already-extracted policy text stored in the database. It intentionally
uses no external model/API and is suitable for validating organization isolation,
chunking, and citations before adding a persistent vector index.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_principal
from app.database import get_db
from app.models import (
    Organization,
    OrganizationMembership,
    PolicyDocument,
    PolicyDocumentVersion,
    Principal,
)

router = APIRouter(prefix="/v1/organizations", tags=["Organization RAG"])

MAX_CHUNK_WORDS = 160
CHUNK_OVERLAP_WORDS = 24
_TOKEN_RE = re.compile(r"(?u)[a-zA-Z0-9]+(?:[-._][a-zA-Z0-9]+)*")
_CLAUSE_RE = re.compile(r"\b[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)*-\d+(?:\.\d+)*\b", re.IGNORECASE)
_PAGE_RE = re.compile(r"^\s*\[PAGE\s+(\d+)\]\s*$", re.IGNORECASE)
_SECTION_RE = re.compile(r"^\s*\[SECTION:\s*(.*?)\]\s*$", re.IGNORECASE)

_STOP_WORDS = set(
    "a an and are as at be been being but by did do does doing for from had has have having he her hers him his how i if in into is it its me my of on once only or other our ours she so than that the their theirs them then there these they this those through to too under until up us very was we were what when where which while who whom why will with would you your yours please tell explain according".split()
)


class RAGQueryRequest(BaseModel):
    query: str = Field(min_length=3, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=10)


def _require_org_membership(
    db: Session, principal: Principal, organization_id: int
) -> OrganizationMembership:
    if not principal.is_active:
        raise HTTPException(status_code=403, detail="This principal is inactive.")

    organization = db.get(Organization, organization_id)
    if organization is None or not organization.is_active:
        raise HTTPException(status_code=404, detail="Organization not found or inactive.")

    membership = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.principal_id == principal.id,
            OrganizationMembership.is_active.is_(True),
        )
        .first()
    )
    if membership is None or membership.role not in {"org_admin", "org_viewer"}:
        raise HTTPException(
            status_code=403,
            detail="An active organization membership is required to search these policies.",
        )

    # Keep the same tenant-boundary check as the document management endpoints.
    team_org_id = principal.team.organization_id if principal.team else None
    if team_org_id != organization_id:
        raise HTTPException(
            status_code=403,
            detail="The authenticated principal's team does not belong to this organization.",
        )
    return membership


def _tokens(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text) if t.lower() not in _STOP_WORDS]


def _source_units(extracted_text: str) -> list[dict[str, Any]]:
    """Turn extracted lines into text units annotated with page/section markers."""
    units: list[dict[str, Any]] = []
    page: int | None = None
    section: str | None = None

    for raw_line in extracted_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        page_match = _PAGE_RE.match(line)
        if page_match:
            page = int(page_match.group(1))
            continue
        section_match = _SECTION_RE.match(line)
        if section_match:
            section = section_match.group(1).strip() or None
            continue
        units.append({"text": line, "page": page, "section": section})
    return units


def _make_chunks(extracted_text: str) -> list[dict[str, Any]]:
    units = _source_units(extracted_text)
    chunks: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []
    current_count = 0

    def emit(items: list[dict[str, Any]]) -> None:
        if not items:
            return
        text = "\n".join(item["text"] for item in items).strip()
        if not text:
            return
        clause_ids = sorted(set(_CLAUSE_RE.findall(text)), key=str.casefold)
        pages = sorted({item["page"] for item in items if item["page"] is not None})
        sections = list(dict.fromkeys(item["section"] for item in items if item["section"]))
        chunks.append({
            "text": text,
            "tokens": _tokens(text),
            "clause_ids": clause_ids,
            "pages": pages,
            "sections": sections,
        })

    def emit_long_unit(unit: dict[str, Any]) -> None:
        words = unit["text"].split()
        start = 0
        while start < len(words):
            piece = " ".join(words[start:start + MAX_CHUNK_WORDS])
            emit([{**unit, "text": piece}])
            if start + MAX_CHUNK_WORDS >= len(words):
                break
            start += MAX_CHUNK_WORDS - CHUNK_OVERLAP_WORDS

    for unit in units:
        word_count = len(unit["text"].split())
        has_clause_id = bool(_CLAUSE_RE.search(unit["text"]))

        # Policy clause IDs are strong citation boundaries. Keep each clause
        # in its own chunk so retrieved citations are precise instead of mixing
        # several neighboring rules into one result.
        if has_clause_id:
            emit(current)
            current = []
            current_count = 0
            if word_count > MAX_CHUNK_WORDS:
                emit_long_unit(unit)
            else:
                emit([unit])
            continue

        if word_count > MAX_CHUNK_WORDS:
            emit(current)
            current = []
            current_count = 0
            emit_long_unit(unit)
            continue

        if current and current_count + word_count > MAX_CHUNK_WORDS:
            emit(current)
            overlap: list[dict[str, Any]] = []
            overlap_count = 0
            for prior in reversed(current):
                prior_count = len(prior["text"].split())
                if overlap and overlap_count + prior_count > CHUNK_OVERLAP_WORDS:
                    break
                overlap.insert(0, prior)
                overlap_count += prior_count
            current = overlap
            current_count = overlap_count

        current.append(unit)
        current_count += word_count

    emit(current)
    return [chunk for chunk in chunks if chunk["tokens"]]


def _rank_bm25(query_terms: list[str], chunks: list[dict[str, Any]]) -> list[tuple[float, int]]:
    if not chunks or not query_terms:
        return []
    doc_freq: Counter[str] = Counter()
    for chunk in chunks:
        doc_freq.update(set(chunk["tokens"]))
    count = len(chunks)
    avg_len = sum(len(chunk["tokens"]) for chunk in chunks) / max(count, 1)
    scores: list[tuple[float, int]] = []
    k1, b = 1.5, 0.75

    for index, chunk in enumerate(chunks):
        frequencies = Counter(chunk["tokens"])
        doc_len = len(chunk["tokens"])
        score = 0.0
        for term in query_terms:
            tf = frequencies.get(term, 0)
            if tf == 0:
                continue
            df = doc_freq.get(term, 0)
            idf = math.log(1 + (count - df + 0.5) / (df + 0.5))
            denominator = tf + k1 * (1 - b + b * doc_len / max(avg_len, 1))
            score += idf * (tf * (k1 + 1)) / denominator
        if score > 0:
            scores.append((score, index))
    scores.sort(key=lambda result: result[0], reverse=True)
    return scores


def organization_has_active_policy_documents(db: Session, organization_id: int) -> bool:
    """Return whether an organization currently has any active, ready policy version."""
    match = (
        db.query(PolicyDocument.id)
        .join(
            PolicyDocumentVersion,
            PolicyDocumentVersion.document_id == PolicyDocument.id,
        )
        .filter(
            PolicyDocument.scope == "organization",
            PolicyDocument.organization_id == organization_id,
            PolicyDocument.status == "active",
            PolicyDocumentVersion.is_active.is_(True),
            PolicyDocumentVersion.processing_status == "ready",
            PolicyDocumentVersion.extracted_text.is_not(None),
        )
        .first()
    )
    return match is not None


def retrieve_policy_evidence(
    db: Session,
    organization_id: int,
    query: str,
    top_k: int = 5,
) -> dict[str, Any]:
    """Retrieve lexical evidence from active policy documents for one organization.

    This service function deliberately does not authorize a caller. Public routes must
    authorize the principal first; chat derives organization_id from the authenticated
    principal's team and applies the membership requirement when active policies exist.
    """
    active_versions = (
        db.query(PolicyDocument, PolicyDocumentVersion)
        .join(PolicyDocumentVersion, PolicyDocumentVersion.document_id == PolicyDocument.id)
        .filter(
            PolicyDocument.scope == "organization",
            PolicyDocument.organization_id == organization_id,
            PolicyDocument.status == "active",
            PolicyDocumentVersion.is_active.is_(True),
            PolicyDocumentVersion.processing_status == "ready",
            PolicyDocumentVersion.extracted_text.is_not(None),
        )
        .order_by(PolicyDocument.id.asc(), PolicyDocumentVersion.version_number.desc())
        .all()
    )

    all_chunks: list[dict[str, Any]] = []
    for document, version in active_versions:
        for local_index, chunk in enumerate(_make_chunks(version.extracted_text or "")):
            all_chunks.append({
                **chunk,
                "document_id": document.id,
                "document_title": document.title,
                "version_id": version.id,
                "version_number": version.version_number,
                "filename": version.original_filename,
                "local_chunk_index": local_index,
            })

    query_terms = _tokens(query)
    ranked = _rank_bm25(query_terms, all_chunks)[:max(1, min(top_k, 10))]
    results: list[dict[str, Any]] = []
    for score, index in ranked:
        chunk = all_chunks[index]
        citation = {
            "document_id": chunk["document_id"],
            "document_title": chunk["document_title"],
            "version_id": chunk["version_id"],
            "version_number": chunk["version_number"],
            "filename": chunk["filename"],
            "clause_ids": chunk["clause_ids"],
            "pages": chunk["pages"],
            "sections": chunk["sections"],
        }
        results.append({
            "rank": len(results) + 1,
            "score": round(score, 4),
            "text": chunk["text"],
            "citation": citation,
        })

    return {
        "organization_id": organization_id,
        "query": query,
        "retrieval_method": "bm25_lexical_baseline",
        "active_policy_documents_searched": len({doc.id for doc, _ in active_versions}),
        "retrieved_count": len(results),
        "results": results,
        "message": (
            "No matching active policy text was found."
            if not results
            else "Retrieved organization policy evidence."
        ),
    }


@router.post("/{organization_id}/rag/query")
def query_organization_policy_rag(
    organization_id: int,
    request: RAGQueryRequest,
    principal: Principal = Depends(get_current_principal),
    db: Session = Depends(get_db),
):
    """Retrieve relevant chunks only from active policies owned by this organization.

    This endpoint returns evidence and citations for testing/debugging. It does not
    call an LLM or make policy allow/block decisions; those remain separate controls.
    """
    _require_org_membership(db, principal, organization_id)

    if not _tokens(request.query):
        raise HTTPException(
            status_code=422,
            detail="Query needs meaningful policy-related terms after normalization.",
        )

    evidence = retrieve_policy_evidence(
        db=db,
        organization_id=organization_id,
        query=request.query,
        top_k=request.top_k,
    )
    if evidence["retrieved_count"] == 0:
        evidence["message"] = "No matching active policy text was found."
    else:
        evidence["message"] = (
            "Retrieved evidence only; this endpoint does not itself decide whether a request is allowed or blocked."
        )
    return evidence
