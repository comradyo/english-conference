from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Iterable
from xml.etree import ElementTree

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.opc.constants import RELATIONSHIP_TYPE as RT


@dataclass(frozen=True)
class AppProperties:
    pages: int | None = None
    characters_with_spaces: int | None = None


class Validator:
    REQUIRED_PAGE_WIDTH_CM = 21.0
    REQUIRED_PAGE_HEIGHT_CM = 29.7
    REQUIRED_MARGIN_CM = 2.0
    REQUIRED_FONT_NAME = "Times New Roman"
    REQUIRED_FONT_SIZE_PT = 12.0
    REQUIRED_LINE_SPACING = 1.5
    MIN_PAGE_COUNT = 4
    MAX_PAGE_COUNT = 6
    MIN_CHARACTERS_WITH_SPACES = 6000
    CM_TOLERANCE = 0.08
    PT_TOLERANCE = 0.1

    EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
    KEYWORDS_PATTERN = re.compile(r"^\s*key\s*words?\s*[:.]?\s*(?P<keywords>.+)$", re.IGNORECASE)
    CAPTION_PREFIXES = ("рис.", "рисунок", "fig.", "figure", "table", "табл.")
    TITLE_SCAN_LIMIT = 15
    EMAIL_LINK_LABELS = {"email", "e-mail", "e mail"}

    def __init__(self, source: str | Path | BinaryIO):
        self.source = source
        self.source_path = Path(source) if isinstance(source, (str, Path)) else None
        self._docx_bytes = self._read_source_bytes(source)
        self.doc = Document(io.BytesIO(self._docx_bytes))
        self.app_properties = self._read_app_properties()
        self.errors = []
        self.errors_eng = []

    def validate(self):
        self.validate_global_requirements()
        return self.errors, self.errors_eng

    def validate_global_requirements(self):
        self.check_docx_extension()
        self.check_page_size()
        self.check_margins()
        self.check_orientation()
        self.check_volume()
        self.check_font_and_size()
        self.check_line_spacing()
        self.check_hyperlinks()
        self.check_section_breaks()

    @staticmethod
    def _read_source_bytes(source: str | Path | BinaryIO) -> bytes:
        if isinstance(source, (str, Path)):
            return Path(source).read_bytes()

        if hasattr(source, "seek"):
            try:
                source.seek(0)
            except (OSError, ValueError):
                pass

        content = source.read()

        if hasattr(source, "seek"):
            try:
                source.seek(0)
            except (OSError, ValueError):
                pass

        return content

    @staticmethod
    def _local_name(tag: str) -> str:
        return tag.rsplit("}", 1)[-1]

    @classmethod
    def _app_property_int(cls, values: dict[str, str], name: str) -> int | None:
        value = values.get(name)
        if value is None:
            return None
        try:
            return int(value)
        except ValueError:
            return None

    def _read_app_properties(self) -> AppProperties:
        try:
            with zipfile.ZipFile(io.BytesIO(self._docx_bytes)) as archive:
                app_xml = archive.read("docProps/app.xml")
        except (KeyError, zipfile.BadZipFile):
            return AppProperties()

        try:
            root = ElementTree.fromstring(app_xml)
        except ElementTree.ParseError:
            return AppProperties()

        values = {
            self._local_name(element.tag): element.text.strip()
            for element in root.iter()
            if element.text and element.text.strip()
        }
        return AppProperties(
            pages=self._app_property_int(values, "Pages"),
            characters_with_spaces=self._app_property_int(values, "CharactersWithSpaces"),
        )

    def _add_error(self, message_ru: str, message_en: str) -> None:
        if message_ru not in self.errors:
            self.errors.append(message_ru)
        if message_en not in self.errors_eng:
            self.errors_eng.append(message_en)

    # Убирает лишние пробелы
    @staticmethod
    def _normalize_text(text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    @classmethod
    def _has_visible_text(cls, text: str) -> bool:
        return bool(cls._normalize_text(text))

    @classmethod
    def _cm_matches(cls, actual_cm: float, expected_cm: float) -> bool:
        return abs(actual_cm - expected_cm) <= cls.CM_TOLERANCE

    @classmethod
    def _pt_matches(cls, actual_pt: float, expected_pt: float) -> bool:
        return abs(actual_pt - expected_pt) <= cls.PT_TOLERANCE

    def _iter_all_paragraphs(self) -> Iterable:
        yield from self.doc.paragraphs
        for table in self.doc.tables:
            yield from self._iter_table_paragraphs(table)

    @classmethod
    def _iter_table_paragraphs(cls, table) -> Iterable:
        for row in table.rows:
            for cell in row.cells:
                yield from cell.paragraphs
                for nested_table in cell.tables:
                    yield from cls._iter_table_paragraphs(nested_table)

    def _character_count_with_spaces(self) -> int:
        texts = [
            paragraph.text
            for paragraph in self._iter_all_paragraphs()
            if self._has_visible_text(paragraph.text)
        ]
        return len(" ".join(texts))

    @staticmethod
    def _run_contains_formula(run) -> bool:
        try:
            return bool(
                run._element.xpath(".//*[local-name()='oMath' or local-name()='oMathPara']")
                or run._element.xpath("ancestor::*[local-name()='oMath' or local-name()='oMathPara']")
            )
        except Exception:
            return False

    @classmethod
    def _hyperlink_text(cls, hyperlink_element) -> str:
        return cls._normalize_text("".join(hyperlink_element.xpath(".//*[local-name()='t']/text()")))

    def _hyperlink_target(self, hyperlink_element) -> str:
        relationship_id = hyperlink_element.get(
            "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
        )
        if not relationship_id:
            return ""

        relationship = self.doc.part.rels.get(relationship_id)
        if relationship is None:
            return ""

        return str(getattr(relationship, "target_ref", "") or "")

    @classmethod
    def _is_email_hyperlink(cls, text: str, target: str) -> bool:
        normalized_text = cls._normalize_text(text).lower()
        normalized_target = target.strip().lower()
        if normalized_target.startswith("mailto:"):
            return True
        if cls.EMAIL_PATTERN.search(text):
            return True
        return normalized_text in cls.EMAIL_LINK_LABELS

    # Итерируется по цепочке стилей (видимо, стили идут не массивом, а связным списком) 
    @staticmethod
    def _iter_style_chain(style):
        seen = set()
        current_style = style
        while current_style is not None and id(current_style) not in seen:
            yield current_style
            seen.add(id(current_style))
            current_style = current_style.base_style

    @classmethod
    def _style_font_name(cls, style) -> str | None:
        for current_style in cls._iter_style_chain(style):
            if current_style.font.name:
                return current_style.font.name
        return None

    @classmethod
    def _style_font_size_pt(cls, style) -> float | None:
        for current_style in cls._iter_style_chain(style):
            if current_style.font.size is not None:
                return current_style.font.size.pt
        return None

    @classmethod
    def _effective_run_font_name(cls, run, paragraph) -> str | None:
        if run.font.name:
            return run.font.name

        if run.style is not None:
            run_style_name = cls._style_font_name(run.style)
            if run_style_name:
                return run_style_name

        return cls._style_font_name(paragraph.style)

    @classmethod
    def _effective_run_font_size_pt(cls, run, paragraph) -> float | None:
        if run.font.size is not None:
            return run.font.size.pt

        if run.style is not None:
            run_style_size = cls._style_font_size_pt(run.style)
            if run_style_size is not None:
                return run_style_size

        return cls._style_font_size_pt(paragraph.style)

    # Вычисляет, какое выравнивание используется в параграфе
    @classmethod
    def _effective_alignment(cls, paragraph):
        if paragraph.alignment is not None:
            return paragraph.alignment

        for style in cls._iter_style_chain(paragraph.style):
            alignment = style.paragraph_format.alignment
            if alignment is not None:
                return alignment

        return None

    @classmethod
    def _effective_line_spacing(cls, paragraph):
        spacing = paragraph.paragraph_format.line_spacing
        rule = paragraph.paragraph_format.line_spacing_rule
        if spacing is not None or rule is not None:
            return spacing, rule

        for style in cls._iter_style_chain(paragraph.style):
            spacing = style.paragraph_format.line_spacing
            rule = style.paragraph_format.line_spacing_rule
            if spacing is not None or rule is not None:
                return spacing, rule

        return None, None

    @staticmethod
    def _line_spacing_multiplier(line_spacing) -> float | None:
        if line_spacing is None:
            return None
        if hasattr(line_spacing, "pt"):
            return None

        try:
            return float(line_spacing)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _has_required_line_spacing(cls, paragraph) -> bool:
        spacing, rule = cls._effective_line_spacing(paragraph)
        multiplier = cls._line_spacing_multiplier(spacing)

        if spacing is None and rule is None:
            return False
        if rule == WD_LINE_SPACING.ONE_POINT_FIVE:
            return multiplier is None or abs(multiplier - cls.REQUIRED_LINE_SPACING) <= 0.01
        if rule == WD_LINE_SPACING.MULTIPLE:
            return multiplier is not None and abs(multiplier - cls.REQUIRED_LINE_SPACING) <= 0.01
        if rule is None and multiplier is not None:
            return abs(multiplier - cls.REQUIRED_LINE_SPACING) <= 0.01

        return False

    # Проверяет, что стиль (или предки, от которых он наследуется), является полужирным
    @classmethod
    def _style_font_bold(cls, style) -> bool | None:
        for current_style in cls._iter_style_chain(style):
            if current_style.font.bold is not None:
                return current_style.font.bold
        return None

    # Проверяет, что стиль (или предки, от которых он наследуется), является курсивным
    @classmethod
    def _style_font_italic(cls, style) -> bool | None:
        for current_style in cls._iter_style_chain(style):
            if current_style.font.italic is not None:
                return current_style.font.italic
        return None

    # Вычисляет эффективный курсив для run-а с учётом цепочки стилей
    @classmethod
    def _run_is_italic(cls, run, paragraph) -> bool:
        if run.italic is not None:
            return bool(run.italic)

        if run.style is not None:
            run_style_italic = cls._style_font_italic(run.style)
            if run_style_italic is not None:
                return run_style_italic

        paragraph_style_italic = cls._style_font_italic(paragraph.style)
        if paragraph_style_italic is not None:
            return paragraph_style_italic

        return False

    # Проверяет, что в параграфе есть жирный текст
    @classmethod
    def _paragraph_has_bold_text(cls, paragraph) -> bool:
        paragraph_style_bold = cls._style_font_bold(paragraph.style)

        for run in paragraph.runs:
            if not cls._normalize_text(run.text):
                continue

            if run.bold is not None:
                if run.bold:
                    return True
                continue

            if run.style is not None:
                run_style_bold = cls._style_font_bold(run.style)
                if run_style_bold is not None:
                    if run_style_bold:
                        return True
                    continue

            if paragraph_style_bold:
                return True

        return False

    # Проверяет, что параграф является центрированным
    @classmethod
    def _is_centered(cls, paragraph) -> bool:
        return cls._effective_alignment(paragraph) == WD_ALIGN_PARAGRAPH.CENTER

    # Проверяет, что параграф является подписью к изображению/таблице
    @classmethod
    def _is_caption_paragraph(cls, paragraph) -> bool:
        text = cls._normalize_text(paragraph.text).lower()
        return text.startswith(cls.CAPTION_PREFIXES)

    # Первые *limit* штук непустых параграфов
    @classmethod
    def _leading_non_empty_paragraphs(cls, paragraphs, limit: int):
        found = []
        for paragraph in paragraphs:
            if cls._normalize_text(paragraph.text):
                found.append(paragraph)
            if len(found) >= limit:
                break
        return found

    # Формат файла
    def check_docx_extension(self):
        if self.source_path is None:
            return
        if self.source_path.suffix.lower() != ".docx":
            self._add_error(
                "Статья должна быть представлена в виде файла формата .docx",
                "The article must be submitted as a .docx file",
            )

    # Формат страницы
    def check_page_size(self):
        for section in self.doc.sections:
            dimensions = sorted((section.page_width.cm, section.page_height.cm))
            if not (
                self._cm_matches(dimensions[0], self.REQUIRED_PAGE_WIDTH_CM)
                and self._cm_matches(dimensions[1], self.REQUIRED_PAGE_HEIGHT_CM)
            ):
                self._add_error(
                    "Материалы должны быть представлены на формате А4",
                    "The article must use A4 page size",
                )
                return

    # Поля
    def check_margins(self):
        for section in self.doc.sections:
            if not self._cm_matches(section.top_margin.cm, self.REQUIRED_MARGIN_CM):
                self._add_error(
                    "Отступ сверху должен равняться 2 см",
                    "The top margin must be 2 cm",
                )
            if not self._cm_matches(section.bottom_margin.cm, self.REQUIRED_MARGIN_CM):
                self._add_error(
                    "Отступ снизу должен равняться 2 см",
                    "The bottom margin must be 2 cm",
                )
            if not self._cm_matches(section.left_margin.cm, self.REQUIRED_MARGIN_CM):
                self._add_error(
                    "Отступ слева должен равняться 2 см",
                    "The left margin must be 2 cm",
                )
            if not self._cm_matches(section.right_margin.cm, self.REQUIRED_MARGIN_CM):
                self._add_error(
                    "Отступ справа должен равняться 2 см",
                    "The right margin must be 2 cm",
                )

    # Ориентация страниц
    def check_orientation(self):
        for section in self.doc.sections:
            if section.orientation != WD_ORIENT.PORTRAIT:
                self._add_error(
                    "Ориентация страниц должна быть книжной",
                    "The orientation of the pages must be portrait",
                )
                return

    # Объем статьи
    def check_volume(self):
        pages = self.app_properties.pages
        if pages is not None and not (self.MIN_PAGE_COUNT <= pages <= self.MAX_PAGE_COUNT):
            self._add_error(
                "Общий объем статьи должен составлять 4-6 страниц",
                "The total article volume must be 4-6 pages",
            )

        characters_with_spaces = self._character_count_with_spaces()
        if characters_with_spaces < self.MIN_CHARACTERS_WITH_SPACES:
            self._add_error(
                "Минимальный объем статьи должен составлять 6000 знаков с пробелами",
                "The article must contain at least 6000 characters including spaces",
            )

    # Шрифт и размер
    def check_font_and_size(self):
        for paragraph in self._iter_all_paragraphs():
            for run in paragraph.runs:
                if not self._has_visible_text(run.text) or self._run_contains_formula(run):
                    continue

                font_name = self._effective_run_font_name(run, paragraph)
                if font_name and font_name.lower() != self.REQUIRED_FONT_NAME.lower():
                    self._add_error(
                        "В тексте статьи необходимо использовать шрифт Times New Roman, за исключением математических формул",
                        "The Times New Roman font should be used in the article text, except for mathematical formulas",
                    )
                    return

                font_size_pt = self._effective_run_font_size_pt(run, paragraph)
                if font_size_pt is not None and not self._pt_matches(font_size_pt, self.REQUIRED_FONT_SIZE_PT):
                    self._add_error(
                        "Размер шрифта должен быть 12",
                        "The font size must be 12",
                    )
                    return

    # Межстрочный интервал
    def check_line_spacing(self):
        for paragraph in self._iter_all_paragraphs():
            if not self._has_visible_text(paragraph.text):
                continue
            if not self._has_required_line_spacing(paragraph):
                self._add_error(
                    "Межстрочный интервал должен равняться 1.5",
                    "The line spacing must be 1.5",
                )
                return

    # Гиперссылки
    def check_hyperlinks(self):
        for hyperlink_element in self.doc.element.xpath(".//*[local-name()='hyperlink']"):
            text = self._hyperlink_text(hyperlink_element)
            target = self._hyperlink_target(hyperlink_element)
            if self._is_email_hyperlink(text, target):
                continue

            self._add_error(
                "Применять гиперссылки в тексте не допускается",
                "Hyperlinks are not allowed in the article text",
            )
            return

        if any(
            rel.reltype == RT.HYPERLINK and not self._is_email_hyperlink("", str(rel.target_ref))
            for rel in self.doc.part.rels.values()
        ):
            self._add_error(
                "Применять гиперссылки в тексте не допускается",
                "Hyperlinks are not allowed in the article text",
            )

    # Разрывы разделов
    def check_section_breaks(self):
        if len(self.doc.sections) > 1:
            self._add_error(
                "Разрывы разделов внутри текста не допускаются",
                "Section breaks inside the text are not allowed",
            )

    # Абзацный отступ
    def check_first_line_indent(self):
        for p in self.doc.paragraphs:
            if not self._normalize_text(p.text):
                continue
            if self._is_centered(p) or self._is_caption_paragraph(p):
                continue
            indent = p.paragraph_format.first_line_indent
            if indent and round(indent.cm, 2) != 1.25:
                self.errors.append("Абзацный отступ должен равняться 1.25 единицам")
                self.errors_eng.append("The paragraph indentation must be 1.25 units")
                return

    # Email (курсив)
    def check_email(self):
        found = False

        for p in self.doc.paragraphs:
            if self.EMAIL_PATTERN.search(p.text):
                found = True
                for run in p.runs:
                    if self.EMAIL_PATTERN.search(run.text):
                        if not self._run_is_italic(run, p):
                            self.errors.append("Email должен быть напечатан курсивом")
                            self.errors_eng.append("The email must be printed in italics")
                break

        if not found:
            self.errors.append("Email автора не найден")
            self.errors_eng.append("The author's email was not found")

    # Название статьи (по центру, жирное)
    def check_title(self):
        for p in self._leading_non_empty_paragraphs(self.doc.paragraphs, self.TITLE_SCAN_LIMIT):
            text = self._normalize_text(p.text)
            if not self._is_centered(p):
                continue
            if self.EMAIL_PATTERN.search(text):
                continue
            if text.lower().startswith(("abstract", "keywords", "key words")):
                continue

            bold_found = self._paragraph_has_bold_text(p)
            if not bold_found:
                self.errors.append("Для названия статьи необходимо использовать полужирное начертание")
                self.errors_eng.append("The title of the article must be printed in bold")
            return
        self.errors.append("Название статьи не найдено")
        self.errors_eng.append("The title of the article was not found")

    # Ключевые слова
    def check_keywords(self):
        for p in self.doc.paragraphs:
            match = self.KEYWORDS_PATTERN.match(p.text)
            if match:
                keywords_text = match.group("keywords").strip()
                if ";" in keywords_text:
                    self.errors.append("Разделителем ключевых слов должна быть запятая")
                    self.errors_eng.append("Keywords must be separated by commas")
                    return

                keywords = [keyword.strip() for keyword in keywords_text.split(",") if keyword.strip()]
                if not (5 <= len(keywords) <= 10):
                    self.errors.append("Ключевых слов должно быть от 5 до 10")
                    self.errors_eng.append("There should be from 5 to 10 keywords")
                return
        self.errors.append("Ключевые слова не найдены")
        self.errors_eng.append("Keywords of the article were not found")

    # Аннотация
    def check_annotation(self):
        for p in self.doc.paragraphs:
            if "abstract." in p.text.lower():
                abstract_text = p.text.lower().strip()
                abstract_text = abstract_text.replace(" ", "")
                text_len = len(abstract_text) - len("abstract.")
                if not (300 <= text_len <= 500):
                    self.errors.append("Аннотация на английском должна содержать от 300 до 500 знаков без учёта пробелов")
                    self.errors_eng.append("The abstract in English should contain from 300 to 500 characters without spaces")
                italic = any(run.italic for run in p.runs)
                if not italic:
                    self.errors.append("Аннотация должна быть напечатана курсивом")
                    self.errors_eng.append("The abstract should be printed in italics")
                return
        self.errors.append("Аннотация не найдена")
        self.errors_eng.append("The abstract was not found")

    # Формат ссылок
    def check_reference_format(self):
        pattern = r"\[\d+(,\s?с\.\s?\d+)?(;\s?\d+(,\s?с\.\s?\d+)?)?\]"
        for p in self.doc.paragraphs:
            if p.text == "REFERENCES":
                return
            matches = re.findall(r"\[.*?]", p.text)
            for m in matches:
                if not re.match(pattern, m):
                    self.errors.append(f"Неверный формат ссылки: {m}")
                    self.errors_eng.append(f"Invalid reference format: {m}")

    # Список литературы
    def check_references_count(self):
        start = False
        count = 0
        for p in self.doc.paragraphs:
            lower_text = p.text.lower()
            if "references" in lower_text or "список литературы" in lower_text: # TODO: нужно ли на английском?
                start = True
                continue
            if start:
                if p.text.strip() == "":
                    break
                count += 1

        if count < 5:
            self.errors.append("Список литературы должен содержать не менее 5 источников")
            self.errors_eng.append("The list of references should contain at least 5 sources.")
