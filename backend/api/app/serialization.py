from fastapi.encoders import jsonable_encoder


def record(row):
    return jsonable_encoder(
        {
            column.name: getattr(row, column.name)
            for column in row.__table__.columns
            if column.name not in {"storage_key", "checksum"}
        }
    )
