from datetime import datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import tuple_


def page(db, query, model, view, limit, cursor):
    if cursor:
        try:
            value, identifier = cursor.split("|")
            after = datetime.fromisoformat(value)
            if after.tzinfo is None:
                raise ValueError("timezone required")
            query = query.where(
                tuple_(model.created_at, model.id) > tuple_(after, UUID(identifier))
            )
        except ValueError:
            raise HTTPException(422, "Cursor inválido") from None
    rows = list(db.scalars(query.order_by(model.created_at, model.id).limit(limit + 1)))
    selected = rows[:limit]
    serializer = getattr(view, "model_validate", view)
    return {
        "items": [serializer(row) for row in selected],
        "next_cursor": f"{selected[-1].created_at.isoformat()}|{selected[-1].id}"
        if len(rows) > limit
        else None,
    }
