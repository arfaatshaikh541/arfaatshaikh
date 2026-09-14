from pydantic import BaseModel, Field
class ScholarProfileValidationRequest(BaseModel):
    verification_status:str
    may_issue_platform_rulings:bool=False
class ReviewAssignmentRequest(BaseModel):
    review_type:str
    author_user_id:str
    reviewer_user_id:str
    assigned_by_user_id:str
class ReviewValidationRequest(BaseModel):
    decision:str
    comments:str=Field(min_length=1,max_length=10000)
    evidence_checked:bool=False
    independent:bool=True
    review_type:str
class PublicationDecisionRequest(BaseModel):
    evidence_count:int=Field(ge=0)
    islamic_approvals:int=Field(ge=0)
    editorial_approvals:int=Field(ge=0)
    source_integrity_approvals:int=Field(ge=0)
    rejections:int=Field(ge=0)
    required_islamic_reviews:int=Field(default=2,ge=1,le=10)
    required_editorial_reviews:int=Field(default=1,ge=1,le=10)
class VersionCompareRequest(BaseModel):
    old_body:str
    new_body:str
    old_evidence_ids:list[str]=[]
    new_evidence_ids:list[str]=[]
