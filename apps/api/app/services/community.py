from __future__ import annotations
import re

class CommunityPolicyError(ValueError): pass
REPORT_CATEGORIES={'harassment','hate','spam','misinformation','unsafe_advice','sectarian_abuse','impersonation','privacy','other'}
MOD_ACTIONS={'approve','hide','remove','lock','warn','escalate','dismiss'}
DANGEROUS_PATTERNS=(r'\bkill\b',r'\battack\b',r'\bsuicide\b',r'\bself[- ]harm\b')
TAKFIR_PATTERNS=(r'\bkafir\b',r'\bkaafir\b',r'\bapostate\b',r'\bnot a muslim\b')


def validate_discussion_content(*,body:str,is_religious_claim:bool,evidence_count:int,authoritative_claim:bool=False)->dict:
    text=body.strip()
    if not text: raise CommunityPolicyError('discussion content is required')
    if len(text)>30000: raise CommunityPolicyError('discussion content is too long')
    lowered=text.lower()
    if any(re.search(p,lowered) for p in DANGEROUS_PATTERNS):
        raise CommunityPolicyError('dangerous or self-harm content requires safety escalation')
    if any(re.search(p,lowered) for p in TAKFIR_PATTERNS):
        raise CommunityPolicyError('takfir and declarations of apostasy are prohibited')
    if authoritative_claim:
        raise CommunityPolicyError('community reputation does not grant religious authority')
    if is_religious_claim and evidence_count<1:
        raise CommunityPolicyError('religious claims require governed evidence')
    return {'publishable':True,'requires_moderation':is_religious_claim}


def validate_report(*,target_type:str,category:str,details:str)->int:
    if target_type not in {'thread','post','profile'}: raise CommunityPolicyError('invalid report target')
    if category not in REPORT_CATEGORIES: raise CommunityPolicyError('invalid report category')
    if category in {'unsafe_advice','hate','sectarian_abuse','impersonation'}: return 90
    if category in {'harassment','misinformation','privacy'}: return 65
    return 30


def validate_moderation_decision(*,action:str,reason:str,policy_code:str,moderator_is_author:bool=False)->None:
    if action not in MOD_ACTIONS: raise CommunityPolicyError('invalid moderation action')
    if not reason.strip() or not policy_code.strip(): raise CommunityPolicyError('moderation reason and policy code are required')
    if moderator_is_author and action not in {'dismiss'}: raise CommunityPolicyError('authors cannot moderate their own content')


def reputation_points(*,event_type:str)->int:
    mapping={'evidence_accepted':3,'constructive_reply':1,'report_upheld':2,'content_removed':-5,'abuse_confirmed':-10}
    if event_type not in mapping: raise CommunityPolicyError('unsupported reputation event')
    return mapping[event_type]
