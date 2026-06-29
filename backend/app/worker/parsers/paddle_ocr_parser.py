# OCR解析器：PaddleOCR识别图片文字，配合视觉模型理解

import base64
import logging
import os
from typing import List, Dict, Any, Optional

import httpx
from PIL import Image

from .base import BaseParser

logger = logging.getLogger(__name__)


class PaddleOCRParser(BaseParser):
    """
    PaddleOCR 图片文字识别
    - 自动识别图片中的中文文字
    - 配合 MiniCPM-V-8B 进行内容理解
    """

    def __init__(self):
        from app.config import settings
        self.settings = settings
        self._ocr_engine = None

    def _get_ocr_engine(self):
        """延迟初始化 PaddleOCR 引擎"""
        if self._ocr_engine is None:
            try:
                from paddleocr import PaddleOCR
                self._ocr_engine = PaddleOCR(
                    use_angle_cls=True,
                    lang="ch",
                    use_gpu=False,
                    show_log=False,
                )
                logger.info("PaddleOCR 引擎初始化成功")
            except ImportError as e:
                logger.warning(f"PaddleOCR 库未安装: {e}")
                return None
        return self._ocr_engine

    def parse(self, file_path: str) -> List[Dict[str, Any]]:
        """
        解析图片：PaddleOCR 文字识别 + MiniCPM-V-8B 理解
        """
        logger.info(f"[PaddleOCRParser] 解析图片 {file_path}")

        # 1. PaddleOCR 文字识别
        ocr_text = self._paddle_ocr_recognize(file_path)

        # 2. MiniCPM-V-8B 深度理解
        vision_description = self._call_vision_llm(file_path, ocr_text)

        # 3. 合并结果并分块
        combined_content = self._combine_results(file_path, ocr_text, vision_description)

        if not combined_content:
            return self._fallback_metadata(file_path)

        chunks = self.chunk_text(combined_content, chunk_size=1000, overlap=200)

        return [
            {
                "content": chunk,
                "page_number": 1,
                "paragraph": "图片内容",
            }
            for chunk in chunks
        ]

    def _paddle_ocr_recognize(self, file_path: str) -> Optional[str]:
        """使用 PaddleOCR 识别图片文字"""
        ocr_engine = self._get_ocr_engine()
        if ocr_engine is None:
            return None

        try:
            result = ocr_engine.ocr(file_path, cls=True)
            if not result:
                return None

            text_lines = []
            for line in result:
                if line:
                    for item in line:
                        if isinstance(item, list) and len(item) >= 2:
                            text_lines.append(str(item[1]))
                        elif isinstance(item, dict) and "text" in item:
                            text_lines.append(str(item["text"]))

            ocr_text = "\n".join(text_lines)
            logger.info(f"PaddleOCR 识别到 {len(text_lines)} 行文字")
            return ocr_text if ocr_text else None

        except Exception as e:
            logger.warning(f"PaddleOCR 识别失败: {e}")
        return None

    def _call_vision_llm(self, image_path: str, ocr_text: Optional[str]) -> Optional[str]:
        """调用 MiniCPM-V-8B 进行图片理解"""
        try:
            if not self.settings.VISION_ENABLED:
                return None

            with open(image_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode("utf-8")

            prompt = self._build_vision_prompt(ocr_text, os.path.basename(image_path))

            with httpx.Client(timeout=300.0) as client:
                response = client.post(
                    self.settings.VISION_LLM_API_URL,
                    json={
                        "model": self.settings.VISION_LLM_MODEL,
                        "prompt": prompt,
                        "images": [image_data],
                        "stream": False,
                        "options": {
                            "temperature": 0.3,
                            "num_ctx": 4096,
                        }
                    },
                )
                response.raise_for_status()
                result = response.json().get("response", "")
                return result.strip() if result else None

        except Exception as e:
            logger.warning(f"MiniCPM-V 图片理解失败: {e}")
        return None

    def _build_vision_prompt(self, ocr_text: Optional[str], filename: str) -> str:
        """构建视觉模型提示词"""
        base_prompt = """请用中文详细分析这张图片，重点关注：
1. 图片中的所有文字内容
2. 图表、示意图的结构和数据含义
3. 整体主题、结构和关键信息

请尽可能详细地描述，以便后续检索。"""

        if ocr_text:
            return f"{base_prompt}\n\nPaddleOCR 已识别的文字：\n{ocr_text[:2000]}"

        return base_prompt

    def _combine_results(self, file_path: str, ocr_text: Optional[str], vision_desc: Optional[str]) -> str:
        """合并 OCR 和视觉模型结果"""
        parts = [f"[图片文件] {os.path.basename(file_path)}"]

        if ocr_text:
            parts.append(f"【文字识别结果】\n{ocr_text}")

        if vision_desc:
            parts.append(f"【图片内容理解】\n{vision_desc}")

        return "\n\n".join(parts) if parts else ""

    def _fallback_metadata(self, file_path: str) -> List[Dict[str, Any]]:
        """元数据降级"""
        file_size = os.path.getsize(file_path)
        return [{
            "content": f"[图片] {os.path.basename(file_path)}\n文件大小: {file_size / 1024:.1f} KB\n由 PaddleOCR + MiniCPM-V-8B 处理。",
            "page_number": 1,
            "paragraph": "图片",
        }]
