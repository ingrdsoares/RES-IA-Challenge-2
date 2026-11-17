from datetime import date
from uuid import UUID

from qdrant_client import models

from app.legal.index import COLLECTION
from app.legal.models import NormVersion


def retrieve_legal(
    db,
    index,
    question,
    context,
    embed,
    limit=5,
    score_threshold=0.5,
    collection=COLLECTION,
    hybrid_collection=None,
    reranker=None,
):
    hybrid = bool(hybrid_collection and index.collection_exists(hybrid_collection))
    effective_collection = hybrid_collection if hybrid else collection
    if not index.collection_exists(effective_collection):
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
    vector = embed(question)
    strategy = "dense"
    try:
        if hybrid:
            from app.sparse import vetor_consulta

            indices, values = vetor_consulta(question)
            prefetch = [
                models.Prefetch(
                    query=vector, using="dense", filter=query_filter, limit=min(limit * 4, 40)
                )
            ]
            if indices:
                prefetch.append(
                    models.Prefetch(
                        query=models.SparseVector(indices=indices, values=values),
                        using="sparse",
                        filter=query_filter,
                        limit=min(limit * 4, 40),
                    )
                )
            fused = index.query_points(
                effective_collection,
                prefetch=prefetch,
                query=models.FusionQuery(fusion=models.Fusion.RRF),
                query_filter=query_filter,
                limit=min(limit * 4, 40),
            ).points
            # Fused rank is not cosine similarity. Apply the dense threshold separately.
            eligible = (
                index.query_points(
                    effective_collection,
                    query=vector,
                    using="dense",
                    query_filter=models.Filter(
                        must=[query_filter, models.HasIdCondition(has_id=[h.id for h in fused])]
                    ),
                    score_threshold=score_threshold,
                    limit=max(1, len(fused)),
                ).points
                if fused
                else []
            )
            allowed = {hit.id for hit in eligible}
            hits = [hit for hit in fused if hit.id in allowed]
            strategy = "hybrid"
        else:
            hits = index.query_points(
                collection,
                query=vector,
                limit=min(limit * 4, 40),
                query_filter=query_filter,
                score_threshold=score_threshold,
            ).points
    except Exception:
        if not hybrid or not index.collection_exists(collection):
            raise
        hits = index.query_points(
            collection,
            query=vector,
            limit=min(limit * 4, 40),
            query_filter=query_filter,
            score_threshold=score_threshold,
        ).points
        strategy = "dense_fallback"
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
                "retrieval_strategy": strategy,
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
        if len(passages) >= (min(limit * 4, 40) if reranker else limit):
            break
    if reranker and passages:
        from app.schemas import Source

        sources = [
            Source(id=i, text=p["text"], source=p["official_url"], score=1.0, title=p["title"])
            for i, p in enumerate(passages)
        ]
        passages = [passages[int(source.id)] for source in reranker.reordenar(question, sources)]
    return passages[:limit]
