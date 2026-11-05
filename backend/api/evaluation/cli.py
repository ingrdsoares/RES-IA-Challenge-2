import argparse
import json
import logging
from pathlib import Path

from evaluation.config import resolve_config
from evaluation.dataset import canonical_hash, load_dataset, select_cases
from evaluation.storage import RunStore, make_manifest

logger = logging.getLogger(__name__)


def build_parser():
    parser = argparse.ArgumentParser(
        description="Avaliação do RAG: coleta, métricas e Excel independentes"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for command in [
        "validate",
        "template",
        "prepare-model",
        "collect",
        "score",
        "report",
        "run",
        "compare",
    ]:
        p = sub.add_parser(command)
        p.add_argument("--config", type=Path)
        if command in ["validate", "collect", "run"]:
            p.add_argument("--dataset", type=Path, required=True)
            group = p.add_mutually_exclusive_group()
            group.add_argument("--preset", choices=["pilot", "reference"])
            group.add_argument("--limit", type=int)
            group.add_argument("--all", dest="all_cases", action="store_true", default=None)
            p.add_argument("--split", choices=["development", "final"])
            p.add_argument("--repeats", type=int)
        if command in ["collect", "run"]:
            p.add_argument("--rag-version")
            p.add_argument("--corpus-version")
            p.add_argument("--resume", action="store_true")
            p.add_argument("--retry-failed", action="store_true")
            p.add_argument("--retry-uncertain", action="store_true")
        if command in ["collect", "score", "report", "run"]:
            p.add_argument("--run-dir", type=Path, required=True)
        if command in ["template", "compare"]:
            p.add_argument("--output", type=Path, required=True)
        if command == "compare":
            p.add_argument("--run-a", type=Path, required=True)
            p.add_argument("--run-b", type=Path, required=True)
        if command in ["score", "run", "prepare-model"]:
            for name in [
                "bert-model",
                "bert-revision",
                "bert-model-path",
                "device",
                "baseline-path",
            ]:
                p.add_argument("--" + name)
            p.add_argument("--bert-layers", type=int)
            p.add_argument("--bert-batch-size", type=int)
            p.add_argument("--idf", action=argparse.BooleanOptionalAction, default=None)
            p.add_argument("--rescale", action=argparse.BooleanOptionalAction, default=None)
            p.add_argument("--bert-overflow", dest="overflow", choices=["error", "truncate"])
            p.add_argument(
                "--allow-model-download", dest="allow_download", action="store_true", default=None
            )
            if command == "prepare-model":
                p.add_argument(
                    "--allow-download", dest="allow_download", action="store_true", default=None
                )
        if command in ["validate", "collect", "run", "report", "compare"]:
            p.add_argument("--seed", type=int)
        if command in ["report", "run", "compare"]:
            p.add_argument("--bootstrap", type=int)
            p.add_argument("--margin", type=float)
            p.add_argument("--metric-fingerprint")
            p.add_argument("--adjudications", type=Path)
            p.add_argument("--pilot-run", type=Path)
    return parser


def main(argv=None, client_factory=None, bert_factory=None):
    args = build_parser().parse_args(argv)
    values = vars(args)
    overrides = {}
    run_keys = ["repeats", "rag_version", "corpus_version"]
    selection_keys = ["preset", "limit", "all_cases", "split", "seed"]
    metric_keys = [
        "bert_model",
        "bert_revision",
        "bert_model_path",
        "bert_layers",
        "bert_batch_size",
        "device",
        "idf",
        "rescale",
        "baseline_path",
        "overflow",
        "allow_download",
    ]
    overrides["run"] = {k: values[k] for k in run_keys if values.get(k) is not None}
    overrides["run"]["selection"] = {
        k: values[k] for k in selection_keys if values.get(k) is not None
    }
    overrides["metrics"] = {k: values[k] for k in metric_keys if values.get(k) is not None}
    overrides["stats"] = {
        k: values[k] for k in ["bootstrap", "margin", "seed"] if values.get(k) is not None
    }
    try:
        config = resolve_config(args.config, overrides)
        if args.command == "template":
            from evaluation.reports.export import write_template

            print(json.dumps([str(p) for p in write_template(args.output)]))
            return 0
        if args.command == "prepare-model":
            from evaluation.metrics.bert import prepare_model

            print(json.dumps(prepare_model(config.metrics, config.metrics.allow_download)))
            return 0
        if args.command in ["validate", "collect", "run"]:
            selection = select_cases(load_dataset(args.dataset), config.run.selection)
            if args.command == "validate":
                print(selection.model_dump_json(indent=2))
                return 0
            if not config.run.rag_version.strip() or not config.run.corpus_version.strip():
                raise ValueError("Coleta exige --rag-version e --corpus-version")
            if (args.run_dir / "checkpoints.sqlite3").exists() and not args.resume:
                raise ValueError("Execução existente: use --resume ou outro diretório")
            if client_factory is None:
                from evaluation.adapter import InternalRagClient

                client_factory = InternalRagClient
            client = client_factory()
            try:
                manifest = make_manifest(selection, config.run, client.metadata())
                from evaluation.collect import collect_run

                with RunStore(args.run_dir) as store:
                    store.initialize(manifest)
                    print(
                        json.dumps(
                            collect_run(client, store, args.retry_failed, args.retry_uncertain)
                        )
                    )
            finally:
                client.close()
            if args.command == "collect":
                return 0
        if args.command in ["score", "run"]:
            from evaluation.metrics.engine import score_run

            with RunStore(args.run_dir) as store:
                result = score_run(
                    store,
                    config.metrics,
                    **({"bert_factory": bert_factory} if bert_factory else {}),
                )
                print(json.dumps(result))
            if args.command == "score":
                return 0
            fingerprint = result["metric_fingerprint"]
        else:
            fingerprint = values.get("metric_fingerprint")
        if args.command in ["report", "run", "compare"]:
            from evaluation.comparison import apply_adjudications, compare_runs
            from evaluation.reports.export import write_report
            from evaluation.statistics import summarize_run

            source = args.run_a if args.command == "compare" else args.run_dir
            with RunStore(source) as store:
                snapshot = store.snapshot(fingerprint)
            if values.get("adjudications"):
                snapshot = apply_adjudications(snapshot, json.loads(args.adjudications.read_text()))
            pilot = None
            pilot_identity = None
            if values.get("pilot_run"):
                with RunStore(args.pilot_run) as store:
                    pilot_snapshot = store.snapshot(snapshot.metric_fingerprint)
                pilot_identity = pilot_snapshot.manifest.run_id
                pilot = summarize_run(pilot_snapshot.manifest, pilot_snapshot.results, config.stats)
            summary = summarize_run(snapshot.manifest, snapshot.results, config.stats, pilot)
            summary["pilot_run_id"] = pilot_identity
            comparison = None
            if args.command == "compare":
                with RunStore(args.run_b) as store:
                    other = store.snapshot(snapshot.metric_fingerprint)
                comparison = compare_runs(snapshot, other, config.stats)
                output = args.output
            else:
                output = (
                    args.run_dir
                    / "reports"
                    / snapshot.metric_fingerprint
                    / canonical_hash(
                        {
                            "stats": config.stats.model_dump(),
                            "snapshot": snapshot.model_dump(mode="json"),
                            "pilot": pilot_identity,
                        }
                    )
                )
            # Lock the destination separately, since source snapshots are now immutable in memory.
            import portalocker

            output.mkdir(parents=True, exist_ok=True)
            with portalocker.Lock(str(output / ".report.lock"), timeout=0):
                print(
                    json.dumps(
                        [str(p) for p in write_report(snapshot, summary, output, comparison)]
                    )
                )
        return 0
    except (ValueError, OSError, KeyError) as exc:
        logger.error("%s", exc)
        return 2
    except Exception as exc:
        logger.error("Falha operacional: %s", type(exc).__name__)
        return 1
