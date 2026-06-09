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
    conn.commit()
    return {"id": cursor.lastrowid, "message": "事务提交成功"}


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

    cursor.execute(
        """UPDATE affairs SET status = ?, handler = ?, result = ?,
           updated_at = datetime('now', 'localtime') WHERE id = ?""",
        (new_status, data.handler, data.result, affair_id)
    )
    conn.commit()
    return {"message": "事务处理成功", "status": new_status}
