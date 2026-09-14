from __future__ import annotations
import hashlib, json, secrets
from dataclasses import dataclass

PUBLISH_ORDER=('draft','author_review','islamic_review','editorial_review','approved','published','archived','superseded')
CERTIFICATE_DISCLAIMER='This certificate confirms completion of a World of Islam platform course. It is not an ijazah, scholarly qualification, or authority to issue religious rulings.'

class LearningPolicyError(ValueError): pass

def transition_content(current:str,target:str)->str:
    if current not in PUBLISH_ORDER or target not in PUBLISH_ORDER: raise LearningPolicyError('unknown publication state')
    if target in ('archived','superseded') and current=='published': return target
    if PUBLISH_ORDER.index(target)!=PUBLISH_ORDER.index(current)+1: raise LearningPolicyError('invalid publication transition')
    return target

def validate_publication(*, evidence_ids:list[str], reviews:dict[str,str], author_id:str, reviewer_ids:dict[str,str], translation_structure_hash:str|None=None, canonical_structure_hash:str|None=None, translation_evidence_hash:str|None=None, canonical_evidence_hash:str|None=None)->None:
    if not evidence_ids or any(not x for x in evidence_ids): raise LearningPolicyError('governed evidence is required')
    for required in ('islamic','editorial','publisher'):
        if reviews.get(required)!='approved': raise LearningPolicyError(f'{required} review is required')
        if reviewer_ids.get(required)==author_id: raise LearningPolicyError('author cannot self-approve required review')
    if translation_structure_hash is not None and translation_structure_hash!=canonical_structure_hash: raise LearningPolicyError('translation changed lesson structure')
    if translation_evidence_hash is not None and translation_evidence_hash!=canonical_evidence_hash: raise LearningPolicyError('translation changed evidence mapping')

def grade_objective(*, correct_option_ids:set[str], selected_option_ids:set[str], points:int=1)->int:
    return points if correct_option_ids==selected_option_ids else 0

def calculate_score(earned:int,possible:int)->int:
    if possible<=0: raise LearningPolicyError('possible score must be positive')
    return round(earned*100/possible)

def select_recorded_score(scores:list[int],policy:str)->int:
    if not scores: raise LearningPolicyError('at least one score is required')
    if policy=='highest': return max(scores)
    if policy=='latest': return scores[-1]
    if policy=='first': return scores[0]
    if policy=='average': return round(sum(scores)/len(scores))
    raise LearningPolicyError('unsupported scoring policy')

def completion_percent(completed_required:int,total_required:int)->int:
    if total_required<=0: return 0
    return min(100,round(completed_required*100/total_required))

def issue_certificate_code()->str: return secrets.token_urlsafe(24)

def validate_certificate_eligibility(*,course_complete:bool,assessment_passed:bool)->None:
    if not course_complete or not assessment_passed: raise LearningPolicyError('completion requirements are not satisfied')

def deterministic_recommendations(candidates:list[dict],preferred_language:str,completed_course_ids:set[str])->list[dict]:
    ranked=[]
    for c in candidates:
        if c['id'] in completed_course_ids: continue
        score=50 + (20 if preferred_language in c.get('languages',[]) else 0) + min(20,int(c.get('prerequisite_match',0)))
        ranked.append({**c,'recommendation_score':score,'reason_code':'language_and_prerequisite_fit'})
    return sorted(ranked,key=lambda x:(-x['recommendation_score'],x['id']))

def validate_child_defaults(*,public_profile:bool,discussion_enabled:bool,certificate_public:bool)->None:
    if public_profile or discussion_enabled or certificate_public: raise LearningPolicyError('child privacy defaults must remain restrictive')

def content_fingerprint(payload:dict)->str:
    return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
