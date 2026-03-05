from __future__ import annotations

from typing import Any

from models import PARTICIPATION_OPTIONS, REVIEW_STATUSES, SECTION_OPTIONS


DEFAULT_LANGUAGE = "ru"
SUPPORTED_LANGUAGES = ("ru", "en")
LANGUAGE_COOKIE_NAME = "site_lang"

TEXTS: dict[str, dict[str, str]] = {
    "footer": {
        "ru": "© 2026 Московский государственный технический университет им. Н.Э. Баумана",
        "en": "© 2026 Bauman Moscow State Technical University",
    },
    "language_ru": {"ru": "Русский", "en": "Russian"},
    "language_en": {"ru": "English", "en": "English"},
    "language_switcher_label": {"ru": "Язык", "en": "Language"},
    "guest": {"ru": "Гость", "en": "Guest"},
    "role_admin": {"ru": "Администратор", "en": "Administrator"},
    "role_user": {"ru": "Пользователь", "en": "User"},
    "nav_auth": {"ru": "Вход и регистрация", "en": "Sign in and registration"},
    "nav_register": {"ru": "Создание заявки", "en": "Creating an application"},
    "nav_my_records": {"ru": "Мои заявки", "en": "My applications"},
    "nav_all_records": {"ru": "Все заявки", "en": "All applications"},
    "nav_logout": {"ru": "Выйти", "en": "Log out"},
    "notice_login_required": {"ru": "Сначала войдите в личный кабинет.", "en": "Please sign in first."},
    "notice_logged_out": {"ru": "Сеанс завершён.", "en": "You have been signed out."},
    "notice_comment_saved": {
        "ru": "Комментарий и статус заявки сохранены.",
        "en": "The comment and application status have been saved.",
    },
    "notice_password_reset_email_queued": {
        "ru": "Если аккаунт с таким email существует, мы отправили ссылку для смены пароля.",
        "en": "If an account with this email exists, we have sent a password reset link.",
    },
    "notice_password_changed": {
        "ru": "Пароль обновлён. Теперь можно войти с новым паролем.",
        "en": "Your password has been updated. You can now sign in with the new password.",
    },
    "not_specified": {"ru": "Не указано", "en": "Not specified"},
    "not_uploaded": {"ru": "Не загружен", "en": "Not uploaded"},
    "see_nested_fields": {"ru": "См. вложенные поля", "en": "See nested fields"},
    "no_remarks": {"ru": "Нет замечаний", "en": "No remarks"},
    "comment_not_added": {"ru": "Комментарий пока не добавлен.", "en": "No comment has been added yet."},
    "comment_not_specified": {"ru": "Комментарий не указан.", "en": "No comment provided."},
    "unnamed_record": {"ru": "Заявка без имени", "en": "Application without a name"},
    "unnamed_person": {"ru": "Без имени", "en": "Unnamed"},
    "without_section": {"ru": "Без секции", "en": "No section"},
    "participant_fallback": {"ru": "Участник", "en": "Participant"},
    "untitled_publication": {"ru": "Без названия", "en": "Untitled"},
    "file_name_prefix": {"ru": "Файл:", "en": "File:"},
    "bytes_unit": {"ru": "байт", "en": "bytes"},
    "timezone_suffix": {"ru": "МСК", "en": "MSK"},
    "auth_page_title": {"ru": "Личный кабинет конференции", "en": "Conference personal account"},
    "auth_login_title": {"ru": "Вход в личный кабинет", "en": "Sign in"},
    "auth_login_desc": {
        "ru": "Введите email и пароль, чтобы открыть форму регистрации на конференцию и список своих заявок.",
        "en": "Enter your email and password to access the conference registration form and your applications.",
    },
    "auth_email": {"ru": "Адрес электронной почты", "en": "Email address"},
    "auth_password": {"ru": "Пароль", "en": "Password"},
    "auth_repeat_password": {"ru": "Повторите пароль", "en": "Repeat password"},
    "auth_sign_in": {"ru": "Войти", "en": "Sign in"},
    "auth_create_account": {"ru": "Создать аккаунт", "en": "Create account"},
    "auth_register_title": {"ru": "Регистрация", "en": "Registration"},
    "auth_register_desc": {
        "ru": "Создайте личный кабинет. Повторно зарегистрировать тот же email нельзя.",
        "en": "Create a personal account. The same email address cannot be registered twice.",
    },
    "auth_register_button": {"ru": "Зарегистрироваться", "en": "Register"},
    "auth_back_to_login": {"ru": "Назад ко входу", "en": "Back to sign in"},
    "auth_forgot_password": {"ru": "Забыли пароль?", "en": "Forgot your password?"},
    "forgot_title": {"ru": "Смена пароля", "en": "Password reset"},
    "forgot_desc": {
        "ru": "Введите адрес электронной почты. Если аккаунт существует, мы отправим ссылку для установки нового пароля.",
        "en": "Enter your email address. If the account exists, we will send a link to set a new password.",
    },
    "forgot_button": {"ru": "Отправить ссылку", "en": "Send link"},
    "reset_page_title": {"ru": "Смена пароля", "en": "Password reset"},
    "reset_title": {"ru": "Новый пароль", "en": "New password"},
    "reset_desc": {
        "ru": "Введите новый пароль для вашего аккаунта. Ссылка действует ограниченное время.",
        "en": "Enter a new password for your account. The link is valid for a limited time.",
    },
    "reset_save_button": {"ru": "Сохранить новый пароль", "en": "Save new password"},
    "reset_invalid_title": {"ru": "Ссылка недействительна", "en": "The link is invalid"},
    "reset_invalid_desc": {
        "ru": "Запросите новое письмо для смены пароля и используйте свежую ссылку.",
        "en": "Request a new password reset email and use the fresh link.",
    },
    "back_to_login": {"ru": "Вернуться ко входу", "en": "Back to sign in"},
    "conference_page_title": {"ru": "Создание заявки", "en": "Creating an application"},
    "conference_title": {"ru": "Создание заявки", "en": "Creating an application"},
    "conference_desc": {
        "ru": 'После сохранения заявка появится в разделе "Мои заявки".',
        "en": 'After saving, the application will appear in the "My applications" section.',
    },
    "precheck_title": {
        "ru": "Предварительная проверка файла публикации",
        "en": "Preliminary publication file validation",
    },
    "precheck_desc": {
        "ru": "Загрузите .docx-файл, чтобы проверить его перед отправкой основной заявки.",
        "en": "Upload a .docx file to validate it before submitting the main application.",
    },
    "precheck_result": {"ru": "Результат проверки", "en": "Validation result"},
    "precheck_button": {"ru": "Проверить файл", "en": "Validate file"},
    "placeholder_last_name": {"ru": "Иванов", "en": "Smith"},
    "placeholder_first_name": {"ru": "Иван", "en": "Jack"},
    "placeholder_place_of_study": {"ru": "МГТУ им. Н.Э. Баумана", "en": "BMSTU"},
    "placeholder_department": {"ru": "Л2", "en": "student"},
    "placeholder_phone": {"ru": "+79001000102", "en": "+79001000102"},
    "placeholder_email": {"ru": "example@bmstu.ru", "en": "example@bmstu.ru"},
    "hint_publication_file": {"ru": "Формат docx, размер <10Мб", "en": "docx, <10Мб"},
    "hint_expert_opinion_file": {
        "ru": "При отсутствии на момент подачи заявки необходимо впоследствии отправить на graduate.applications@yandex.ru",
        "en": "If unavailable at the time of application should be sent subsequently to graduate.applications@yandex.ru",
    },
    "modal_close": {"ru": "Закрыть", "en": "Close"},
    "modal_success_title": {"ru": "Заявка сохранена", "en": "Application saved"},
    "submit_application": {"ru": "Сохранить заявку", "en": "Save application"},
    "required_note": {
        "ru": "Поля, обязательные для заполнения.",
        "en": "Fields marked with * are required.",
    },
    "validation_result_label": {
        "ru": "Результат автопроверки файла",
        "en": "Automatic validation result",
    },
    "publication_file_size": {"ru": "Размер файла публикации", "en": "Publication file size"},
    "expert_file_size": {"ru": "Размер экспертного заключения", "en": "Expert opinion file size"},
    "owner_account_email": {"ru": "Владелец аккаунта", "en": "Account owner"},
    "records_my_title": {"ru": "Мои заявки", "en": "My applications"},
    "records_admin_title": {"ru": "Все заявки пользователей", "en": "All user applications"},
    "records_empty_my": {
        "ru": "Вы ещё не оставляли заявок на конференцию.",
        "en": "You have not submitted any conference applications yet.",
    },
    "records_empty_admin": {"ru": "В системе пока нет заявок.", "en": "There are no applications in the system yet."},
    "records_empty_action": {"ru": "Перейти к форме регистрации", "en": "Go to the registration form"},
    "highlight_status": {"ru": "Статус", "en": "Status"},
    "highlight_validation": {
        "ru": "Автопроверка файла публикации",
        "en": "Automatic publication file validation",
    },
    "highlight_comment": {"ru": "Комментарий к заявке", "en": "Application comment"},
    "admin_side_empty_title": {"ru": "Действия по заявке", "en": "Application actions"},
    "admin_side_empty_desc": {
        "ru": "Нажмите на строку в таблице, чтобы открыть инструменты для выбранной заявки.",
        "en": "Click a table row to open tools for the selected application.",
    },
    "admin_tools_desc": {
        "ru": "Вы можете скачать файлы, изменить статус и оставить комментарий к заявке.",
        "en": "You can download files, change the status, and leave a comment for the application.",
    },
    "admin_download_publication": {"ru": "Скачать публикацию", "en": "Download publication"},
    "admin_download_expert": {"ru": "Скачать экспертное заключение", "en": "Download expert opinion"},
    "admin_save": {"ru": "Сохранить и уведомить по Email", "en": "Save and notify by Email"},
    "admin_table_participant": {"ru": "Участник", "en": "Participant"},
    "admin_table_contacts": {"ru": "Контакты", "en": "Contacts"},
    "admin_table_participation": {"ru": "Участие", "en": "Participation"},
    "admin_table_publication": {"ru": "Публикация", "en": "Publication"},
    "admin_table_status": {"ru": "Статус", "en": "Status"},
    "admin_table_created_at": {"ru": "Создано", "en": "Created"},
    "section_count": {"ru": "({count} заявок)", "en": "({count} applications)"},
    "forbidden_title": {"ru": "Доступ запрещён", "en": "Access denied"},
    "forbidden_body": {
        "ru": "Для просмотра этой страницы нужны права администратора.",
        "en": "Administrator rights are required to view this page.",
    },
    "forbidden_error": {"ru": "Недостаточно прав доступа.", "en": "Insufficient permissions."},
    "error_title": {"ru": "Ошибка", "en": "Error"},
    "task_not_queued_title": {"ru": "Задача не поставлена", "en": "Task not queued"},
    "invalid_file_kind_body": {
        "ru": "Запрошенный тип файла не поддерживается.",
        "en": "The requested file type is not supported.",
    },
    "invalid_file_kind_error": {"ru": "Некорректный тип файла.", "en": "Invalid file type."},
    "record_not_found_body": {"ru": "Заявка не найдена.", "en": "Application not found."},
    "record_not_found_error": {"ru": "Заявка не найдена.", "en": "Application not found."},
    "invalid_record_id_error": {
        "ru": "Некорректный идентификатор заявки.",
        "en": "Invalid application identifier.",
    },
    "invalid_status_body": {"ru": "Указан недопустимый статус заявки.", "en": "An invalid application status was provided."},
    "invalid_status_error": {"ru": "Недопустимый статус заявки.", "en": "Invalid application status."},
    "email_task_runtime_body": {
        "ru": "Изменения в заявке сохранены, но задачу на отправку письма поставить не удалось. {link}",
        "en": "The application changes were saved, but the email task could not be queued. {link}",
    },
    "email_task_storage_body": {
        "ru": "Изменения в заявке сохранены, но очередь email-уведомлений сейчас недоступна. {link}",
        "en": "The application changes were saved, but the email notification queue is currently unavailable. {link}",
    },
    "queue_write_failed": {
        "ru": "Не удалось записать задачу в очередь: {error}",
        "en": "Failed to write the task to the queue: {error}",
    },
    "back_to_records_link": {"ru": "Вернуться к списку заявок", "en": "Back to the applications list"},
    "request_precheck_service_not_configured": {
        "ru": "Сервис предварительной проверки не настроен.",
        "en": "The preliminary validation service is not configured.",
    },
    "request_precheck_service_unavailable": {
        "ru": "Сервис предварительной проверки сейчас недоступен: {error}",
        "en": "The preliminary validation service is currently unavailable: {error}",
    },
    "request_precheck_empty_result": {
        "ru": "Сервис проверки не вернул текст результата.",
        "en": "The validation service returned an empty result.",
    },
    "invalid_email": {"ru": "Введите корректный адрес электронной почты.", "en": "Enter a valid email address."},
    "password_too_short": {
        "ru": "Пароль должен содержать не менее 8 символов.",
        "en": "The password must contain at least 8 characters.",
    },
    "auth_invalid_login_input": {
        "ru": "Введите корректные email и пароль.",
        "en": "Enter a valid email and password.",
    },
    "auth_invalid_credentials": {"ru": "Неверный email или пароль.", "en": "Incorrect email or password."},
    "auth_passwords_mismatch": {"ru": "Пароли не совпадают.", "en": "Passwords do not match."},
    "auth_registration_invalid": {
        "ru": "Проверьте данные для регистрации.",
        "en": "Please check the registration data.",
    },
    "auth_account_exists": {
        "ru": "Аккаунт с таким адресом электронной почты уже существует.",
        "en": "An account with this email address already exists.",
    },
    "auth_user_create_failed": {"ru": "Не удалось создать пользователя.", "en": "Failed to create the user."},
    "forgot_email_task_failed": {
        "ru": "Не удалось поставить задачу на отправку письма: {error}",
        "en": "Failed to queue the email task: {error}",
    },
    "reset_missing_token": {
        "ru": "Ссылка для смены пароля не содержит токен.",
        "en": "The password reset link does not contain a token.",
    },
    "reset_invalid_token": {
        "ru": "Ссылка для смены пароля недействительна или истекла.",
        "en": "The password reset link is invalid or has expired.",
    },
    "reset_user_not_found": {
        "ru": "Пользователь для этой ссылки не найден.",
        "en": "No user was found for this reset link.",
    },
    "form_invalid": {"ru": "Проверьте заполнение формы.", "en": "Please check the form fields."},
    "publication_read_failed": {
        "ru": "Не удалось прочитать файл публикации.",
        "en": "Failed to read the publication file.",
    },
    "registration_saved": {"ru": "Заявка сохранена.", "en": "The application has been saved."},
    "docx_file_required": {"ru": "{field}: файл обязателен.", "en": "{field}: the file is required."},
    "docx_only": {"ru": "{field}: можно загрузить только файл в формате .docx.", "en": "{field}: only .docx files are allowed."},
    "docx_empty": {"ru": "{field}: загруженный файл пуст.", "en": "{field}: the uploaded file is empty."},
    "docx_too_large": {
        "ru": "{field}: размер файла превышает допустимые {size} байт.",
        "en": "{field}: the file size exceeds the allowed limit of {size} bytes.",
    },
    "password_reset_email_invalid_recipient": {
        "ru": "Нельзя отправить письмо: указан некорректный email для сброса пароля.",
        "en": "Cannot send the email: the password reset recipient email is invalid.",
    },
    "password_reset_email_missing_link": {
        "ru": "Нельзя отправить письмо: отсутствует ссылка для сброса пароля.",
        "en": "Cannot send the email: the password reset link is missing.",
    },
    "registration_email_invalid_recipient": {
        "ru": "В заявке не указан корректный адрес электронной почты для уведомления.",
        "en": "The application does not contain a valid email address for notification.",
    },
    "checker_pending_status": {"ru": "Ожидает проверки. Обновите вкладку через несколько секунд.",
                               "en": "Pending validation. Please refresh the tab in a few seconds."},
    "checker_pending_summary": {
        "ru": "Файл публикации ожидает автоматической проверки. Обновите вкладку через несколько секунд.",
        "en": "The publication file is waiting for automatic validation. Please refresh the tab in a few seconds.",
    },
}

FIELD_LABELS: dict[str, dict[str, str]] = {
    "publication_validation": {"ru": "Автопроверка файла публикации", "en": "Publication file validation"},
    "publication_validation.status": {"ru": "Автопроверка: статус", "en": "Validation: status"},
    "publication_validation.summary": {"ru": "Автопроверка: итог", "en": "Validation: summary"},
    "publication_validation.errors": {"ru": "Автопроверка: замечания", "en": "Validation: remarks"},
    "publication_validation.checked_at": {"ru": "Автопроверка: завершена", "en": "Validation: completed"},
    "publication_validation.started_at": {"ru": "Автопроверка: начата", "en": "Validation: started"},
    "publication_validation.updated_at": {"ru": "Автопроверка: обновлена", "en": "Validation: updated"},
    "publication_validation.last_error": {"ru": "Автопроверка: системная ошибка", "en": "Validation: system error"},
    "_id": {"ru": "ID заявки", "en": "Application ID"},
    "owner_user_id": {"ru": "ID пользователя", "en": "User ID"},
    "owner_email": {"ru": "Email аккаунта", "en": "Account email"},
    "last_name": {"ru": "Фамилия", "en": "Surname"},
    "first_name": {"ru": "Имя", "en": "Name"},
    "middle_name": {"ru": "Отчество", "en": "Middle name"},
    "place_of_study": {"ru": "Место учёбы", "en": "University"},
    "department": {"ru": "Кафедра", "en": "Department"},
    "place_of_work": {"ru": "Место работы", "en": "Affiliation"},
    "job_title": {"ru": "Должность", "en": "Position"},
    "phone": {"ru": "Телефон для связи", "en": "Contact phone number"},
    "email": {"ru": "Электронная почта", "en": "Email"},
    "participation": {"ru": "Формат участия", "en": "Participation format"},
    "section": {"ru": "Секция", "en": "Scope"},
    "publication_title": {"ru": "Название публикации", "en": "Title of publication"},
    "foreign_language_consultant": {
        "ru": "ФИО Консультанта по иностранному языку",
        "en": "Language consultant's full name",
    },
    "publication_file": {"ru": "Файл публикации", "en": "Publication file"},
    "publication_file.filename": {"ru": "Файл публикации: имя", "en": "Publication file: name"},
    "publication_file.content_type": {"ru": "Файл публикации: тип", "en": "Publication file: type"},
    "publication_file.size_bytes": {"ru": "Файл публикации: размер", "en": "Publication file: size"},
    "expert_opinion_file": {"ru": "Экспертное заключение", "en": "Expert report"},
    "expert_opinion_file.filename": {"ru": "Экспертное заключение: имя", "en": "Expert report: name"},
    "expert_opinion_file.content_type": {"ru": "Экспертное заключение: тип", "en": "Expert report: type"},
    "expert_opinion_file.size_bytes": {"ru": "Экспертное заключение: размер", "en": "Expert report: size"},
    "review_status": {"ru": "Статус", "en": "Status"},
    "admin_comment": {"ru": "Комментарий к заявке", "en": "Application comment"},
    "created_at": {"ru": "Создано", "en": "Created"},
}

PARTICIPATION_LABELS = {
    PARTICIPATION_OPTIONS[0]: {"ru": PARTICIPATION_OPTIONS[0], "en": "Presentation with slides"},
    PARTICIPATION_OPTIONS[1]: {
        "ru": PARTICIPATION_OPTIONS[1],
        "en": "Online presentation (for participants from other cities)",
    },
    PARTICIPATION_OPTIONS[2]: {
        "ru": PARTICIPATION_OPTIONS[2],
        "en": "Publication in proceedings (without presentation)",
    },
    PARTICIPATION_OPTIONS[3]: {"ru": PARTICIPATION_OPTIONS[3], "en": "Guest"},
}

SECTION_LABELS = {
    SECTION_OPTIONS[0]: {"ru": SECTION_OPTIONS[0], "en": "Electronics and Laser Technology"},
    SECTION_OPTIONS[1]: {"ru": SECTION_OPTIONS[1], "en": "Fundamental Mathematics and Physics"},
    SECTION_OPTIONS[2]: {"ru": SECTION_OPTIONS[2], "en": "Engineering Technologies"},
    SECTION_OPTIONS[3]: {"ru": SECTION_OPTIONS[3], "en": "Mechanical Engineering"},
    SECTION_OPTIONS[4]: {"ru": SECTION_OPTIONS[4], "en": "Power Engineering"},
    SECTION_OPTIONS[5]: {"ru": SECTION_OPTIONS[5], "en": "Robotics and Complex Automation"},
    SECTION_OPTIONS[6]: {"ru": SECTION_OPTIONS[6], "en": "Computer Science and Information Technologies"},
    SECTION_OPTIONS[7]: {"ru": SECTION_OPTIONS[7], "en": "Biomedical Technologies"},
    SECTION_OPTIONS[8]: {"ru": SECTION_OPTIONS[8], "en": "Engineering Business and Management"},
    SECTION_OPTIONS[9]: {"ru": SECTION_OPTIONS[9], "en": "Humanities"},
}

REVIEW_STATUS_LABELS = {
    REVIEW_STATUSES[0]: {"ru": REVIEW_STATUSES[0], "en": "Under review"},
    REVIEW_STATUSES[1]: {"ru": REVIEW_STATUSES[1], "en": "Accepted"},
    REVIEW_STATUSES[2]: {"ru": REVIEW_STATUSES[2], "en": "Rejected"},
}


def resolve_language(value: str | None) -> str:
    if value in SUPPORTED_LANGUAGES:
        return value
    return DEFAULT_LANGUAGE


def text(lang: str, key: str, **kwargs: Any) -> str:
    language = resolve_language(lang)
    value = TEXTS.get(key, {}).get(language) or TEXTS.get(key, {}).get(DEFAULT_LANGUAGE) or key
    if kwargs:
        return value.format(**kwargs)
    return value


def notice_text(lang: str, key: str | None) -> str | None:
    if not key:
        return None
    notice_key = f"notice_{key}"
    if notice_key not in TEXTS:
        return None
    return text(lang, notice_key)


def field_label(lang: str, path: str) -> str:
    labels = FIELD_LABELS.get(path)
    if not labels:
        return path.replace("_", " ")
    return labels.get(resolve_language(lang), labels[DEFAULT_LANGUAGE])


def participation_label(lang: str, value: str) -> str:
    labels = PARTICIPATION_LABELS.get(value)
    if not labels:
        return value
    return labels.get(resolve_language(lang), labels[DEFAULT_LANGUAGE])


def section_label(lang: str, value: str) -> str:
    labels = SECTION_LABELS.get(value)
    if not labels:
        return value
    return labels.get(resolve_language(lang), labels[DEFAULT_LANGUAGE])


def review_status_label(lang: str, value: str) -> str:
    labels = REVIEW_STATUS_LABELS.get(value)
    if not labels:
        return value
    return labels.get(resolve_language(lang), labels[DEFAULT_LANGUAGE])


def validation_status_label(lang: str, value: str) -> str:
    if value == TEXTS["checker_pending_status"]["ru"]:
        return text(lang, "checker_pending_status")
    return value


def validation_summary_label(lang: str, value: str) -> str:
    if value == TEXTS["checker_pending_summary"]["ru"]:
        return text(lang, "checker_pending_summary")
    return value
