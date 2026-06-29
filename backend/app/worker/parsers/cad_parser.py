# CAD图纸解析：ezdxf提取元数据，MiniCPM-V做视觉理解

import base64
import logging
import os
import tempfile
from typing import List, Dict, Any, Optional

import httpx

from .base import BaseParser

logger = logging.getLogger(__name__)


class CADParser(BaseParser):
    """
    CAD 图纸解析器
    - DWG/DXF 使用 ezdxf 提取元数据
    - 结合 MiniCPM-V-8B 进行图纸内容理解
    """

    def __init__(self):
        from app.config import settings
        self.settings = settings
        self._ezdxf_available = None

    def _check_ezdxf(self) -> bool:
        """检查 ezdxf 是否可用"""
        if self._ezdxf_available is None:
            try:
                import ezdxf
                self._ezdxf_available = True
                logger.info("ezdxf 可用")
            except ImportError:
                self._ezdxf_available = False
                logger.warning("ezdxf 库未安装，DWG 格式支持受限")
        return self._ezdxf_available

    def parse(self, file_path: str, file_type: str) -> List[Dict[str, Any]]:
        """
        解析工程图纸：ezdxf 元数据提取 + MiniCPM-V-8B 图纸理解
        """
        logger.info(f"[CADParser] 解析图纸 {file_path} (type={file_type})")

        # 1. 尝试使用 ezdxf 提取元数据
        dxf_metadata = self._extract_dxf_metadata(file_path, file_type)

        # 2. 转为图片后用 MiniCPM-V-8B 理解
        vision_description = self._extract_as_image_and_understand(file_path, file_type)

        # 3. 合并结果
        combined_content = self._combine_results(file_path, file_type, dxf_metadata, vision_description)

        if not combined_content:
            return self._fallback_metadata(file_path, file_type)

        chunks = self.chunk_text(combined_content, chunk_size=1000, overlap=200)

        return [
            {
                "content": chunk,
                "page_number": 1,
                "paragraph": f"{file_type.upper()} 工程图纸",
            }
            for chunk in chunks
        ]

    def _extract_dxf_metadata(self, file_path: str, file_type: str) -> Optional[str]:
        """使用 ezdxf 提取 DXF/DWG 元数据"""
        if file_type.lower() not in ("dxf", "dwg"):
            return None

        if not self._check_ezdxf():
            return None

        try:
            import ezdxf

            if file_type.lower() == "dwg":
                # DWG 需要先转为 DXF（ODA Converter 或其他工具）
                # 这里暂时只处理 DXF
                logger.info("DWG 文件建议先转换为 DXF 格式以获得完整支持")
                return None

            # 读取 DXF 文件
            doc = ezdxf.readfile(file_path)
            dxf_version = doc.dxfversion
            layers = list(doc.layers)
            entities_count = len(list(doc.modelspace()))

            metadata = f"""【DXF 图纸元数据】
CAD 版本: {dxf_version}
图层数量: {len(layers)}
实体数量: {entities_count}
图层列表: {', '.join([layer.dxf.name for layer in layers[:20]])}{'...' if len(layers) > 20 else ''}
"""

            return metadata

        except Exception as e:
            logger.warning(f"ezdxf 元数据提取失败: {e}")
        return None

    def _extract_as_image_and_understand(self, file_path: str, file_type: str) -> Optional[str]:
        """将图纸转为图片后用 MiniCPM-V-8B 理解"""
        try:
            if not self.settings.VISION_ENABLED:
                return None

            # 尝试将 DXF 转为图片
            image_path = self._convert_dxf_to_image(file_path)
            if not image_path or not os.path.exists(image_path):
                return None

            return self._call_vision_llm(image_path)

        except Exception as e:
            logger.warning(f"CAD 图纸图像理解失败: {e}")
        return None

    def _convert_dxf_to_image(self, file_path: str) -> Optional[str]:
        """将 DXF 转为图片"""
        try:
            import ezdxf
            from ezdxf import recover
            from PIL import Image, ImageDraw, ImageFont

            # 尝试读取 DXF/DWG
            try:
                doc = ezdxf.readfile(file_path)
            except Exception:
                # 尝试恢复损坏的文件
                try:
                    doc, _ = recover.readfile(file_path)
                except Exception as e:
                    logger.warning(f"无法读取 CAD 文件: {e}")
                    return None

            # 创建渲染尺寸
            width, height = 1920, 1080

            # 创建空白图片
            img = Image.new("RGB", (width, height), "white")
            draw = ImageDraw.Draw(img)

            # 获取 modelspace 并渲染基本图形
            msp = doc.modelspace()

            # 简单的实体渲染
            for entity in msp:
                try:
                    entity_type = entity.dxftype()

                    if entity_type == "LINE":
                        start = entity.dxf.start
                        end = entity.dxf.end
                        draw.line(
                            [(start.x % width, start.y % height), (end.x % width, end.y % height)],
                            fill="black", width=1
                        )

                    elif entity_type == "CIRCLE":
                        center = (entity.dxf.center.x % width, entity.dxf.center.y % height)
                        radius = min(entity.dxf.radius, 100)
                        draw.ellipse(
                            [center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius],
                            outline="black"
                        )

                    elif entity_type == "TEXT":
                        pos = (entity.dxf.insert.x % width, entity.dxf.insert.y % height)
                        text = str(entity.dxf.text)[:50]
                        draw.text(pos, text, fill="black")

                    elif entity_type == "MTEXT":
                        pos = (entity.dxf.insert.x % width, entity.dxf.insert.y % height)
                        text = str(entity.text)[:100] if hasattr(entity, "text") else ""
                        draw.text(pos, text, fill="black")

                except Exception:
                    pass

            # 保存临时图片
            temp_file = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            img.save(temp_file.name)
            temp_file.close()

            logger.info(f"CAD 图纸已转为图片: {temp_file.name}")
            return temp_file.name

        except Exception as e:
            logger.warning(f"DXF 转图片失败: {e}")
        return None

    def _call_vision_llm(self, image_path: str) -> Optional[str]:
        """调用 MiniCPM-V-8B 理解图纸图片"""
        try:
            with open(image_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode("utf-8")

            prompt = """请详细分析这张工程图纸图片，重点关注：
1. 图纸中的所有文字标注、尺寸数据
2. 符号、标记、图例的含义
3. 整体结构和技术内容
4. 任何可见的工程信息

请尽可能详细地描述，以便后续检索。"""

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
            logger.warning(f"MiniCPM-V 图纸理解失败: {e}")
        return None

    def _combine_results(
        self,
        file_path: str,
        file_type: str,
        dxf_metadata: Optional[str],
        vision_desc: Optional[str]
    ) -> str:
        """合并 CAD 解析结果"""
        parts = [f"[{file_type.upper()} 工程图纸] {os.path.basename(file_path)}"]

        if dxf_metadata:
            parts.append(dxf_metadata)

        if vision_desc:
            parts.append(f"【图纸内容理解】\n{vision_desc}")

        if not dxf_metadata and not vision_desc:
            parts.append("【提示】请将 CAD 图纸导出为 DXF/PDF/PNG 格式以获得更好的解析效果。")

        return "\n\n".join(parts)

    def _fallback_metadata(self, file_path: str, file_type: str) -> List[Dict[str, Any]]:
        """元数据降级"""
        file_size = os.path.getsize(file_path)
        return [{
            "content": f"[{file_type.upper()} 工程图纸] {os.path.basename(file_path)}\n文件大小: {file_size / 1024:.1f} KB\n由 ezdxf + MiniCPM-V-8B 处理。",
            "page_number": 1,
            "paragraph": f"{file_type.upper()} 工程图纸",
        }]
