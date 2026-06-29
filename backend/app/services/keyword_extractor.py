# 关键词提取：jieba分词，支持问题意图识别和停用词过滤

import re
import logging
from typing import List, Set, Optional

logger = logging.getLogger(__name__)

# 尝试导入 jieba（可选依赖，未安装时自动回退到空格分词）
try:
    import jieba
    _JIEBA_AVAILABLE = True
except ImportError:
    _JIEBA_AVAILABLE = False
    logger.info("jieba 未安装，关键词提取将使用空格分词")
    jieba = None


# 元数据/统计类问题关键词
METADATA_KEYWORDS = [
    "知识库里面有什么", "知识库有什么", "有哪些文档", "有哪些文件",
    "知识库包含什么", "知识库包含哪些", "知识库的内容", "知识库内容",
    "有什么类型的文档", "什么类型的文件", "文档类型", "文件类型",
    "有多少文档", "多少文件", "文档数量", "文件数量",
    "知识库概况", "知识库总览", "知识库统计", "统计信息",
    "有哪些车型", "有哪些区域", "有哪些标签",
]

# 身份类问题关键词
IDENTITY_KEYWORDS = [
    "你是谁", "你叫什么", "你的名字", "介绍一下你自己", "自我介绍",
    "你是做什么的", "你是什么", "你的身份", "你是谁呀", "你叫什么名字",
    "what is your name", "who are you",
]

# 停用词表
STOP_WORDS: Set[str] = {
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一", "一个",
    "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有", "看", "好",
    "自己", "这", "他", "她", "它", "们", "那", "什么", "怎么", "如何", "为什么",
    "哪些", "哪个", "可以", "应该", "需要", "能", "能够", "吗", "呢", "啊", "吧",
    "请", "让", "把", "被", "对", "从", "用", "给", "向", "与", "或", "但",
    "中", "前", "后", "左", "右", "里", "外", "内", "间", "旁", "边",
    "还", "更", "最", "太", "只", "刚", "才", "又", "再", "经常", "已经",
    "这个", "那个", "这些", "那些", "这里", "那里", "这样", "那样",
    "问", "想", "知道", "了解", "查", "找", "搜", "分析", "解释",
}

# 问句模式
QUESTION_PATTERNS = [
    r"^(?:能不能|可以|能否|会不会|是不是|有没有|要不要)",
    r"^(?:告诉我|请问|想问|想了解|想知道|问一下)",
    r"^(?:帮我|帮我查|帮我找|帮我分析)",
]


class KeywordExtractor:
    """关键词提取器"""

    @staticmethod
    def extract_keywords(question: str, max_keywords: int = 10) -> List[str]:
        """
        从问题中提取关键词（jieba 分词 + 停用词过滤）

        :param question: 用户问题
        :param max_keywords: 最大关键词数量
        :return: 关键词列表
        """
        if not question:
            return []

        # 移除问句前缀
        cleaned = question
        for pattern in QUESTION_PATTERNS:
            cleaned = re.sub(pattern, "", cleaned)

        # 用 jieba 对中文文本进行分词；jieba 不可用时回退到空格分词
        if _JIEBA_AVAILABLE and jieba is not None:
            words = jieba.lcut(cleaned)
        else:
            words = cleaned.split()

        # 移除停用词、单字、纯标点
        keywords = []
        for w in words:
            w = w.strip()
            w = re.sub(r"[^\w\u4e00-\u9fff-]", "", w)
            if w and len(w) > 1 and w not in STOP_WORDS:
                keywords.append(w)

        return keywords[:max_keywords]

    @staticmethod
    def is_metadata_question(question: str) -> bool:
        """判断是否为元数据/统计类问题"""
        q = question.lower()
        return any(kw in q for kw in METADATA_KEYWORDS)

    @staticmethod
    def is_identity_question(question: str) -> bool:
        """判断是否为身份类问题"""
        q = question.lower()
        return any(kw in q for kw in IDENTITY_KEYWORDS)

    @staticmethod
    def get_question_type(question: str) -> str:
        """
        判断问题类型

        :return: "identity" | "metadata" | "normal"
        """
        if KeywordExtractor.is_identity_question(question):
            return "identity"
        if KeywordExtractor.is_metadata_question(question):
            return "metadata"
        return "normal"


# 预设回答模板
IDENTITY_ANSWER = """我是智能驾驶知识库问答助手，专门为您提供以下服务：

1. **文档问答**：基于知识库中的技术文档、设计规范、测试报告等资料，回答您关于智能驾驶相关的问题
2. **知识检索**：帮您查找和定位相关的技术文档和资料
3. **内容分析**：对文档内容进行深度分析和解读

我可以帮您解答关于智能驾驶系统的技术问题，请随时提问！"""

METADATA_ANSWER_TEMPLATE = """知识库当前包含以下内容：

- 文档总数：{doc_count} 份
- 文档类型：技术文档、设计规范、测试报告、会议记录等

如需了解具体内容，请直接向我提问！"""