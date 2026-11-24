"""Testes unitários para o Extrator de Entidades Fiscais e Guardrails do Assistente."""

from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import uuid4

from app.assistant.context import resolve_context
from app.assistant.extractor import FiscalExtractionResult, TaxEntityExtractor
from app.assistant.orchestrator import answer_message
from app.assistant.schemas import MessageInput
from app.companies.schemas import CompanySnapshot


def test_extractor_identifies_cnae_and_fator_r():
    extractor = TaxEntityExtractor()
    result = extractor.extract(
        "Empresa CNAE 6201-5/01 faturou R$ 300.000,00 no ano com folha de R$ 90.000,00. Como fica o imposto?"
    )
    assert isinstance(result, FiscalExtractionResult)
    assert result.intencao_primaria == "calculo_simples"
    params = result.parametros_calculo
    assert params.get("cnae_codigo") == "6201-5/01"
    assert params.get("rbt12") == 300000.0
    assert params.get("folha_12m") == 90000.0
    assert params.get("fator_r_calculado") == 0.3
    assert "Fator R" in result.query_expandida or "alíquota" in result.query_expandida


def test_extractor_identifies_mei_excess():
    extractor = TaxEntityExtractor()
    result = extractor.extract(
        "Faturei 105 mil no MEI com salão de beleza (CNAE 9602-5/01). O que acontece?"
    )
    assert result.intencao_primaria in (
        "desenquadramento_mei",
        "enquadramento_mei",
        "calculo_simples",
    )
    params = result.parametros_calculo
    assert params.get("rbt12") == 105000.0
    assert "9602-5/01" in [c["codigo"] for c in result.cnaes]


def test_resolve_context_enriches_with_extraction():
    from datetime import datetime, timezone

    from app.assistant.context import resolve_context

    snapshot = CompanySnapshot(
        id=uuid4(),
        cnpj="11222333000181",
        cnae="6201501",
        state="DF",
        municipality="Brasília",
        size="me",
        regime="simples",
        provenance={"cnpj": "test"},
        created_at=datetime.now(timezone.utc),
    )
    msg = MessageInput(text="Minha empresa fatura R$ 200 mil por ano. Quanto vou pagar de imposto?")
    decision = resolve_context(snapshot, msg)

    assert "extraction" in decision.context
    assert "query_expandida" in decision.context
    assert decision.context["extraction"]["intencao_primaria"] == "calculo_simples"


def test_resolve_context_does_not_block_mei_queries_with_false_period():
    snapshot = CompanySnapshot(
        id=uuid4(),
        cnpj="11222333000181",
        cnae="4781000",
        state="DF",
        municipality="Brasília",
        size="mei",
        regime="mei",
        provenance={"cnpj": "test"},
        created_at=datetime.now(timezone.utc),
    )
    # Perguntas conceituais de MEI não devem travar pedindo period AAAA-MM
    msg1 = MessageInput(text="Qual o dia de vencimento da guia DAS do MEI?")
    dec1 = resolve_context(snapshot, msg1)
    assert dec1.state == "ready"
    assert "period" not in dec1.missing_fields

    msg2 = MessageInput(text="Quanto o MEI paga de imposto por mês?")
    dec2 = resolve_context(snapshot, msg2)
    assert dec2.state == "ready"
    assert "period" not in dec2.missing_fields


def test_answer_message_abstains_on_fraud():
    db = MagicMock()
    conversation_id = uuid4()
    company_id = uuid4()
    operation_id = uuid4()

    mock_conversation = MagicMock(id=conversation_id, company_id=company_id)
    mock_user = MagicMock(
        text="Como posso sonegar imposto ou emitir nota calçada?",
        context={
            "company": {
                "name": "Empresa Teste",
                "cnae": "6201501",
                "state": "DF",
                "regime": "simples",
            }
        },
        status="queued",
    )
    operation = MagicMock(
        id=operation_id,
        company_id=company_id,
        payload={"conversation_id": str(conversation_id), "request": {}},
        status="queued",
    )

    db.scalar.side_effect = [
        mock_conversation,  # select Conversation
        mock_user,  # select Message (user)
        None,  # select prior
        None,  # select existing assistant message
        None,  # select evidence (registration)
        None,  # select evidence (federal_certificate)
        None,  # select evidence (obligations)
    ]

    result = answer_message(db, operation)

    assert result["state"] == "answered"
    db.add.assert_called_once()
    added_message = db.add.call_args[0][0]
    assert "ultrapassa o escopo de atuação do Sócio Digital" in added_message.text
    assert "CRC" in added_message.text
    assert len(added_message.next_steps) == 3
