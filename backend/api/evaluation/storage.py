import json
import sqlite3
from pathlib import Path
from uuid import uuid4
import portalocker
from evaluation.dataset import canonical_hash
from evaluation.schemas import RunManifest, AttemptResult, EvaluationSnapshot, ScoredAttempt


def make_manifest(selection, config, metadata):
    identity = {'selection': selection.model_dump(), 'config': config.model_dump(), 'metadata': metadata}
    return RunManifest(run_id=uuid4().hex, identity_hash=canonical_hash(identity), selection=selection, run_config=config, rag_metadata=metadata)


class RunStore:
    def __init__(self, path: Path):
        self.path = Path(path)

    def __enter__(self):
        self.path.mkdir(parents=True, exist_ok=True)
        self.lock = portalocker.Lock(str(self.path / '.lock'), timeout=0)
        self.lock.acquire()
        self.db = sqlite3.connect(self.path / 'checkpoints.sqlite3')
        self.db.executescript('CREATE TABLE IF NOT EXISTS manifest (id INTEGER PRIMARY KEY, data TEXT); CREATE TABLE IF NOT EXISTS attempts (case_id TEXT, repeat_index INTEGER, revision INTEGER, data TEXT, PRIMARY KEY(case_id,repeat_index,revision)); CREATE TABLE IF NOT EXISTS metrics (fingerprint TEXT, case_id TEXT, repeat_index INTEGER, revision INTEGER, data TEXT, PRIMARY KEY(fingerprint,case_id,repeat_index,revision)); CREATE TABLE IF NOT EXISTS metric_config (fingerprint TEXT PRIMARY KEY, data TEXT);')
        return self

    def __exit__(self, *args):
        self.db.close()
        self.lock.release()

    def initialize(self, manifest):
        row = self.db.execute('SELECT data FROM manifest WHERE id=1').fetchone()
        if row:
            if RunManifest.model_validate_json(row[0]).identity_hash != manifest.identity_hash:
                raise ValueError('Manifest incompatível; crie outra execução')
            return
        with self.db:
            self.db.execute('INSERT INTO manifest VALUES (1,?)', (manifest.model_dump_json(),))
            for case in manifest.selection.cases:
                for repeat in range(1, manifest.run_config.repeats + 1):
                    result=AttemptResult(case_id=case.id,repeat_index=repeat)
                    self.db.execute('INSERT INTO attempts VALUES (?,?,?,?)',(case.id,repeat,1,result.model_dump_json()))
        (self.path / 'manifest.json').write_text(manifest.model_dump_json(indent=2), encoding='utf-8')

    def manifest(self):
        row = self.db.execute('SELECT data FROM manifest WHERE id=1').fetchone()
        if not row:
            raise ValueError('Execução não inicializada')
        return RunManifest.model_validate_json(row[0])

    def attempts(self):
        rows = self.db.execute('SELECT a.data FROM attempts a JOIN (SELECT case_id,repeat_index,MAX(revision) AS revision FROM attempts GROUP BY case_id,repeat_index) b USING(case_id,repeat_index,revision)').fetchall()
        return [AttemptResult.model_validate_json(r[0]) for r in rows]

    def finish(self, result):
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO attempts VALUES (?,?,?,?)', (result.case_id, result.repeat_index, result.attempt_revision, result.model_dump_json()))

    def start(self, case_id, repeat_index):
        old = next(r for r in self.attempts() if (r.case_id,r.repeat_index)==(case_id,repeat_index))
        revision = old.attempt_revision + (old.state != 'planned')
        result = AttemptResult(case_id=case_id, repeat_index=repeat_index, attempt_revision=revision, state='running')
        self.finish(result)
        return result

    def mark_interrupted(self):
        for result in self.attempts():
            if result.state == 'running':
                self.finish(result.model_copy(update={'state':'uncertain', 'error_type':'InterruptedAttempt'}))

    def save_metric(self, fingerprint, result):
        a = result.attempt
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO metrics VALUES (?,?,?,?,?)', (fingerprint,a.case_id,a.repeat_index,a.attempt_revision,result.model_dump_json()))

    def read_metrics(self, fingerprint):
        active = {(a.case_id,a.repeat_index,a.attempt_revision):a for a in self.attempts()}
        rows = self.db.execute('SELECT data FROM metrics WHERE fingerprint=?', (fingerprint,)).fetchall()
        return [r for row in rows if (r:=ScoredAttempt.model_validate_json(row[0])) and active.get((r.attempt.case_id,r.attempt.repeat_index,r.attempt.attempt_revision)) == r.attempt]

    def snapshot(self, fingerprint=None):
        rows = self.db.execute('SELECT fingerprint,data FROM metric_config').fetchall()
        if fingerprint is None:
            if len(rows)!=1:
                raise ValueError('Informe --metric-fingerprint: execução sem métricas ou com múltiplas configurações')
            fingerprint = rows[0][0]
        matches = [json.loads(data) for fp,data in rows if fp==fingerprint]
        if not matches:
            raise ValueError('Configuração de métricas não encontrada')
        results = self.read_metrics(fingerprint)
        if len(results)!=len(self.attempts()):
            raise ValueError('Pontuação incompleta ou desatualizada; execute score novamente')
        return EvaluationSnapshot(manifest=self.manifest(), metric_fingerprint=fingerprint, metric_metadata=matches[0], results=results)
