# 文档解析器入口：根据文件类型分发到对应解析器，带重试和降级

import logging
import time
from typing import List, Dict, Any, Optional
from functools import wraps

from .base import BaseParser
from .vision_parser import UnifiedVisionParser
from .unstructured_parser import UnstructuredParser
from .paddle_ocr_parser import PaddleOCRParser
from .cad_parser import CADParser

logger = logging.getLogger(__name__)

# 最大重试次数
MAX_RETRIES = 3
RETRY_DELAY = 1.0


def with_retry(func):
    # 重试装饰器，最多3次
    @wraps(func)
    def wrapper(*args, **kwargs):
        last_exception = None
        for attempt in range(MAX_RETRIES):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt < MAX_RETRIES - 1:
                    logger.warning(f"{func.__name__} 第 {attempt + 1} 次尝试失败: {e}")
                    time.sleep(RETRY_DELAY * (attempt + 1))
                else:
                    logger.error(f"{func.__name__} 最终失败: {e}")
        raise last_exception
    return wrapper


class DocumentParser:
    # 文档解析统一入口，自动选择解析器

    # 支持的文件类型映射
    PARSER_MAP = {
        # 工程图纸
        "dwg": "_cad_parser",
        "dxf": "_cad_parser",
        # 图片格式
        "png": "_paddle_ocr_parser",
        "jpg": "_paddle_ocr_parser",
        "jpeg": "_paddle_ocr_parser",
        "bmp": "_paddle_ocr_parser",
        "gif": "_paddle_ocr_parser",
        "tiff": "_paddle_ocr_parser",
        "webp": "_paddle_ocr_parser",
        # 常规文档
        "pdf": "_unstructured_parser",
        "docx": "_unstructured_parser",
        "doc": "_unstructured_parser",
        "xlsx": "_unstructured_parser",
        "xls": "_unstructured_parser",
        "md": "_unstructured_parser",
        "txt": "_unstructured_parser",
        "csv": "_unstructured_parser",
        "log": "_unstructured_parser",
    }

    def __init__(self):
        self._unstructured_parser = UnstructuredParser()
        self._paddle_ocr_parser = PaddleOCRParser()
        self._vision_parser = UnifiedVisionParser()
        self._cad_parser = CADParser()
        self._parser_cache: Dict[str, str] = {}

    def _get_parser_name(self, ext: str) -> str:
        # 根据扩展名选解析器，默认Unstructured
        if ext in self.PARSER_MAP:
            return self.PARSER_MAP[ext]
        return "_unstructured_parser"

    @with_retry
    def parse(self, file_path: str, file_type: str) -> List[Dict[str, Any]]:
        # 解析主入口，失败自动降级
        import time
        start_time = time.time()

        ext = file_type.lower().lstrip(".")
        parser_name = self._get_parser_name(ext)

        logger.info(f"[DocumentParser] 开始解析: {file_path} (type={ext}, parser={parser_name})")

        # 获取解析器
        parser = getattr(self, parser_name, self._unstructured_parser)

        # 执行解析
        try:
            if parser_name == "_cad_parser":
                chunks = parser.parse(file_path, ext)
            elif parser_name == "_paddle_ocr_parser":
                chunks = parser.parse(file_path)
            else:
                chunks = parser.parse(file_path, ext)
        except Exception as e:
            logger.warning(f"解析器 {parser_name} 执行失败: {e}")
            chunks = []

        elapsed = time.time() - start_time
        logger.info(f"[DocumentParser] 解析完成: {file_path}, 耗时 {elapsed:.2f}s, 产出 {len(chunks)} 个块")

        # 验证结果
        if not chunks:
            logger.warning(f"解析结果为空，尝试降级方案: {file_path}")
            chunks = self._fallback_parse(file_path, ext)

        # 进一步降级
        if not chunks:
            chunks = self._final_fallback(file_path, ext)

        return chunks

    def _fallback_parse(self, file_path: str, ext: str) -> List[Dict[str, Any]]:
        # 降级：先试视觉解析，再试直接读文本
        logger.info(f"[DocumentParser] 使用降级策略: {file_path}")

        # 尝试 Vision Parser
        try:
            chunks = self._vision_parser.parse(file_path, ext)
            if chunks:
                logger.info(f"[DocumentParser] VisionParser 降级成功")
                return chunks
        except Exception as e:
            logger.warning(f"VisionParser 降级失败: {e}")

        # 尝试文本直接读取
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            if content and content.strip():
                return [{
                    "content": content[:5000],  # 限制大小
                    "page_number": 1,
                    "paragraph": "降级文本提取",
                }]
        except Exception as e:
            logger.warning(f"文本直接读取失败: {e}")

        return []

    def _final_fallback(self, file_path: str, ext: str) -> List[Dict[str, Any]]:
        # 最后兜底，返回文件元信息，保证总有结果
        import os
        file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0

        return [{
            "content": f"[文档: {os.path.basename(file_path)}] (类型: {ext.upper()}, 大小: {file_size / 1024:.1f} KB)",
            "page_number": 1,
            "paragraph": f"{ext.upper()} 文档",
        }]

    def parse_with_validation(
        self,
        file_path: str,
        file_type: str,
        min_content_length: int = 10,
    ) -> List[Dict[str, Any]]:
        # 解析并过滤太短的无效块
        chunks = self.parse(file_path, file_type)

        # 过滤无效块
        valid_chunks = [
            c for c in chunks
            if c.get("content") and len(c["content"].strip()) >= min_content_length
        ]

        if len(valid_chunks) < len(chunks):
            logger.warning(f"过滤掉 {len(chunks) - len(valid_chunks)} 个无效块")

        return valid_chunks

    @staticmethod
    def chunk_text(
        text: str,
        chunk_size: int = 1000,
        overlap: int = 200,
        min_chunk_size: int = 100,
    ) -> List[str]:
        # 委托给基类的文本分块
        return BaseParser.chunk_text(text, chunk_size, overlap, min_chunk_size)

    def get_supported_types(self) -> List[str]:
        # 返回支持的文件扩展名列表
        return list(set(self.PARSER_MAP.keys()))
