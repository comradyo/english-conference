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
    ALLOWED_PARAGRAPH_INDENTS_CM = (0.0, 1.0, 1.25)
    EXCLUSIVE_PARAGRAPH_INDENTS_CM = (1.0, 1.25)
    MIN_PAGE_COUNT = 4
    MAX_PAGE_COUNT = 6
    MIN_CHARACTERS_WITH_SPACES = 6000
    MAX_TABLES = 2
    MAX_FIGURES = 5
    CM_TOLERANCE = 0.08
    PT_TOLERANCE = 0.1

    EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
    LOOSE_UDK_PATTERN = re.compile(r"^\s*(?:УДК|UDC)\b", re.IGNORECASE)
    UDK_PATTERN = re.compile(r"^\s*УДК\s+(?P<code>\S.+)$", re.IGNORECASE)
    RU_ABSTRACT_PATTERN = re.compile(r"^\s*Аннотация\s*[.:]\s*(?P<body>.+)$", re.IGNORECASE)
    EN_ABSTRACT_PATTERN = re.compile(r"^\s*Abstract\s*[.:]\s*(?P<body>.+)$", re.IGNORECASE)
    RU_KEYWORDS_PATTERN = re.compile(r"^\s*Ключевые\s+слова\s*[:.]\s*(?P<keywords>.+)$", re.IGNORECASE)
    EN_KEYWORDS_PATTERN = re.compile(r"^\s*key\s*words?\s*[:.]?\s*(?P<keywords>.+)$", re.IGNORECASE)
    KEYWORDS_PATTERN = EN_KEYWORDS_PATTERN
    SOURCES_HEADING_PATTERN = re.compile(r"^\s*References\s*$")
    SPIN_PATTERN = re.compile(r"^\s*SPIN(?:-код|-code)?\s*:\s*(?P<code>\d{4}-\d{4})\s*$", re.IGNORECASE)
    TABLE_CAPTION_PATTERN = re.compile(r"^\s*(?:Таблица|Table)\s+(?P<number>\d+)\b", re.IGNORECASE)
    FIGURE_CAPTION_PATTERN = re.compile(
        r"^\s*(?:Рис\.?|Рисунок|Fig\.?|Figure)\s+(?P<number>\d+)\b",
        re.IGNORECASE,
    )
    REFERENCE_ENTRY_PATTERN = re.compile(r"^\s*\[(?P<number>\d+)\]")
    BRACKETED_REFERENCE_PATTERN = re.compile(r"\[[^\[\]]+\]")
    REFERENCE_NUMBER_TOKEN_PATTERN = re.compile(r"^\d+(?:\s*[-–]\s*\d+)?$")
    REFERENCE_PAGE_TOKEN_PATTERN = re.compile(r"^(?:с|c|p)\.?\s*\d+(?:\s*[-–]\s*\d+)?$", re.IGNORECASE)
    WORD_PATTERN = re.compile(r"[A-Za-zА-Яа-яЁё]+(?:[-'][A-Za-zА-Яа-яЁё]+)?")
    RU_NAME_WORD_PATTERN = re.compile(r"[А-ЯЁ][А-Яа-яЁё-]+")
    EN_NAME_WORD_PATTERN = re.compile(r"[A-Z][A-Za-z'-]+")
    ABBREVIATION_PATTERN = re.compile(r"\b[A-ZА-ЯЁ]{2,}\b")
    PLAIN_TEXT_FORMULA_PATTERN = re.compile(r"[A-Za-zА-Яа-яЁё0-9)\]]\s*(?:=|≈|≠|≤|≥|<|>|±|∑|√)\s*[\w([{]")
    CAPTION_PREFIXES = ("рис.", "рисунок", "fig.", "figure", "table", "табл.")
    FORMULA_TABLE_NUMBER_PATTERN = re.compile(r"^\(?\d+[A-Za-zА-Яа-яЁё]?\)?$")
    AFFILIATION_HINTS = (
        "университет",
        "институт",
        "кафедр",
        "мгту",
        "москва",
        "россия",
        "university",
        "institute",
        "department",
        "faculty",
        "moscow",
        "russia",
        "bmstu",
    )
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
        self._error_pairs = set()

    def validate(self):
        self.validate_global_requirements()
        self.structure = self._build_article_structure()
        self.validate_article_structure()
        self.validate_article_formatting()
        self.validate_metadata_and_authors()
        self.validate_annotations_and_keywords()
        self.validate_tables_figures_and_formulas()
        self.validate_references()
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
        self.check_auto_hyphenation()

    def validate_article_structure(self):
        structure = self.structure
        if structure.udk_pos is None:
            self._add_error("УДК не найден", "UDC was not found")
        if structure.ru_title_pos is None:
            self._add_error("Заголовок статьи не найден", "The article title was not found")
        if not self._ru_author_items(structure):
            self._add_error("Сведения об авторах не найдены", "Author information was not found")
        if self._has_metadata_before_title(structure, "ru"):
            self._add_error(
                "Сведения об авторах должны располагаться после заголовка статьи",
                "Author information must be placed after the article title",
            )
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
        if self._has_metadata_before_title(structure, "en"):
            self._add_error(
                "Сведения об авторах на английском языке должны располагаться после заголовка статьи на английском языке",
                "English author information must be placed after the English article title",
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
            self._add_error(
                "Заголовок списка источников должен быть References",
                "The references heading must be 'References'",
            )

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

    def validate_article_formatting(self):
        self.check_structural_formatting()

    def validate_metadata_and_authors(self):
        self.check_udk()
        self.check_titles_metadata()
        self.check_authors_metadata()

    def validate_annotations_and_keywords(self):
        self.check_annotations()
        self.check_keywords_metadata()

    def validate_tables_figures_and_formulas(self):
        self.check_tables()
        self.check_figures()
        self.check_formulas()

    def validate_references(self):
        self.check_references()
        self.check_reference_formatting()

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

    def _word_setting_enabled(self, setting_name: str) -> bool:
        try:
            with zipfile.ZipFile(io.BytesIO(self._docx_bytes)) as archive:
                settings_xml = archive.read("word/settings.xml")
        except (KeyError, zipfile.BadZipFile):
            return False

        try:
            root = ElementTree.fromstring(settings_xml)
        except ElementTree.ParseError:
            return False

        for element in root.iter():
            if self._local_name(element.tag) != setting_name:
                continue
            value = None
            for attr_name, attr_value in element.attrib.items():
                if self._local_name(attr_name) == "val":
                    value = str(attr_value).strip().lower()
                    break
            return value not in {"0", "false", "off", "no"}

        return False

    def _add_error(self, message_ru: str, message_en: str) -> None:
        pair = (message_ru, message_en)
        if pair in self._error_pairs:
            return
        self._error_pairs.add(pair)
        self.errors.append(message_ru)
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
        udk_pos = self._find_position(items, lambda item: self._is_udk_line(item.text))
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

        ru_title_pos = self._title_position(items, self._next_position(udk_pos), ru_abstract_pos, "ru")
        en_title_pos = self._title_position(items, self._next_position(ru_keywords_pos), en_abstract_pos, "en")
        main_text_pos = (
            None
            if en_keywords_pos is None
            else self._first_content_position(items, self._next_position(en_keywords_pos), sources_pos)
        )

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
            lambda item: (
                not self._is_udk_line(item.text)
                and not self._is_spin_line(item.text)
                and not self._is_affiliation_line(item.text)
            ),
            start,
            end,
        )

    def _title_position(self, items: list[ParagraphItem], start: int, end: int | None, lang: str) -> int | None:
        upper_bound = len(items) if end is None else min(end, len(items))
        content_positions = [
            position
            for position in range(max(start, 0), upper_bound)
            if (
                not self._is_udk_line(items[position].text)
                and not self._is_spin_line(items[position].text)
                and not self._is_affiliation_line(items[position].text)
            )
        ]
        if not content_positions:
            return None

        first_position = content_positions[0]
        if not self._looks_like_metadata_before_title(items[first_position], lang):
            return first_position

        for position in content_positions[1:self.TITLE_SCAN_LIMIT + 1]:
            if self._is_title_candidate(items[position], lang):
                return position
        return first_position

    @classmethod
    def _is_udk_line(cls, text: str) -> bool:
        return cls.LOOSE_UDK_PATTERN.match(text) is not None

    @classmethod
    def _looks_like_metadata_before_title(cls, item: ParagraphItem, lang: str) -> bool:
        text = item.text
        if cls.EMAIL_PATTERN.search(text) or cls._looks_like_affiliation_metadata(text):
            return True

        word_count = cls._word_count(text)
        has_author_marker = bool(re.search(r"[\d,;/]", text))
        if re.search(r"(?:[А-ЯЁ]\.\s*){1,2}[А-ЯЁ][А-Яа-яЁё-]+", text):
            return True
        if cls._is_ru_author_line(item) or cls._is_en_author_line(item):
            return word_count <= 4 or (word_count <= 8 and has_author_marker)
        return False

    @classmethod
    def _looks_like_affiliation_metadata(cls, text: str) -> bool:
        normalized = cls._normalize_text(text).lower()
        return any(hint in normalized for hint in cls.AFFILIATION_HINTS)

    @classmethod
    def _is_title_candidate(cls, item: ParagraphItem, lang: str) -> bool:
        if cls._looks_like_metadata_before_title(item, lang):
            return False
        return cls._word_count(item.text) >= 5

    @classmethod
    def _slice_items(
            cls,
            structure: ArticleStructure,
            start_pos: int | None,
            end_pos: int | None,
    ) -> list[ParagraphItem]:
        if start_pos is None:
            start_pos = title_pos
        if start_pos is None:
            return []
        start = start_pos + 1
        end = len(structure.items) if end_pos is None else end_pos
        if start >= end:
            return []
        return structure.items[start:end]

    def _metadata_items(self, structure: ArticleStructure, lang: str) -> list[ParagraphItem]:
        if lang == "ru":
            start_pos = structure.udk_pos
            title_pos = structure.ru_title_pos
            end_pos = structure.ru_abstract_pos
        else:
            start_pos = structure.ru_keywords_pos
            title_pos = structure.en_title_pos
            end_pos = structure.en_abstract_pos

        if start_pos is None:
            return []

        end = len(structure.items) if end_pos is None else end_pos
        return [
            item
            for position, item in enumerate(structure.items[self._next_position(start_pos):end], self._next_position(start_pos))
            if position != title_pos
        ]

    def _metadata_items_before_title(self, structure: ArticleStructure, lang: str) -> list[ParagraphItem]:
        if lang == "ru":
            start_pos = structure.udk_pos
            title_pos = structure.ru_title_pos
        else:
            start_pos = structure.ru_keywords_pos
            title_pos = structure.en_title_pos

        if start_pos is None or title_pos is None or self._next_position(start_pos) >= title_pos:
            return []
        return structure.items[self._next_position(start_pos):title_pos]

    def _has_metadata_before_title(self, structure: ArticleStructure, lang: str) -> bool:
        return any(
            self._is_spin_line(item.text)
            or self._is_affiliation_line(item.text)
            or self._looks_like_metadata_before_title(item, lang)
            for item in self._metadata_items_before_title(structure, lang)
        )

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
            for item in self._metadata_items(structure, "ru")
            if self._is_ru_author_line(item)
        ]

    def _en_author_items(self, structure: ArticleStructure) -> list[ParagraphItem]:
        return [
            item
            for item in self._metadata_items(structure, "en")
            if self._is_en_author_line(item)
        ]

    def _ru_affiliation_items(self, structure: ArticleStructure) -> list[ParagraphItem]:
        return [
            item
            for item in self._metadata_items(structure, "ru")
            if self._is_affiliation_line(item.text)
        ]

    def _en_affiliation_items(self, structure: ArticleStructure) -> list[ParagraphItem]:
        return [
            item
            for item in self._metadata_items(structure, "en")
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

    def _formula_count(self) -> int:
        try:
            return len(self.doc.element.xpath(".//*[local-name()='oMath' or local-name()='oMathPara']"))
        except Exception:
            return 0

    def _drawing_count(self) -> int:
        try:
            count = 0
            for paragraph in self.doc.paragraphs:
                count += len(paragraph._p.xpath(".//*[local-name()='drawing' or local-name()='pict']"))
        except Exception:
            return 0
        return count

    def _caption_items(self, pattern) -> list[ParagraphItem]:
        items = []
        for item in getattr(self, "structure", self._build_article_structure()).items:
            if pattern.match(item.text):
                items.append(item)
        return items

    def _caption_numbers(self, pattern) -> list[int]:
        numbers = []
        for item in self._caption_items(pattern):
            match = pattern.match(item.text)
            if match:
                numbers.append(int(match.group("number")))
        return numbers

    @staticmethod
    def _has_sequential_numbers(numbers: list[int]) -> bool:
        return numbers == list(range(1, len(numbers) + 1))

    def _available_text_width_cm(self) -> float | None:
        widths = []
        for section in self.doc.sections:
            width = section.page_width.cm - section.left_margin.cm - section.right_margin.cm
            if width > 0:
                widths.append(width)
        if not widths:
            return None
        return min(widths)

    @staticmethod
    def _table_width_cm(table) -> float | None:
        try:
            grid_columns = table._tbl.xpath("./*[local-name()='tblGrid']/*[local-name()='gridCol']")
        except Exception:
            return None

        widths_twips = []
        for column in grid_columns:
            width = None
            for attr_name, attr_value in column.attrib.items():
                if attr_name.endswith("}w") or attr_name == "w":
                    width = attr_value
                    break
            if width is None:
                return None
            try:
                widths_twips.append(int(width))
            except ValueError:
                return None

        if not widths_twips:
            return None
        return sum(widths_twips) / 1440 * 2.54

    def _top_level_blocks(self):
        paragraph_by_element_id = {id(paragraph._p): paragraph for paragraph in self.doc.paragraphs}
        table_by_element_id = {id(table._tbl): table for table in self.doc.tables}
        for child in self.doc.element.body.iterchildren():
            name = self._local_name(child.tag)
            if name == "p":
                paragraph = paragraph_by_element_id.get(id(child))
                if paragraph is not None:
                    yield "paragraph", paragraph
            elif name == "tbl":
                table = table_by_element_id.get(id(child))
                if table is not None:
                    yield "table", table

    @classmethod
    def _previous_non_empty_paragraphs(cls, blocks: list[tuple[str, Any]], table_index: int, count: int):
        paragraphs = []
        for block_type, block in reversed(blocks[:table_index]):
            if block_type == "table":
                break
            if cls._normalize_text(block.text):
                paragraphs.append(block)
                if len(paragraphs) == count:
                    break
        return list(reversed(paragraphs))

    def _top_level_table_caption_pairs(self) -> list[tuple[Any | None, Any | None]]:
        blocks = list(self._top_level_blocks())
        pairs = []
        for index, (block_type, _) in enumerate(blocks):
            if block_type != "table":
                continue
            if self._is_formula_layout_table(blocks[index][1]):
                continue
            previous_paragraphs = self._previous_non_empty_paragraphs(blocks, index, 2)
            number_paragraph = previous_paragraphs[0] if len(previous_paragraphs) == 2 else None
            title_paragraph = previous_paragraphs[1] if len(previous_paragraphs) == 2 else None
            pairs.append((number_paragraph, title_paragraph))
        return pairs

    @classmethod
    def _table_contains_formula(cls, table) -> bool:
        try:
            return bool(table._tbl.xpath(".//*[local-name()='oMath' or local-name()='oMathPara']"))
        except Exception:
            return False

    @classmethod
    def _is_formula_table_number_cell(cls, text: str) -> bool:
        return cls.FORMULA_TABLE_NUMBER_PATTERN.match(cls._normalize_text(text)) is not None

    @classmethod
    def _is_formula_layout_table(cls, table) -> bool:
        try:
            row_count = len(table.rows)
            column_count = len(table.columns)
        except Exception:
            return False

        if row_count != 1 or column_count not in (2, 3):
            return False

        cell_texts = [cls._normalize_text(cell.text) for cell in table.rows[0].cells]
        if not any(cls._is_formula_table_number_cell(text) for text in cell_texts):
            return False

        non_number_texts = [text for text in cell_texts if not cls._is_formula_table_number_cell(text)]
        non_number_text = " ".join(text for text in non_number_texts if text)
        if len(non_number_text) > 160:
            return False

        return cls._table_contains_formula(table) or any(
            cls._looks_like_plain_text_formula(text) for text in non_number_texts
        )

    @classmethod
    def _looks_like_plain_text_formula(cls, text: str) -> bool:
        normalized = cls._normalize_text(text)
        if not normalized or len(normalized) > 120:
            return False
        if cls.EMAIL_PATTERN.search(normalized) or re.search(r"https?://|doi\.org|www\.", normalized, re.IGNORECASE):
            return False
        if not cls.PLAIN_TEXT_FORMULA_PATTERN.search(normalized):
            return False

        word_count = len(re.findall(r"[A-Za-zА-Яа-яЁё]{2,}", normalized))
        return word_count <= 6

    @classmethod
    def _reference_items(cls, structure: ArticleStructure) -> list[ParagraphItem]:
        if structure.sources_pos is None:
            return []
        return structure.items[structure.sources_pos + 1:]

    @classmethod
    def _reference_numbers(cls, structure: ArticleStructure) -> list[int]:
        numbers = []
        for item in cls._reference_items(structure):
            match = cls.REFERENCE_ENTRY_PATTERN.match(item.text)
            if match:
                numbers.append(int(match.group("number")))
        return numbers

    @classmethod
    def _main_text_reference_items(cls, structure: ArticleStructure) -> list[ParagraphItem]:
        if structure.en_keywords_pos is None:
            return []
        end = len(structure.items) if structure.sources_pos is None else structure.sources_pos
        if structure.en_keywords_pos + 1 >= end:
            return []
        return structure.items[structure.en_keywords_pos + 1: end]

    @classmethod
    def _expand_reference_number_token(cls, token: str) -> list[int] | None:
        if cls.REFERENCE_NUMBER_TOKEN_PATTERN.match(token) is None:
            return None

        parts = [part.strip() for part in re.split(r"[-–]", token)]
        try:
            if len(parts) == 1:
                return [int(parts[0])]
            start, end = int(parts[0]), int(parts[1])
        except (IndexError, ValueError):
            return None

        if start > end:
            return None
        return list(range(start, end + 1))

    @classmethod
    def _parse_reference_marker(cls, marker: str) -> tuple[list[int], bool]:
        inner_text = marker.strip()[1:-1].strip()
        if not inner_text:
            return [], False

        numbers = []
        for group in re.split(r"\s*;\s*", inner_text):
            if not group:
                return [], False

            tokens = [token.strip() for token in group.split(",") if token.strip()]
            if not tokens:
                return [], False

            first_numbers = cls._expand_reference_number_token(tokens[0])
            if first_numbers is None:
                return [], False
            numbers.extend(first_numbers)

            for token in tokens[1:]:
                if cls.REFERENCE_PAGE_TOKEN_PATTERN.match(token):
                    continue
                token_numbers = cls._expand_reference_number_token(token)
                if token_numbers is None:
                    return [], False
                numbers.extend(token_numbers)

        return numbers, True

    @classmethod
    def _unique_in_order(cls, values: list[int]) -> list[int]:
        seen = set()
        result = []
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            result.append(value)
        return result

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
    def _run_has_text_requiring_text_format(cls, run) -> bool:
        return cls._has_visible_text(run.text) and not cls._run_contains_formula(run)

    @classmethod
    def _paragraph_has_text_requiring_text_format(cls, paragraph) -> bool:
        return any(cls._run_has_text_requiring_text_format(run) for run in paragraph.runs)

    @classmethod
    def _cm_matches(cls, actual_cm: float, expected_cm: float) -> bool:
        return abs(actual_cm - expected_cm) <= cls.CM_TOLERANCE

    @classmethod
    def _pt_matches(cls, actual_pt: float, expected_pt: float) -> bool:
        return abs(actual_pt - expected_pt) <= cls.PT_TOLERANCE

    def _iter_all_paragraphs(self) -> Iterable:
        yield from self.doc.paragraphs
        for table in self.doc.tables:
            if self._is_formula_layout_table(table):
                continue
            yield from self._iter_table_paragraphs(table)

    @classmethod
    def _iter_table_paragraphs(cls, table) -> Iterable:
        for row in table.rows:
            for cell in row.cells:
                yield from cell.paragraphs
                for nested_table in cell.tables:
                    yield from cls._iter_table_paragraphs(nested_table)

    def _iter_all_tables(self) -> Iterable:
        for table in self.doc.tables:
            yield table
            yield from self._iter_nested_tables(table)

    @classmethod
    def _iter_nested_tables(cls, table) -> Iterable:
        for row in table.rows:
            for cell in row.cells:
                for nested_table in cell.tables:
                    yield nested_table
                    yield from cls._iter_nested_tables(nested_table)

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

    @classmethod
    def _effective_first_line_indent_cm(cls, paragraph) -> float:
        indent = paragraph.paragraph_format.first_line_indent
        if indent is not None:
            return indent.cm

        for style in cls._iter_style_chain(paragraph.style):
            indent = style.paragraph_format.first_line_indent
            if indent is not None:
                return indent.cm

        return 0.0

    # Проверяет, что стиль (или предки, от которых он наследуется), является полужирным
    @classmethod
    def _style_font_bold(cls, style) -> bool | None:
        for current_style in cls._iter_style_chain(style):
            if current_style.font.bold is not None:
                return current_style.font.bold
        return None

    @classmethod
    def _run_is_bold(cls, run, paragraph) -> bool:
        if run.bold is not None:
            return bool(run.bold)

        if run.style is not None:
            run_style_bold = cls._style_font_bold(run.style)
            if run_style_bold is not None:
                return run_style_bold

        paragraph_style_bold = cls._style_font_bold(paragraph.style)
        if paragraph_style_bold is not None:
            return paragraph_style_bold

        return False

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

    @classmethod
    def _is_right_aligned(cls, paragraph) -> bool:
        return cls._effective_alignment(paragraph) == WD_ALIGN_PARAGRAPH.RIGHT

    @classmethod
    def _is_justified(cls, paragraph) -> bool:
        return cls._effective_alignment(paragraph) == WD_ALIGN_PARAGRAPH.JUSTIFY

    @classmethod
    def _is_left_or_justified(cls, paragraph) -> bool:
        alignment = cls._effective_alignment(paragraph)
        return alignment in (None, WD_ALIGN_PARAGRAPH.LEFT, WD_ALIGN_PARAGRAPH.JUSTIFY)

    # Проверяет, что параграф является подписью к изображению/таблице
    @classmethod
    def _is_caption_paragraph(cls, paragraph) -> bool:
        text = cls._normalize_text(paragraph.text).lower()
        return text.startswith(cls.CAPTION_PREFIXES)

    @classmethod
    def _visible_run_spans(cls, paragraph):
        position = 0
        spans = []
        for run in paragraph.runs:
            text = run.text or ""
            start = position
            end = start + len(text)
            if cls._has_visible_text(text):
                spans.append((run, start, end, text))
            position = end
        return spans

    @classmethod
    def _runs_in_text_range(cls, paragraph, start: int, end: int):
        for run, run_start, run_end, text in cls._visible_run_spans(paragraph):
            if run_end <= start or run_start >= end:
                continue
            overlap_start = max(start, run_start) - run_start
            overlap_end = min(end, run_end) - run_start
            if cls._has_visible_text(text[overlap_start:overlap_end]):
                yield run

    @classmethod
    def _paragraph_runs_have_style(
            cls,
            paragraph,
            *,
            bold: bool | None = None,
            italic: bool | None = None,
            start: int = 0,
            end: int | None = None,
    ) -> bool:
        if end is None:
            end = len(paragraph.text or "")
        for run in cls._runs_in_text_range(paragraph, start, end):
            if bold is not None and cls._run_is_bold(run, paragraph) != bold:
                return False
            if italic is not None and cls._run_is_italic(run, paragraph) != italic:
                return False
        return True

    @classmethod
    def _paragraph_has_bold_run(cls, paragraph) -> bool:
        return any(cls._run_is_bold(run, paragraph) for run, *_ in cls._visible_run_spans(paragraph))

    @classmethod
    def _paragraph_has_italic_run(cls, paragraph) -> bool:
        return any(cls._run_is_italic(run, paragraph) for run, *_ in cls._visible_run_spans(paragraph))

    @classmethod
    def _paragraph_indent_bucket(cls, paragraph) -> float | None:
        indent_cm = cls._effective_first_line_indent_cm(paragraph)
        for allowed_indent in cls.ALLOWED_PARAGRAPH_INDENTS_CM:
            if cls._cm_matches(indent_cm, allowed_indent):
                return allowed_indent
        return None

    @classmethod
    def _paragraph_has_allowed_main_indent(cls, paragraph) -> bool:
        return cls._paragraph_indent_bucket(paragraph) is not None

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
            if not self._paragraph_has_text_requiring_text_format(paragraph):
                continue
            for run in paragraph.runs:
                if not self._run_has_text_requiring_text_format(run):
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
            if not self._paragraph_has_text_requiring_text_format(paragraph):
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

    def check_auto_hyphenation(self):
        if self._word_setting_enabled("autoHyphenation"):
            self._add_error(
                "Автоматическая расстановка переносов должна быть отключена",
                "Automatic hyphenation must be disabled",
            )

    def check_structural_formatting(self):
        structure = self.structure

        self._check_left_or_justified(
            self._item_at(structure, structure.udk_pos),
            "УДК должен быть выровнен по левому краю или по ширине",
            "UDC must be left-aligned or justified",
        )
        self._check_plain_paragraph(
            self._item_at(structure, structure.udk_pos),
            "УДК не должен быть выделен полужирным или курсивом",
            "UDC must not be bold or italic",
        )

        self._check_title_formatting(
            self._item_at(structure, structure.ru_title_pos),
            "Заголовок статьи должен быть выровнен по левому краю или по ширине",
            "The article title must be left-aligned or justified",
            "Заголовок статьи должен быть выделен полужирным и не должен быть набран курсивом",
            "The article title must be bold and must not be italic",
        )
        self._check_title_formatting(
            self._item_at(structure, structure.en_title_pos),
            "Заголовок статьи на английском языке должен быть выровнен по левому краю или по ширине",
            "The English article title must be left-aligned or justified",
            "Заголовок статьи на английском языке должен быть выделен полужирным и не должен быть набран курсивом",
            "The English article title must be bold and must not be italic",
        )

        for item in self._ru_author_items(structure):
            self._check_author_text_formatting(
                item,
                "ФИО и надстрочный знак автора должны быть выделены полужирным",
                "The author's full name and superscript marker must be bold",
                "Email автора не должен быть выделен полужирным или курсивом",
                "The author's email must not be bold or italic",
                "Сведения об авторах не должны быть набраны курсивом",
                "Author information must not be italic",
            )
        for item in self._en_author_items(structure):
            self._check_author_text_formatting(
                item,
                "ФИО автора в английском блоке и надстрочный знак должны быть выделены полужирным",
                "The English author's full name and superscript marker must be bold",
                "Email автора в английском блоке не должен быть выделен полужирным или курсивом",
                "The English author's email must not be bold or italic",
                "Сведения об авторах на английском языке не должны быть набраны курсивом",
                "English author information must not be italic",
            )

        for item in self._ru_affiliation_items(structure):
            self._check_affiliation_formatting(
                item,
                "Аффилиации должны быть выровнены по левому краю или по ширине",
                "Affiliations must be left-aligned or justified",
                "Аффилиации должны быть набраны курсивом без полужирного начертания",
                "Affiliations must be italic and must not be bold",
            )
        for item in self._en_affiliation_items(structure):
            self._check_affiliation_formatting(
                item,
                "Аффилиации на английском языке должны быть выровнены по левому краю или по ширине",
                "English affiliations must be left-aligned or justified",
                "Аффилиации на английском языке должны быть набраны курсивом без полужирного начертания",
                "English affiliations must be italic and must not be bold",
            )

        for item in self._slice_items(structure, structure.ru_title_pos, structure.ru_abstract_pos):
            if self._is_spin_line(item.text):
                self._check_plain_paragraph(
                    item,
                    "SPIN-код не должен быть выделен полужирным или курсивом",
                    "SPIN code must not be bold or italic",
                )
        for item in self._slice_items(structure, structure.en_title_pos, structure.en_abstract_pos):
            if self._is_spin_line(item.text):
                self._check_plain_paragraph(
                    item,
                    "SPIN-code не должен быть выделен полужирным или курсивом",
                    "SPIN code must not be bold or italic",
                )

        self._check_labeled_paragraph_formatting(
            self._item_at(structure, structure.ru_abstract_pos),
            self.RU_ABSTRACT_PATTERN,
            "body",
            "Аннотация должна быть выровнена по ширине",
            "The abstract must be justified",
            "Метка «Аннотация.» должна быть выделена полужирным и не должна быть набрана курсивом",
            "The 'Abstract' label must be bold and must not be italic",
            "Текст аннотации не должен быть выделен полужирным или курсивом",
            "The abstract text must not be bold or italic",
        )
        self._check_labeled_paragraph_formatting(
            self._item_at(structure, structure.ru_keywords_pos),
            self.RU_KEYWORDS_PATTERN,
            "keywords",
            "Ключевые слова должны быть выровнены по ширине",
            "Keywords must be justified",
            "Метка «Ключевые слова:» должна быть выделена полужирным и не должна быть набрана курсивом",
            "The 'Keywords' label must be bold and must not be italic",
            "Текст ключевых слов не должен быть выделен полужирным или курсивом",
            "Keywords text must not be bold or italic",
        )
        self._check_labeled_paragraph_formatting(
            self._item_at(structure, structure.en_abstract_pos),
            self.EN_ABSTRACT_PATTERN,
            "body",
            "Аннотация на английском языке должна быть выровнена по ширине",
            "The English abstract must be justified",
            "Метка «Abstract.» должна быть выделена полужирным и не должна быть набрана курсивом",
            "The 'Abstract' label must be bold and must not be italic",
            "Текст аннотации на английском языке не должен быть выделен полужирным или курсивом",
            "The English abstract text must not be bold or italic",
        )
        self._check_labeled_paragraph_formatting(
            self._item_at(structure, structure.en_keywords_pos),
            self.EN_KEYWORDS_PATTERN,
            "keywords",
            "Ключевые слова на английском языке должны быть выровнены по ширине",
            "English keywords must be justified",
            "Метка «Keywords:» должна быть выделена полужирным и не должна быть набрана курсивом",
            "The 'Keywords' label must be bold and must not be italic",
            "Текст ключевых слов на английском языке не должен быть выделен полужирным или курсивом",
            "English keywords text must not be bold or italic",
        )

        self._check_main_text_formatting(structure)
        self._check_references_heading_formatting(structure)

    def _check_left_or_justified(self, item: ParagraphItem | None, message_ru: str, message_en: str):
        if item is not None and not self._is_left_or_justified(item.paragraph):
            self._add_error(message_ru, message_en)

    def _check_plain_paragraph(self, item: ParagraphItem | None, message_ru: str, message_en: str):
        if item is None:
            return
        if self._paragraph_has_bold_run(item.paragraph) or self._paragraph_has_italic_run(item.paragraph):
            self._add_error(message_ru, message_en)

    def _check_title_formatting(
            self,
            item: ParagraphItem | None,
            alignment_message_ru: str,
            alignment_message_en: str,
            style_message_ru: str,
            style_message_en: str,
    ):
        if item is None:
            return
        if not self._is_left_or_justified(item.paragraph):
            self._add_error(alignment_message_ru, alignment_message_en)
        if not self._paragraph_runs_have_style(item.paragraph, bold=True, italic=False):
            self._add_error(style_message_ru, style_message_en)

    def _check_author_text_formatting(
            self,
            item: ParagraphItem,
            name_message_ru: str,
            name_message_en: str,
            email_message_ru: str,
            email_message_en: str,
            italic_message_ru: str,
            italic_message_en: str,
    ):
        paragraph = item.paragraph
        if self._paragraph_has_italic_run(paragraph):
            self._add_error(italic_message_ru, italic_message_en)

        name_end = len(self._author_name_part(item.text).rstrip())
        if name_end and not self._paragraph_runs_have_style(paragraph, bold=True, italic=False, start=0, end=name_end):
            self._add_error(name_message_ru, name_message_en)

        superscript_runs = [
            run
            for run, _, _, _ in self._visible_run_spans(paragraph)
            if run.font.superscript
        ]
        if any(not self._run_is_bold(run, paragraph) or self._run_is_italic(run, paragraph) for run in superscript_runs):
            self._add_error(name_message_ru, name_message_en)

        for match in self.EMAIL_PATTERN.finditer(paragraph.text):
            if not self._paragraph_runs_have_style(
                    paragraph,
                    bold=False,
                    italic=False,
                    start=match.start(),
                    end=match.end(),
            ):
                self._add_error(email_message_ru, email_message_en)
                break

    def _check_affiliation_formatting(
            self,
            item: ParagraphItem,
            alignment_message_ru: str,
            alignment_message_en: str,
            style_message_ru: str,
            style_message_en: str,
    ):
        if not self._is_left_or_justified(item.paragraph):
            self._add_error(alignment_message_ru, alignment_message_en)
        if not self._paragraph_runs_have_style(item.paragraph, bold=False, italic=True):
            self._add_error(style_message_ru, style_message_en)

    def _check_labeled_paragraph_formatting(
            self,
            item: ParagraphItem | None,
            pattern,
            body_group: str,
            alignment_message_ru: str,
            alignment_message_en: str,
            label_message_ru: str,
            label_message_en: str,
            body_message_ru: str,
            body_message_en: str,
    ):
        if item is None:
            return
        if not self._is_justified(item.paragraph):
            self._add_error(alignment_message_ru, alignment_message_en)

        match = pattern.match(item.text)
        if match is None:
            return

        body_start = match.start(body_group)
        if not self._paragraph_runs_have_style(item.paragraph, bold=True, italic=False, start=0, end=body_start):
            self._add_error(label_message_ru, label_message_en)
        if not self._paragraph_runs_have_style(
                item.paragraph,
                bold=False,
                italic=False,
                start=body_start,
                end=len(item.text),
        ):
            self._add_error(body_message_ru, body_message_en)

    def _check_main_text_formatting(self, structure: ArticleStructure):
        if structure.main_text_pos is None or structure.sources_pos is None:
            return
        end = structure.sources_pos
        skip_numbers = self._table_title_paragraph_numbers(structure)
        non_zero_indent_values = set()

        for item in structure.items[structure.main_text_pos:end]:
            if item.number in skip_numbers:
                continue
            if self.TABLE_CAPTION_PATTERN.match(item.text) or self.FIGURE_CAPTION_PATTERN.match(item.text):
                continue
            if not self._paragraph_has_text_requiring_text_format(item.paragraph):
                continue
            if not self._is_left_or_justified(item.paragraph):
                self._add_error(
                    "Абзацы основного текста должны быть выровнены по левому краю или по ширине",
                    "Main text paragraphs must be left-aligned or justified",
                )
            if not self._paragraph_has_allowed_main_indent(item.paragraph):
                self._add_error(
                    "Абзацный отступ основного текста должен быть 0, 1 см или 1.25 см",
                    "The first-line indent in main text must be 0, 1 cm, or 1.25 cm",
                )
                continue

            indent_value = self._paragraph_indent_bucket(item.paragraph)
            if indent_value in self.EXCLUSIVE_PARAGRAPH_INDENTS_CM:
                non_zero_indent_values.add(indent_value)

        if len(non_zero_indent_values) > 1:
            self._add_error(
                "В документе нельзя одновременно использовать абзацные отступы 1 см и 1.25 см",
                "The document must not mix 1 cm and 1.25 cm first-line indents",
            )

    def _table_title_paragraph_numbers(self, structure: ArticleStructure) -> set[int]:
        title_numbers = set()
        items = structure.items
        for index, item in enumerate(items[:-1]):
            if self.TABLE_CAPTION_PATTERN.match(item.text):
                title_numbers.add(items[index + 1].number)
        return title_numbers

    def _check_references_heading_formatting(self, structure: ArticleStructure):
        item = self._item_at(structure, structure.sources_pos)
        if item is None:
            return
        if not self._is_left_or_justified(item.paragraph):
            self._add_error(
                "Заголовок References должен быть выровнен по левому краю или по ширине",
                "The References heading must be left-aligned or justified",
            )
        if not self._paragraph_runs_have_style(item.paragraph, bold=True, italic=False):
            self._add_error(
                "Заголовок References должен быть выделен полужирным и не должен быть набран курсивом",
                "The References heading must be bold and must not be italic",
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
            "Ключевые слова не должны заканчиваться точкой",
            "Keywords must not end with a period",
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
            "Ключевые слова на английском языке не должны заканчиваться точкой",
            "English keywords must not end with a period",
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
            period_message_ru: str,
            period_message_en: str,
    ):
        if item is None:
            return
        match = pattern.match(item.text)
        if match is None:
            return

        keywords_text = match.group("keywords").strip()
        if ";" in keywords_text:
            self._add_error(separator_message_ru, separator_message_en)
        if keywords_text.endswith("."):
            self._add_error(period_message_ru, period_message_en)

        keywords = [keyword.strip() for keyword in re.split(r"[,;]", keywords_text) if keyword.strip()]
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

    # Таблицы
    def check_tables(self):
        tables = [table for table in self._iter_all_tables() if not self._is_formula_layout_table(table)]
        table_count = len(tables)
        table_caption_numbers = self._caption_numbers(self.TABLE_CAPTION_PATTERN)

        if table_count > self.MAX_TABLES:
            self._add_error(
                "В статье должно быть не более 2 таблиц",
                "The article must contain no more than 2 tables",
            )

        if table_count and len(table_caption_numbers) < table_count:
            self._add_error(
                "Все таблицы должны иметь подписи с номером",
                "All tables must have numbered captions",
            )

        if table_caption_numbers and not self._has_sequential_numbers(table_caption_numbers):
            self._add_error(
                "Таблицы должны нумероваться последовательно в порядке упоминания",
                "Tables must be numbered sequentially in order of mention",
            )

        self._check_table_caption_formatting()
        self._check_table_content_font_and_size(tables)

        available_width_cm = self._available_text_width_cm()
        if available_width_cm is None:
            return
        for table in tables:
            table_width_cm = self._table_width_cm(table)
            if table_width_cm is not None and table_width_cm > available_width_cm + self.CM_TOLERANCE:
                self._add_error(
                    "Таблицы должны располагаться в пределах рабочего поля",
                    "Tables must fit within the working area",
                )
                return

    def _check_table_caption_formatting(self):
        for number_paragraph, title_paragraph in self._top_level_table_caption_pairs():
            if (
                    number_paragraph is None
                    or title_paragraph is None
                    or self.TABLE_CAPTION_PATTERN.match(number_paragraph.text) is None
            ):
                self._add_error(
                    "Номер таблицы должен быть расположен перед заголовком таблицы в формате «Таблица N»",
                    "The table number must be placed before the table title in the format 'Table N'",
                )
                continue

            if not self._is_right_aligned(number_paragraph) or not self._paragraph_runs_have_style(
                    number_paragraph,
                    bold=False,
                    italic=True,
            ):
                self._add_error(
                    "Номер таблицы должен быть выровнен по правому краю и набран курсивом",
                    "The table number must be right-aligned and italic",
                )

            if (
                    self.TABLE_CAPTION_PATTERN.match(title_paragraph.text)
                    or self.FIGURE_CAPTION_PATTERN.match(title_paragraph.text)
                    or self.SOURCES_HEADING_PATTERN.match(title_paragraph.text)
            ):
                self._add_error(
                    "После номера таблицы должен быть указан заголовок таблицы",
                    "A table title must follow the table number",
                )
                continue

            if not self._is_centered(title_paragraph) or not self._paragraph_runs_have_style(
                    title_paragraph,
                    bold=True,
                    italic=False,
            ):
                self._add_error(
                    "Заголовок таблицы должен быть выровнен по центру и выделен полужирным",
                    "The table title must be centered and bold",
                )

    def _check_table_content_font_and_size(self, tables: list[Any]):
        for table in tables:
            for paragraph in self._iter_table_paragraphs(table):
                for run in paragraph.runs:
                    if not self._run_has_text_requiring_text_format(run):
                        continue

                    font_name = self._effective_run_font_name(run, paragraph)
                    if font_name and font_name.lower() != self.REQUIRED_FONT_NAME.lower():
                        self._add_error(
                            "В таблицах необходимо использовать шрифт Times New Roman",
                            "Tables must use the Times New Roman font",
                        )
                        return

                    font_size_pt = self._effective_run_font_size_pt(run, paragraph)
                    if font_size_pt is not None and not self._pt_matches(font_size_pt, self.REQUIRED_FONT_SIZE_PT):
                        self._add_error(
                            "Размер шрифта в таблицах должен быть 12",
                            "The font size in tables must be 12",
                        )
                        return

    # Рисунки
    def check_figures(self):
        figure_count = self._drawing_count()
        figure_caption_numbers = self._caption_numbers(self.FIGURE_CAPTION_PATTERN)

        if figure_count > self.MAX_FIGURES:
            self._add_error(
                "В статье должно быть не более 5 рисунков",
                "The article must contain no more than 5 figures",
            )

        if figure_count and len(figure_caption_numbers) < figure_count:
            self._add_error(
                "Все рисунки должны иметь подрисуночные подписи",
                "All figures must have captions",
            )

        if figure_caption_numbers and not self._has_sequential_numbers(figure_caption_numbers):
            self._add_error(
                "Рисунки должны нумероваться последовательно в порядке упоминания",
                "Figures must be numbered sequentially in order of mention",
            )

    # Формулы
    def check_formulas(self):
        for paragraph in self._iter_all_paragraphs():
            if self._paragraph_contains_formula(paragraph):
                continue
            if self._looks_like_plain_text_formula(paragraph.text):
                self._add_error(
                    "Формулы должны быть набраны в редакторе формул Word, Equation или MathType",
                    "Formulas must be created with Word Equation, Equation, or MathType",
                )
                return

    # Ссылки и список источников
    def check_references(self):
        if not hasattr(self, "structure"):
            self.structure = self._build_article_structure()
        if self.structure.sources_pos is None:
            return

        reference_numbers = self._reference_numbers(self.structure)
        if len(reference_numbers) < 5:
            self._add_error(
                "Список источников должен содержать не менее 5 источников",
                "The list of references must contain at least 5 sources",
            )

        if reference_numbers and reference_numbers != list(range(1, len(reference_numbers) + 1)):
            self._add_error(
                "Источники в списке должны быть пронумерованы последовательно, начиная с [1]",
                "References must be numbered sequentially starting from [1]",
            )

        if self.structure.main_text_pos is None:
            return

        cited_numbers = []
        for item in self._main_text_reference_items(self.structure):
            for marker in self.BRACKETED_REFERENCE_PATTERN.findall(item.text):
                numbers, is_valid = self._parse_reference_marker(marker)
                if not is_valid:
                    self._add_error(
                        f"Неверный формат ссылки: {marker}",
                        f"Invalid reference format: {marker}",
                    )
                    continue
                cited_numbers.extend(numbers)

        if reference_numbers and not cited_numbers:
            self._add_error(
                "В тексте статьи должны быть ссылки на источники из списка",
                "The article text must cite the listed references",
            )
            return

        reference_number_set = set(reference_numbers)
        cited_number_set = set(cited_numbers)
        missing_sources = sorted(cited_number_set - reference_number_set)
        if missing_sources:
            self._add_error(
                "В тексте есть ссылки на источники, отсутствующие в списке",
                "The text cites references that are missing from the reference list",
            )

        uncited_sources = sorted(reference_number_set - cited_number_set)
        if uncited_sources:
            self._add_error(
                "В тексте должны быть ссылки на все источники из списка",
                "The text must cite every source from the reference list",
            )

        first_mentions = self._unique_in_order(cited_numbers)
        if first_mentions and first_mentions != sorted(first_mentions):
            self._add_error(
                "Список источников должен формироваться в порядке первого упоминания в тексте",
                "References must be ordered by first mention in the text",
            )

    def check_reference_formatting(self):
        if not hasattr(self, "structure"):
            self.structure = self._build_article_structure()
        if self.structure.sources_pos is None:
            return

        bad_alignment = False
        bad_bold = False

        for item in self._reference_items(self.structure):
            if self.REFERENCE_ENTRY_PATTERN.match(item.text) is None:
                continue

            if not self._is_left_or_justified(item.paragraph):
                bad_alignment = True
            if self._paragraph_has_bold_run(item.paragraph):
                bad_bold = True

        if bad_alignment:
            self._add_error(
                "Элементы списка источников должны быть выровнены по левому краю или по ширине",
                "Reference entries must be left-aligned or justified",
            )
        if bad_bold:
            self._add_error(
                "Элементы списка источников не должны содержать полужирное начертание",
                "Reference entries must not contain bold text",
            )
