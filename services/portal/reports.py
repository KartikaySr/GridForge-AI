"""Immutable, scoped field observations; never production or dispatch authority."""

import psycopg
from fastapi import HTTPException

from services.portal.contracts import FieldReportReceipt, FieldReportWrite, PortalIdentity
from services.portal.service import PortalDenied


def receive_report(dsn: str, user: PortalIdentity, report: FieldReportWrite) -> FieldReportReceipt:
    with psycopg.connect(dsn) as conn:
        conn.execute("SELECT set_config('gridforge.portal_user',%s,true)", (str(user.id),))
        conn.execute("SET LOCAL ROLE gridforge_mobile_writer")
        conn.execute("SET LOCAL statement_timeout='2000ms'")
        if not conn.execute(
            "SELECT 1 FROM sync_edges e JOIN portal_memberships m "
            "ON m.org_id=e.org_id AND m.facility_id=e.facility_id "
            "WHERE e.edge_id=%s AND m.user_id=%s AND e.enabled",
            (report.edge_id, user.id),
        ).fetchone():
            raise PortalDenied("FACILITY_UNAVAILABLE")
        conn.execute(
            "INSERT INTO mobile_reports(user_id,request_id,edge_id,text) VALUES(%s,%s,%s,%s) "
            "ON CONFLICT DO NOTHING",
            (user.id, report.request_id, report.edge_id, report.text),
        )
        row = conn.execute(
            "SELECT edge_id,text,received_at FROM mobile_reports "
            "WHERE user_id=%s AND request_id=%s",
            (user.id, report.request_id),
        ).fetchone()
        if not row or row[:2] != (report.edge_id, report.text):
            raise HTTPException(409, "REPORT_CONFLICT")
        return FieldReportReceipt(request_id=report.request_id, received_at=row[2])
