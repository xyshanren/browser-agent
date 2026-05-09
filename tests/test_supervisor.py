"""监督纠错模块单元测试

测试 Supervisor 的核心功能：
- 图片哈希计算
- 相似/不同截图的比对
- 重试逻辑
"""

import pytest
from browser_agent.supervisor import Supervisor


def _make_test_image(size: tuple = (100, 100), pattern: str = "gray") -> bytes:
    """生成测试图片的 JPEG 字节流。

    Args:
        pattern: 图案类型 — gray(纯灰), white(纯白), gradient(渐变), stripe(条纹)
    """
    from PIL import Image, ImageDraw
    import io
    img = Image.new("RGB", size, (128, 128, 128))
    draw = ImageDraw.Draw(img)
    if pattern == "gray":
        draw.rectangle((0, 0, *size), fill=(128, 128, 128))
    elif pattern == "white":
        draw.rectangle((0, 0, *size), fill=(255, 255, 255))
    elif pattern == "gradient":
        for x in range(size[0]):
            v = int(255 * x / size[0])
            draw.line([(x, 0), (x, size[1])], fill=(v, v, v))
    elif pattern == "stripe":
        for y in range(0, size[1], 10):
            draw.rectangle((0, y, size[0], y + 5), fill=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


class TestSupervisor:
    """Supervisor 模块单元测试。"""

    def test_same_image_no_change(self):
        """相同图片 → 无变化。"""
        img = _make_test_image(pattern="gradient")
        sv = Supervisor(threshold=0.05)
        sv.record_before(img)
        result = sv.verify(img)
        assert not result.changed
        assert result.score < 0.05

    def test_different_image_detected(self):
        """完全不同的图片 → 检测到变化。"""
        gray = _make_test_image(pattern="stripe")
        white = _make_test_image(pattern="white")
        sv = Supervisor(threshold=0.05)
        sv.record_before(gray)
        result = sv.verify(white)
        assert result.changed
        assert result.score > 0.05

    def test_threshold_custom(self):
        """自定义阈值生效。"""
        # 创建两幅相似但有微小差异的图片
        from PIL import Image, ImageDraw
        import io
        img_a = Image.new("RGB", (100, 100), (200, 200, 200))
        draw_a = ImageDraw.Draw(img_a)
        for x in range(100):
            v = int(255 * x / 100)
            draw_a.line([(x, 0), (x, 100)], fill=(v, v, v))
        buf_a = io.BytesIO()
        img_a.save(buf_a, format="JPEG", quality=85)

        # img_b: 在 img_a 基础上，在右下角画个小方块
        img_b = img_a.copy()
        draw_b = ImageDraw.Draw(img_b)
        draw_b.rectangle((80, 80, 95, 95), fill=(0, 0, 0))
        buf_b = io.BytesIO()
        img_b.save(buf_b, format="JPEG", quality=85)

        img_a_bytes = buf_a.getvalue()
        img_b_bytes = buf_b.getvalue()

        # 两图相似，得分应 <0.15
        # 宽松阈值 → 认为无变化
        sv = Supervisor(threshold=0.30)
        sv.record_before(img_a_bytes)
        result = sv.verify(img_b_bytes)
        assert not result.changed, f"expected unchanged, score={result.score}"
        # 严格阈值 → 认为有变化
        sv2 = Supervisor(threshold=0.01)
        sv2.record_before(img_a_bytes)
        result2 = sv2.verify(img_b_bytes)
        assert result2.changed, f"expected changed, score={result2.score}"

    def test_should_retry(self):
        """重试逻辑：无变化且在重试次数内 → 应重试。"""
        img = _make_test_image(pattern="gradient")
        sv = Supervisor()
        sv.record_before(img)
        result = sv.verify(img)
        # 相同图片，无变化 → 应重试
        assert sv.should_retry(result, attempt=0)
        assert sv.should_retry(result, attempt=1)
        # 第三次 → 不应重试（超过 MAX_RETRIES）
        assert not sv.should_retry(result, attempt=2)

    def test_no_retry_on_change(self):
        """有变化 → 不应重试。"""
        gray = _make_test_image(pattern="stripe")
        white = _make_test_image(pattern="white")
        sv = Supervisor()
        sv.record_before(gray)
        result = sv.verify(white)
        assert not sv.should_retry(result, attempt=0)

    def test_missing_before_hash(self):
        """未调用 record_before → verify 应返回 changed=True。"""
        img = _make_test_image(pattern="gradient")
        sv = Supervisor()
        result = sv.verify(img)  # 没有 record_before
        assert result.changed

    def test_verification_result_metadata(self):
        """VerificationResult 包含完整的元数据。"""
        img = _make_test_image(pattern="gradient")
        sv = Supervisor()
        sv.record_before(img)
        result = sv.verify(
            img,
            action_name="click",
            action_args={"x": 100, "y": 200},
        )
        assert result.action_name == "click"
        assert result.action_args == {"x": 100, "y": 200}
        assert isinstance(result.before_hash, str)
        assert isinstance(result.after_hash, str)
        assert len(result.before_hash) == 64  # 8x8 = 64 bits

    def test_hash_consistency(self):
        """相同图片 → 相同哈希。"""
        img = _make_test_image(pattern="gradient")
        h1 = Supervisor._compute_hash(img)
        h2 = Supervisor._compute_hash(img)
        assert h1 == h2
        assert len(h1) == 64

    def test_hash_comparison_toolarge(self):
        """哈希长度不同 → 视为完全不同。"""
        score = Supervisor._compare_hashes("0101", "010101")
        assert score == 1.0

    def test_hash_empty_string(self):
        """空哈希 → 视为完全不同。"""
        score = Supervisor._compare_hashes("", "0101")
        assert score == 1.0
