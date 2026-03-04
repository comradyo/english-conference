from typing import Annotated, Literal

from pydantic import BaseModel, EmailStr, StringConstraints


PARTICIPATION_OPTIONS = (
    "Выступление с презентацией",
    "Online-презентация (для иногородних участников)",
    "Публикация в сборнике (без презентации)",
    "Гость",
)

SECTION_OPTIONS = (
    "Электроника и лазерная техника",
    "Фундаментальная математика и физика",
    "Инженерные технологии",
    "Машиностроение",
    "Энергетика",
    "Робототехника и комплексная автоматизация",
    "Информатика и ИТ",
    "Биомедицинские технологии",
    "Инженерный бизнес и менеджмент",
    "Гуманитарные науки",
)

REVIEW_STATUSES = ("На рассмотрении", "Принята", "Отклонена")
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024

NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
OptionalText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
PhoneNumber = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=7,
        max_length=32,
        pattern=r"^[0-9+()\-\s]+$",
    ),
]
RegistrationPassword = Annotated[str, StringConstraints(min_length=8, max_length=128)]
LoginPassword = Annotated[str, StringConstraints(min_length=1, max_length=128)]
ResetToken = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=256)]


class AccountRegistrationPayload(BaseModel):
    email: EmailStr
    password: RegistrationPassword
    password_repeat: RegistrationPassword


class AccountLoginPayload(BaseModel):
    email: EmailStr
    password: LoginPassword


class PasswordResetRequestPayload(BaseModel):
    email: EmailStr


class PasswordResetConfirmPayload(BaseModel):
    token: ResetToken
    password: RegistrationPassword
    password_repeat: RegistrationPassword


class ConferenceRegistrationPayload(BaseModel):
    last_name: NonEmptyText
    first_name: NonEmptyText
    middle_name: OptionalText | None = None
    place_of_study: NonEmptyText
    department: NonEmptyText
    place_of_work: OptionalText | None = None
    job_title: OptionalText | None = None
    phone: PhoneNumber
    email: EmailStr
    participation: Literal[
        "Выступление с презентацией",
        "Online-презентация (для иногородних участников)",
        "Публикация в сборнике (без презентации)",
        "Гость",
    ]
    section: Literal[
        "Электроника и лазерная техника",
        "Фундаментальная математика и физика",
        "Инженерные технологии",
        "Машиностроение",
        "Энергетика",
        "Робототехника и комплексная автоматизация",
        "Информатика и ИТ",
        "Биомедицинские технологии",
        "Инженерный бизнес и менеджмент",
        "Гуманитарные науки",
    ]
    publication_title: NonEmptyText
    foreign_language_consultant: NonEmptyText
