from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, EmailStr, HttpUrl


class TildaSubmission(BaseModel):
    last_name: str = Field(alias="Фамилия")
    first_name: str = Field(alias="Имя")
    middle_name: str = Field(alias="Отчество")

    place_of_study: str = Field(alias="Место_учебы")
    department: str = Field(alias="Кафедра")
    place_of_work: str = Field(alias="Место_работы")
    position: str = Field(alias="Должность")

    phone: str = Field(alias="Телефон_для_связи")
    email: EmailStr = Field(alias="Электронная_почта")

    participation: str = Field(alias="Участие")
    section: str = Field(alias="Секция")

    publication_title: str = Field(alias="Название_публикации")
    language_consultant: str = Field(alias="Консультант_по_языку")
    publication_file_url: HttpUrl = Field(alias="Файл_публикации")

    # служебные поля, которые Tilda часто присылает
    tranid: Optional[str] = None
    formid: Optional[str] = None
    cookies: Optional[str] = Field(default=None, alias="COOKIES")

    model_config = ConfigDict(populate_by_name=True, extra="ignore")
