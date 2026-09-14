from pydantic import BaseModel, Field
class DiscussionValidationRequest(BaseModel):
    body:str=Field(min_length=1,max_length=30000)
    is_religious_claim:bool=False
    evidence_count:int=Field(default=0,ge=0,le=100)
    authoritative_claim:bool=False
class ReportValidationRequest(BaseModel):
    target_type:str
    category:str
    details:str=Field(default='',max_length=5000)
class ModerationDecisionRequest(BaseModel):
    action:str
    reason:str=Field(min_length=1,max_length=5000)
    policy_code:str=Field(min_length=1,max_length=80)
    moderator_is_author:bool=False
class ReputationRequest(BaseModel): event_type:str
