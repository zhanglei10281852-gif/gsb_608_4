from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from app.database import get_connection
from app.models import AffairCreate, AffairProcess, AffairStatus

router = APIRouter(prefix="/affairs", tags=["事务办理"])


@router.post("", status_code=201)
def create_affair(affair: AffairCreate):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM residents WHERE id = ?", (affair.applicant_id,))
    if not cursor.fetchone():
        raise HTTPException(status_code=404, detail="申请人不存在")

    cursor.execute(
        """INSERT INTO affairs (title, category, applicant_id, description)
           VALUES (?, ?, ?, ?)""",
        (affair.title, affair.category.value, affair.applicant_id, affair.description)
    )
    affair_id = cursor.lastrowid

    cursor.execute(
        """INSERT INTO affair_history (affair_id, from_status, to_status, handler, remark)
           VALUES (?, ?, ?, ?, ?)""",
        (affair_id, None, "待受理", "系统", "事务提交")
    )

    conn.commit()
    return {"id": affair_id, "message": "事务提交成功"}


@router.get("")
def list_affairs(
    status: Optional[AffairStatus] = None,
    category: Optional[str] = None,
    applicant_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100)
):
    conn = get_connection()
    conditions = []
    params = []
    if status:
        conditions.append("a.status = ?")
        params.append(status.value)
    if category:
        conditions.append("a.category = ?")
        params.append(category)
    if applicant_id:
        conditions.append("a.applicant_id = ?")
        params.append(applicant_id)

    where_clause = " WHERE " + " AND ".join(conditions) if conditions else ""

    count_sql = f"SELECT COUNT(*) as total FROM affairs a{where_clause}"
    cursor = conn.cursor()
    cursor.execute(count_sql, params)
    total = cursor.fetchone()["total"]

    offset = (page - 1) * size
    query_sql = f"""SELECT a.*, r.name as applicant_name
                    FROM affairs a
                    LEFT JOIN residents r ON a.applicant_id = r.id
                    {where_clause}
                    ORDER BY a.created_at DESC LIMIT ? OFFSET ?"""
    cursor.execute(query_sql, params + [size, offset])
    rows = cursor.fetchall()

    return {
        "total": total,
        "page": page,
        "size": size,
        "data": [dict(row) for row in rows]
    }


@router.get("/stats/summary")
def get_stats_summary():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT status, COUNT(*) as count FROM affairs GROUP BY status")
    status_counts = {row["status"]: row["count"] for row in cursor.fetchall()}

    cursor.execute("SELECT category, COUNT(*) as count FROM affairs GROUP BY category")
    category_counts = {row["category"]: row["count"] for row in cursor.fetchall()}

    cursor.execute("""
        SELECT AVG(
            (julianday(ah.completed_at) - julianday(a.created_at)) * 24 * 60
        ) as avg_minutes
        FROM affairs a
        JOIN (
            SELECT affair_id, MIN(created_at) as completed_at
            FROM affair_history
            WHERE to_status = '已办结'
            GROUP BY affair_id
        ) ah ON a.id = ah.affair_id
        WHERE a.status = '已办结'
    """)
    avg_row = cursor.fetchone()
    avg_minutes = avg_row["avg_minutes"] if avg_row["avg_minutes"] is not None else 0

    return {
        "total": sum(status_counts.values()),
        "by_status": {
            "待受理": status_counts.get("待受理", 0),
            "办理中": status_counts.get("办理中", 0),
            "已办结": status_counts.get("已办结", 0),
            "已退回": status_counts.get("已退回", 0)
        },
        "by_category": category_counts,
        "avg_completion_minutes": round(avg_minutes, 1)
    }


@router.get("/stats/overdue")
def get_overdue_affairs(days: int = Query(7, ge=1, le=365)):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT a.*, r.name as applicant_name,
               CAST((julianday('now', 'localtime') - julianday(a.created_at)) AS INTEGER) as days_elapsed
        FROM affairs a
        LEFT JOIN residents r ON a.applicant_id = r.id
        WHERE a.status IN ('待受理', '办理中', '已退回')
          AND julianday('now', 'localtime') - julianday(a.created_at) > ?
        ORDER BY a.created_at ASC
    """, (days,))
    rows = cursor.fetchall()

    return {
        "overdue_days_threshold": days,
        "count": len(rows),
        "data": [dict(row) for row in rows]
    }


@router.put("/{affair_id}/process")
def process_affair(affair_id: int, data: AffairProcess):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM affairs WHERE id = ?", (affair_id,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="事务不存在")

    current_status = row["status"]
    new_status = data.status.value

    valid_transitions = {
        "待受理": ["办理中", "已退回"],
        "办理中": ["已办结", "已退回"],
        "已退回": ["待受理"],
        "已办结": []
    }

    if new_status not in valid_transitions.get(current_status, []):
        raise HTTPException(
            status_code=400,
            detail=f"状态不允许从'{current_status}'转换到'{new_status}'"
        )

    remark_map = {
        "办理中": "开始受理",
        "已办结": "办理完成",
        "已退回": "退回补正",
        "待受理": "重新提交"
    }

    cursor.execute(
        """UPDATE affairs SET status = ?, handler = ?, result = ?,
           updated_at = datetime('now', 'localtime') WHERE id = ?""",
        (new_status, data.handler, data.result, affair_id)
    )

    cursor.execute(
        """INSERT INTO affair_history (affair_id, from_status, to_status, handler, remark)
           VALUES (?, ?, ?, ?, ?)""",
        (affair_id, current_status, new_status, data.handler, remark_map.get(new_status, data.result))
    )

    conn.commit()
    return {"message": "事务处理成功", "status": new_status}


@router.get("/{affair_id}/timeline")
def get_affair_timeline(affair_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM affairs WHERE id = ?", (affair_id,))
    if not cursor.fetchone():
        raise HTTPException(status_code=404, detail="事务不存在")

    cursor.execute(
        """SELECT id, from_status, to_status, handler, remark, created_at
           FROM affair_history
           WHERE affair_id = ?
           ORDER BY created_at ASC, id ASC""",
        (affair_id,)
    )
    rows = cursor.fetchall()

    return {
        "affair_id": affair_id,
        "timeline": [dict(row) for row in rows]
    }


@router.get("/{affair_id}")
def get_affair(affair_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT a.*, r.name as applicant_name, r.phone as applicant_phone
           FROM affairs a
           LEFT JOIN residents r ON a.applicant_id = r.id
           WHERE a.id = ?""",
        (affair_id,)
    )
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="事务不存在")
    return dict(row)
