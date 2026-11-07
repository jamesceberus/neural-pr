"""Deterministic metrics; preserve raw text separately from normalized scoring text."""
import re
import unicodedata

def words(text):
    text=unicodedata.normalize('NFKC',text).casefold().replace('’',"'")
    return re.findall(r"[^\W_]+(?:'[^\W_]+)*",text,re.UNICODE)

def edits(reference,hypothesis):
    """Levenshtein distance with deterministic S/D/I backtrace, including empty speech."""
    ref=words(reference);hyp=words(hypothesis)
    previous=[(j,0,0,j) for j in range(len(hyp)+1)]
    for i,left in enumerate(ref,1):
        current=[(i,0,i,0)]
        for j,right in enumerate(hyp,1):
            if left==right:current.append(previous[j-1]);continue
            substitution=previous[j-1];deletion=previous[j];insertion=current[j-1]
            options=[(substitution[0]+1,substitution[1]+1,substitution[2],substitution[3]),
                     (deletion[0]+1,deletion[1],deletion[2]+1,deletion[3]),
                     (insertion[0]+1,insertion[1],insertion[2],insertion[3]+1)]
            current.append(min(options,key=lambda x:x[0]))
        previous=current
    distance,substitutions,deletions,insertions=previous[-1]
    return {'edits':distance,'substitutions':substitutions,'deletions':deletions,'insertions':insertions,
            'reference_words':len(ref),'wer':distance/len(ref) if ref else None}

def score(manifest,predictions):
    ids={row['id'] for row in manifest}
    if len(ids)!=len(manifest) or set(predictions)!=ids:raise ValueError('Predictions must cover the complete manifest exactly once')
    result={'recordings':len(manifest),'errors':[],'speech':{'recordings':0,'scored':0,'edits':0,'reference_words':0,'empty_ids':[]},
            'nonspeech':{'recordings':0,'scored':0,'lexical_output_ids':[],'weak_label_lexical_output_ids':[],
                         'strong_label_lexical_output_ids':[]},'per_recording':{}}
    for item in manifest:
        prediction=predictions[item['id']]
        group=result['speech' if item['kind']=='speech' else 'nonspeech'];group['recordings']+=1
        if prediction['status']!='ok':
            result['errors'].append({'id':item['id'],'status':prediction['status'],'error':prediction.get('error')})
            result['per_recording'][item['id']]={'status':prediction['status']};continue
        group['scored']+=1;text=prediction['text']
        if item['kind']=='speech':
            measures=edits(item['reference_text'],text)
            group['edits']+=measures['edits'];group['reference_words']+=measures['reference_words']
            if not words(text):group['empty_ids'].append(item['id'])
        else:
            lexical=bool(words(text));measures={'lexical_output':lexical,'label_review_required':item.get('review_required',True)}
            if lexical:
                group['lexical_output_ids'].append(item['id'])
                group['weak_label_lexical_output_ids' if item.get('review_required',True) else 'strong_label_lexical_output_ids'].append(item['id'])
        result['per_recording'][item['id']]={'status':'ok',**measures}
    speech=result['speech']
    speech['wer']=speech['edits']/speech['reference_words'] if speech['reference_words'] else None
    speech['wer_complete']=speech['scored']==speech['recordings']
    result['complete']=not result['errors']
    return result

def compare(manifest,baseline,candidate):
    before=score(manifest,baseline);after=score(manifest,candidate)
    newly_empty=[item['id'] for item in manifest if item['kind']=='speech' and baseline[item['id']]['status']=='ok'
                 and candidate[item['id']]['status']=='ok' and words(baseline[item['id']]['text']) and not words(candidate[item['id']]['text'])]
    wer_delta=after['speech']['wer']-before['speech']['wer'] if after['speech']['wer'] is not None and before['speech']['wer'] is not None else None
    fewer=len(after['nonspeech']['lexical_output_ids'])<len(before['nonspeech']['lexical_output_ids'])
    return {'baseline':before,'candidate':after,'newly_empty_speech_ids':newly_empty,'speech_wer_delta':wer_delta,
            'gate_pass':bool(before['complete'] and after['complete'] and fewer and not newly_empty and wer_delta is not None and wer_delta<=0.01+1e-12),
            'gate_scope':'Supplied-label pilot: weak non-speech labels remain unverified, not confirmed hallucinations.'}
