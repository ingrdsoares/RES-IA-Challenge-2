import re
import unicodedata
from rouge_score.rouge_scorer import RougeScorer
from evaluation.schemas import MetricScore


class UnicodeTokenizer:
    def tokenize(self, text):
        return re.findall(r'[^\W_]+', unicodedata.normalize('NFC',text).casefold(),flags=re.UNICODE)


class RougeMetric:
    def __init__(self):
        self.scorer = RougeScorer(['rougeL'],use_stemmer=False,tokenizer=UnicodeTokenizer())

    def score(self, reference, candidate):
        score = self.scorer.score(reference,candidate)['rougeL']
        return MetricScore(precision=score.precision,recall=score.recall,f1=score.fmeasure,state='success')
