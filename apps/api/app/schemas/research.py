from pydantic import BaseModel, Field
class PermissionCheckRequest(BaseModel): actual_role:str; required_role:str
class ResearchItemValidationRequest(BaseModel): item_type:str; item_id:str|None=None; external_url:str|None=None
class AnnotationValidationRequest(BaseModel): body:str=Field(min_length=1,max_length=20000); visibility:str='private'; eligible_as_evidence:bool=False
class CitationRenderRequest(BaseModel): title:str; source_label:str; locator:str; canonical_url:str|None=None; sequence:int=Field(ge=1)
