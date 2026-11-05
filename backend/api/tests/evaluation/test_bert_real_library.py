"""Library compatibility with tiny random weights; not a product-quality benchmark."""
import pytest


def test_bertscore_cpu_library_with_local_fixture(tmp_path):
    torch=pytest.importorskip('torch')
    pytest.importorskip('bert_score')
    from transformers import BertConfig,BertModel,BertTokenizer
    from evaluation.metrics.bert import BertMetric
    from evaluation.schemas import MetricConfig
    torch.manual_seed(42)
    model=BertModel(BertConfig(vocab_size=10,hidden_size=16,num_hidden_layers=2,num_attention_heads=2,intermediate_size=32))
    model.save_pretrained(tmp_path)
    (tmp_path/'vocab.txt').write_text('[PAD]\n[UNK]\n[CLS]\n[SEP]\n[MASK]\nação\nfiscal\ntexto\nde\nteste\n')
    BertTokenizer(vocab_file=str(tmp_path/'vocab.txt'),do_lower_case=False).save_pretrained(tmp_path)
    metric=BertMetric(MetricConfig(bert_model_path=str(tmp_path),bert_layers=2),['ação fiscal'])
    score=metric.score_pairs([('ação fiscal','ação fiscal')])[0]
    assert score.state=='success'
    assert score.f1==pytest.approx(1,abs=1e-5)
    assert metric.metadata()['resolved'] is True
