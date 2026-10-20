import json

import litellm

from settings import MID_MODEL, SMART_MODEL


def weekly_event_recap(events: list[dict], top_clips: list[str], tone: str = "hype") -> str:
    event_lines = "\n".join(f"- {e['date']}: {e['title']} ({e['participants']} players) {e['highlight']}" for e in events)
    clip_lines = "\n".join(top_clips)
    resp = litellm.completion(
        model=SMART_MODEL,
        messages=[
            {
                "role": "system",
                "content": f"You are the community manager for a team shooter. Write the Friday recap "
                f"post for the Discord. Tone: {tone}. Mention at least three events by name and "
                "end with a teaser for next week's tournament.",
            },
            {"role": "user", "content": f"Events this week:\n{event_lines}\n\nClips voted by players:\n{clip_lines}"},
        ],
        temperature=0.9,
    )
    return resp.choices[0].message.content


def suggest_team_comp(roster: list[dict], map_name: str, opponent_notes: str) -> str:
    resp = litellm.completion(
        model=SMART_MODEL,
        messages=[
            {
                "role": "user",
                "content": "Given our five-player roster and what we know about the opponent, "
                "recommend a hero/class composition and a pick order for the map. Explain why "
                "each pick counters their tendencies.\n\n"
                f"Roster: {json.dumps(roster)}\nMap: {map_name}\nOpponent notes: {opponent_notes}",
            }
        ],
    )
    return resp.choices[0].message.content


def reply_to_support_ticket(ticket_text: str, player_name: str, platform: str) -> str:
    resp = litellm.completion(
        model=MID_MODEL,
        messages=[
            {
                "role": "system",
                "content": "You are Rook, the friendly support rep for the studio. Answer the "
                "player's ticket helpfully. If it needs an account change or refund, say a human "
                "will follow up within two business days.",
            },
            {"role": "user", "content": f"Player: {player_name} ({platform})\n\n{ticket_text}"},
        ],
    )
    return resp.choices[0].message.content
