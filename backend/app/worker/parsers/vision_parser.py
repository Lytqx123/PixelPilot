# 视觉解析器：MiniCPM-V-8B做图片/图纸内容理解

import base64
import logging
import os
from typing import List, Dict, Any

import httpx
from PIL import Image

from .base import BaseParser

logger = logging.getLogger(__name__)


class UnifiedVisionParser(BaseParser):
    """
    统一视觉模型解析器：使用 MiniCPM-V-8B
    """

    def __init__(self):
        from app.config import settings
        self.settings = settings

    def parse(self, file_path: str, file_type: str) -> List[Dict[str, Any]]:
        """主解析入口：根据文件类型选择策略"""
        ext = file_type.lower().lstrip(".")

        logger.info(f"[UnifiedVisionParser] 使用 MiniCPM-V-8B 解析: {file_path} (type={ext})")

        # 图片格式
        if ext in ("png", "jpg", "jpeg", "bmp", "gif", "tiff", "webp"):
            return self._parse_as_image(file_path)

        # 文本类文件
        if ext in ("pdf", "docx", "doc", "xlsx", "xls", "txt", "md", "csv", "log"):
            return self._parse_text_file(file_path, ext)

        # CAD 图纸
        if ext in ("dxf", "dwg"):
            return self._parse_cad_file(file_path, ext)

        # 默认
        return self._parse_generic(file_path)

    def _parse_as_image(self, file_path: str) -> List[Dict[str, Any]]:
        """直接解析图片"""
        description = self._call_vision_llm(file_path)
        if description:
            return [{
                "content": f"[图片文件] {os.path.basename(file_path)}\n{description}",
                "page_number": 1,
                "paragraph": f"图片: {os.path.basename(file_path)}",
            }]
        return self._fallback_metadata(file_path, "图片")

    def _parse_text_file(self, file_path: str, ext: str) -> List[Dict[str, Any]]:
        """解析文本类文件"""
        text_content = self._read_text_content(file_path, ext)

        if text_content and len(text_content.strip()) > 0:
            description = self._call_vision_llm_with_text(file_path, text_content, ext)
            if description:
                return [{
                    "content": f"[{ext.upper()} 文件] {os.path.basename(file_path)}\n{description}",
                    "page_number": 1,
                    "paragraph": f"{ext.upper()}文档",
                }]

        # 降级：生成元数据
        return self._fallback_metadata(file_path, ext.upper())

    def _parse_cad_file(self, file_path: str, ext: str) -> List[Dict[str, Any]]:
        """CAD 图纸解析提示"""
        content = (
            f"[{ext.upper()} 工程图纸] {os.path.basename(file_path)}\n"
            f"文件大小: {os.path.getsize(file_path) / 1024:.1f} KB\n"
            f"由 ezdxf + MiniCPM-V-8B 解析处理。"
        )
        return [{
            "content": content,
            "page_number": 1,
            "paragraph": f"{ext.upper()}工程图纸",
        }]

    def _parse_generic(self, file_path: str) -> List[Dict[str, Any]]:
        """通用解析"""
        try:
            with Image.open(file_path) as img:
                return self._parse_as_image(file_path)
        except Exception:
            pass

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read(10000)
            return self._parse_text_file(file_path, "txt")
        except Exception:
            pass

        return self._fallback_metadata(file_path, "文件")

    def _read_text_content(self, file_path: str, ext: str) -> str:
        """读取文本文件内容"""
        if ext in ("txt", "md", "csv", "log"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    return f.read()
            except UnicodeDecodeError:
                try:
                    with open(file_path, "r", encoding="gbk") as f:
                        return f.read()
                except Exception:
                    pass
        return ""

    def _call_vision_llm(self, image_path: str) -> str:
        """调用 MiniCPM-V-8B 视觉模型"""
        return self._call_vision_llm_internal(image_path, None, None)

    def _call_vision_llm_with_text(self, file_path: str, text_content: str, ext: str) -> str:
        """调用 MiniCPM-V-8B 处理文本内容"""
        try:
            max_text_len = 8000
            if len(text_content) > max_text_len:
                text_content = text_content[:max_text_len] + "\n... (内容已截断)"

            prompt = self._build_text_prompt(text_content, ext, os.path.basename(file_path))
            return self._call_llm_text_only(prompt)

        except Exception as e:
            logger.warning(f"MiniCPM-V text call failed: {e}")
            return ""

    def _call_vision_llm_internal(self, image_path: str, text_content: str | None, ext: str | None) -> str:
        """内部方法：调用 MiniCPM-V-8B"""
        try:
            if not self.settings.VISION_ENABLED:
                logger.warning("Vision LLM not enabled")
                return ""

            with open(image_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode("utf-8")

            prompt = self._build_vision_prompt(text_content, ext, os.path.basename(image_path) if image_path else "")

            with httpx.Client(timeout=300.0) as client:
                response = client.post(
                    self.settings.VISION_LLM_API_URL,
                    json={
                        "model": self.settings.VISION_LLM_MODEL,  # minicpm-v:8b
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
                return result.strip() if result else ""

        except Exception as e:
            logger.warning(f"MiniCPM-V call failed: {e}")
            return ""

    def _call_llm_text_only(self, prompt: str) -> str:
        """调用 LLM 纯文本模式"""
        try:
            with httpx.Client(timeout=300.0) as client:
                response = client.post(
                    self.settings.LLM_API_URL,
                    json={
                        "model": self.settings.LLM_MODEL,  # qwen2.5:14b
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.3,
                            "num_ctx": 4096,
                        }
                    },
                )
                response.raise_for_status()
                result = response.json().get("response", "")
                return result.strip() if result else ""
        except Exception as e:
            logger.warning(f"Text LLM call failed: {e}")
            return ""

    def _build_vision_prompt(self, text_content: str | None, ext: str | None, filename: str) -> str:
        """构建 MiniCPM-V-8B 视觉模型提示词"""
        base_prompt = """请用中文详细分析这张图片，重点关注：
1. 图片中的所有文字内容（包括标题、段落、表格、说明、标签、技术文档等）
2. 图表、流程图、示意图的结构和数据含义
3. 工程图纸中的尺寸标注、技术符号、组件标识
4. 整体主题、结构和关键信息

请尽可能详细地描述，以便后续检索时能够精确匹配相关内容。"""

        if text_content and ext:
            return f"{base_prompt}\n\n补充上下文：这是一个 {ext.upper()} 文件，文件名为 {filename}。\n文件部分内容预览：\n{text_content[:2000]}"

        return base_prompt

    def _build_text_prompt(self, text_content: str, ext: str, filename: str) -> str:
        """构建文本提示词"""
        return f"""请用中文详细分析以下 {ext.upper()} 文档内容，文件名为 {filename}。

请重点关注：
1. 文档的主题、核心观点和关键结论
2. 所有重要的数据、参数、规格、代码等
3. 文档的结构、章节和组织
4. 技术细节、测试结果、Bug 描述、解决方案

请生成一个详细的、结构化的摘要，包含所有关键信息，以便后续语义检索。

---
文档内容：
{text_content}
---

请用中文输出详细分析："""

    def _fallback_metadata(self, file_path: str, type_label: str) -> List[Dict[str, Any]]:
        """元数据降级"""
        file_size = os.path.getsize(file_path)
        content = (
            f"[{type_label}] {os.path.basename(file_path)}\n"
            f"文件大小: {file_size / 1024:.1f} KB\n"
            f"由 MiniCPM-V-8B 统一视觉模型处理。"
        )
        return [{
            "content": content,
            "page_number": 1,
            "paragraph": f"{type_label}",
        }]
