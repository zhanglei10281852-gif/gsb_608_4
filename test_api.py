import requests
import json

BASE_URL = "http://127.0.0.1:8433"

def test():
    print("=" * 60)
    print("开始测试功能...")
    print("=" * 60)

    print("\n1. 查询居民列表，获取一个居民ID")
    r = requests.get(f"{BASE_URL}/residents")
    residents = r.json()
    print(f"   查询居民: {r.status_code}, 共 {residents['total']} 人")
    if residents["total"] > 0:
        resident_id = residents["data"][0]["id"]
        print(f"   使用现有居民ID: {resident_id}")
    else:
        r = requests.post(f"{BASE_URL}/residents", json={
            "name": "张三",
            "id_card": "110101199001011234",
            "gender": "男",
            "birth_date": "1990-01-01",
            "phone": "13800138000",
            "address": "幸福村1号",
            "village": "幸福村"
        })
        resident_id = r.json()["id"]
        print(f"   创建居民ID: {resident_id}")

    print("\n2. 创建一个事务")
    r = requests.post(f"{BASE_URL}/affairs", json={
        "title": "办理医保报销",
        "category": "医保",
        "applicant_id": resident_id,
        "description": "住院费用报销申请"
    })
    print(f"   创建事务: {r.status_code}")
    affair = r.json()
    print(f"   结果: {json.dumps(affair, ensure_ascii=False, indent=2)}")
    affair_id = affair["id"]

    print("\n3. 查询事务时间线（创建后应该有一条记录）")
    r = requests.get(f"{BASE_URL}/affairs/{affair_id}/timeline")
    print(f"   查询时间线: {r.status_code}")
    timeline = r.json()
    print(f"   结果: {json.dumps(timeline, ensure_ascii=False, indent=2)}")
    assert len(timeline["timeline"]) == 1, "应该有1条初始记录"
    assert timeline["timeline"][0]["to_status"] == "待受理"

    print("\n4. 处理事务：待受理 -> 办理中")
    r = requests.put(f"{BASE_URL}/affairs/{affair_id}/process", json={
        "status": "办理中",
        "handler": "李工作人员",
        "result": None
    })
    print(f"   处理事务: {r.status_code}")
    print(f"   结果: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")

    print("\n5. 再次查询时间线（应该有2条记录）")
    r = requests.get(f"{BASE_URL}/affairs/{affair_id}/timeline")
    print(f"   查询时间线: {r.status_code}")
    timeline = r.json()
    print(f"   结果: {json.dumps(timeline, ensure_ascii=False, indent=2)}")
    assert len(timeline["timeline"]) == 2, "应该有2条记录"
    assert timeline["timeline"][1]["to_status"] == "办理中"
    assert timeline["timeline"][1]["from_status"] == "待受理"

    print("\n6. 处理事务：办理中 -> 已办结")
    r = requests.put(f"{BASE_URL}/affairs/{affair_id}/process", json={
        "status": "已办结",
        "handler": "李工作人员",
        "result": "报销已审批通过，款项将在3个工作日内到账"
    })
    print(f"   处理事务: {r.status_code}")
    print(f"   结果: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")

    print("\n7. 查询最终时间线（应该有3条完整记录）")
    r = requests.get(f"{BASE_URL}/affairs/{affair_id}/timeline")
    print(f"   查询时间线: {r.status_code}")
    timeline = r.json()
    print(f"   结果: {json.dumps(timeline, ensure_ascii=False, indent=2)}")
    assert len(timeline["timeline"]) == 3, "应该有3条完整记录"
    assert timeline["timeline"][2]["to_status"] == "已办结"

    print("\n8. 测试状态机校验：已办结不能再处理")
    r = requests.put(f"{BASE_URL}/affairs/{affair_id}/process", json={
        "status": "办理中",
        "handler": "李工作人员"
    })
    print(f"   非法状态转换: {r.status_code}")
    print(f"   结果: {json.dumps(r.json(), ensure_ascii=False, indent=2)}")
    assert r.status_code == 400, "非法状态转换应该返回400"

    print("\n9. 创建第二个事务（用于测试统计）")
    r = requests.post(f"{BASE_URL}/affairs", json={
        "title": "户籍迁移",
        "category": "户籍",
        "applicant_id": resident_id,
        "description": "户口迁出申请"
    })
    affair2_id = r.json()["id"]
    print(f"   事务ID: {affair2_id}")

    print("\n10. 测试办件统计接口")
    r = requests.get(f"{BASE_URL}/affairs/stats/summary")
    print(f"   查询统计: {r.status_code}")
    stats = r.json()
    print(f"   结果: {json.dumps(stats, ensure_ascii=False, indent=2)}")
    assert "total" in stats
    assert "by_status" in stats
    assert "by_category" in stats
    assert "avg_completion_minutes" in stats
    assert stats["by_status"]["已办结"] >= 1

    print("\n11. 测试超期预警接口（默认7天，当前应该没有超期）")
    r = requests.get(f"{BASE_URL}/affairs/stats/overdue")
    print(f"   查询超期: {r.status_code}")
    overdue = r.json()
    print(f"   结果: {json.dumps(overdue, ensure_ascii=False, indent=2)}")
    assert "overdue_days_threshold" in overdue
    assert "count" in overdue
    assert "data" in overdue

    print("\n12. 测试超期预警接口（设置0天阈值，未完成的都应该超期）")
    r = requests.get(f"{BASE_URL}/affairs/stats/overdue?days=0")
    print(f"   查询超期: {r.status_code}")
    overdue = r.json()
    print(f"   结果: {json.dumps(overdue, ensure_ascii=False, indent=2)}")
    assert overdue["count"] >= 1, "应该至少有1个超期事项"

    print("\n13. 测试事务详情接口")
    r = requests.get(f"{BASE_URL}/affairs/{affair_id}")
    print(f"   查询详情: {r.status_code}")
    detail = r.json()
    print(f"   结果包含申请人姓名: {'applicant_name' in detail}")
    assert detail["status"] == "已办结"

    print("\n" + "=" * 60)
    print("✅ 所有功能测试通过！")
    print("=" * 60)


if __name__ == "__main__":
    test()
