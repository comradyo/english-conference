import re
from dataclasses import dataclass
from typing import BinaryIO

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.text.paragraph import Paragraph
from lxml import etree

XML_NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


@dataclass(frozen=True)
class ParagraphInfo:
    position: int
    paragraph_index: int
    paragraph: Paragraph
    text: str


class Validator:
    FONT_NAME = "times new roman"
    FONT_SIZE_PT = 14.0
    FONT_SIZE_TOLERANCE_PT = 0.25
    MARGIN_CM = 2.5
    MARGIN_TOLERANCE_CM = 0.05
    A4_WIDTH_CM = 21.0
    A4_HEIGHT_CM = 29.7
    PAGE_SIZE_TOLERANCE_CM = 0.15
    LINE_SPACING = 1.5
    LINE_SPACING_TOLERANCE = 0.01
    FIRST_LINE_INDENT_CM = 1.25
    FIRST_LINE_INDENT_TOLERANCE_CM = 0.05
    TITLE_SCAN_LIMIT = 25

    EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
    UDC_PATTERN = re.compile(r"^\s*УДК\b[:\s]*", re.IGNORECASE)
    RU_ABSTRACT_PATTERN = re.compile(r"^\s*Аннотация\s*[.:]\s*(?P<text>.+)$", re.IGNORECASE)
    EN_ABSTRACT_PATTERN = re.compile(r"^\s*Abstract\s*[.:]\s*(?P<text>.+)$", re.IGNORECASE)
    RU_KEYWORDS_PATTERN = re.compile(r"^\s*Ключевые\s+слова\s*[.:]\s*(?P<text>.+)$", re.IGNORECASE)
    EN_KEYWORDS_PATTERN = re.compile(r"^\s*Key\s*words?\s*[.:]\s*(?P<text>.+)$", re.IGNORECASE)
    REFERENCES_HEADING_PATTERN = re.compile(r"^\s*(СПИСОК ЛИТЕРАТУРЫ|REFERENCES)\s*$", re.IGNORECASE)
    LIST_ITEM_PATTERN = re.compile(r"^\s*(?:[-–•]|\d+[.)])\s+")
    CAPTION_PREFIXES = ("рис.", "рисунок", "fig.", "figure", "table", "табл.")
    REFERENCE_PATTERN = re.compile(
        r"^\["
        r"\d+(?:,\s*(?:с\.\s*\d+(?:-\d+)?|д\.\s*\d+,\s*л\.\s*\d+))?"
        r"(?:;\s*\d+(?:,\s*(?:с\.\s*\d+(?:-\d+)?|д\.\s*\d+,\s*л\.\s*\d+))?)*"
        r"\]$",
        re.IGNORECASE,
    )

    def __init__(self, source: str | BinaryIO):
        self.source = source
        self.doc = Document(source)
        self.errors: list[str] = []
        self.errors_eng: list[str] = []
        self.paragraph_infos = self._collect_paragraph_infos()
        self._structure_cache: dict[str, object] | None = None

    def validate(self):
        self.check_page_size()
        self.check_margins()
        self.check_orientation()
        self.check_page_numbers()
        self.check_footnotes()
        self.check_hyphenation()
        self.check_udc()
        self.check_font_and_size()
        self.check_line_spacing()
        self.check_titles()
        self.check_author_metadata()
        self.check_abstracts()
        self.check_keywords()
        self.check_body_alignment()
        self.check_first_line_indent()
        self.check_references_count()
        self.check_reference_format()
        return self.errors, self.errors_eng

    def _add_error(self, ru_text: str, en_text: str) -> None:
        if ru_text not in self.errors:
            self.errors.append(ru_text)
        if en_text not in self.errors_eng:
            self.errors_eng.append(en_text)

    @staticmethod
    def _normalize_text(text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    def _collect_paragraph_infos(self) -> list[ParagraphInfo]:
        infos: list[ParagraphInfo] = []
        for paragraph_index, paragraph in enumerate(self.doc.paragraphs, start=1):
            text = self._normalize_text(paragraph.text)
            if not text:
                continue
            infos.append(
                ParagraphInfo(
                    position=len(infos),
                    paragraph_index=paragraph_index,
                    paragraph=paragraph,
                    text=text,
                )
            )
        return infos

    @staticmethod
    def _iter_style_chain(style):
        seen = set()
        current_style = style
        while current_style is not None and id(current_style) not in seen:
            yield current_style
            seen.add(id(current_style))
            current_style = current_style.base_style

    @classmethod
    def _effective_alignment(cls, paragraph: Paragraph):
        if paragraph.alignment is not None:
            return paragraph.alignment

        for style in cls._iter_style_chain(paragraph.style):
            alignment = style.paragraph_format.alignment
            if alignment is not None:
                return alignment

        return None

    @classmethod
    def _effective_line_spacing(cls, paragraph: Paragraph):
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

    @classmethod
    def _effective_first_line_indent(cls, paragraph: Paragraph):
        indent = paragraph.paragraph_format.first_line_indent
        if indent is not None:
            return indent

        for style in cls._iter_style_chain(paragraph.style):
            indent = style.paragraph_format.first_line_indent
            if indent is not None:
                return indent

        return None

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
    def _has_required_line_spacing(cls, paragraph: Paragraph) -> bool:
        spacing, rule = cls._effective_line_spacing(paragraph)
        multiplier = cls._line_spacing_multiplier(spacing)

        if spacing is None and rule is None:
            return True
        if rule == WD_LINE_SPACING.ONE_POINT_FIVE:
            return multiplier is None or abs(multiplier - cls.LINE_SPACING) <= cls.LINE_SPACING_TOLERANCE
        if rule == WD_LINE_SPACING.MULTIPLE:
            return multiplier is not None and abs(multiplier - cls.LINE_SPACING) <= cls.LINE_SPACING_TOLERANCE
        if rule is None and multiplier is not None:
            return abs(multiplier - cls.LINE_SPACING) <= cls.LINE_SPACING_TOLERANCE

        return False

    @classmethod
    def _style_font_flag(cls, style, flag_name: str) -> bool | None:
        for current_style in cls._iter_style_chain(style):
            value = getattr(current_style.font, flag_name)
            if value is not None:
                return value
        return None

    @classmethod
    def _paragraph_has_text_with_flag(cls, paragraph: Paragraph, flag_name: str) -> bool:
        paragraph_style_flag = cls._style_font_flag(paragraph.style, flag_name)

        for run in paragraph.runs:
            if not cls._normalize_text(run.text):
                continue

            value = getattr(run, flag_name)
            if value is not None:
                if value:
                    return True
                continue

            if run.style is not None:
                run_style_flag = cls._style_font_flag(run.style, flag_name)
                if run_style_flag is not None:
                    if run_style_flag:
                        return True
                    continue

            if paragraph_style_flag:
                return True

        return False

    @classmethod
    def _paragraph_has_bold_text(cls, paragraph: Paragraph) -> bool:
        return cls._paragraph_has_text_with_flag(paragraph, "bold")

    @classmethod
    def _paragraph_has_italic_text(cls, paragraph: Paragraph) -> bool:
        return cls._paragraph_has_text_with_flag(paragraph, "italic")

    def _iter_font_sources(self, run, paragraph: Paragraph):
        yield run.font
        if run.style is not None:
            for style in self._iter_style_chain(run.style):
                yield style.font
        for style in self._iter_style_chain(paragraph.style):
            yield style.font

    def _effective_run_font_name(self, run, paragraph: Paragraph) -> str | None:
        for font in self._iter_font_sources(run, paragraph):
            if font.name:
                return str(font.name).strip()
        return None

    def _effective_run_font_size_pt(self, run, paragraph: Paragraph) -> float | None:
        for font in self._iter_font_sources(run, paragraph):
            if font.size is not None:
                return float(font.size.pt)
        return None

    @staticmethod
    def _is_left_aligned(paragraph: Paragraph) -> bool:
        alignment = Validator._effective_alignment(paragraph)
        return alignment in (None, WD_ALIGN_PARAGRAPH.LEFT)

    @staticmethod
    def _is_centered(paragraph: Paragraph) -> bool:
        return Validator._effective_alignment(paragraph) == WD_ALIGN_PARAGRAPH.CENTER

    @staticmethod
    def _is_justified(paragraph: Paragraph) -> bool:
        return Validator._effective_alignment(paragraph) == WD_ALIGN_PARAGRAPH.JUSTIFY

    def _is_caption_paragraph(self, paragraph: Paragraph) -> bool:
        text = self._normalize_text(paragraph.text).lower()
        return text.startswith(self.CAPTION_PREFIXES)

    @classmethod
    def _is_list_paragraph(cls, text: str) -> bool:
        return bool(cls.LIST_ITEM_PATTERN.match(text))

    def _is_body_heading(self, info: ParagraphInfo) -> bool:
        text = info.text
        words = re.findall(r"[\w-]+", text, re.UNICODE)
        if not words:
            return False
        if len(words) <= 10 and self._paragraph_has_bold_text(info.paragraph):
            return True
        if len(words) <= 8 and text.isupper():
            return True
        return False

    def _is_body_text_paragraph(self, info: ParagraphInfo) -> bool:
        if self._is_caption_paragraph(info.paragraph) or self._is_list_paragraph(info.text) or self._is_body_heading(
                info):
            return False

        words = re.findall(r"[\w-]+", info.text, re.UNICODE)
        if len(words) < 5:
            return False

        return bool(re.search(r"[.!?:;\]]$", info.text))

    @staticmethod
    def _xml_root(part):
        return etree.fromstring(part.blob)

    def _iter_package_parts(self, *suffixes: str):
        for part in self.doc.part.package.parts:
            if str(part.partname).endswith(suffixes):
                yield part

    def _find_match_position(self, pattern: re.Pattern[str], start_pos: int = 0) -> int | None:
        for info in self.paragraph_infos[start_pos:]:
            if pattern.match(info.text):
                return info.position
        return None

    def _find_title_block_before(self, anchor_pos: int | None, min_pos: int = 0) -> list[ParagraphInfo]:
        if anchor_pos is None:
            return []

        title_block: list[ParagraphInfo] = []
        pos = min(anchor_pos - 1, len(self.paragraph_infos) - 1)
        while pos >= min_pos:
            info = self.paragraph_infos[pos]
            if self._is_centered(info.paragraph) and self._paragraph_has_bold_text(info.paragraph):
                title_block.append(info)
                pos -= 1
                continue
            if title_block:
                break
            pos -= 1

        return list(reversed(title_block))

    def _keyword_items(self, raw_text: str) -> list[str]:
        separator = ";" if ";" in raw_text else ","
        parts = [item.strip(" .;,\t") for item in raw_text.split(separator)]
        return [item for item in parts if item]

    def _document_structure(self) -> dict[str, object]:
        if self._structure_cache is not None:
            return self._structure_cache

        infos = self.paragraph_infos
        udc_pos = 0 if infos and self.UDC_PATTERN.match(infos[0].text) else None
        ru_abstract_pos = self._find_match_position(self.RU_ABSTRACT_PATTERN)
        ru_keywords_pos = self._find_match_position(
            self.RU_KEYWORDS_PATTERN,
            start_pos=(ru_abstract_pos + 1) if ru_abstract_pos is not None else 0,
        )
        en_abstract_pos = self._find_match_position(
            self.EN_ABSTRACT_PATTERN,
            start_pos=(ru_keywords_pos + 1) if ru_keywords_pos is not None else 0,
        )
        en_keywords_pos = self._find_match_position(
            self.EN_KEYWORDS_PATTERN,
            start_pos=(en_abstract_pos + 1) if en_abstract_pos is not None else 0,
        )
        ru_title_block = self._find_title_block_before(
            ru_abstract_pos,
            min_pos=(udc_pos + 1) if udc_pos is not None else 0,
        )
        en_title_block = self._find_title_block_before(
            en_abstract_pos,
            min_pos=(ru_keywords_pos + 1) if ru_keywords_pos is not None else 0,
        )
        references_heading_pos = self._find_match_position(
            self.REFERENCES_HEADING_PATTERN,
            start_pos=(en_keywords_pos + 1) if en_keywords_pos is not None else 0,
        )

        self._structure_cache = {
            "udc_pos": udc_pos,
            "ru_title_block": ru_title_block,
            "en_title_block": en_title_block,
            "ru_abstract_pos": ru_abstract_pos,
            "ru_keywords_pos": ru_keywords_pos,
            "en_abstract_pos": en_abstract_pos,
            "en_keywords_pos": en_keywords_pos,
            "references_heading_pos": references_heading_pos,
        }
        return self._structure_cache

    def _metadata_block(self, language: str) -> list[ParagraphInfo]:
        structure = self._document_structure()
        if language == "ru":
            start = (structure["udc_pos"] + 1) if structure["udc_pos"] is not None else 0
            if structure["ru_title_block"]:
                end = structure["ru_title_block"][0].position
            elif structure["ru_abstract_pos"] is not None:
                end = structure["ru_abstract_pos"]
            else:
                end = start
        else:
            if structure["ru_keywords_pos"] is not None:
                start = structure["ru_keywords_pos"] + 1
            elif structure["ru_abstract_pos"] is not None:
                start = structure["ru_abstract_pos"] + 1
            else:
                start = 0
            if structure["en_title_block"]:
                end = structure["en_title_block"][0].position
            elif structure["en_abstract_pos"] is not None:
                end = structure["en_abstract_pos"]
            else:
                end = start

        return self.paragraph_infos[start:end]

    def _body_paragraphs(self) -> list[ParagraphInfo]:
        structure = self._document_structure()
        if structure["en_keywords_pos"] is not None:
            start = structure["en_keywords_pos"] + 1
        elif structure["ru_keywords_pos"] is not None:
            start = structure["ru_keywords_pos"] + 1
        else:
            start = 0

        end = structure["references_heading_pos"] if structure["references_heading_pos"] is not None else len(
            self.paragraph_infos)
        return self.paragraph_infos[start:end]

    def _reference_entries(self) -> list[ParagraphInfo]:
        structure = self._document_structure()
        references_heading_pos = structure["references_heading_pos"]
        if references_heading_pos is None:
            return []
        return self.paragraph_infos[references_heading_pos + 1:]

    def check_page_size(self):
        for section in self.doc.sections:
            width_cm = round(min(section.page_width.cm, section.page_height.cm), 2)
            height_cm = round(max(section.page_width.cm, section.page_height.cm), 2)
            if (
                    abs(width_cm - self.A4_WIDTH_CM) > self.PAGE_SIZE_TOLERANCE_CM
                    or abs(height_cm - self.A4_HEIGHT_CM) > self.PAGE_SIZE_TOLERANCE_CM
            ):
                self._add_error("Формат страницы должен быть A4", "The page format must be A4")
                return

    def check_margins(self):
        for section in self.doc.sections:
            if abs(section.top_margin.cm - self.MARGIN_CM) > self.MARGIN_TOLERANCE_CM:
                self._add_error("Отступ сверху должен равняться 2.5 единицам", "The top margin must be 2.5 units")
            if abs(section.bottom_margin.cm - self.MARGIN_CM) > self.MARGIN_TOLERANCE_CM:
                self._add_error("Отступ снизу должен равняться 2.5 единицам", "The bottom margin must be 2.5 units")
            if abs(section.left_margin.cm - self.MARGIN_CM) > self.MARGIN_TOLERANCE_CM:
                self._add_error("Отступ слева должен равняться 2.5 единицам", "The left margin must be 2.5 units")
            if abs(section.right_margin.cm - self.MARGIN_CM) > self.MARGIN_TOLERANCE_CM:
                self._add_error("Отступ справа должен равняться 2.5 единицам", "The right margin must be 2.5 units")

    def check_orientation(self):
        for section in self.doc.sections:
            if section.orientation != WD_ORIENT.PORTRAIT:
                self._add_error("Ориентация страниц должна быть книжной",
                                "The orientation of the pages must be portrait")
                return

    def check_page_numbers(self):
        for part in self._iter_package_parts(".xml"):
            name = str(part.partname)
            if "/word/header" not in name and "/word/footer" not in name:
                continue
            root = self._xml_root(part)
            fields = root.xpath(".//w:fldSimple/@w:instr", namespaces=XML_NS)
            fields += root.xpath(".//w:instrText/text()", namespaces=XML_NS)
            if any("PAGE" in field.upper() for field in fields):
                self._add_error("В документе не должно быть нумерации страниц",
                                "The document must not contain page numbers")
                return

    def check_footnotes(self):
        for suffix, tag, ru_text, en_text in (
                ("/word/footnotes.xml", "footnote", "В документе не должно быть постраничных сносок",
                 "The document must not contain footnotes"),
                ("/word/endnotes.xml", "endnote", "В документе не должно быть концевых сносок",
                 "The document must not contain endnotes"),
        ):
            for part in self._iter_package_parts(suffix):
                root = self._xml_root(part)
                ids = [
                    element.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}id")
                    for element in root.xpath(f".//w:{tag}", namespaces=XML_NS)
                ]
                actual_ids = [item for item in ids if item not in {"-1", "0", "1", None}]
                if actual_ids:
                    self._add_error(ru_text, en_text)
                    return

    def check_hyphenation(self):
        for part in self._iter_package_parts("/word/settings.xml"):
            root = self._xml_root(part)
            auto_hyphenation = root.xpath(".//w:autoHyphenation", namespaces=XML_NS)
            if auto_hyphenation:
                value = auto_hyphenation[0].get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val")
                if value not in {"0", "false", "False"}:
                    self._add_error("В документе не должно быть переносов", "The document must not contain hyphenation")
                    return

        for part in self._iter_package_parts(".xml"):
            name = str(part.partname)
            if "/word/" not in name:
                continue
            root = self._xml_root(part)
            if root.xpath("boolean(.//w:softHyphen)", namespaces=XML_NS):
                self._add_error("В документе не должно быть переносов", "The document must not contain hyphenation")
                return

    def check_udc(self):
        if not self.paragraph_infos or not self.UDC_PATTERN.match(self.paragraph_infos[0].text):
            self._add_error("Строка с УДК не найдена", "The UDC line was not found")

    def check_font_and_size(self):
        for paragraph in self.doc.paragraphs:
            for run in paragraph.runs:
                if not self._normalize_text(run.text):
                    continue

                font_name = self._effective_run_font_name(run, paragraph)
                if font_name and self.FONT_NAME not in font_name.lower():
                    self._add_error(
                        "В тексте статьи необходимо использовать шрифт Times New Roman, за исключением математических формул",
                        "The Times New Roman font should be used in the text of the article, with the exception of mathematical formulas",
                    )
                    return

                font_size_pt = self._effective_run_font_size_pt(run, paragraph)
                if font_size_pt is not None and abs(font_size_pt - self.FONT_SIZE_PT) > self.FONT_SIZE_TOLERANCE_PT:
                    self._add_error("Размер шрифта должен быть 14", "The font size must be 14")
                    return

    def check_line_spacing(self):
        for info in self.paragraph_infos:
            if not self._has_required_line_spacing(info.paragraph):
                self._add_error("Межстрочный интервал должен равняться 1.5 единицам",
                                "The line spacing must be 1.5 units")
                return

    def check_titles(self):
        structure = self._document_structure()

        for title_block, ru_missing, en_missing in (
                (
                        structure["ru_title_block"],
                        "Название статьи на русском языке не найдено",
                        "The Russian title of the article was not found",
                ),
                (
                        structure["en_title_block"],
                        "Название статьи на английском языке не найдено",
                        "The English title of the article was not found",
                ),
        ):
            if not title_block:
                self._add_error(ru_missing, en_missing)
                continue

            for info in title_block:
                if not self._is_centered(info.paragraph) or not self._paragraph_has_bold_text(info.paragraph):
                    self._add_error(
                        "Название статьи должно быть выровнено по центру и выделено полужирным",
                        "The title of the article must be centered and printed in bold",
                    )
                    break
                indent = self._effective_first_line_indent(info.paragraph)
                if indent is not None and abs(indent.cm) > self.FIRST_LINE_INDENT_TOLERANCE_CM:
                    self._add_error(
                        "Название статьи должно быть без абзацного отступа",
                        "The title of the article must not have a first-line indent",
                    )
                    break

    def _check_metadata_block(self, language: str):
        block = self._metadata_block(language)
        lang_ru = "русском" if language == "ru" else "английском"
        lang_en = "Russian" if language == "ru" else "English"

        if not block:
            self._add_error(
                f"Метаданные автора на {lang_ru} языке не найдены",
                f"The author metadata in {lang_en} was not found",
            )
            return

        non_email_lines = [info for info in block if not self.EMAIL_PATTERN.search(info.text)]
        email_lines = [info for info in block if self.EMAIL_PATTERN.search(info.text)]

        if len(non_email_lines) < 2:
            self._add_error(
                f"Метаданные автора на {lang_ru} языке оформлены не полностью",
                f"The author metadata in {lang_en} is incomplete",
            )

        if not any(self._paragraph_has_bold_text(info.paragraph) for info in non_email_lines):
            self._add_error(
                f"ФИО автора на {lang_ru} языке должно быть выделено полужирным",
                f"The author name in {lang_en} must be printed in bold",
            )

        for info in block:
            if not self._is_left_aligned(info.paragraph):
                self._add_error(
                    f"Метаданные автора на {lang_ru} языке должны быть выровнены по левому краю",
                    f"The author metadata in {lang_en} must be left-aligned",
                )
                break

        if not email_lines:
            self._add_error(
                f"E-mail автора на {lang_ru} языке не найден",
                f"The author e-mail in {lang_en} was not found",
            )
            return

        for info in email_lines:
            if not self._paragraph_has_italic_text(info.paragraph):
                self._add_error(
                    f"E-mail автора на {lang_ru} языке должен быть оформлен курсивом",
                    f"The author e-mail in {lang_en} must be italicized",
                )
                break

    def check_author_metadata(self):
        self._check_metadata_block("ru")
        self._check_metadata_block("en")

    def _check_abstract(self, language: str, position: int | None, pattern: re.Pattern[str]):
        lang_ru = "русском" if language == "ru" else "английском"
        lang_en = "Russian" if language == "ru" else "English"

        if position is None:
            self._add_error(
                f"Аннотация на {lang_ru} языке не найдена",
                f"The abstract in {lang_en} was not found",
            )
            return

        info = self.paragraph_infos[position]
        match = pattern.match(info.text)
        abstract_text = match.group("text") if match else info.text
        abstract_len = len(abstract_text.replace(" ", ""))
        if not (300 <= abstract_len <= 500):
            self._add_error(
                f"Аннотация на {lang_ru} языке должна содержать от 300 до 500 знаков без учёта пробелов",
                f"The abstract in {lang_en} should contain from 300 to 500 characters without spaces",
            )

        if not self._paragraph_has_italic_text(info.paragraph):
            self._add_error(
                f"Аннотация на {lang_ru} языке должна быть напечатана курсивом",
                f"The abstract in {lang_en} must be printed in italics",
            )

    def check_abstracts(self):
        structure = self._document_structure()
        self._check_abstract("ru", structure["ru_abstract_pos"], self.RU_ABSTRACT_PATTERN)
        self._check_abstract("en", structure["en_abstract_pos"], self.EN_ABSTRACT_PATTERN)

    def _check_keywords_block(self, language: str, position: int | None, pattern: re.Pattern[str]):
        lang_ru = "русском" if language == "ru" else "английском"
        lang_en = "Russian" if language == "ru" else "English"

        if position is None:
            self._add_error(
                f"Ключевые слова на {lang_ru} языке не найдены",
                f"The keywords in {lang_en} were not found",
            )
            return

        info = self.paragraph_infos[position]
        match = pattern.match(info.text)
        keywords_text = match.group("text") if match else ""
        keywords = self._keyword_items(keywords_text)
        if not (5 <= len(keywords) <= 10):
            self._add_error(
                f"Ключевых слов на {lang_ru} языке должно быть от 5 до 10",
                f"There should be from 5 to 10 keywords in {lang_en}",
            )

    def check_keywords(self):
        structure = self._document_structure()
        self._check_keywords_block("ru", structure["ru_keywords_pos"], self.RU_KEYWORDS_PATTERN)
        self._check_keywords_block("en", structure["en_keywords_pos"], self.EN_KEYWORDS_PATTERN)

    def check_body_alignment(self):
        body_paragraphs = self._body_paragraphs()
        for info in body_paragraphs:
            if not self._is_body_text_paragraph(info):
                continue
            if not self._is_justified(info.paragraph):
                self._add_error(
                    "Текст статьи должен быть выровнен по ширине",
                    "The article text must be justified",
                )
                return

    def check_first_line_indent(self):
        body_paragraphs = self._body_paragraphs()
        for info in body_paragraphs:
            if not self._is_body_text_paragraph(info):
                continue

            indent = self._effective_first_line_indent(info.paragraph)
            if indent is None or abs(indent.cm - self.FIRST_LINE_INDENT_CM) > self.FIRST_LINE_INDENT_TOLERANCE_CM:
                self._add_error(
                    "Абзацный отступ основного текста должен равняться 1.25 единицам",
                    "The first-line indent of the main text must be 1.25 units",
                )
                return

    def check_reference_format(self):
        structure = self._document_structure()
        stop_pos = structure["references_heading_pos"] if structure["references_heading_pos"] is not None else len(
            self.paragraph_infos)
        for info in self.paragraph_infos[:stop_pos]:
            for reference in re.findall(r"\[[^\[\]]+]", info.text):
                if not self.REFERENCE_PATTERN.match(reference):
                    self._add_error(
                        f"Неверный формат ссылки: {reference}",
                        f"Invalid reference format: {reference}",
                    )
                    return

    def check_references_count(self):
        structure = self._document_structure()
        references_heading_pos = structure["references_heading_pos"]
        if references_heading_pos is None:
            self._add_error("Список литературы не найден", "The list of references was not found")
            return

        entries = self._reference_entries()
        if len(entries) < 5:
            self._add_error(
                "Список литературы должен содержать не менее 5 источников",
                "The list of references should contain at least 5 sources",
            )

        for expected_number, info in enumerate(entries, start=1):
            if not re.match(rf"^{expected_number}\.\s+", info.text):
                self._add_error(
                    "Список литературы должен быть оформлен в виде нумерованного списка по порядку упоминания",
                    "The list of references must be a numbered list in the order of citation",
                )
                return
