def write_plots(snapshot, summary, output):
    import os

    os.environ.setdefault("MPLCONFIGDIR", str(output / ".matplotlib"))
    import matplotlib

    matplotlib.use("Agg")
    from collections import defaultdict

    import matplotlib.pyplot as plt

    paths = []
    values = {}
    for metric in ["rouge_l", "bert_score"]:
        grouped = defaultdict(list)
        for row in snapshot.results:
            score = getattr(row, metric)
            if row.case.expected_behavior == "answer" and score.state == "success":
                grouped[row.case.id].append(score.f1)
        values[metric] = {key: sum(v) / len(v) for key, v in grouped.items()}
        if len(grouped) >= 2:
            fig, ax = plt.subplots()
            ax.hist(list(values[metric].values()), bins=min(10, len(grouped)))
            ax.set(
                xlabel=f"{metric} F1", ylabel="Perguntas", title="Distribuição por pergunta única"
            )
            path = output / f"{metric}_distribution.png"
            fig.savefig(path, bbox_inches="tight")
            plt.close(fig)
            paths.append(path)
    paired = sorted(values["rouge_l"].keys() & values["bert_score"].keys())
    if len(paired) >= 2:
        fig, ax = plt.subplots()
        ax.scatter(
            [values["rouge_l"][k] for k in paired], [values["bert_score"][k] for k in paired]
        )
        ax.set(xlabel="ROUGE-L F1", ylabel="BERTScore F1")
        path = output / "metrics_scatter.png"
        fig.savefig(path, bbox_inches="tight")
        plt.close(fig)
        paths.append(path)
    categories = [
        (key, value)
        for key, value in summary["categories"].items()
        if value["metrics"]["rouge_l"]["mean"] is not None
    ]
    if len(categories) >= 2:
        fig, ax = plt.subplots()
        ax.bar([k for k, v in categories], [v["metrics"]["rouge_l"]["mean"] for k, v in categories])
        ax.tick_params(axis="x", rotation=25)
        ax.set_ylabel("ROUGE-L F1 médio por pergunta")
        path = output / "categories.png"
        fig.savefig(path, bbox_inches="tight")
        plt.close(fig)
        paths.append(path)
    return paths
