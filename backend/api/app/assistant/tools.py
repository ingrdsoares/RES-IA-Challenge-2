from datetime import date
from uuid import UUID

from qdrant_client import models

from app.legal.index import COLLECTION
from app.legal.models import NormVersion


def retrieve_legal(db, index, question, context, embed, limit=5, score_threshold=0.5):
    if not index.collection_exists(COLLECTION):
        return []
    reference = (
        date.fromisoformat(context["period"] + "-01") if context.get("period") else date.today()
    )
    # Use index dates as prefilter, and verify catalog again before any generation.
    jurisdictions = ["BR", "BR-" + context["company"]["state"]]
    query_filter = models.Filter(
        must=[
            models.FieldCondition(key="jurisdiction", match=models.MatchAny(any=jurisdictions)),
            models.FieldCondition(
                key="effective_from_day", range=models.Range(lte=reference.toordinal())
            ),
        ],
        must_not=[
            models.FieldCondition(
                key="effective_to_day", range=models.Range(lt=reference.toordinal())
            )
        ],
    )
    hits = index.query_points(
        COLLECTION,
        query=embed(question),
        limit=min(limit * 4, 40),
        query_filter=query_filter,
        score_threshold=score_threshold,
    ).points
    passages = []
    for hit in hits:
        payload = hit.payload or {}
        try:
            version = db.get(NormVersion, UUID(payload["version_id"]))
        except (ValueError, KeyError, TypeError):
            continue
        if (
            version is None
            or version.status != "ready"
            or version.jurisdiction not in jurisdictions
            or not version.effective_from
            or version.effective_from > reference
            or (version.effective_to and version.effective_to < reference)
            or str(version.document_id) != payload.get("document_id")
            or payload.get("anchor_id") not in version.anchors
            or not payload.get("text")
        ):
            continue
        passages.append(
            {
                "document_id": str(version.document_id),
                "version_id": str(version.id),
                "anchor_id": payload["anchor_id"],
                "text": payload["text"],
                "title": version.title,
                "official_url": version.official_url,
                "reference_date": reference.isoformat(),
                "effective_from": str(version.effective_from),
                "effective_to": str(version.effective_to) if version.effective_to else None,
            }
        )
        if len(passages) >= limit:
            break
    return passages
