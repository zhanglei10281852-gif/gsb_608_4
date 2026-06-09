from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from app.database import get_connection
from app.models import AffairCreate, AffairProcess, AffairStatus

router = APIRouter(prefix="/affairs", tags=["事务办理"])


VALID_TRANSITIONS = {
    "待受理": ["办理中", "已退回"],
    "办理中": ["已办结", "已退回"],
    "已退回": ["待受理"],
    "已办结": []
}


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
        """INSERT INTO affair_logs (affair_id, from_status, to_status, handler, remark)
           VALUES (?, NULL, '待受理', NULL, ?)""",
        (affair_id, "事务创建")
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


@router.get("/stats/overview")
def stats_overview(overdue_days: int = Query(7, ge=1, le=365)):
    """办件统计：各状态、各类别件数 + 已办结平均时长 + 超期未办结预警列表"""
    conn = get_connection()
    cursor = conn.cursor()

    # 总件数
    cursor.execute("SELECT COUNT(*) AS c FROM affairs")
    total = cursor.fetchone()["c"]

    # 按状态分组
    cursor.execute("SELECT status, COUNT(*) AS c FROM affairs GROUP BY status")
    by_status = {row["status"]: row["c"] for row in cursor.fetchall()}
    for s in ("待受理", "办理中", "已办结", "已退回"):
        by_status.setdefault(s, 0)

    # 按类别分组
    cursor.execute("SELECT category, COUNT(*) AS c FROM affairs GROUP BY category")
    by_category = {row["category"]: row["c"] for row in cursor.fetchall()}

    # 已办结平均办理时长（小时），基于 affair_logs 中最后一次进入"已办结"的时间 - 创建时间
    cursor.execute(
        """SELECT AVG((julianday(t.done_at) - julianday(a.created_at)) * 24.0) AS avg_hours,
                  COUNT(*) AS done_count
           FROM affairs a
           JOIN (
               SELECT affair_id, MAX(created_at) AS done_at
               FROM affair_logs
               WHERE to_status = '已办结'
               GROUP BY affair_id
           ) t ON t.affair_id = a.id
           WHERE a.status = '已办结'"""
    )
    avg_row = cursor.fetchone()
    avg_hours = avg_row["avg_hours"]
    done_count = avg_row["done_count"] or 0
    avg_processing_hours = round(avg_hours, 2) if avg_hours is not None else None

    # 超期未办结预警：状态非"已办结" 且 创建至今超过 overdue_days 天
    cursor.execute(
        """SELECT a.id, a.title, a.category, a.status, a.applicant_id,
                  r.name AS applicant_name, a.created_at, a.updated_at,
                  CAST((julianday('now', 'localtime') - julianday(a.created_at)) AS REAL) AS elapsed_days
           FROM affairs a
           LEFT JOIN residents r ON a.applicant_id = r.id
           WHERE a.status != '已办结'
             AND (julianday('now', 'localtime') - julianday(a.created_at)) > ?
           ORDER BY a.created_at ASC""",
        (overdue_days,)
    )
    overdue = []
    for row in cursor.fetchall():
        d = dict(row)
        d["elapsed_days"] = round(d["elapsed_days"], 2) if d["elapsed_days"] is not None else None
        overdue.append(d)

    return {
        "total": total,
        "by_status": by_status,
        "by_category": by_category,
        "avg_processing_hours": avg_processing_hours,
        "completed_count": done_count,
        "overdue_threshold_days": overdue_days,
        "overdue_count": len(overdue),
        "overdue_list": overdue,
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


@router.get("/{affair_id}/timeline")
def affair_timeline(affair_id: int):
    """全流程流转留痕：返回事务从创建到现在的每一次状态变更"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, status, created_at FROM affairs WHERE id = ?", (affair_id,))
    affair = cursor.fetchone()
    if not affair:
        raise HTTPException(status_code=404, detail="事务不存在")

    cursor.execute(
        """SELECT id, from_status, to_status, handler, remark, created_at
           FROM affair_logs
           WHERE affair_id = ?
           ORDER BY created_at ASC, id ASC""",
        (affair_id,)
    )
    logs = [dict(r) for r in cursor.fetchall()]
    return {
        "affair_id": affair_id,
        "current_status": affair["status"],
        "created_at": affair["created_at"],
        "timeline": logs,
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

    if new_status not in VALID_TRANSITIONS.get(current_status, []):
        raise HTTPException(
            status_code=400,
            detail=f"状态不允许从'{current_status}'转换到'{new_status}'"
        )

    try:
        cursor.execute(
            """UPDATE affairs SET status = ?, handler = ?, result = ?,
               updated_at = datetime('now', 'localtime') WHERE id = ?""",
            (new_status, data.handler, data.result, affair_id)
        )
        cursor.execute(
            """INSERT INTO affair_logs (affair_id, from_status, to_status, handler, remark)
               VALUES (?, ?, ?, ?, ?)""",
            (affair_id, current_status, new_status, data.handler, data.result)
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {"message": "事务处理成功", "status": new_status}
