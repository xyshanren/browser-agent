"""Mano-P 云端 API 连通性测试

测试 mano.mininglamp.com 的 API 是否可从当前环境访问。
"""

import asyncio
import json
import uuid
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

BASE_URL = "https://mano.mininglamp.com"
DEVICE_ID = f"browser-agent-test-{uuid.uuid4().hex[:6]}"


async def test_connectivity():
    """测试 Mano-P 云端 API 连通性。"""
    print(f"{'='*60}")
    print(f"🔌 Mano-P 云端 API 连通性测试")
    print(f"{'='*60}")
    print(f"   API 地址: {BASE_URL}")
    print(f"   Device ID: {DEVICE_ID}")
    print()

    import httpx

    async with httpx.AsyncClient(timeout=15.0) as client:
        # ── 测试 1: 基础网络连通性 ──
        print("📡 Test 1: 基础网络连通性")
        try:
            resp = await client.get(f"{BASE_URL}/")
            print(f"   GET / → {resp.status_code}")
            print(f"   响应: {resp.text[:200]}")
        except httpx.ConnectError:
            print("   ❌ 连接失败: 域名无法解析或服务不可达")
            return False
        except Exception as e:
            print(f"   ❌ 错误: {e}")
        print()

        # ── 测试 2: 创建会话 ──
        print("📡 Test 2: 创建自动化会话 (POST /v1/devices/{id}/start)")
        try:
            resp = await client.post(
                f"{BASE_URL}/v1/devices/{DEVICE_ID}/start",
                json={
                    "task": "test connectivity",
                    "device_id": DEVICE_ID,
                    "platform": "Windows",
                },
            )
            print(f"   状态码: {resp.status_code}")
            data = resp.json()
            print(f"   响应: {json.dumps(data, indent=2, ensure_ascii=False)[:500]}")

            session_id = data.get("session_id")
            if session_id:
                print(f"\n   ✅ 会话创建成功! session_id: {session_id}")

                # ── 测试 3: 执行一步推理 ──
                print(f"\n📡 Test 3: 执行一步推理 (POST /v1/sessions/{session_id}/step)")
                try:
                    resp2 = await client.post(
                        f"{BASE_URL}/v1/sessions/{session_id}/step",
                        json={
                            "request_id": str(uuid.uuid4()),
                            "tool_results": [],
                        },
                        timeout=30.0,
                    )
                    print(f"   状态码: {resp2.status_code}")
                    data2 = resp2.json()
                    print(f"   响应: {json.dumps(data2, indent=2, ensure_ascii=False)[:1000]}")
                except Exception as e:
                    print(f"   ❌ 推理请求失败: {e}")

                # ── 测试 4: 关闭会话 ──
                print(f"\n📡 Test 4: 关闭会话")
                try:
                    resp3 = await client.post(
                        f"{BASE_URL}/v1/sessions/{session_id}/close?skip_eval=true",
                        json={},
                    )
                    print(f"   状态码: {resp3.status_code}")
                    print(f"   会话已关闭")
                except Exception as e:
                    print(f"   ❌ 关闭失败: {e}")

                return True
            else:
                # 可能返回了错误信息
                print(f"\n   ⚠️  没有 session_id，可能 API 需要认证")
                return False

        except httpx.HTTPStatusError as e:
            print(f"   ❌ HTTP 错误: {e.response.status_code}")
            print(f"   响应体: {e.response.text[:500]}")
            return False
        except httpx.ConnectError:
            print(f"   ❌ 连接失败: 服务不可达")
            return False
        except Exception as e:
            print(f"   ❌ 错误: {e}")
            return False


async def main():
    success = await test_connectivity()
    print(f"\n{'='*60}")
    if success:
        print("✅ Mano-P 云端 API 可用!")
    else:
        print("❌ Mano-P 云端 API 当前不可用")
        print("   建议继续使用 qwen3-vl:2b (Ollama) + PlaywrightExecutor 方案")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
