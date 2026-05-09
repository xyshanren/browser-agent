"""监督纠错模块 — 截图比对 + 动作验证

通过比对动作执行前后的截图，检测动作是否产生了视觉变化。
如果截图无明显变化，说明动作可能失败或未生效。

用法:
    supervisor = Supervisor(threshold=0.15)
    supervisor.record_before(screenshot_bytes)
    result = await executor.act(tool_name, args)
    changed = supervisor.verify(screenshot_bytes_after)
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Optional

from browser_agent.utils.logger import logger


@dataclass
class VerificationResult:
    """截图验证结果。"""
    changed: bool               # 截图是否有明显变化
    score: float                # 变化分数（0-1, 越大变化越大）
    before_hash: str            # 执行前的截图哈希
    after_hash: str             # 执行后的截图哈希
    action_name: str = ""       # 被验证的动作名称
    action_args: dict | None = None


class Supervisor:
    """监督器 — 通过截图哈希比对检测动作是否产生视觉变化。

    阈值说明:
        - >0.15: 有明显变化（正常）
        - 0.05-0.15: 轻微变化（可能有效）
        - <0.05: 无明显变化（疑似失败）
    """

    # 默认阈值：变化分数低于此值视为"无变化"
    DEFAULT_THRESHOLD = 0.10

    # 最大重试次数
    MAX_RETRIES = 2

    def __init__(self, threshold: float = DEFAULT_THRESHOLD):
        self.threshold = threshold
        self._before_hash: Optional[str] = None

    def record_before(self, screenshot_bytes: bytes):
        """记录动作执行前的截图哈希。"""
        self._before_hash = self._compute_hash(screenshot_bytes)

    def verify(
        self,
        screenshot_bytes: bytes,
        action_name: str = "",
        action_args: dict | None = None,
    ) -> VerificationResult:
        """比对新截图与执行前的截图，返回验证结果。"""
        after_hash = self._compute_hash(screenshot_bytes)

        if self._before_hash is None:
            logger.warning("⚠️ supervisor: before hash is None, skipping verification")
            return VerificationResult(
                changed=True,
                score=1.0,
                before_hash="",
                after_hash=after_hash,
                action_name=action_name,
                action_args=action_args,
            )

        score = self._compare_hashes(self._before_hash, after_hash)
        changed = score >= self.threshold

        if not changed:
            logger.warning(
                f"⚠️ supervision: action '{action_name}' had no visual effect "
                f"(score={score:.3f} < threshold={self.threshold})"
            )
        else:
            logger.debug(
                f"✓ supervision: action '{action_name}' changed screen "
                f"(score={score:.3f})"
            )

        return VerificationResult(
            changed=changed,
            score=score,
            before_hash=self._before_hash,
            after_hash=after_hash,
            action_name=action_name,
            action_args=action_args,
        )

    def should_retry(self, result: VerificationResult, attempt: int) -> bool:
        """判断是否需要重试。"""
        return not result.changed and attempt < self.MAX_RETRIES

    # --- 图片哈希实现 ---

    @staticmethod
    def _compute_hash(image_bytes: bytes) -> str:
        """计算图片的感知哈希 (pHash)。

        步骤:
            1. 缩小到 8x8
            2. 转灰度
            3. 计算均值
            4. 生成 64位哈希
        """
        try:
            from PIL import Image
            img = Image.open(BytesIO(image_bytes))
            # 缩小到 8x8 并转灰度
            small = img.resize((8, 8), Image.LANCZOS).convert("L")
            # 获取像素数据（兼容 Pillow 10-14）
            try:
                pixels = list(small.getdata())
            except AttributeError:
                pixels = list(small.get_flattened_data())
            avg = sum(pixels) / len(pixels)
            # 生成哈希字符串（>= 均值记为 1）
            hash_bits = "".join("1" if p >= avg else "0" for p in pixels)
            return hash_bits
        except Exception as e:
            logger.warning(f"⚠️ supervisor: hash computation failed: {e}")
            return ""

    @staticmethod
    def _compare_hashes(hash1: str, hash2: str) -> float:
        """比较两个哈希的相似度。

        返回 0-1 之间的变化分数:
            - 0: 完全相同
            - 1: 完全不同
        """
        if not hash1 or not hash2:
            return 1.0  # 无法比较时认为有变化

        if len(hash1) != len(hash2):
            return 1.0

        hamming = sum(1 for a, b in zip(hash1, hash2) if a != b)
        return hamming / len(hash1)
