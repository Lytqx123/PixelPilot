import csv
import io
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List

from sqlalchemy.ext.asyncio import AsyncSession
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.lib.pagesizes import A4

from app.models.user import User

logger = logging.getLogger(__name__)

CST = timezone(timedelta(hours=8))

try:
    pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
    CN_FONT = 'STSong-Light'
    logger.info("中文字体 STSong-Light 注册成功（reportlab 内置 CID 字体）")
except Exception as e:
    logger.warning(f"CID 字体注册失败: {e}，将使用 Helvetica 作为降级方案")
    CN_FONT = 'Helvetica'


class ExportService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def export_qa_results(
        self, user: User, query: Optional[str], document_ids: Optional[List[int]], fmt: str
    ) -> bytes:
        """根据查询内容和文档ID导出问答结果"""
        export_time = datetime.now(tz=CST)

        if fmt == "csv":
            return self._export_csv(query, document_ids, export_time)
        else:
            return self._export_pdf(query, document_ids, export_time)

    def _export_pdf(
        self,
        query: Optional[str],
        document_ids: Optional[List[int]],
        export_time: datetime,
    ) -> bytes:
        """生成 PDF 导出文件（支持中文，文本自动换行不截断）"""
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        margin_left = 40
        usable_width = width - margin_left - 40
        bottom_margin = 60

        c.setFont(CN_FONT, 16)
        c.drawString(margin_left, height - 40, "PixelPulse - 对话导出")

        c.setFont(CN_FONT, 10)
        c.drawString(
            margin_left,
            height - 65,
            f"导出时间: {export_time.strftime('%Y-%m-%d %H:%M:%S')}",
        )

        y = height - 90

        if query:
            qa_pairs = query.split("; ")
            c.setFont(CN_FONT, 12)
            c.drawString(margin_left, y, "对话内容")
            y -= 24

            for i, pair in enumerate(qa_pairs, 1):
                if not pair.strip():
                    continue

                if "|" in pair:
                    parts = pair.split("|", 1)
                    q_text = parts[0].strip()
                    a_text = parts[1].strip() if len(parts) > 1 else ""
                else:
                    q_text = pair.strip()
                    a_text = ""

                q_label = f"[Q{i}]"
                c.setFont(CN_FONT, 11)
                y -= 4
                c.drawString(margin_left, y, q_label)
                label_w = pdfmetrics.stringWidth(q_label, CN_FONT, 11) + 6
                y = self._draw_multiline_text(
                    c, q_text, CN_FONT, 10, margin_left + label_w,
                    usable_width - label_w, y, bottom_margin, height,
                )

                if a_text:
                    a_label = f"[A{i}]"
                    c.setFont(CN_FONT, 11)
                    c.drawString(margin_left + 20, y, a_label)
                    label_w = pdfmetrics.stringWidth(a_label, CN_FONT, 11) + 6
                    y = self._draw_multiline_text(
                        c, a_text, CN_FONT, 10, margin_left + 20 + label_w,
                        usable_width - 20 - label_w, y, bottom_margin, height,
                    )

                y -= 10

                if y < bottom_margin:
                    c.showPage()
                    y = height - 40

        if document_ids:
            if y < bottom_margin + 20:
                c.showPage()
                y = height - 40
            c.setFont(CN_FONT, 9)
            c.drawString(
                margin_left, y,
                f"参考文档 ID: {', '.join(str(d) for d in document_ids[:20])}",
            )

        c.save()
        return buffer.getvalue()

    @staticmethod
    def _draw_multiline_text(
        c: canvas.Canvas, text: str, font_name: str, font_size: int,
        start_x: float, max_width: float, start_y: float,
        bottom_margin: float, page_height: float,
    ) -> float:
        c.setFont(font_name, font_size)
        line_height = font_size * 1.8
        y = start_y

        lines = ExportService._split_text_to_lines(text, font_name, font_size, max_width)

        for line in lines:
            if y < bottom_margin:
                c.showPage()
                c.setFont(font_name, font_size)
                y = page_height - 40
            c.drawString(start_x, y, line)
            y -= line_height

        return y

    @staticmethod
    def _split_text_to_lines(
        text: str, font_name: str, font_size: int, max_width: float,
    ) -> list:
        if not text:
            return []

        lines = []
        current_line = ""

        for ch in text:
            test_line = current_line + ch
            test_width = pdfmetrics.stringWidth(test_line, font_name, font_size)
            if test_width > max_width and current_line:
                lines.append(current_line)
                current_line = ch
            else:
                current_line = test_line

        if current_line:
            lines.append(current_line)

        return lines

    def _export_csv(
        self,
        query: Optional[str],
        document_ids: Optional[List[int]],
        export_time: datetime,
    ) -> bytes:
        """生成 CSV 导出文件"""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["导出信息", ""])
        writer.writerow(["导出时间", export_time.strftime('%Y-%m-%d %H:%M:%S')])
        writer.writerow([])

        if query:
            qa_pairs = query.split("; ")
            writer.writerow(["序号", "问题", "回答"])
            for i, pair in enumerate(qa_pairs, 1):
                if "|" in pair:
                    q, a = pair.split("|", 1)
                else:
                    q, a = pair, ""
                writer.writerow([i, q.strip(), a.strip()])
            writer.writerow([])

        if document_ids:
            writer.writerow(["相关文档ID", ", ".join(str(d) for d in document_ids)])

        return output.getvalue().encode("utf-8-sig")

