from __future__ import annotations
import hashlib, json, re
from urllib.parse import urlparse

ALLOWED_ROLES={'viewer':0,'contributor':1,'editor':2,'owner':3}
ALLOWED_ITEM_TYPES={'source_passage','quran_ayah','hadith_narration','tafsir_entry','lesson','external_reference'}
class ResearchPolicyError(ValueError): pass

def require_workspace_role(actual_role:str, required_role:str)->None:
    if actual_role not in ALLOWED_ROLES or required_role not in ALLOWED_ROLES or ALLOWED_ROLES[actual_role] < ALLOWED_ROLES[required_role]:
        raise ResearchPolicyError('insufficient workspace permission')

def validate_research_item(*,item_type:str,item_id:str|None,external_url:str|None)->None:
    if item_type not in ALLOWED_ITEM_TYPES: raise ResearchPolicyError('unsupported research item type')
    if item_type=='external_reference':
        if not external_url: raise ResearchPolicyError('external reference URL is required')
        p=urlparse(external_url)
        if p.scheme!='https' or not p.hostname or p.username or p.password: raise ResearchPolicyError('external references require a safe HTTPS URL')
    elif not item_id: raise ResearchPolicyError('internal research items require an item id')

def validate_annotation(*,body:str,visibility:str,eligible_as_evidence:bool)->None:
    if not body.strip(): raise ResearchPolicyError('annotation body is required')
    if visibility not in {'private','workspace'}: raise ResearchPolicyError('invalid annotation visibility')
    if eligible_as_evidence: raise ResearchPolicyError('research annotations can never become Islamic evidence')

def canonical_citation_key(title:str,sequence:int)->str:
    stem=re.sub(r'[^a-z0-9]+','-',title.lower()).strip('-')[:48] or 'source'
    return f'{stem}-{sequence}'

def provenance_fingerprint(payload:dict)->str:
    return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def render_woi_citation(*,title:str,source_label:str,locator:str,canonical_url:str|None=None)->str:
    base=f'{source_label}, {locator}: {title}'
    return f'{base}. {canonical_url}' if canonical_url else base
