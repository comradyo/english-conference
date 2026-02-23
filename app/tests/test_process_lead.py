import pytest
from types import SimpleNamespace

from services.lead_service import process_lead


class FakeInsertResult:
    inserted_id = "fake_id_123"


class FakeCollection:
    def __init__(self):
        self.doc = None

    async def insert_one(self, doc):
        self.doc = doc
        return FakeInsertResult()


@pytest.mark.asyncio
async def test_process_lead_normalizes_and_sets_file_pending():
    fake_collection = FakeCollection()
    fake_app = SimpleNamespace(
        state=SimpleNamespace(mongo_collection=fake_collection)
    )

    payload = {
        "Фамилия": "Романов",
        "Имя": "Евгений",
        "Отчество": "Игоревич",
        "Место_учебы": "МГТУ",
        "Кафедра": "МТ1",
        "Место_работы": "Газпром",
        "Должность": "Стажёр",
        "Телефон_для_связи": "+7 (800) 123-45-67",
        "Электронная_почта": "mail@mail.ru",
        "Участие": "выступление с презентацией",
        "Секция": "Электроника и лазерная техника",
        "Название_публикации": "Yellow world",
        "Консультант_по_языку": "Иванов",
        "Файл_публикации": "https://tupwidget.com/xxx/test_tilda76220179.docx",
        "tranid": "t1",
        "formid": "f1",
        "COOKIES": "utm_source=test",
    }

    inserted_id = await process_lead(payload, "https://example.com/page", fake_app)
    assert inserted_id == "fake_id_123"

    doc = fake_collection.doc
    assert doc["meta"]["referer"] == "https://example.com/page"
    assert doc["meta"]["tranid"] == "t1"

    # нормализованные поля (snake_case)
    assert doc["submission"]["email"] == "mail@mail.ru"
    assert doc["submission"]["publication_title"] == "Yellow world"
    assert doc["submission"]["publication_file_url"].endswith((".doc", ".docx"))
