from datetime import datetime, timedelta


class TATAgent:
    """Calculates delivery commitment dates based on classification."""

    TAT_MAP = {
        "HOT": 2,
        "WARM": 24,
        "COLD": 48,
    }

    def compute(self, classification: str) -> dict:
        hours = self.TAT_MAP.get(classification.upper(), 24)
        deadline = datetime.now() + timedelta(hours=hours)
        return {
            "tat_hours": hours,
            "tat_label": f"{hours} Hours",
            "deadline_dt": deadline,
            "deadline_str": deadline.strftime("%d-%b-%Y %I:%M %p"),
        }
