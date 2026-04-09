import re
from typing import BinaryIO

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.shared import Pt, Cm


class Validator:
    EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
    KEYWORDS_PATTERN = re.compile(r"^\s*key\s*words?\s*[:.]?\s*(?P<keywords>.+)$", re.IGNORECASE)
    CAPTION_PREFIXES = ("рис.", "рисунок", "fig.", "figure", "table", "табл.")
    TITLE_SCAN_LIMIT = 15

    def __init__(self, source: str | BinaryIO):
        self.source = source
        self.doc = Document(source)
        self.errors = []
        self.errors_eng = []

    def validate(self):
        self.check_margins()
        self.check_orientation()
        self.check_font_and_size()
        self.check_line_spacing()
        self.check_first_line_indent()
        self.check_email()
        self.check_title()
        self.check_keywords()
        self.check_annotation()
        self.check_references_count()
        self.check_reference_format()
        return self.errors, self.errors_eng

    # Убирает лишние пробелы
    @staticmethod
    def _normalize_text(text: str) -> str:
        return re.sub(r"\s+", " ", text).strip()

    # Итерируется по цепочке стилей (видимо, стили идут не массивом, а связным списком) 
    @staticmethod
    def _iter_style_chain(style):
        seen = set()
        current_style = style
        while current_style is not None and id(current_style) not in seen:
            yield current_style
            seen.add(id(current_style))
            current_style = current_style.base_style

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
            return True
        if rule == WD_LINE_SPACING.ONE_POINT_FIVE:
            return multiplier is None or abs(multiplier - 1.5) <= 0.01
        if rule == WD_LINE_SPACING.MULTIPLE:
            return multiplier is not None and abs(multiplier - 1.5) <= 0.01
        if rule is None and multiplier is not None:
            return abs(multiplier - 1.5) <= 0.01

        return False

    # Проверяет, что стиль (или предки, от которых он наследуется), является полужирным
    @classmethod
    def _style_font_bold(cls, style) -> bool | None:
        for current_style in cls._iter_style_chain(style):
            if current_style.font.bold is not None:
                return current_style.font.bold
        return None

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

    # Поля
    def check_margins(self):
        for section in self.doc.sections:
            if round(section.top_margin.cm, 1) != 2.5:
                self.errors.append("Отступ сверху должен равняться 2.5 единицам")
                self.errors_eng.append("The top margin must be 2.5 units")
            if round(section.bottom_margin.cm, 1) != 2.5:
                self.errors.append("Отступ снизу должен равняться 2.5 единицам")
                self.errors_eng.append("The bottom margin must be 2.5 units")
            if round(section.left_margin.cm, 1) != 2.5:
                self.errors.append("Отступ слева должен равняться 2.5 единицам")
                self.errors_eng.append("The left margin must be 2.5 units")
            if round(section.right_margin.cm, 1) != 2.5:
                self.errors.append("Отступ справа должен равняться 2.5 единицам")
                self.errors_eng.append("The right margin must be 2.5 units")

    # Ориентация страниц
    def check_orientation(self):
        for section in self.doc.sections:
            if section.orientation != 0:  # 0 = portrait
                self.errors.append("Ориентация страниц должна быть книжной")
                self.errors_eng.append("The orientation of the pages must be portrait")

    # Шрифт и размер
    def check_font_and_size(self):
        for p in self.doc.paragraphs:
            for run in p.runs:
                if run.font.name and run.font.name != "Times New Roman":
                    self.errors.append("В тексте статьи необходимо использовать шрифт Times New Roman, за исключением математических формул")
                    self.errors_eng.append("The Times New Roman font should be used in the text of the article, with the exception of mathematical formulas")
                    return
                if run.font.size and run.font.size.pt != 14:
                    self.errors.append("Размер шрифта должен быть 14")
                    self.errors_eng.append("The font size must be 14")
                    return

    # Межстрочный интервал
    def check_line_spacing(self):
        for p in self.doc.paragraphs:
            if not self._normalize_text(p.text):
                continue
            if not self._has_required_line_spacing(p):
                self.errors.append("Межстрочный интервал должен равняться 1.5 единицам")
                self.errors_eng.append("The line spacing must be 1.5 units")
                return

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
                        if not run.italic:
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
