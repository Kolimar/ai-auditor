DEFECT_CLASSES = ("scratch", "dent", "porosity", "misalignment", "contamination", "unknown")

DEFECT_PROMPT = (
    "Operators type short free-form remarks when they reject a part. "
    "Decide which of these defect classes the remark describes: " + ", ".join(DEFECT_CLASSES) + ". "
    "Output the class name and nothing else."
)

LOG_PARSE_PROMPT = """Each input line has the fixed layout
<ISO timestamp> <LINE> TEMP=<float> PRESS=<float> CYCLE=<int>
Return JSON with timestamp, line, temp, press and cycle."""

DISPOSITION_PROMPT = """Decide the disposition of a machined part from its measurements.
Spec limits come with the input. Rules:
 - every measurement inside its limits -> ACCEPT
 - bore_mm outside limits by less than 0.010 mm and flatness inside limits -> REWORK
 - any other deviation -> SCRAP
Answer with one word."""

COMPLIANCE_PROMPT = """Below is the full assembly SOP for the plant, followed by the operator's
description of what they did at their station. State whether the described actions follow the SOP
for that station and list any steps that were skipped or done out of order."""

NCR_TEMPLATE = (
    "You are drafting a non-conformance report (NCR).\n"
    "Part: {part}\nLot: {lot}\nDisposition: {disposition}\n"
    "Inspector remarks: {remarks}\n\n"
    "Write the narrative section: what was found, how it was detected, and the immediate containment "
    "action. Plain engineering language, no blame."
)

RCA_PROMPT = """You support a manufacturing quality engineer investigating a recurring failure.
Review the failure records and process parameters, form hypotheses for the root cause, test each
against the data, and rank them. Show your full reasoning; the engineer will review it in the 8D meeting."""

SPC_EXPLAIN_PROMPT = (
    "A shift supervisor with no statistics background is reading the numbers below, which were already "
    "computed by the SPC module. Explain in a short paragraph what they mean for the process and whether "
    "anyone should be worried. Do not recompute anything."
)

SOP_QA_PROMPT = "Answer the technician's question using only the SOP passages provided and cite the section numbers."
