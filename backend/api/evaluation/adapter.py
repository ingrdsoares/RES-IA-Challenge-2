import hashlib
import subprocess
from typing import Protocol
from urllib.parse import urlsplit, urlunsplit
from app.config import Settings
from app.models import LocalModels, SYSTEM_PROMPT
from app.vector_store import VectorStore
from app.rag import RagService


class RagClient(Protocol):
    def query(self, question: str): ...
    def metadata(self) -> dict: ...
    def close(self) -> None: ...


class InternalRagClient:
    def __init__(self, settings=None):
        self.settings = settings or Settings()
        self.service = RagService(self.settings, VectorStore(self.settings), LocalModels(self.settings))

    def query(self, question):
        from app.schemas import QueryRequest
        return self.service.query(QueryRequest(question=question).question)

    def metadata(self):
        self.service.ready()
        config = self.settings.model_dump(mode='json')
        for key in ['qdrant_url','ollama_url']:
            url = urlsplit(config[key])
            config[key] = urlunsplit((url.scheme, url.hostname + (f':{url.port}' if url.port else ''), url.path,'',''))
        git = subprocess.run(['git','rev-parse','HEAD'],capture_output=True,text=True)
        collection = self.service.store.client.get_collection(self.settings.collection_name)
        models = self.service.models.client.list()
        return {'settings':config,'git_sha':git.stdout.strip() or 'unavailable','prompt_hash':hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest(),'collection':collection.config.model_dump(mode='json'),'points':self.service.store.count(),'models':[{'model':m.model,'digest':m.digest} for m in models.models]}

    def close(self):
        self.service.close()
