from typing import Dict, List, Union


def formdata_to_dict(form) -> Dict[str, Union[str, List[str]]]:
    """
    FormData/Multidict -> dict.
    Если ключ встречается несколько раз — собираем в список.
    """
    out: Dict[str, Union[str, List[str]]] = {}
    for key in form.keys():
        values = form.getlist(key)
        if not values:
            continue
        out[key] = values[0] if len(values) == 1 else values
    return out
