from typing import Annotated, Literal

from pydantic import BaseModel, EmailStr, StringConstraints


PARTICIPATION_ORAL_PRESENTATION = "Выступление с презентацией"
PARTICIPATION_ORAL_PRESENTATION_WITHOUT_PUBLICATION = "Выступление с презентацией без публикации"
PARTICIPATION_ONLINE_PRESENTATION = "Online-презентация (для иногородних участников)"
PARTICIPATION_PUBLICATION_ONLY = "Публикация в сборнике (без презентации)"
PARTICIPATION_GUEST = "Гость"

PARTICIPATION_OPTIONS = (
    PARTICIPATION_ORAL_PRESENTATION,
    PARTICIPATION_ORAL_PRESENTATION_WITHOUT_PUBLICATION,
    PARTICIPATION_ONLINE_PRESENTATION,
    PARTICIPATION_PUBLICATION_ONLY,
    PARTICIPATION_GUEST,
)

OPTIONAL_PUBLICATION_PARTICIPATION_OPTIONS = frozenset(
    {
        PARTICIPATION_ORAL_PRESENTATION_WITHOUT_PUBLICATION,
        PARTICIPATION_GUEST,
    }
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

REVIEW_STATUSES = ("На рассмотрении", "Принята", "На доработке", "Отклонена")
PARTICIPATION_STATUSES = (
    "На рассмотрении",
    "Отклонено",
    "Подтверждено. Ждём вас на конференции",
)
PENDING_REVIEW_STATUS = REVIEW_STATUSES[0]
REVISION_REVIEW_STATUS = REVIEW_STATUSES[2]
CONFIRMED_PARTICIPATION_STATUS = PARTICIPATION_STATUSES[2]
EDITABLE_REVIEW_STATUSES = (PENDING_REVIEW_STATUS, REVISION_REVIEW_STATUS)
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

ConferenceParticipation = Literal[
    PARTICIPATION_ORAL_PRESENTATION,
    PARTICIPATION_ORAL_PRESENTATION_WITHOUT_PUBLICATION,
    PARTICIPATION_ONLINE_PRESENTATION,
    PARTICIPATION_PUBLICATION_ONLY,
    PARTICIPATION_GUEST,
]


def participation_requires_publication_file(participation: str) -> bool:
    return participation not in OPTIONAL_PUBLICATION_PARTICIPATION_OPTIONS


def author_can_edit_registration(
    *,
    participation: str,
    participation_status: str,
    review_status: str,
) -> bool:
    if participation_requires_publication_file(participation):
        return review_status in EDITABLE_REVIEW_STATUSES
    return participation_status != CONFIRMED_PARTICIPATION_STATUS


def author_can_delete_registration(
    *,
    participation: str,
    participation_status: str,
    review_status: str,
) -> bool:
    if participation_requires_publication_file(participation):
        return review_status == PENDING_REVIEW_STATUS
    return participation_status != CONFIRMED_PARTICIPATION_STATUS


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
    department: OptionalText | None = None
    place_of_work: NonEmptyText
    job_title: OptionalText | None = None
    phone: PhoneNumber
    email: EmailStr
    participation: ConferenceParticipation
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
