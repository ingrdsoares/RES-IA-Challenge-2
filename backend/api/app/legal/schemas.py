from datetime import date
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StringConstraints, model_validator

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=256)]


class Section(BaseModel):
    anchor_id: str
    text: str


class LegalDocument(BaseModel):
    schema_version: int = 1
    sections: list[Section] = Field(min_length=1)


class IngestMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_key: Text
    title: Text
    official_url: HttpUrl
    version_label: Text
    authority: Text
    norm_type: Text
    subjects: list[Text] = Field(default_factory=list, max_length=30)
    effective_from: date | None = None
    effective_to: date | None = None

    @model_validator(mode="after")
    def validate_dates(self):
        if self.effective_to and (
            not self.effective_from or self.effective_to < self.effective_from
        ):
            raise ValueError("Intervalo de vigência inválido")
        return self
