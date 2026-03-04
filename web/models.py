from typing import Annotated, Literal

from pydantic import BaseModel, EmailStr, StringConstraints

PARTICIPATION_OPTIONS = ("онлайн", "выступление с презентацией")
SECTION_OPTIONS = ("ИБМ", "ИУ")
REVIEW_STATUSES = ("На рассмотрении", "Принята", "Отклонена")
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024

NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
RegistrationPassword = Annotated[str, StringConstraints(min_length=8, max_length=128)]
LoginPassword = Annotated[str, StringConstraints(min_length=1, max_length=128)]


class AccountRegistrationPayload(BaseModel):
    email: EmailStr
    password: RegistrationPassword
    password_repeat: RegistrationPassword


class AccountLoginPayload(BaseModel):
    email: EmailStr
    password: LoginPassword


class ConferenceRegistrationPayload(BaseModel):
    last_name: NonEmptyText
    first_name: NonEmptyText
    place_of_study: NonEmptyText
    department: NonEmptyText
    phone: NonEmptyText
    email: EmailStr
    participation: Literal["онлайн", "выступление с презентацией"]
    section: Literal["ИБМ", "ИУ"]
    publication_title: NonEmptyText
    language_consultant: NonEmptyText
