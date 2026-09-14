from pydantic import BaseModel, Field
class TransitionRequest(BaseModel): current:str; target:str
class PublicationValidationRequest(BaseModel):
    evidence_ids:list[str]=Field(min_length=1); reviews:dict[str,str]; author_id:str; reviewer_ids:dict[str,str]
class ScoreRequest(BaseModel): earned:int=Field(ge=0); possible:int=Field(gt=0)
class RecommendationCandidate(BaseModel): id:str; title:str; languages:list[str]=[]; prerequisite_match:int=0
class RecommendationRequest(BaseModel): candidates:list[RecommendationCandidate]; preferred_language:str='en'; completed_course_ids:list[str]=[]
class ChildDefaultsRequest(BaseModel): public_profile:bool=False; discussion_enabled:bool=False; certificate_public:bool=False
