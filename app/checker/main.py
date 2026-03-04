import validator

validator = validator.Validator("test.docx")
errors = validator.validate()

if errors:
    print("Ошибки:")
    for e in errors:
        print("-", e)
else:
    print("Файл прошёл автоматическую проверку")
