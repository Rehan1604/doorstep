"""Hand-written missions used when the model is unavailable or misbehaves.
The app must stay useful with no model at all."""
from .schema import Mission, MissionRequest

_SAFETY = ["Stay on public paths and away from traffic.", "Tell someone where you're going if you're alone."]


def fallback_mission(req: MissionRequest) -> Mission:
    m = req.minutes
    if req.energy == "low":
        title, diff = "The Slow Look", "easy"
        steps = ["Walk until something makes you stop.", "Stand still for 90 seconds.",
                 "Name three different sounds you hear.", "Walk back the long way."]
    elif req.energy == "high":
        title, diff = "Pace and Notice", "moderate"
        steps = ["Walk briskly for the first third of your time.", "Find three different leaf shapes.",
                 "Pick a spot and sit for 2 minutes without your phone.", "Head home at an easy pace."]
    else:
        title, diff = "Three Things Outside", "easy"
        steps = ["Walk for half your time in one direction.", "Find three things you've never noticed before.",
                 "Pause somewhere quiet for 60 seconds.", "Return by a different route."]
    return Mission(
        title=title, duration_minutes=m, difficulty=diff,
        objective=f"Spend {m} minutes outside paying attention to {req.interest}.",
        steps=steps,
        why_it_matters="Attention is the point; the distance is not.",
        safety_notes=_SAFETY,
    )


def fallback_reflection(completed: bool, minutes: int) -> str:
    if completed:
        return f"You didn't need a perfect plan. You needed {minutes} minutes of paying attention, and you gave them."
    return "Not every day works out. You still stepped toward the door, and that counts."
