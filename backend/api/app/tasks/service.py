from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import delete, select

from app.assistant.models import Message
from app.assistant.service import require_conversation
from app.companies.service import require_company
from app.jobs.models import Operation
from app.jobs.service import enqueue
from app.serialization import record
from app.tasks.models import Task, TaskEvent


def require_task(db, account_id, task_id, lock=False):
    query = select(Task).where(Task.id == task_id)
    task = db.scalar(query.with_for_update() if lock else query)
    if not task:
        raise HTTPException(404, "Tarefa não encontrada")
    require_company(db, account_id, task.company_id)
    return task


def create_task(db, company_id, account_id, data):
    require_company(db, account_id, company_id)
    title = data.title
    action_support = None
    if data.source_message_id:
        message = db.scalar(
            select(Message).where(Message.id == data.source_message_id).with_for_update()
        )
        if not message:
            raise HTTPException(404, "Mensagem não encontrada")
        conversation, _ = require_conversation(db, account_id, message.conversation_id)
        if conversation.company_id != company_id:
            raise HTTPException(404, "Mensagem não encontrada")
        if (
            message.role != "assistant"
            or data.source_step_index is None
            or data.source_step_index >= len(message.next_steps)
        ):
            raise HTTPException(422, "Passo de origem inválido")
        existing = db.scalar(
            select(Task).where(
                Task.source_message_id == message.id,
                Task.source_step_index == data.source_step_index,
            )
        )
        if existing:
            return existing
        title = message.next_steps[data.source_step_index]
        if message.actions and data.source_step_index < len(message.actions):
            action_support = message.actions[data.source_step_index]
    elif data.source_step_index is not None:
        raise HTTPException(422, "Passo exige mensagem de origem")
    if not title:
        raise HTTPException(422, "Informe título ou passo de origem")
    task = Task(
        company_id=company_id,
        action_support=action_support,
        **{**data.model_dump(), "title": title},
    )
    db.add(task)
    db.commit()
    return task


def complete_task(db, task, account_id, completed, key):
    operation = enqueue(
        db,
        "task.complete",
        account_id,
        task.company_id,
        key,
        {"task_id": str(task.id), "completed": completed},
    )
    if operation.status == "succeeded":
        return operation.result
    if task.completed != completed:
        task.completed = completed
        task.completed_at = datetime.now(UTC) if completed else None
        db.add(TaskEvent(task_id=task.id, completed=completed))
    db.flush()
    operation.status = "succeeded"
    operation.result = record(task)
    db.commit()
    return operation.result


def edit_task(db, task, data):
    for name, value in data.model_dump().items():
        setattr(task, name, value)
    db.commit()
    return task


def delete_task(db, task):
    db.execute(delete(TaskEvent).where(TaskEvent.task_id == task.id))
    # Os recibos de conclusão guardam uma cópia da tarefa.
    db.execute(
        delete(Operation).where(
            Operation.kind == "task.complete",
            Operation.company_id == task.company_id,
            Operation.payload["task_id"].as_string() == str(task.id),
        )
    )
    db.delete(task)
    db.commit()
