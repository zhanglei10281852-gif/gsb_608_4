import requests
import json

BASE_URL = "http://127.0.0.1:8433"

def test():
    print("=" * 60)
    print("测试退回/重新提交流程...")
    print("=" * 60)

    r = requests.get(f"{BASE_URL}/residents")
    residents = r.json()
    resident_id = residents["data"][0]["id"]

    print("\n1. 创建新事务")
    r = requests.post(f"{BASE_URL}/affairs", json={
        "title": "低保申请",
        "category": "低保",
        "applicant_id": resident_id,
        "description": "申请农村低保"
    })
    affair_id = r.json()["id"]
    print(f"   事务ID: {affair_id}")

    print("\n2. 待受理 -> 已退回")
    r = requests.put(f"{BASE_URL}/affairs/{affair_id}/process", json={
        "status": "已退回",
        "handler": "王主任",
        "result": "材料不全，请补充收入证明"
    })
    print(f"   {r.json()}")

    print("\n3. 已退回 -> 待受理（重新提交）")
    r = requests.put(f"{BASE_URL}/affairs/{affair_id}/process", json={
        "status": "待受理",
        "handler": "张三",
        "result": "材料已补充"
    })
    print(f"   {r.json()}")

    print("\n4. 待受理 -> 办理中")
    r = requests.put(f"{BASE_URL}/affairs/{affair_id}/process", json={
        "status": "办理中",
        "handler": "李工作人员"
    })
    print(f"   {r.json()}")

    print("\n5. 办理中 -> 已办结")
    r = requests.put(f"{BASE_URL}/affairs/{affair_id}/process", json={
        "status": "已办结",
        "handler": "李工作人员",
        "result": "低保申请审批通过"
    })
    print(f"   {r.json()}")

    print("\n6. 查询完整时间线")
    r = requests.get(f"{BASE_URL}/affairs/{affair_id}/timeline")
    timeline = r.json()
    print(json.dumps(timeline, ensure_ascii=False, indent=2))
    assert len(timeline["timeline"]) == 5, f"应该有5条记录，实际有{len(timeline['timeline'])}"

    print("\n7. 查询统计")
    r = requests.get(f"{BASE_URL}/affairs/stats/summary")
    stats = r.json()
    print(f"   总计: {stats['total']}")
    print(f"   各状态: {stats['by_status']}")
    print(f"   各类别: {stats['by_category']}")
    print(f"   平均办理时长(分钟): {stats['avg_completion_minutes']}")

    print("\n✅ 退回流程测试通过！")

if __name__ == "__main__":
    test()
