"""Prompt text for the hiring funnel."""

WEBHOOK_EXTRACT = (
    "Below is the raw body of a webhook delivered by our applicant tracking system. "
    "Pull out the candidate id, the candidate email, the stage name and the created_at "
    "timestamp, and give them back as a JSON object with exactly those four keys."
)

SCREEN_RULES = """You are the screening step of our hiring funnel.
Decide the next stage for the candidate below using ONLY these rules:
1. If years_experience is under 3, answer REJECT.
2. If country is not one of DE, ES, PT, NL, IE, answer REJECT.
3. If the skills list contains both "python" and "sql", answer ADVANCE.
4. Anything else is HOLD.
Reply with one word: ADVANCE, REJECT or HOLD."""

PANEL_BRIEF = (
    "Write a short briefing (max 120 words) for the interview panel about this candidate. "
    "Highlight what is distinctive about their background and anything worth probing. "
    "Source material is the candidate's CV text."
)

OFFER_ARITHMETIC = (
    "Work out the first-year cash compensation for this offer. Add the base salary, the "
    "signing bonus, the relocation allowance, and the annual bonus (base salary multiplied "
    "by the bonus percentage). Return only the final number."
)

DECLINE_STYLE = (
    "You write on behalf of a recruiter at a mid-sized software company. Compose a kind, "
    "personal note declining a candidate after the final round. Mention one concrete thing "
    "from their interview feedback that impressed the team and leave the door open."
)

COVER_LETTER_SCORE = (
    "Read the cover letter and rate how convincingly the writer connects their motivation "
    "to our mission, from 1 (generic) to 5 (specific and sincere). Reply with the digit only."
)

PLANNER_SYSTEM = (
    "You help hiring managers prepare interview loops. Given a role description and a "
    "candidate CV, propose six probing questions tailored to gaps and strengths you notice, "
    "and say what a strong answer would show."
)
