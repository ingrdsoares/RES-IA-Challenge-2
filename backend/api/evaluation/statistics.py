import math
from collections import defaultdict, Counter
import numpy as np


def summarize_values(values, config):
    x = np.asarray(values,dtype=float)
    if not np.isfinite(x).all():
        raise ValueError('Estatística exige valores finitos')
    result = dict(n=len(x),mean=None,median=None,sample_std=None,minimum=None,maximum=None,percentiles=None,ci95=None)
    if not len(x):
        return result
    result.update(mean=float(x.mean()),median=float(np.median(x)),minimum=float(x.min()),maximum=float(x.max()),percentiles=dict(zip(['p5','p25','p75','p95'],map(float,np.percentile(x,[5,25,75,95])))))
    if len(x)>1:
        result['sample_std']=float(x.std(ddof=1))
        rng=np.random.default_rng(config.seed)
        means=[]
        for offset in range(0,config.bootstrap,256):
            count=min(256,config.bootstrap-offset)
            means.extend(rng.choice(x,size=(count,len(x)),replace=True).mean(axis=1))
        result['ci95']=list(map(float,np.percentile(means,[2.5,97.5])))
        result['degenerate_ci']=result['sample_std']==0
    return result


def estimate_sample_size(sample_std, margin, available):
    if not math.isfinite(margin) or margin<=0:
        raise ValueError('Margem deve ser positiva e finita')
    if sample_std is None:
        return {'required':None,'operational_minimum':None,'available':available,'numerically_sufficient':None}
    raw=math.ceil((1.96*sample_std/margin)**2)
    return {'required':raw,'operational_minimum':max(2,raw),'available':available,'numerically_sufficient':available>=max(2,raw),'zero_observed_variance':sample_std==0}


def summarize_run(manifest, attempts, config, pilot_summary=None):
    def group(rows, category=None, behavior=None):
        if category is not None:
            pool=manifest.selection.available_by_category.get(category) or dict(Counter(c.expected_behavior for c in manifest.selection.cases if c.category==category))
        else:
            pool=manifest.selection.available
        available=pool.get(behavior,0) if behavior else sum(pool.values())
        output={'unique_questions':len({r.case.id for r in rows}),'attempts':len(rows),'operational_states':dict(Counter(r.attempt.state for r in rows)),'rag_states':dict(Counter(r.attempt.rag_status or 'none' for r in rows)), 'metrics':{},'variability':[]}
        for metric in ['rouge_l','bert_score']:
            by_id=defaultdict(list)
            for row in rows:
                score=getattr(row,metric)
                if score.state=='success' and score.f1 is not None:
                    by_id[row.case.id].append(score.f1)
            values=[float(np.mean(v)) for v in by_id.values()]
            stats=summarize_values(values,config)
            stats['scored_attempts']=sum(map(len,by_id.values()))
            stats['unscored_attempts']=len(rows)-stats['scored_attempts']
            stats['unscored_questions']=output['unique_questions']-len(by_id)
            stats['sample_size']=estimate_sample_size(stats['sample_std'],config.margin,available)
            output['metrics'][metric]=stats
            for case_id, repeats in by_id.items():
                output['variability'].append({'id':case_id,'metric':metric,'repeats_scored':len(repeats),'mean':float(np.mean(repeats)),'within_question_std':float(np.std(repeats,ddof=1)) if len(repeats)>1 else None})
        judged=[r for r in rows if r.judgment!='not_assessed']
        output['behavioral_review']={'reviewed':len(judged),'correct':sum(r.judgment=='correct' for r in judged),'unreviewed':len(rows)-len(judged)}
        return output
    summary={'method':'question-level percentile bootstrap','config':config.model_dump(),'total_questions':len(manifest.selection.cases),'planned_attempts':len(manifest.selection.cases)*manifest.run_config.repeats,'all':group(attempts),'primary':group([r for r in attempts if r.case.expected_behavior=='answer'],behavior='answer'),'categories':{},'behaviors':{},'sample_size_origin':'pilot' if manifest.run_config.selection.preset in [None,'pilot'] and manifest.run_config.selection.limit is None and not manifest.run_config.selection.all_cases else 'exploratory'}
    for category in sorted({r.case.category for r in attempts}):
        summary['categories'][category]=group([r for r in attempts if r.case.category==category],category=category)
    for behavior in ['answer','abstain','clarify']:
        summary['behaviors'][behavior]=group([r for r in attempts if r.case.expected_behavior==behavior],behavior=behavior)
    if pilot_summary:
        for metric in ['rouge_l','bert_score']:
            sd=pilot_summary['primary']['metrics'][metric]['sample_std']
            summary['primary']['metrics'][metric]['sample_size']=estimate_sample_size(sd,config.margin,manifest.selection.available.get('answer',0))
        summary['sample_size_origin']='external_pilot'
    return summary
