from __future__ import annotations

import io
import re
import unicodedata
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO, Iterable
from xml.etree import ElementTree

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.opc.constants import RELATIONSHIP_TYPE as RT


@dataclass(frozen=True)
class AppProperties:
    pages: int | None = None
    characters_with_spaces: int | None = None


@dataclass(frozen=True)
class ParagraphItem:
    number: int
    paragraph: Any
    text: str


@dataclass(frozen=True)
class ArticleStructure:
    items: list[ParagraphItem]
    udk_pos: int | None = None
    ru_title_pos: int | None = None
    ru_abstract_pos: int | None = None
    ru_keywords_pos: int | None = None
    en_title_pos: int | None = None
    en_abstract_pos: int | None = None
    en_keywords_pos: int | None = None
    main_text_pos: int | None = None
    sources_pos: int | None = None


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
    UDK_PATTERN = re.compile(r"^\s*УДК\s+(?P<code>\S.+)$", re.IGNORECASE)
    RU_ABSTRACT_PATTERN = re.compile(r"^\s*Аннотация\s*[.:]\s*(?P<body>.+)$", re.IGNORECASE)
    EN_ABSTRACT_PATTERN = re.compile(r"^\s*Abstract\s*[.:]\s*(?P<body>.+)$", re.IGNORECASE)
    RU_KEYWORDS_PATTERN = re.compile(r"^\s*Ключевые\s+слова\s*[:.]\s*(?P<keywords>.+)$", re.IGNORECASE)
    EN_KEYWORDS_PATTERN = re.compile(r"^\s*key\s*words?\s*[:.]?\s*(?P<keywords>.+)$", re.IGNORECASE)
    KEYWORDS_PATTERN = EN_KEYWORDS_PATTERN
    SOURCES_HEADING_PATTERN = re.compile(r"^\s*(Список\s+источников|References)\s*$", re.IGNORECASE)
    SPIN_PATTERN = re.compile(r"^\s*SPIN(?:-код|-code)?\s*:\s*(?P<code>\d{4}-\d{4})\s*$", re.IGNORECASE)
    WORD_PATTERN = re.compile(r"[A-Za-zА-Яа-яЁё]+(?:[-'][A-Za-zА-Яа-яЁё]+)?")
    RU_NAME_WORD_PATTERN = re.compile(r"[А-ЯЁ][А-Яа-яЁё-]+")
    EN_NAME_WORD_PATTERN = re.compile(r"[A-Z][A-Za-z'-]+")
    ABBREVIATION_PATTERN = re.compile(r"\b[A-ZА-ЯЁ]{2,}\b")
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
        self.structure = self._build_article_structure()
        self.validate_article_structure()
        self.validate_metadata_and_authors()
        self.validate_annotations_and_keywords()
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

    def validate_article_structure(self):
        structure = self.structure
        if structure.udk_pos is None:
            self._add_error("УДК не найден", "UDC was not found")
        if structure.ru_title_pos is None:
            self._add_error("Заголовок статьи не найден", "The article title was not found")
        if not self._ru_author_items(structure):
            self._add_error("Сведения об авторах не найдены", "Author information was not found")
        if structure.ru_abstract_pos is None:
            self._add_error("Аннотация не найдена", "The abstract was not found")
        if structure.ru_keywords_pos is None:
            self._add_error("Ключевые слова не найдены", "Keywords were not found")
        if structure.en_title_pos is None:
            self._add_error(
                "Заголовок статьи на английском языке не найден",
                "The English article title was not found",
            )
        if not self._en_author_items(structure):
            self._add_error(
                "Сведения об авторах на английском языке не найдены",
                "English author information was not found",
            )
        if structure.en_abstract_pos is None:
            self._add_error(
                "Аннотация на английском языке не найдена",
                "The English abstract was not found",
            )
        if structure.en_keywords_pos is None:
            self._add_error(
                "Ключевые слова на английском языке не найдены",
                "English keywords were not found",
            )
        if structure.main_text_pos is None:
            self._add_error("Основной текст статьи не найден", "The main article text was not found")
        if structure.sources_pos is None:
            self._add_error("Список источников не найден", "The list of sources was not found")

        ordered_positions = [
            position
            for position in (
                structure.udk_pos,
                structure.ru_title_pos,
                structure.ru_abstract_pos,
                structure.ru_keywords_pos,
                structure.en_title_pos,
                structure.en_abstract_pos,
                structure.en_keywords_pos,
                structure.main_text_pos,
                structure.sources_pos,
            )
            if position is not None
        ]
        if ordered_positions != sorted(ordered_positions):
            self._add_error(
                "Структура статьи должна соответствовать порядку из требований",
                "The article structure must follow the required order",
            )

    def validate_metadata_and_authors(self):
        self.check_udk()
        self.check_titles_metadata()
        self.check_authors_metadata()

    def validate_annotations_and_keywords(self):
        self.check_annotations()
        self.check_keywords_metadata()

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

    def _paragraph_items(self) -> list[ParagraphItem]:
        return [
            ParagraphItem(number=index, paragraph=paragraph, text=self._normalize_text(paragraph.text))
            for index, paragraph in enumerate(self.doc.paragraphs)
            if self._normalize_text(paragraph.text)
        ]

    @staticmethod
    def _item_at(structure: ArticleStructure, position: int | None) -> ParagraphItem | None:
        if position is None:
            return None
        return structure.items[position]

    @staticmethod
    def _find_position(items: list[ParagraphItem], predicate, start: int = 0, end: int | None = None) -> int | None:
        upper_bound = len(items) if end is None else min(end, len(items))
        for position in range(max(start, 0), upper_bound):
            if predicate(items[position]):
                return position
        return None

    @staticmethod
    def _next_position(start: int | None) -> int:
        return 0 if start is None else start + 1

    def _build_article_structure(self) -> ArticleStructure:
        items = self._paragraph_items()
        udk_pos = self._find_position(items, lambda item: self.UDK_PATTERN.match(item.text) is not None)
        ru_abstract_pos = self._find_position(
            items,
            lambda item: self.RU_ABSTRACT_PATTERN.match(item.text) is not None,
            self._next_position(udk_pos),
        )
        ru_keywords_pos = self._find_position(
            items,
            lambda item: self.RU_KEYWORDS_PATTERN.match(item.text) is not None,
            self._next_position(ru_abstract_pos),
        )
        en_abstract_pos = self._find_position(
            items,
            lambda item: self.EN_ABSTRACT_PATTERN.match(item.text) is not None,
            self._next_position(ru_keywords_pos),
        )
        en_keywords_pos = self._find_position(
            items,
            lambda item: self.EN_KEYWORDS_PATTERN.match(item.text) is not None,
            self._next_position(en_abstract_pos),
        )
        sources_pos = self._find_position(
            items,
            lambda item: self.SOURCES_HEADING_PATTERN.match(item.text) is not None,
            self._next_position(en_keywords_pos),
        )

        ru_title_pos = self._first_content_position(items, self._next_position(udk_pos), ru_abstract_pos)
        en_title_pos = self._first_content_position(items, self._next_position(ru_keywords_pos), en_abstract_pos)
        main_text_pos = self._first_content_position(items, self._next_position(en_keywords_pos), sources_pos)

        return ArticleStructure(
            items=items,
            udk_pos=udk_pos,
            ru_title_pos=ru_title_pos,
            ru_abstract_pos=ru_abstract_pos,
            ru_keywords_pos=ru_keywords_pos,
            en_title_pos=en_title_pos,
            en_abstract_pos=en_abstract_pos,
            en_keywords_pos=en_keywords_pos,
            main_text_pos=main_text_pos,
            sources_pos=sources_pos,
        )

    def _first_content_position(self, items: list[ParagraphItem], start: int, end: int | None) -> int | None:
        return self._find_position(
            items,
            lambda item: not self._is_spin_line(item.text) and not self._is_affiliation_line(item.text),
            start,
            end,
        )

    @classmethod
    def _slice_items(
        cls,
        structure: ArticleStructure,
        start_pos: int | None,
        end_pos: int | None,
    ) -> list[ParagraphItem]:
        if start_pos is None:
            return []
        start = start_pos + 1
        end = len(structure.items) if end_pos is None else end_pos
        if start >= end:
            return []
        return structure.items[start:end]

    @classmethod
    def _is_spin_line(cls, text: str) -> bool:
        return text.lower().startswith(("spin-код", "spin-code", "spin:"))

    @staticmethod
    def _is_affiliation_line(text: str) -> bool:
        return re.match(r"^\s*\d+\s+\S", text) is not None

    @classmethod
    def _is_ru_author_line(cls, item: ParagraphItem) -> bool:
        if cls._is_spin_line(item.text) or cls._is_affiliation_line(item.text):
            return False
        return len(cls._author_name_words(item.text, "ru")) >= 3

    @classmethod
    def _is_en_author_line(cls, item: ParagraphItem) -> bool:
        if cls._is_spin_line(item.text) or cls._is_affiliation_line(item.text):
            return False
        return len(cls._author_name_words(item.text, "en")) >= 3

    @classmethod
    def _author_name_part(cls, text: str) -> str:
        text_without_email = cls.EMAIL_PATTERN.sub(" ", text)
        text_without_email = re.sub(r"\be-?mail\b", " ", text_without_email, flags=re.IGNORECASE)
        return re.split(r"\d", text_without_email, maxsplit=1)[0]

    @classmethod
    def _author_name_words(cls, text: str, lang: str) -> list[str]:
        name_part = cls._author_name_part(text)
        pattern = cls.RU_NAME_WORD_PATTERN if lang == "ru" else cls.EN_NAME_WORD_PATTERN
        return pattern.findall(name_part)

    def _ru_author_items(self, structure: ArticleStructure) -> list[ParagraphItem]:
        return [
            item
            for item in self._slice_items(structure, structure.ru_title_pos, structure.ru_abstract_pos)
            if self._is_ru_author_line(item)
        ]

    def _en_author_items(self, structure: ArticleStructure) -> list[ParagraphItem]:
        return [
            item
            for item in self._slice_items(structure, structure.en_title_pos, structure.en_abstract_pos)
            if self._is_en_author_line(item)
        ]

    def _ru_affiliation_items(self, structure: ArticleStructure) -> list[ParagraphItem]:
        return [
            item
            for item in self._slice_items(structure, structure.ru_title_pos, structure.ru_abstract_pos)
            if self._is_affiliation_line(item.text)
        ]

    def _en_affiliation_items(self, structure: ArticleStructure) -> list[ParagraphItem]:
        return [
            item
            for item in self._slice_items(structure, structure.en_title_pos, structure.en_abstract_pos)
            if self._is_affiliation_line(item.text)
        ]

    @staticmethod
    def _has_cyrillic(text: str) -> bool:
        return re.search(r"[А-Яа-яЁё]", text) is not None

    @staticmethod
    def _has_latin(text: str) -> bool:
        return re.search(r"[A-Za-z]", text) is not None

    @staticmethod
    def _has_foreign_letters(text: str) -> bool:
        for char in text:
            if not unicodedata.category(char).startswith("L"):
                continue
            if re.match(r"[A-Za-zА-Яа-яЁё]", char):
                continue
            return True
        return False

    @classmethod
    def _word_count(cls, text: str) -> int:
        return len(cls.WORD_PATTERN.findall(text))

    @staticmethod
    def _paragraph_contains_formula(paragraph) -> bool:
        try:
            return bool(paragraph._element.xpath(".//*[local-name()='oMath' or local-name()='oMathPara']"))
        except Exception:
            return False

    @classmethod
    def _superscript_text(cls, paragraph) -> str:
        parts = []
        for run in paragraph.runs:
            if run.font.superscript and cls._normalize_text(run.text):
                parts.append(run.text)
        return "".join(parts)

    @classmethod
    def _superscript_affiliation_numbers(cls, paragraph) -> set[str]:
        return set(re.findall(r"\d+", cls._superscript_text(paragraph)))

    @classmethod
    def _has_corresponding_author_marker(cls, paragraph) -> bool:
        return "*" in cls._superscript_text(paragraph)

    def _paragraph_mailto_targets(self, paragraph) -> list[str]:
        targets = []
        for hyperlink_element in paragraph._p.xpath(".//*[local-name()='hyperlink']"):
            target = self._hyperlink_target(hyperlink_element)
            if target.lower().startswith("mailto:"):
                targets.append(target)
        return targets

    def _paragraph_has_email(self, paragraph) -> bool:
        return bool(self.EMAIL_PATTERN.search(paragraph.text) or self._paragraph_mailto_targets(paragraph))

    @staticmethod
    def _affiliation_number(item: ParagraphItem) -> str | None:
        match = re.match(r"^\s*(\d+)\s+", item.text)
        return match.group(1) if match else None

    @staticmethod
    def _has_organization_city_country(item: ParagraphItem) -> bool:
        rest = re.sub(r"^\s*\d+\s+", "", item.text).strip()
        parts = [part.strip() for part in rest.split(",") if part.strip()]
        return len(parts) >= 3

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

    # УДК
    def check_udk(self):
        item = self._item_at(self.structure, self.structure.udk_pos)
        if item is None:
            return
        match = self.UDK_PATTERN.match(item.text)
        if match is None or not re.match(r"^\d[\d./-]*(?:\s*[:;]\s*[\d./-]+)*$", match.group("code").strip()):
            self._add_error(
                "УДК должен быть указан в формате «УДК 520.607»",
                "UDC must be specified in the format 'UDC 520.607'",
            )

    # Заголовки
    def check_titles_metadata(self):
        ru_title = self._item_at(self.structure, self.structure.ru_title_pos)
        if ru_title is not None:
            title_text = ru_title.text
            word_count = self._word_count(title_text)
            if not (6 <= word_count <= 15):
                self._add_error(
                    "Заголовок статьи должен содержать от 6 до 15 слов",
                    "The article title must contain from 6 to 15 words",
                )
            if len(re.findall(r"[.!?]", title_text)) > 1:
                self._add_error(
                    "Заголовок статьи не должен состоять из нескольких предложений",
                    "The article title must not consist of several sentences",
                )
            if self._paragraph_contains_formula(ru_title.paragraph):
                self._add_error(
                    "Заголовок статьи не должен содержать математические формулы",
                    "The article title must not contain mathematical formulas",
                )
            if self._has_foreign_letters(title_text):
                self._add_error(
                    "Заголовок статьи должен содержать только буквы русского и латинского алфавитов",
                    "The article title must contain only Russian and Latin letters",
                )

        en_title = self._item_at(self.structure, self.structure.en_title_pos)
        if en_title is not None:
            if not self._has_latin(en_title.text):
                self._add_error(
                    "Заголовок статьи на английском языке должен быть указан латиницей",
                    "The English article title must be written in Latin letters",
                )
            if self._has_cyrillic(en_title.text):
                self._add_error(
                    "Заголовок статьи на английском языке не должен содержать кириллицу",
                    "The English article title must not contain Cyrillic letters",
                )

    # Сведения об авторах
    def check_authors_metadata(self):
        ru_authors = self._ru_author_items(self.structure)
        en_authors = self._en_author_items(self.structure)
        ru_affiliations = self._ru_affiliation_items(self.structure)
        en_affiliations = self._en_affiliation_items(self.structure)

        if len(ru_authors) > 6:
            self._add_error(
                "Число авторов в статье не может превышать 6 человек",
                "The number of article authors must not exceed 6",
            )
        if en_authors and ru_authors and len(en_authors) != len(ru_authors):
            self._add_error(
                "Количество авторов в русском и английском блоках должно совпадать",
                "The number of authors in Russian and English blocks must match",
            )

        self._check_author_block(
            author_items=ru_authors,
            affiliation_items=ru_affiliations,
            lang="ru",
            full_name_message_ru="Фамилии, имена и отчества авторов должны быть указаны полностью",
            full_name_message_en="Authors' surnames, names, and patronymics must be specified in full",
            email_message_ru="В строке каждого автора должен быть указан email",
            email_message_en="Each author line must include an email address",
            superscript_message_ru="После ФИО каждого автора должен быть надстрочный знак аффилиации",
            superscript_message_en="Each author must have a superscript affiliation marker",
            affiliation_message_ru="Для каждой аффилиации нужно указать организацию, город и страну",
            affiliation_message_en="Each affiliation must include organization, city, and country",
        )
        self._check_author_block(
            author_items=en_authors,
            affiliation_items=en_affiliations,
            lang="en",
            full_name_message_ru="В английском блоке ФИО всех авторов должны быть указаны латиницей полностью",
            full_name_message_en="English author names must be fully specified in Latin letters",
            email_message_ru="В английском блоке в строке каждого автора должен быть указан email",
            email_message_en="Each English author line must include an email address",
            superscript_message_ru="В английском блоке после ФИО каждого автора должен быть надстрочный знак аффилиации",
            superscript_message_en="Each English author must have a superscript affiliation marker",
            affiliation_message_ru="В английском блоке для каждой аффилиации нужно указать организацию, город и страну",
            affiliation_message_en="Each English affiliation must include organization, city, and country",
        )

        if ru_authors and not any(self._has_corresponding_author_marker(item.paragraph) for item in ru_authors):
            self._add_error(
                "В сведениях об авторах должен быть указан корреспондирующий автор с пометкой (*)",
                "Author information must indicate the corresponding author with (*)",
            )

        for item in self._slice_items(self.structure, self.structure.ru_title_pos, self.structure.ru_abstract_pos):
            if self._is_spin_line(item.text) and self.SPIN_PATTERN.match(item.text) is None:
                self._add_error(
                    "SPIN-код должен быть указан в формате 1234-5678",
                    "SPIN code must be specified in the format 1234-5678",
                )
        for item in self._slice_items(self.structure, self.structure.en_title_pos, self.structure.en_abstract_pos):
            if self._is_spin_line(item.text) and self.SPIN_PATTERN.match(item.text) is None:
                self._add_error(
                    "SPIN-code должен быть указан в формате 1234-5678",
                    "SPIN code must be specified in the format 1234-5678",
                )
            if self._has_cyrillic(item.text):
                self._add_error(
                    "Сведения об авторах на английском языке должны быть указаны латиницей",
                    "English author information must be written in Latin letters",
                )

    def _check_author_block(
        self,
        *,
        author_items: list[ParagraphItem],
        affiliation_items: list[ParagraphItem],
        lang: str,
        full_name_message_ru: str,
        full_name_message_en: str,
        email_message_ru: str,
        email_message_en: str,
        superscript_message_ru: str,
        superscript_message_en: str,
        affiliation_message_ru: str,
        affiliation_message_en: str,
    ):
        affiliation_numbers = {
            number
            for number in (self._affiliation_number(item) for item in affiliation_items)
            if number is not None
        }

        for item in author_items:
            if len(self._author_name_words(item.text, lang)) < 3:
                self._add_error(full_name_message_ru, full_name_message_en)
            if not self._paragraph_has_email(item.paragraph):
                self._add_error(email_message_ru, email_message_en)

            author_affiliation_numbers = self._superscript_affiliation_numbers(item.paragraph)
            if not author_affiliation_numbers:
                self._add_error(superscript_message_ru, superscript_message_en)
            elif affiliation_numbers and not author_affiliation_numbers <= affiliation_numbers:
                self._add_error(
                    "Надстрочные знаки авторов должны соответствовать указанным аффилиациям",
                    "Authors' superscript markers must match the specified affiliations",
                )

        for item in affiliation_items:
            if not self._has_organization_city_country(item):
                self._add_error(affiliation_message_ru, affiliation_message_en)

    # Аннотации
    def check_annotations(self):
        self._check_annotation_length(
            self._item_at(self.structure, self.structure.ru_abstract_pos),
            self.RU_ABSTRACT_PATTERN,
            "Аннотация должна содержать от 650 до 1000 знаков с пробелами",
            "The abstract must contain from 650 to 1000 characters including spaces",
        )
        self._check_annotation_length(
            self._item_at(self.structure, self.structure.en_abstract_pos),
            self.EN_ABSTRACT_PATTERN,
            "Аннотация на английском языке должна содержать от 650 до 1000 знаков с пробелами",
            "The English abstract must contain from 650 to 1000 characters including spaces",
        )

    def _check_annotation_length(self, item: ParagraphItem | None, pattern, message_ru: str, message_en: str):
        if item is None:
            return
        match = pattern.match(item.text)
        if match is None:
            return
        body = self._normalize_text(match.group("body"))
        if not (650 <= len(body) <= 1000):
            self._add_error(message_ru, message_en)

    # Ключевые слова
    def check_keywords_metadata(self):
        self._check_keywords(
            self._item_at(self.structure, self.structure.ru_keywords_pos),
            self.RU_KEYWORDS_PATTERN,
            "Ключевых слов должно быть от 5 до 7",
            "There must be from 5 to 7 keywords",
            "Ключевые слова должны разделяться запятыми",
            "Keywords must be separated by commas",
            "Ключевые слова не должны содержать аббревиатуры",
            "Keywords must not contain abbreviations",
            "Ключевые фразы не должны быть длиннее четырех слов",
            "Keyword phrases must not be longer than four words",
        )
        self._check_keywords(
            self._item_at(self.structure, self.structure.en_keywords_pos),
            self.EN_KEYWORDS_PATTERN,
            "Ключевых слов на английском языке должно быть от 5 до 7",
            "There must be from 5 to 7 English keywords",
            "Ключевые слова на английском языке должны разделяться запятыми",
            "English keywords must be separated by commas",
            "Ключевые слова на английском языке не должны содержать аббревиатуры",
            "English keywords must not contain abbreviations",
            "Ключевые фразы на английском языке не должны быть длиннее четырех слов",
            "English keyword phrases must not be longer than four words",
        )

    def _check_keywords(
        self,
        item: ParagraphItem | None,
        pattern,
        count_message_ru: str,
        count_message_en: str,
        separator_message_ru: str,
        separator_message_en: str,
        abbreviation_message_ru: str,
        abbreviation_message_en: str,
        phrase_message_ru: str,
        phrase_message_en: str,
    ):
        if item is None:
            return
        match = pattern.match(item.text)
        if match is None:
            return

        keywords_text = match.group("keywords").strip()
        if ";" in keywords_text:
            self._add_error(separator_message_ru, separator_message_en)

        keywords = [keyword.strip() for keyword in keywords_text.split(",") if keyword.strip()]
        if not (5 <= len(keywords) <= 7):
            self._add_error(count_message_ru, count_message_en)

        for keyword in keywords:
            if self.ABBREVIATION_PATTERN.search(keyword):
                self._add_error(abbreviation_message_ru, abbreviation_message_en)
                break

        for keyword in keywords:
            if self._word_count(keyword) > 4:
                self._add_error(phrase_message_ru, phrase_message_en)
                break

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
