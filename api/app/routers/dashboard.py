"""Dashboard router — stats, renewal alerts, and recent activity."""

from __future__ import annotations

import logging
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException

from app.lib.db_operations import run_query
from app.schemas.client import ActivityEntry, DashboardStats, RenewalAlert

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStats)
def get_stats() -> DashboardStats:
    """クライアント数、今月のログ数、更新アラート件数を返す。"""
    try:
        # Client count
        client_rows = run_query("MATCH (c:Client) RETURN count(c) AS cnt")
        client_count = client_rows[0]["cnt"] if client_rows else 0

        # Support logs this month
        today = date.today()
        month_start = today.replace(day=1).isoformat()
        log_rows = run_query(
            """
            MATCH (sl:SupportLog)
            WHERE sl.date >= $month_start
            RETURN count(sl) AS cnt
            """,
            {"month_start": month_start},
        )
        log_count = log_rows[0]["cnt"] if log_rows else 0

        # Renewal alerts (certificates expiring within 90 days)
        threshold = (today + timedelta(days=90)).isoformat()
        alert_rows = run_query(
            """
            MATCH (c:Client)-[:HAS_CERTIFICATE]->(cert:Certificate)
            WHERE cert.nextRenewalDate IS NOT NULL
              AND cert.nextRenewalDate <= $threshold
              AND cert.nextRenewalDate >= $today
            RETURN count(cert) AS cnt
            """,
            {"threshold": threshold, "today": today.isoformat()},
        )
        renewal_count = alert_rows[0]["cnt"] if alert_rows else 0

        return DashboardStats(
            client_count=client_count,
            log_count_this_month=log_count,
            renewal_alerts=renewal_count,
        )

    except Exception as exc:
        logger.error("get_stats failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/alerts", response_model=list[RenewalAlert])
def get_alerts() -> list[RenewalAlert]:
    """90日以内に更新期限を迎える証明書のアラートリストを返す。"""
    today = date.today()
    threshold = (today + timedelta(days=90)).isoformat()
    try:
        rows = run_query(
            """
            MATCH (c:Client)-[:HAS_CERTIFICATE]->(cert:Certificate)
            WHERE cert.nextRenewalDate IS NOT NULL
              AND cert.nextRenewalDate <= $threshold
              AND cert.nextRenewalDate >= $today
            RETURN c.name AS client_name,
                   cert.type AS certificate_type,
                   cert.nextRenewalDate AS next_renewal_date
            ORDER BY cert.nextRenewalDate ASC
            """,
            {"threshold": threshold, "today": today.isoformat()},
        )
        alerts: list[RenewalAlert] = []
        for row in rows:
            renewal_date = row.get("next_renewal_date", "")
            try:
                renewal_date_obj = date.fromisoformat(str(renewal_date))
                days_remaining = (renewal_date_obj - today).days
            except (ValueError, TypeError):
                days_remaining = 0
            alerts.append(
                RenewalAlert(
                    client_name=row.get("client_name", ""),
                    certificate_type=row.get("certificate_type", ""),
                    next_renewal_date=str(renewal_date),
                    days_remaining=days_remaining,
                )
            )
        return alerts

    except Exception as exc:
        logger.error("get_alerts failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/activity", response_model=list[ActivityEntry])
def get_activity(limit: int = 20) -> list[ActivityEntry]:
    """最近の監査ログを返す（デフォルト 20 件）。"""
    try:
        rows = run_query(
            """
            MATCH (a:AuditLog)-[:AUDIT_FOR]->(c:Client)
            RETURN a.createdAt AS date,
                   c.name AS client_name,
                   a.action AS action,
                   a.details AS summary
            ORDER BY a.createdAt DESC
            LIMIT $limit
            """,
            {"limit": limit},
        )
        activities: list[ActivityEntry] = []
        for row in rows:
            activities.append(
                ActivityEntry(
                    date=str(row.get("date", "")),
                    client_name=str(row.get("client_name", "")),
                    action=str(row.get("action", "")),
                    summary=str(row.get("summary", "")),
                )
            )
        return activities

    except Exception as exc:
        logger.error("get_activity failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
