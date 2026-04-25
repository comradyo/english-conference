from __future__ import annotations

import io
import unittest
import zipfile
from xml.etree import ElementTree

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

from checker.validator import Validator


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _set_docx_page_count(content: bytes, pages: int) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(content), "r") as source, zipfile.ZipFile(output, "w") as target:
        for item in source.infolist():
            content = source.read(item.filename)
            if item.filename == "docProps/app.xml":
                root = ElementTree.fromstring(content)
                for element in root.iter():
                    if _local_name(element.tag) == "Pages":
                        element.text = str(pages)
                        break
                content = ElementTree.tostring(root, encoding="utf-8", xml_declaration=True)
            target.writestr(item, content)
    return output.getvalue()


def _configure_valid_section(section) -> None:
    section.orientation = WD_ORIENT.PORTRAIT
    section.page_width = Cm(21)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(2)
    section.bottom_margin = Cm(2)
    section.left_margin = Cm(2)
    section.right_margin = Cm(2)


def _add_body_paragraph(doc: Document, text: str):
    paragraph = doc.add_paragraph()
    paragraph.paragraph_format.line_spacing = 1.5
    run = paragraph.add_run(text)
    run.font.name = "Times New Roman"
    run.font.size = Pt(12)
    return paragraph


def _docx_bytes(doc: Document, *, pages: int) -> io.BytesIO:
    output = io.BytesIO()
    doc.save(output)
    output = io.BytesIO(_set_docx_page_count(output.getvalue(), pages))
    output.seek(0)
    return output


def _valid_docx_bytes() -> io.BytesIO:
    doc = Document()
    _configure_valid_section(doc.sections[0])
    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(12)
    _add_body_paragraph(doc, "Текст статьи " * 620)
    return _docx_bytes(doc, pages=4)


def _validate_global(content: io.BytesIO):
    validator = Validator(content)
    validator.validate_global_requirements()
    return validator.errors, validator.errors_eng


def _add_superscript_run(paragraph, text: str) -> None:
    run = paragraph.add_run(text)
    run.font.name = "Times New Roman"
    run.font.size = Pt(12)
    run.font.superscript = True
    run.bold = True


def _add_article_paragraph(doc: Document, text: str, *, bold: bool = False):
    paragraph = doc.add_paragraph()
    paragraph.paragraph_format.line_spacing = 1.5
    run = paragraph.add_run(text)
    run.font.name = "Times New Roman"
    run.font.size = Pt(12)
    run.bold = bold
    return paragraph


def _add_author_paragraph(doc: Document, name: str, marker: str, email: str):
    paragraph = doc.add_paragraph()
    paragraph.paragraph_format.line_spacing = 1.5
    name_run = paragraph.add_run(name)
    name_run.font.name = "Times New Roman"
    name_run.font.size = Pt(12)
    name_run.bold = True
    _add_superscript_run(paragraph, marker)
    email_run = paragraph.add_run(f" {email}")
    email_run.font.name = "Times New Roman"
    email_run.font.size = Pt(12)
    return paragraph


def _long_text(seed: str, min_length: int = 700) -> str:
    parts = []
    while len(" ".join(parts)) < min_length:
        parts.append(seed)
    return " ".join(parts)


def _valid_article_document() -> Document:
    doc = Document()
    _configure_valid_section(doc.sections[0])
    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(12)

    _add_article_paragraph(doc, "УДК 520.607")
    _add_article_paragraph(doc, "Экономика многоразовости будущей космонавтики и вопросы оперативности", bold=True)
    _add_author_paragraph(doc, "Иванов Иван Иванович", "1", "ivanov@example.com")
    _add_article_paragraph(doc, "SPIN-код: 1234-5678")
    _add_author_paragraph(doc, "Петров Петр Петрович", "2(*)", "petrov@example.com")
    _add_article_paragraph(doc, "1 ФГБУ НПО Тайфун, Москва, Россия")
    _add_article_paragraph(doc, "2 МГТУ им. Н.Э. Баумана, Москва, Россия")
    _add_article_paragraph(doc, "Аннотация. " + _long_text("Рассмотрены перспективы развития технологий и экономики многоразовых космических систем."))
    _add_article_paragraph(
        doc,
        "Ключевые слова: энергообеспечение, загрязнение окружающей среды, нанотехнологии, экологическое равновесие, свойства наноматериалов",
    )
    _add_article_paragraph(doc, "Economy of Reusability of Future Cosmonautics and Issues of Efficiency", bold=True)
    _add_author_paragraph(doc, "Ivanov Ivan Ivanovich", "1", "ivanov@example.com")
    _add_article_paragraph(doc, "SPIN-code: 1234-5678")
    _add_author_paragraph(doc, "Petrov Petr Petrovich", "2(*)", "petrov@example.com")
    _add_article_paragraph(doc, "1 FSBI NPO Typhoon, Moscow, Russia")
    _add_article_paragraph(doc, "2 BMSTU, Moscow, Russia")
    _add_article_paragraph(doc, "Abstract. " + _long_text("The article considers technological and economic aspects of reusable space systems."))
    _add_article_paragraph(
        doc,
        "Keywords: energy supply, environmental pollution, nanotechnology, ecological balance, material properties",
    )
    _add_article_paragraph(doc, "Introduction. " + ("This main article text is intentionally written in English. " * 90))
    _add_article_paragraph(doc, "Список источников")
    _add_article_paragraph(doc, "[1] Source title. Moscow, Publisher, 2024, 10 p.")
    return doc


def _valid_article_docx_bytes() -> io.BytesIO:
    return _docx_bytes(_valid_article_document(), pages=4)


def _add_hyperlink(paragraph, text: str, url: str) -> None:
    relationship_id = paragraph.part.relate_to(url, RT.HYPERLINK, is_external=True)
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), relationship_id)
    run = OxmlElement("w:r")
    text_element = OxmlElement("w:t")
    text_element.text = text
    run.append(text_element)
    hyperlink.append(run)
    paragraph._p.append(hyperlink)


class ValidatorGlobalRequirementsTest(unittest.TestCase):
    def test_global_requirements_pass_for_valid_docx(self):
        errors_ru, errors_en = _validate_global(_valid_docx_bytes())

        self.assertEqual([], errors_ru)
        self.assertEqual([], errors_en)

    def test_global_requirements_report_common_violations(self):
        doc = Document()
        section = doc.sections[0]
        section.page_width = Cm(20)
        section.page_height = Cm(28)
        section.top_margin = Cm(1)
        section.bottom_margin = Cm(1)
        section.left_margin = Cm(1)
        section.right_margin = Cm(1)

        paragraph = doc.add_paragraph()
        paragraph.paragraph_format.line_spacing = 1
        run = paragraph.add_run("Short text")
        run.font.name = "Arial"
        run.font.size = Pt(14)
        _add_hyperlink(paragraph, "link", "https://example.com")
        doc.add_section()

        errors_ru, _ = _validate_global(_docx_bytes(doc, pages=2))

        self.assertIn("Материалы должны быть представлены на формате А4", errors_ru)
        self.assertIn("Отступ сверху должен равняться 2 см", errors_ru)
        self.assertIn("Общий объем статьи должен составлять 4-6 страниц", errors_ru)
        self.assertIn("Минимальный объем статьи должен составлять 6000 знаков с пробелами", errors_ru)
        self.assertIn(
            "В тексте статьи необходимо использовать шрифт Times New Roman, за исключением математических формул",
            errors_ru,
        )
        self.assertIn("Межстрочный интервал должен равняться 1.5", errors_ru)
        self.assertIn("Применять гиперссылки в тексте не допускается", errors_ru)
        self.assertIn("Разрывы разделов внутри текста не допускаются", errors_ru)

    def test_font_check_ignores_empty_runs_and_formula_runs(self):
        doc = Document()
        _configure_valid_section(doc.sections[0])
        _add_body_paragraph(doc, "Текст статьи " * 620)
        paragraph = _add_body_paragraph(doc, "Формула: ")

        empty_run = paragraph.add_run("")
        empty_run.font.name = "Arial"
        empty_run.font.size = Pt(18)

        formula_run = paragraph.add_run("x")
        formula_run.font.name = "Cambria Math"
        formula_run.font.size = Pt(10)
        formula_run._element.append(
            parse_xml(
                '<m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">'
                "<m:r><m:t>x</m:t></m:r>"
                "</m:oMath>"
            )
        )

        errors_ru, _ = _validate_global(_docx_bytes(doc, pages=4))

        self.assertNotIn(
            "В тексте статьи необходимо использовать шрифт Times New Roman, за исключением математических формул",
            errors_ru,
        )
        self.assertNotIn("Размер шрифта должен быть 12", errors_ru)

    def test_hyperlink_check_allows_email_links(self):
        doc = Document()
        _configure_valid_section(doc.sections[0])
        _add_body_paragraph(doc, "Текст статьи " * 620)
        paragraph = _add_body_paragraph(doc, "Контакт: ")
        _add_hyperlink(paragraph, "e-mail", "mailto:author@example.com")

        errors_ru, _ = _validate_global(_docx_bytes(doc, pages=4))

        self.assertNotIn("Применять гиперссылки в тексте не допускается", errors_ru)

    def test_valid_article_structure_metadata_and_annotations_pass(self):
        errors_ru, errors_en = Validator(_valid_article_docx_bytes()).validate()

        self.assertEqual([], errors_ru)
        self.assertEqual([], errors_en)

    def test_article_structure_requires_main_text(self):
        doc = _valid_article_document()
        doc.paragraphs[-3].clear()

        errors_ru, _ = Validator(_docx_bytes(doc, pages=4)).validate()

        self.assertIn("Основной текст статьи не найден", errors_ru)

    def test_article_structure_requires_sources_heading(self):
        doc = _valid_article_document()
        doc.paragraphs[-2].clear()

        errors_ru, _ = Validator(_docx_bytes(doc, pages=4)).validate()

        self.assertIn("Список источников не найден", errors_ru)

    def test_metadata_and_keyword_violations_are_reported(self):
        doc = _valid_article_document()
        doc.paragraphs[0].text = "УДК wrong"
        doc.paragraphs[1].text = "Короткий заголовок"
        doc.paragraphs[7].text = "Аннотация. Слишком коротко."
        doc.paragraphs[8].text = "Ключевые слова: PLM; слишком длинная ключевая фраза из пяти слов"
        doc.paragraphs[15].text = "Abstract. Too short."
        doc.paragraphs[16].text = "Keywords: AI, one, two, three"

        errors_ru, _ = Validator(_docx_bytes(doc, pages=4)).validate()

        self.assertIn("УДК должен быть указан в формате «УДК 520.607»", errors_ru)
        self.assertIn("Заголовок статьи должен содержать от 6 до 15 слов", errors_ru)
        self.assertIn("Аннотация должна содержать от 650 до 1000 знаков с пробелами", errors_ru)
        self.assertIn("Аннотация на английском языке должна содержать от 650 до 1000 знаков с пробелами", errors_ru)
        self.assertIn("Ключевые слова должны разделяться запятыми", errors_ru)
        self.assertIn("Ключевые слова не должны содержать аббревиатуры", errors_ru)
        self.assertIn("Ключевых слов на английском языке должно быть от 5 до 7", errors_ru)


if __name__ == "__main__":
    unittest.main()
