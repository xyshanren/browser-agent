"""Mano-P 云端 API 真实测试 — 基于 OpenAPI 规格"""

import asyncio
import json
import uuid

BASE_URL = "https://mano.mininglamp.com"


async def test_api():
    import httpx

    async with httpx.AsyncClient(timeout=30.0) as client:
        # ── Test 1: Create session ──
        print("📡 Creating session...")
        resp = await client.post(
            f"{BASE_URL}/v1/sessions",
            json={
                "task": "打开百度，搜索深圳天气，告诉我今天的温度",
                "device_id": f"test-pc-{uuid.uuid4().hex[:4]}",
                "platform": "Windows",
            },
        )
        print(f"   Status: {resp.status_code}")
        data = resp.json()
        print(f"   Response: {json.dumps(data, indent=2, ensure_ascii=False)[:300]}")

        session_id = data.get("session_id")
        if not session_id:
            print("❌ No session_id returned")
            return False

        print(f"\n✅ Session created: {session_id}")

        # ── Test 2: Step with screenshot ──
        print(f"\n📡 Sending step (with screenshot)...")

        # Take a real screenshot
        try:
            import mss
            with mss.mss() as sct:
                monitor = sct.monitors[1]
                raw = sct.grab(monitor)
                from PIL import Image
                import io
                import base64
                img = Image.frombytes("RGB", raw.size, raw.rgb)
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=50)
                b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
                print(f"   Screenshot: {len(buf.getvalue()) // 1024}KB")
        except ImportError:
            print("   No mss available, using dummy screenshot")
            b64 = ""

        resp2 = await client.post(
            f"{BASE_URL}/v1/sessions/{session_id}/step",
            json={
                "request_id": str(uuid.uuid4()),
                "screenshot_b64": b64 or None,
                "tool_results": [],
            },
        )
        print(f"   Status: {resp2.status_code}")
        data2 = resp2.json()
        print(f"   Response: {json.dumps(data2, indent=2, ensure_ascii=False)[:500]}")

        actions = data2.get("actions", [])
        reasoning = data2.get("reasoning", "")
        status = data2.get("status", "")
        print(f"\n   Reasoning: {reasoning[:200]}")
        print(f"   Status: {status}")
        print(f"   Actions: {len(actions)}")
        for a in actions[:3]:
            print(f"     - {json.dumps(a, ensure_ascii=False)[:150]}")

        # ── Test 3: Close session ──
        print(f"\n📡 Closing session...")
        resp3 = await client.post(
            f"{BASE_URL}/v1/sessions/{session_id}/close",
            json={},
        )
        print(f"   Status: {resp3.status_code}")
        print(f"   Response: {resp3.json()}")

        return True


async def main():
    success = await test_api()
    print(f"\n{'='*50}")
    print(f"{'✅ Mano-P API 可用!' if success else '❌ Mano-P API 测试失败'}")


if __name__ == "__main__":
    asyncio.run(main())
