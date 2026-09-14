from __future__ import annotations
import hashlib, json, difflib

class ScholarlyPolicyError(ValueError): pass

REVIEW_TYPES={'islamic','editorial','source_integrity','translation'}
DECISIONS={'approve','changes_requested','reject','abstain'}

def fingerprint_text(text:str)->str:
    normalized=' '.join(text.split())
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()

def fingerprint_evidence(source_passage_ids:list[str])->str:
    payload=json.dumps(sorted(set(source_passage_ids)),separators=(',',':'))
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()

def validate_scholar_profile(*,verification_status:str,may_issue_platform_rulings:bool)->dict:
    if verification_status not in {'unverified','pending','verified','rejected','suspended'}:
        raise ScholarlyPolicyError('invalid scholar verification status')
    if may_issue_platform_rulings:
        raise ScholarlyPolicyError('profile verification does not grant authority to issue platform rulings')
    return {'valid':True,'religious_authority_granted':False}

def validate_review_assignment(*,review_type:str,author_user_id:str,reviewer_user_id:str,assigned_by_user_id:str)->None:
    if review_type not in REVIEW_TYPES: raise ScholarlyPolicyError('invalid review type')
    if author_user_id==reviewer_user_id: raise ScholarlyPolicyError('authors cannot independently review their own work')
    if reviewer_user_id==assigned_by_user_id and review_type=='islamic':
        raise ScholarlyPolicyError('islamic reviewers cannot self-assign')

def validate_review(*,decision:str,comments:str,evidence_checked:bool,independent:bool,review_type:str)->None:
    if decision not in DECISIONS: raise ScholarlyPolicyError('invalid review decision')
    if not comments.strip(): raise ScholarlyPolicyError('review comments are required')
    if not independent: raise ScholarlyPolicyError('required reviews must be independent')
    if review_type in {'islamic','source_integrity'} and not evidence_checked:
        raise ScholarlyPolicyError('religious and source-integrity reviews must check evidence')

def publication_decision(*,evidence_count:int,islamic_approvals:int,editorial_approvals:int,source_integrity_approvals:int,rejections:int,required_islamic_reviews:int=2,required_editorial_reviews:int=1)->dict:
    blockers=[]
    if evidence_count<1: blockers.append('governed evidence is required')
    if rejections>0: blockers.append('unresolved rejection exists')
    if islamic_approvals<required_islamic_reviews: blockers.append('insufficient independent Islamic reviews')
    if editorial_approvals<required_editorial_reviews: blockers.append('insufficient editorial reviews')
    if source_integrity_approvals<1: blockers.append('source-integrity approval is required')
    return {'publishable':not blockers,'blockers':blockers}

def compare_versions(*,old_body:str,new_body:str,old_evidence_ids:list[str],new_evidence_ids:list[str])->dict:
    diff=list(difflib.unified_diff(old_body.splitlines(),new_body.splitlines(),lineterm=''))
    old=set(old_evidence_ids); new=set(new_evidence_ids)
    return {'content_changed':fingerprint_text(old_body)!=fingerprint_text(new_body),'evidence_changed':fingerprint_evidence(old_evidence_ids)!=fingerprint_evidence(new_evidence_ids),'evidence_added':sorted(new-old),'evidence_removed':sorted(old-new),'diff':diff}
