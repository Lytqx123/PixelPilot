# 文档解析器基类：提供分块、段落切分等通用方法，各格式解析器继承

import logging
import re
from typing import List, Optional, Callable

logger = logging.getLogger(__name__)


# 句子边界定义
SENTENCE_DELIMITERS = [
    "。", "！", "？", "；", "\n",
    ". ", "! ", "? ", "; ",
]


class BaseParser:
    """文档解析器基类"""

    # 句子边界正则
    SENTENCE_PATTERN = re.compile(
        r'(?<=[。！？；\n])|(?<=[.!?;]\s)',
        re.MULTILINE
    )

    # 段落分割符
    PARAGRAPH_PATTERN = re.compile(r'\n\s*\n')

    @classmethod
    def chunk_text(
        cls,
        text: str,
        chunk_size: int = 1000,
        overlap: int = 200,
        min_chunk_size: int = 100,
    ) -> List[str]:
        """
        语义分块：优先按段落分割，过长的段落按句子边界分割。

        优化点：
        1. 更好的段落边界检测
        2. 句子边界智能切分
        3. 重叠内容确保上下文连续性
        4. 过小chunk合并处理

        :param text: 输入文本
        :param chunk_size: 每个块目标字符数（默认1000）
        :param overlap: 块之间重叠字符数（默认200）
        :param min_chunk_size: 最小块大小，过小的块会与相邻块合并
        :return: 分块后的文本列表
        """
        if not text or not text.strip():
            return []

        # 1. 清理文本
        text = cls._clean_text(text)
        if not text:
            return []

        # 2. 按段落分割
        paragraphs = cls._split_paragraphs(text)
        paragraphs = [p for p in paragraphs if p.strip()]

        if not paragraphs:
            return []

        # 3. 构建块
        chunks: List[str] = []
        current_chunk: List[str] = []
        current_len = 0

        for para in paragraphs:
            para_len = len(para)

            # 如果当前段落加入后不超过 chunk_size，直接追加
            if current_len + para_len <= chunk_size:
                current_chunk.append(para)
                current_len += para_len
                continue

            # 当前 chunk 已满，先保存
            if current_chunk:
                chunk_text = "\n".join(current_chunk)
                chunks.append(chunk_text)

                # 带 overlap 的新 chunk：取最后一段作为上下文
                if overlap > 0 and len(current_chunk) > 0:
                    last_text = current_chunk[-1]
                    overlap_text = last_text[-overlap:] if len(last_text) > overlap else last_text
                    current_chunk = [overlap_text]
                    current_len = len(overlap_text)
                else:
                    current_chunk = []
                    current_len = 0

            # 处理超长段落
            if para_len > chunk_size:
                sub_chunks = cls._split_long_paragraph(para, chunk_size, overlap, min_chunk_size)
                if sub_chunks:
                    # 前面的子块直接作为独立 chunk
                    chunks.extend(sub_chunks[:-1])
                    # 最后一个子块保留为当前 chunk,作为下一段的 overlap 上下文
                    current_chunk = [sub_chunks[-1]]
                    current_len = len(sub_chunks[-1])
                else:
                    current_chunk = []
                    current_len = 0
            else:
                current_chunk.append(para)
                current_len = para_len

        # 保存最后一个 chunk
        if current_chunk:
            chunks.append("\n".join(current_chunk))

        # 4. 合并过小的块
        chunks = cls._merge_small_chunks(chunks, min_chunk_size, overlap)

        return chunks

    @classmethod
    def _clean_text(cls, text: str) -> str:
        """清理文本：移除多余空白、规范换行"""
        if not text:
            return ""

        # 移除零宽字符
        text = re.sub(r'[\u200b-\u200f\u2028-\u202f\ufeff]', '', text)

        # 规范化换行：超过两个连续换行改为两个
        text = re.sub(r'\n{3,}', '\n\n', text)

        # 移除行首行尾空白
        lines = [line.strip() for line in text.split('\n')]
        text = '\n'.join(line for line in lines if line)

        return text

    @classmethod
    def _split_paragraphs(cls, text: str) -> List[str]:
        """按段落分割文本"""
        parts = cls.PARAGRAPH_PATTERN.split(text)
        return [p.strip() for p in parts if p.strip()]

    @classmethod
    def _split_long_paragraph(
        cls,
        text: str,
        chunk_size: int,
        overlap: int,
        min_chunk_size: int,
    ) -> List[str]:
        """
        将超长段落按句子边界切分

        策略：
        1. 优先在句子边界（。！？；）切分
        2. 句子过长时按子句切分
        3. 保证每个子块至少 min_chunk_size 字符
        """
        if len(text) <= chunk_size:
            return [text]

        # 1. 句子分割
        sentences = cls._split_sentences(text)
        if not sentences:
            # 无法识别句子，直接按长度切分
            return cls._split_by_length(text, chunk_size, overlap)

        # 2. 按 chunk_size 重组句子
        chunks: List[str] = []
        current: List[str] = []
        current_len = 0

        for sentence in sentences:
            sentence_len = len(sentence)

            # 如果句子本身就超过 chunk_size，需要进一步切分
            if sentence_len > chunk_size:
                # 先保存当前chunk
                if current:
                    chunks.append("".join(current))
                    current = []
                    current_len = 0

                # 超长句子按长度切分
                sub_chunks = cls._split_by_length(sentence, chunk_size, overlap)
                chunks.extend(sub_chunks[:-1] if len(sub_chunks) > 1 else [])
                if sub_chunks:
                    current = [sub_chunks[-1]]
                    current_len = len(sub_chunks[-1])
                continue

            # 正常句子加入当前chunk
            if current_len + sentence_len <= chunk_size:
                current.append(sentence)
                current_len += sentence_len
            else:
                # 当前chunk已满
                chunks.append("".join(current))
                current = [sentence]
                current_len = sentence_len

        # 保存最后一块
        if current:
            chunks.append("".join(current))

        return chunks

    @classmethod
    def _split_sentences(cls, text: str) -> List[str]:
        """
        将文本分割为句子

        注意：中文优先使用标点，英文使用句号+空格
        """
        if not text:
            return []

        sentences = []

        # 简单策略：按句子边界字符分割
        # 保留分隔符在句子末尾
        parts = re.split(r'([。！？；\n]+\s*)', text)

        current = ""
        for part in parts:
            current += part
            # 检查是否达到句子边界
            if re.search(r'[。！？；\n]+$', part):
                stripped = current.strip()
                if stripped:
                    sentences.append(stripped)
                current = ""

        # 处理剩余内容
        if current.strip():
            sentences.append(current.strip())

        return sentences

    @classmethod
    def _split_by_length(cls, text: str, chunk_size: int, overlap: int) -> List[str]:
        """按固定长度切分文本（兜底方案）"""
        if len(text) <= chunk_size:
            return [text]

        chunks = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = start + chunk_size
            chunk = text[start:end]

            # 尝试在单词边界（空格）处截断，减少单词断裂
            if end < text_len:
                last_space = chunk.rfind(' ')
                if last_space > chunk_size * 0.7:  # 如果在70%位置内有空格
                    chunk = chunk[:last_space]
                    end = start + last_space

            chunks.append(chunk)
            start = end - overlap if overlap > 0 else end

        return [c for c in chunks if c]

    @classmethod
    def _merge_small_chunks(
        cls,
        chunks: List[str],
        min_chunk_size: int,
        overlap: int,
    ) -> List[str]:
        """
        合并过小的块

        策略：将过小的块与前一个块合并
        如果第一个块就过小，则与后一个合并
        """
        if not chunks or len(chunks) == 1:
            return chunks

        result = []
        i = 0

        while i < len(chunks):
            chunk = chunks[i]

            # 如果当前块过小
            if len(chunk) < min_chunk_size:
                if i == 0:
                    # 第一个块，与后一个合并
                    if i + 1 < len(chunks):
                        merged = chunk + "\n" + chunks[i + 1]
                        result.append(merged)
                        i += 2
                    else:
                        result.append(chunk)
                        i += 1
                else:
                    # 与前一个合并
                    if result:
                        # 移除前一个的末尾overlap，合并新内容
                        prev = result.pop()
                        merged = prev + "\n" + chunk
                        result.append(merged)
                    else:
                        result.append(chunk)
                    i += 1
            else:
                result.append(chunk)
                i += 1

        return result

    @classmethod
    def extract_metadata(cls, text: str) -> dict:
        """
        从文本中提取元数据

        :return: dict，包含 title, summary, keywords 等
        """
        lines = text.split('\n')
        title = lines[0][:100] if lines else ""

        # 简单统计
        char_count = len(text)
        word_count = len(text.split())
        para_count = len([l for l in lines if l.strip()])

        return {
            "title": title,
            "char_count": char_count,
            "word_count": word_count,
            "para_count": para_count,
        }
