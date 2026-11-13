"""Source/provenance structure validation for classical xiang corpus records.
This does not authenticate quotations or settle dating/interpretation."""
from collections.abc import Mapping, Sequence
from datetime import date
from urllib.parse import urlsplit
PERIODS={"pre_qin","qin_han","wei_jin_northern_southern","sui_tang","song_yuan","ming","qing_pre_1912","modern_post_1912","uncertain"}
SOURCES={"classical_text","historical_commentary","bibliographic_record","modern_scholarship","field_observation","research_hypothesis","synthetic_fixture","model_generated"}
METHOD_FAMILIES=["classification","analogical_argument","rhetorical_analogy","cosmological_correspondence","lexical_taxonomy","symbolic_correspondence","phenomenological_observation","causal_claim","commentarial_exegesis","comparative_exegesis"]
RELATION_FAMILIES={"generative","taxonomic","functional","directional","temporal","correlative","symbolic","normative_analogy","causal_assertion","rhetorical_analogy","lexical"}
CAUSAL_STATUSES={"not_claimed","textual_causal_assertion","observational_support","experimental_support","challenged","unassessed"}
REASONING_OPERATIONS={"observe","select_image","classify","compare","abstract_shared_basis","identify_difference","infer_by_analogy","shift_perspective","map_function","map_time","map_position","symbolize","rhetorical_indirection","transfer_norm","test_counterexample","intervene_condition","refuse_transfer"}
TAGS=["observation","image_selection","analogy_method","analogy_limit","classification","correspondence","yin_yang","state_change","cosmology","sensory_classification","causal_inference_limit","metaphor","name_reality","ritual_institution","natural_knowledge","commentarial_exegesis"]
CLAIMS={"textual_observation","traditional_interpretation","commentarial_interpretation","project_operational_definition","research_hypothesis","modern_scholarship_claim"}
def validate_record(r: Mapping) -> None:
    required=("record_id","record_version","work","period","source_type","witness","locator","text","text_status","claims","review_status","concept_tags","method_families")
    if not isinstance(r,Mapping) or any(k not in r for k in required): raise ValueError("missing required top-level fields")
    for k in ("record_id","record_version","text"):
        if not isinstance(r[k],str) or not r[k].strip(): raise ValueError(f"{k} must be non-empty")
    if not isinstance(r["period"],str) or r["period"] not in PERIODS or not isinstance(r["source_type"],str) or r["source_type"] not in SOURCES: raise ValueError("unknown period or source_type")
    tags=r["concept_tags"]
    if not isinstance(tags,list) or not tags or any(not isinstance(t,str) for t in tags) or len(tags)!=len(set(tags)) or any(t not in TAGS for t in tags): raise ValueError("concept_tags must be a non-empty unique list of known project facets")
    if not isinstance(r["review_status"],str) or r["review_status"] not in {"unreviewed","candidate","reviewed","disputed","rejected","superseded"}: raise ValueError("unknown review_status")
    methods=r["method_families"]
    if not isinstance(methods,list) or not methods or any(not isinstance(m,str) for m in methods) or len(methods)!=len(set(methods)) or any(m not in METHOD_FAMILIES for m in methods): raise ValueError("method_families must be a non-empty unique list of known inference families")
    w,src,loc=r["work"],r["witness"],r["locator"]
    if not isinstance(w,Mapping) or any(not isinstance(w.get(k),str) or not w[k].strip() for k in ("title","traditional_authority","composition_period","genre")): raise ValueError("incomplete work metadata")
    if not isinstance(src,Mapping) or any(not isinstance(src.get(k),str) or not src[k].strip() for k in ("witness_id","edition_or_database","url","access_date","witness_kind")): raise ValueError("incomplete witness metadata")
    if not isinstance(src["witness_kind"],str) or src["witness_kind"] not in {"critical_edition","printed_edition","facsimile","digital_transcription","catalogue","secondary_transcription","unknown"}: raise ValueError("unknown witness_kind")
    parsed_url=urlsplit(src["url"])
    if parsed_url.scheme not in {"http","https"} or not parsed_url.netloc: raise ValueError("witness url must be an absolute HTTP(S) URL")
    try: date.fromisoformat(src["access_date"])
    except ValueError as exc: raise ValueError("access_date must be an ISO date") from exc
    if not isinstance(loc,Mapping) or any(not isinstance(loc.get(k),str) or not loc[k].strip() for k in ("chapter","section_or_line")): raise ValueError("exact chapter and section locator required")
    if not isinstance(r["text_status"],str) or r["text_status"] not in {"verified_against_witness","transcribed_unverified","ocr_unverified","paraphrase","quotation_fragment"}: raise ValueError("unknown text_status")
    claims=r["claims"]
    if not isinstance(claims,Sequence) or isinstance(claims,(str,bytes)) or not claims: raise ValueError("at least one claim required")
    ids=[]
    for c in claims:
        if not isinstance(c,Mapping): raise ValueError("claim must be object")
        for k in ("claim_id","claim_kind","subject","predicate","object","interpretive_note","scope","review_status"):
            if not isinstance(c.get(k),str) or not c[k].strip(): raise ValueError(f"claim field {k} required")
        if not isinstance(c["claim_kind"],str) or c["claim_kind"] not in CLAIMS or not isinstance(c["review_status"],str) or c["review_status"] not in {"unreviewed","reviewed","disputed","rejected"}: raise ValueError("unknown claim kind/status")
        if "xiang_domain" in c and (not isinstance(c["xiang_domain"],str) or not c["xiang_domain"].strip()): raise ValueError("xiang_domain must be non-empty")
        if "relation_family" in c and (not isinstance(c["relation_family"],str) or c["relation_family"] not in RELATION_FAMILIES): raise ValueError("unknown relation_family")
        if "causal_status" in c and (not isinstance(c["causal_status"],str) or c["causal_status"] not in CAUSAL_STATUSES): raise ValueError("unknown causal_status")
        if "reasoning_operations" in c and (not isinstance(c["reasoning_operations"],list) or not c["reasoning_operations"] or any(not isinstance(op,str) for op in c["reasoning_operations"]) or len(c["reasoning_operations"])!=len(set(c["reasoning_operations"])) or any(op not in REASONING_OPERATIONS for op in c["reasoning_operations"])): raise ValueError("reasoning_operations must be a non-empty unique list of known operations")
        for field in ("shared_basis","non_shared_basis","scope_conditions"):
            if field in c and (not isinstance(c[field],list) or any(not isinstance(v,str) or not v.strip() for v in c[field])): raise ValueError(f"{field} must be a list of non-empty strings")
        ids.append(c["claim_id"])
    if len(ids)!=len(set(ids)): raise ValueError("duplicate claim_id")
    if r["source_type"]=="model_generated" and r["review_status"]=="reviewed": raise ValueError("model-generated content cannot self-certify as reviewed")
