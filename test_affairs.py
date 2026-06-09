import requests
import json

BASE_URL = "http://localhost:8432"

def print_response(title, response):
    print(f"\n{'='*60}")
    print(f"【{title}】")
    print(f"状态码: {response.status_code}")
    try:
        data = response.json()
        print(f"响应数据: {json.dumps(data, ensure_ascii=False, indent=2)}")
        return data
    except:
        print(f"响应内容: {response.text}")
        return None

def main():
    print("="*60)
    print("事务办理模块功能测试")
    print("="*60)

    try:
        # 1. 先创建一个居民作为申请人
        print("\n--- 1. 创建测试居民 ---")
        resident_data = {
            "name": "张三",
            "id_card": "110101199001011234",
            "gender": "男",
            "birth_date": "1990-01-01",
            "phone": "13800138000",
            "address": "某某镇某某村1号",
            "village": "某某村",
            "household_head": "张三"
        }
        try:
            response = requests.post(f"{BASE_URL}/residents", json=resident_data)
            if response.status_code == 201:
                resident_id = response.json()["id"]
                print(f"创建成功，居民ID: {resident_id}")
            elif response.status_code == 400 and "已存在" in response.text:
                # 如果已存在，查一下
                response = requests.get(f"{BASE_URL}/residents")
                residents = response.json()["data"]
                resident_id = residents[0]["id"]
                print(f"居民已存在，使用ID: {resident_id}")
            else:
                print(f"创建居民失败: {response.status_code} - {response.text}")
                return
        except Exception as e:
            print(f"创建居民出错: {e}")
            return

        # 2. 创建事务
        print("\n--- 2. 创建事务 ---")
        affair_data = {
            "title": "申请低保",
            "category": "低保",
            "applicant_id": resident_id,
            "description": "家庭困难，申请低保待遇"
        }
        response = requests.post(f"{BASE_URL}/affairs", json=affair_data)
        affair_id = print_response("创建事务", response)["id"]
        assert affair_id > 0, "事务创建失败"

        # 3. 查询事务详情
        print("\n--- 3. 查询事务详情 ---")
        response = requests.get(f"{BASE_URL}/affairs/{affair_id}")
        affair_detail = print_response("查询事务详情", response)
        assert affair_detail["status"] == "待受理", "初始状态应该是待受理"

        # 4. 查询事务流转历史（初始记录）
        print("\n--- 4. 查询事务流转历史（初始） ---")
        response = requests.get(f"{BASE_URL}/affairs/{affair_id}/history")
        history = print_response("查询流转历史", response)
        assert len(history) == 1, "应该有1条初始记录"
        assert history[0]["to_status"] == "待受理", "初始状态应该是待受理"
        assert history[0]["from_status"] is None, "初始状态from_status应该为None"
        print("✓ 初始流转记录正确")

        # 5. 处理事务：待受理 → 办理中
        print("\n--- 5. 处理事务：待受理 → 办理中 ---")
        process_data = {
            "status": "办理中",
            "handler": "李主任",
            "result": "已受理，正在核实材料"
        }
        response = requests.put(f"{BASE_URL}/affairs/{affair_id}/process", json=process_data)
        print_response("办理中处理", response)
        assert response.status_code == 200, "处理失败"

        # 6. 再次查询流转历史
        print("\n--- 6. 查询流转历史（2条记录） ---")
        response = requests.get(f"{BASE_URL}/affairs/{affair_id}/history")
        history = print_response("查询流转历史", response)
        assert len(history) == 2, "应该有2条记录"
        assert history[1]["from_status"] == "待受理", "from_status应该是待受理"
        assert history[1]["to_status"] == "办理中", "to_status应该是办理中"
        assert history[1]["handler"] == "李主任", "处理人应该是李主任"
        print("✓ 第二条流转记录正确")

        # 7. 继续处理：办理中 → 已办结
        print("\n--- 7. 处理事务：办理中 → 已办结 ---")
        process_data = {
            "status": "已办结",
            "handler": "李主任",
            "result": "经审核符合条件，已批准低保申请"
        }
        response = requests.put(f"{BASE_URL}/affairs/{affair_id}/process", json=process_data)
        print_response("办结处理", response)
        assert response.status_code == 200, "处理失败"

        # 8. 再次查询流转历史（3条记录）
        print("\n--- 8. 查询流转历史（3条记录） ---")
        response = requests.get(f"{BASE_URL}/affairs/{affair_id}/history")
        history = print_response("查询流转历史", response)
        assert len(history) == 3, "应该有3条记录"
        assert history[2]["from_status"] == "办理中", "from_status应该是办理中"
        assert history[2]["to_status"] == "已办结", "to_status应该是已办结"
        print("✓ 第三条流转记录正确")

        # 9. 测试状态机校验：已办结不能再转换
        print("\n--- 9. 测试状态机校验：已办结不能再转换 ---")
        process_data = {
            "status": "办理中",
            "handler": "测试",
            "result": "测试"
        }
        response = requests.put(f"{BASE_URL}/affairs/{affair_id}/process", json=process_data)
        print_response("状态机校验测试", response)
        assert response.status_code == 400, "应该返回400错误"
        print("✓ 状态机校验正确")

        # 10. 再创建几个不同状态的事务，用于测试统计
        print("\n--- 10. 创建更多测试数据用于统计 ---")

        # 待受理的
        for i in range(2):
            affair_data = {
                "title": f"测试待受理事务{i+1}",
                "category": "户籍" if i % 2 == 0 else "社保",
                "applicant_id": resident_id,
                "description": "测试数据"
            }
            requests.post(f"{BASE_URL}/affairs", json=affair_data)

        # 办理中的
        for i in range(2):
            affair_data = {
                "title": f"测试办理中事务{i+1}",
                "category": "医保" if i % 2 == 0 else "建房",
                "applicant_id": resident_id,
                "description": "测试数据"
            }
            resp = requests.post(f"{BASE_URL}/affairs", json=affair_data)
            aid = resp.json()["id"]
            process_data = {"status": "办理中", "handler": "王科员", "result": "正在处理"}
            requests.put(f"{BASE_URL}/affairs/{aid}/process", json=process_data)

        # 已退回的
        affair_data = {
            "title": "测试已退回事务",
            "category": "其他",
            "applicant_id": resident_id,
            "description": "测试数据"
        }
        resp = requests.post(f"{BASE_URL}/affairs", json=affair_data)
        aid = resp.json()["id"]
        process_data = {"status": "已退回", "handler": "李主任", "result": "材料不全，请补充"}
        requests.put(f"{BASE_URL}/affairs/{aid}/process", json=process_data)

        print("✓ 测试数据创建完成")

        # 11. 测试统计接口
        print("\n--- 11. 测试办件统计接口 ---")
        response = requests.get(f"{BASE_URL}/affairs/statistics/summary")
        stats = print_response("办件统计", response)

        assert "total" in stats, "应该有total字段"
        assert "status_stats" in stats, "应该有status_stats字段"
        assert "category_stats" in stats, "应该有category_stats字段"
        assert "avg_completion_days" in stats, "应该有avg_completion_days字段"
        assert "overdue_count" in stats, "应该有overdue_count字段"
        assert "overdue_list" in stats, "应该有overdue_list字段"

        assert stats["status_stats"]["待受理"] >= 2, "待受理数量不对"
        assert stats["status_stats"]["办理中"] >= 2, "办理中数量不对"
        assert stats["status_stats"]["已办结"] >= 1, "已办结数量不对"
        assert stats["status_stats"]["已退回"] >= 1, "已退回数量不对"

        print("✓ 统计接口字段完整，数据正确")

        # 12. 测试查询不存在的事务历史
        print("\n--- 12. 测试查询不存在的事务历史 ---")
        response = requests.get(f"{BASE_URL}/affairs/99999/history")
        print_response("查询不存在的事务历史", response)
        assert response.status_code == 404, "应该返回404"
        print("✓ 404处理正确")

        print("\n" + "="*60)
        print("✅ 所有测试通过！功能正常！")
        print("="*60)

    except Exception as e:
        print(f"\n❌ 测试出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
