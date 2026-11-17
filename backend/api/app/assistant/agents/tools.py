from qdrant_client import QdrantClient
from sqlalchemy import select

from app.assistant.agents.models import AgentStep
from app.assistant.tools import retrieve_legal
from app.companies.service import require_company
from app.evidence.service import get_fiscal_status
from app.fiscal.models import Calculation
from app.fiscal.schemas import CalculationInput
from app.fiscal.service import calculate
from app.legal.hybrid import active_collection
from app.models import LocalModels
from app.reranker import Reranker
from app.serialization import record


class AgentTools:
    def __init__(self, factory, owner_id, company_id, context, settings):
        self.factory, self.owner_id, self.company_id = factory, owner_id, company_id
        self.context, self.settings = context, settings

    def fiscal_status(self, period):
        with self.factory() as db:
            require_company(db, self.owner_id, self.company_id)
            return get_fiscal_status(db, self.company_id, period)

    def calculate(self, data, step_id):
        request = CalculationInput.model_validate(data)
        if request.period != self.context.get("period"):
            raise ValueError("Competência divergente")
        with self.factory.begin() as db:
            require_company(db, self.owner_id, self.company_id)
            step = db.scalar(select(AgentStep).where(AgentStep.id == step_id).with_for_update())
            if step is None:
                raise ValueError("Etapa inexistente")
            from app.assistant.agents.models import AgentRun

            run = db.get(AgentRun, step.run_id)
            if (
                run.company_id != self.company_id
                or run.owner_id != self.owner_id
                or run.revision != step.revision
            ):
                raise ValueError("Etapa não autorizada")
            existing = db.scalar(select(Calculation).where(Calculation.agent_step_id == step_id))
            if existing:
                if (
                    existing.request != request.model_dump(mode="json")
                    or existing.company_snapshot != self.context["company"]
                ):
                    raise ValueError("Cálculo idempotente divergente")
                return record(existing)
            result = calculate(
                db,
                self.company_id,
                self.owner_id,
                request,
                context_snapshot=self.context["company"],
            )
            result.agent_step_id = step_id
            db.flush()
            return record(result)

    def legal(self, question):
        index = QdrantClient(
            url=str(self.settings.qdrant_url), timeout=self.settings.qdrant_timeout
        )
        models = LocalModels(self.settings)
        reranker = Reranker(self.settings)
        try:
            with self.factory() as db:
                require_company(db, self.owner_id, self.company_id)
                return retrieve_legal(
                    db,
                    index,
                    question,
                    self.context,
                    models.embed_question,
                    self.settings.top_k,
                    self.settings.score_threshold,
                    hybrid_collection=active_collection(db),
                    reranker=reranker,
                )
        finally:
            reranker.close()
            index.close()
            models.close()
