from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import PointLedger


DEFAULT_ASSIGNMENT_POINT_RULE = {
    "enabled": True,
    "points_per_score": 1,
    "max_points": None,
}


def normalize_assignment_point_rule(rule_json: dict | None) -> dict:
    if rule_json is None:
        return DEFAULT_ASSIGNMENT_POINT_RULE.copy()
    enabled = bool(rule_json.get("enabled", DEFAULT_ASSIGNMENT_POINT_RULE["enabled"]))
    points_per_score = int(rule_json.get("points_per_score", DEFAULT_ASSIGNMENT_POINT_RULE["points_per_score"]))
    max_points = rule_json.get("max_points", DEFAULT_ASSIGNMENT_POINT_RULE["max_points"])
    if max_points is not None:
        max_points = int(max_points)
    return {
        "enabled": enabled,
        "points_per_score": points_per_score,
        "max_points": max_points,
    }


def points_for_assignment_score(score: int, rule: dict) -> int:
    if not rule["enabled"]:
        return 0
    points = score * rule["points_per_score"]
    max_points = rule.get("max_points")
    if max_points is not None:
        points = min(points, max_points)
    return points


def assignment_grade_point_total(db: Session, submission_id: int) -> int:
    total = db.scalar(
        select(func.coalesce(func.sum(PointLedger.delta), 0)).where(
            PointLedger.submission_id == submission_id,
            PointLedger.reason == "assignment_grade",
        )
    )
    return int(total or 0)
