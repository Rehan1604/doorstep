"""Hand-written missions used when the model is unavailable or misbehaves.
The app must stay useful with no model at all."""
from .schema import Mission, MissionRequest

_SAFETY = ["Stay on public paths and away from traffic.", "Tell someone where you're going if you're alone."]

_BANK = {
    "stillness": ("The Still Point", "easy", ["Walk until something makes you stop.", "Stand or sit still for 2 minutes.",
                  "Name three different sounds you hear.", "Notice one thing that moves.", "Walk back slowly."]),
    "movement": ("Pace and Notice", "moderate", ["Walk briskly for the first third of your time.",
                 "Find three different leaf shapes.", "Pick a spot and pause for 2 minutes without your phone.",
                 "Head home at an easy pace."]),
    "hunt": ("The Three-Sense Hunt", "easy", ["Find three different leaf shapes.", "Listen for two distinct sounds.",
            "Find one smell worth remembering.", "Return by a different route."]),
    "closeup": ("One Small Thing", "easy", ["Choose one small thing: a leaf, bark, a stone.",
               "Study it for 3 minutes without your phone.", "Notice five details you missed at first glance.",
               "Put it back where you found it."]),
    "together": ("Ask Outside", "easy", ["Walk together at an easy pace.", "Each of you asks one question about what you see.",
                 "Swap: each point out one thing the other hasn't noticed.", "Finish with one shared favourite."]),
    "detour": ("The Unfamiliar Turn", "easy", ["Walk your usual way until the first turn.", "Take a public path you've never taken.",
              "Notice what is new there.", "Come back the way you came."]),
}


def fallback_mission(req: MissionRequest, style: str | None = None) -> Mission:
    if style not in _BANK:
        style = "stillness" if req.energy == "low" else "movement" if req.energy == "high" else "hunt"
    title, diff, steps = _BANK[style]
    return Mission(
        title=title, duration_minutes=req.minutes, difficulty=diff,
        objective=f"Spend {req.minutes} minutes outside paying attention to {req.interest}.",
        steps=steps, why_it_matters="Attention is the point; the distance is not.", safety_notes=_SAFETY,
    )


def fallback_reflection(completed: bool, minutes: int) -> str:
    if completed:
        return f"You didn't need a perfect plan. You needed {minutes} minutes of paying attention, and you gave them."
    return "Not every day works out. You still stepped toward the door, and that counts."