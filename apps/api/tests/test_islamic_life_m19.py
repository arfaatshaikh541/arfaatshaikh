import pytest
from app.services.islamic_life import *
from app.models.islamic_life import *
H='a'*64

def test_manifest_deterministic():
 a=compute_time_profile_manifest(profile_slug='dubai',method_code='published',authority_ids=['b','a'],parameter_sha256=['b'*64,H])
 b=compute_time_profile_manifest(profile_slug='dubai',method_code='published',authority_ids=['a','b'],parameter_sha256=[H,'b'*64])
 assert a==b and len(a)==64

def test_manifest_rejects_bad_hash():
 with pytest.raises(ValueError):compute_time_profile_manifest(profile_slug='x',method_code='y',authority_ids=['a'],parameter_sha256=['bad'])

def test_prayer_time_passes():
 assert evaluate_prayer_time_governance(verified_authorities=1,jurisdictions=1,calculation_method_published=True,high_latitude_rule_defined=True,location_precision_meters=1000,astronomical_validation_percent=99,manual_override_audited=True,manifest_sha256=H)['allowed']
@pytest.mark.parametrize('field,code',[
 ('verified_authorities','verified_time_authority_required'),('jurisdictions','time_jurisdiction_required'),('calculation_method_published','published_calculation_method_required'),('high_latitude_rule_defined','high_latitude_rule_required'),('location_precision_meters','location_precision_above_limit'),('astronomical_validation_percent','astronomical_validation_below_threshold'),('manual_override_audited','audited_manual_override_required'),('manifest_sha256','valid_time_profile_manifest_required')])
def test_prayer_time_failures(field,code):
 d=dict(verified_authorities=1,jurisdictions=1,calculation_method_published=True,high_latitude_rule_defined=True,location_precision_meters=1000,astronomical_validation_percent=99,manual_override_audited=True,manifest_sha256=H)
 d[field]={'verified_authorities':0,'jurisdictions':0,'calculation_method_published':False,'high_latitude_rule_defined':False,'location_precision_meters':1001,'astronomical_validation_percent':98,'manual_override_audited':False,'manifest_sha256':'bad'}[field]
 assert code in evaluate_prayer_time_governance(**d)['reason_codes']

def test_hijri_passes_and_discloses_disagreement():
 assert evaluate_hijri_calendar_release(authority_verified=True,observation_method_published=True,calculation_fallback_disclosed=True,jurisdiction_scope_defined=True,disagreement_disclosed=True,release_notice_hours=72,evidence_sha256=H)['allowed']
 assert 'calendar_disagreement_disclosure_required' in evaluate_hijri_calendar_release(authority_verified=True,observation_method_published=True,calculation_fallback_disclosed=True,jurisdiction_scope_defined=True,disagreement_disclosed=False,release_notice_hours=72,evidence_sha256=H)['reason_codes']

def test_halal_standard_passes():
 assert evaluate_halal_standard(scholarly_board_members=3,independent_labs=1,ingredient_traceability_percent=98,supply_chain_audited=True,cross_contamination_controls=True,recall_process=True,public_standard=True)['allowed']

def test_halal_standard_blocks_weak_traceability():
 assert 'ingredient_traceability_below_threshold' in evaluate_halal_standard(scholarly_board_members=3,independent_labs=1,ingredient_traceability_percent=97,supply_chain_audited=True,cross_contamination_controls=True,recall_process=True,public_standard=True)['reason_codes']

def test_halal_certification_passes():
 assert evaluate_halal_certification(certifier_verified=True,facility_audited=True,product_scope_defined=True,certificate_sha256=H,expires_days=730,revocation_registry=True,critical_findings=0)['allowed']

def test_halal_certification_blocks_critical_findings():
 assert 'unresolved_halal_critical_findings' in evaluate_halal_certification(certifier_verified=True,facility_audited=True,product_scope_defined=True,certificate_sha256=H,expires_days=730,revocation_registry=True,critical_findings=1)['reason_codes']

def test_ethical_commerce_passes():
 assert evaluate_ethical_commerce(price_transparency=True,terms_plain_language=True,no_deceptive_marketing=True,labour_due_diligence=True,environmental_claims_verified=True,complaints_channel=True,traceability_percent=90)['allowed']

def test_ethical_commerce_blocks_deception():
 assert 'deceptive_marketing_detected' in evaluate_ethical_commerce(price_transparency=True,terms_plain_language=True,no_deceptive_marketing=False,labour_due_diligence=True,environmental_claims_verified=True,complaints_channel=True,traceability_percent=90)['reason_codes']

def test_finance_passes():
 assert evaluate_islamic_finance_product(shariah_board_members=3,independent_reviewers=1,contract_structure_disclosed=True,fees_fully_disclosed=True,asset_or_service_linked=True,late_payment_treatment_disclosed=True,annual_shariah_audit=True,critical_findings=0)['allowed']

def test_finance_requires_asset_or_service():
 assert 'underlying_asset_or_service_required' in evaluate_islamic_finance_product(shariah_board_members=3,independent_reviewers=1,contract_structure_disclosed=True,fees_fully_disclosed=True,asset_or_service_linked=False,late_payment_treatment_disclosed=True,annual_shariah_audit=True,critical_findings=0)['reason_codes']

def test_family_service_passes():
 assert evaluate_family_service(qualified_practitioners=1,safeguarding_policy=True,privacy_controls=True,informed_consent=True,domestic_abuse_escalation=True,child_protection_path=True,legal_scope_disclosed=True,scholarly_scope_disclosed=True)['allowed']

def test_family_service_requires_abuse_escalation():
 assert 'domestic_abuse_escalation_required' in evaluate_family_service(qualified_practitioners=1,safeguarding_policy=True,privacy_controls=True,informed_consent=True,domestic_abuse_escalation=False,child_protection_path=True,legal_scope_disclosed=True,scholarly_scope_disclosed=True)['reason_codes']

def test_heritage_passes():
 assert evaluate_heritage_stewardship(ownership_verified=True,significance_documented=True,conservation_plan=True,digital_twin_or_archive=True,community_consultation=True,conflict_risk_assessed=True,public_access_policy=True,evidence_sha256=H)['allowed']

def test_heritage_requires_digital_preservation():
 assert 'heritage_digital_preservation_required' in evaluate_heritage_stewardship(ownership_verified=True,significance_documented=True,conservation_plan=True,digital_twin_or_archive=False,community_consultation=True,conflict_risk_assessed=True,public_access_policy=True,evidence_sha256=H)['reason_codes']

def test_acceptance_fails_on_control():
 r=evaluate_islamic_life_acceptance(timekeeping_passed=False,calendar_passed=True,halal_passed=True,commerce_passed=True,finance_passed=True,family_passed=True,heritage_passed=True,live_authority_validation=True,external_shariah_audit=True,live_traceability_exercise=True)
 assert r['outcome']=='failed' and not r['portable_ready']

def test_acceptance_portable_only():
 r=evaluate_islamic_life_acceptance(timekeeping_passed=True,calendar_passed=True,halal_passed=True,commerce_passed=True,finance_passed=True,family_passed=True,heritage_passed=True,live_authority_validation=False,external_shariah_audit=False,live_traceability_exercise=False)
 assert r['outcome']=='conditional' and r['portable_ready'] and not r['production_ready']

def test_acceptance_production():
 r=evaluate_islamic_life_acceptance(timekeeping_passed=True,calendar_passed=True,halal_passed=True,commerce_passed=True,finance_passed=True,family_passed=True,heritage_passed=True,live_authority_validation=True,external_shariah_audit=True,live_traceability_exercise=True)
 assert r['allowed'] and r['production_ready']

def test_policy_version_stable():assert POLICY_VERSION=='trusted-islamic-life-v1'

def test_all_models_have_tables():
 classes=[PrayerTimeAuthority,PrayerCalculationProfile,PrayerTimeVerification,HijriCalendarAuthority,HalalStandard,HalalCertificationRecord,ProductTraceabilityRecord,EthicalCommerceReview,IslamicFinanceProduct,ShariahBoardReview,ContractDisclosure,CharityFinanceReconciliation,FamilyServiceProgramme,FamilyCaseSafeguard,HeritageSiteRecord,TrustedIslamicLifeAcceptance]
 assert all(getattr(c,'__tablename__',None) for c in classes)

def test_acceptance_table_name():assert TrustedIslamicLifeAcceptance.__tablename__=='trusted_islamic_life_acceptance'
