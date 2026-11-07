"""Development evidence -> transferable policy candidate; never receives held-out material."""
import json
import uuid
from .state import canonical, digest, now
from .worker import InfrastructureError,parse_json_object,ACTION_PROTOCOL

class Improver:
    def __init__(self,state,store,model):self.state=state;self.store=store;self.model=model

    def incident(self,objective,commit,version,evidence,failure_class,uncertainty):
        fingerprint=digest({'objective':objective,'version':version,'class':failure_class,
                            'failed_checks':sorted(k for k,v in evidence.get('checks',{}).items() if not v.get('passed'))})
        existing=self.state.read('incidents/'+fingerprint)
        if existing:
            existing['occurrences']+=1
            self.state.write('incidents/'+fingerprint,existing)
            self.state.emit('incident_deduplicated',incident_id=fingerprint,occurrences=existing['occurrences'])
            return existing
        record={'id':fingerprint,'version':1,'attempted_objective':objective,'source_commit':commit,
                'agent_version':version,'evidence':evidence,'failure_class':failure_class,
                'known_uncertainty':uncertainty,'occurrences':1,'time':now()}
        self.state.write('incidents/'+fingerprint,record)
        self.state.emit('incident_created',incident_id=fingerprint,failure_class=failure_class)
        return record

    def propose(self,incident):
        candidate_id=uuid.uuid4().hex
        parent=self.store.active()
        previous=self.state.read('proposal_count',{'count':0})['count']
        if previous>=2:
            self.state.emit('proposal_disposition',incident_id=incident['id'],disposition='proposal_limit')
            return None
        # Reserve before calling the proposer so crash/restart cannot exceed the proposal budget.
        self.state.write('proposal_count',{'count':previous+1})
        record={'id':candidate_id,'parent':parent,'trigger_incident':incident['id'],'status':'proposed','time':now()}
        self.state.write('candidates/'+candidate_id,record)
        prompt='''Propose one small reusable procedure improvement based ONLY on development evidence.
Return JSON {"hypothesis":"...","scope":"...","skills":[...],"context_rules":[...]}.
Skills and context_rules replace the parent's lists. Change only skills/context_rules.
Do not include implementation code, task solutions, expected answers, evaluation tasks, or grader instructions.
If evidence does not support a useful change return {"disposition":"unsupported","reason":"..."}.
Do not approve yourself. A trusted controller will compare actual coding performance on fresh tasks.
'''
        try:
            raw,usage=self.model.complete([{'role':'system','content':prompt},
                {'role':'user','content':canonical({'incident':incident,'parent':self.store.get(parent)})}],max_tokens=2000,timeout=45)
            self.state.emit('proposer_call',candidate_id=candidate_id,usage=usage,model=self.model.model)
            self.state.write('traces/proposals/'+candidate_id,{'raw_content':raw,'usage':usage,'action_protocol':ACTION_PROTOCOL})
            proposed,normalization=parse_json_object(raw)
            record['response_format']=normalization
            if 'disposition' in proposed:
                record.update(status='rejected',disposition=proposed['disposition'],reason=str(proposed.get('reason',''))[:2000])
            else:
                record['status']='preflight';self.state.write('candidates/'+candidate_id,record)
                content=dict(self.store.get(parent)['content'],skills=proposed['skills'],context_rules=proposed['context_rules'])
                if content==self.store.get(parent)['content']:
                    record.update(status='rejected',disposition='redundant')
                else:
                    # Reject obvious solution-bearing packages. This is a heuristic; scope remains an integrity limitation.
                    joined=canonical([content['skills'],content['context_rules']])
                    if any(x in joined for x in ('```','def ', 'CREATE TABLE','UPDATE jobs','INSERT INTO')):
                        raise ValueError('Policy contains implementation text')
                    version=self.store.create(content,parent)
                    prior=[json.loads(p.read_text()) for p in (self.state.root/'candidates').glob('*.json')]
                    if any(p.get('version')==version for p in prior):
                        record.update(status='rejected',disposition='deduplicated')
                    else:
                        record.update(status='development_checked',version=version,hypothesis=proposed['hypothesis'],
                                      scope=proposed['scope'],diff=self.store.diff(parent,version),usage=usage)
        except InfrastructureError as exc:
            record.update(status='inconclusive',disposition='infrastructure_failure',reason=str(exc))
        except (ValueError,KeyError,TypeError) as exc:
            record.update(status='rejected',disposition='invalid_or_out_of_scope',reason=str(exc)[:1000])
        self.state.write('candidates/'+candidate_id,record)
        self.state.emit('candidate_disposition',candidate_id=candidate_id,status=record['status'],version=record.get('version'),disposition=record.get('disposition'))
        return record
