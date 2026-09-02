# -*- coding: utf-8 -*-
"""
Domain dictionaries for the (grain-only) rail freight request extractor.

These are intentionally simple, explicit lists rather than a black-box model:
every match can be traced back to the exact word/phrase that triggered it,
which is what we need for explainability (see REPORT.md).
"""

# Grain / grain-product cargo types we actually transport (per task scope).
# Maps canonical (dictionary) form -> surface forms seen in free text.
GRAIN_CARGO_FORMS: dict[str, list[str]] = {
    "пшеница": ["пшеница", "пшеницы", "пшеницу", "пшеницей"],
    "ячмень": ["ячмень", "ячменя", "ячменём", "ячменем"],
    "кукуруза": ["кукуруза", "кукурузы", "кукурузу", "кукурузой"],
    "рожь": ["рожь", "ржи"],
    "овёс": ["овёс", "овес", "овса", "овсом"],
    "просо": ["просо"],
    "гречиха": ["гречиха", "гречихи", "гречиху"],
    "соя": ["соя", "сои", "сою", "соей"],
    "подсолнечник": ["подсолнечник", "подсолнечника", "подсолнечником"],
    "рапс": ["рапс", "рапса", "рапсом"],
    "горох": ["горох", "гороха", "горохом"],
    "жмых": ["жмых", "жмыха"],
    "шрот": ["шрот", "шрота"],
    "отруби": ["отруби"],
    "комбикорм": ["комбикорм", "комбикорма"],
}
# Flat list of all surface forms, kept for anything that just needs to check
# "is this word grain-related at all".
GRAIN_CARGO_TYPES = [form for forms in GRAIN_CARGO_FORMS.values() for form in forms]

# Generic (non-specific) grain mentions -> cargo is present but AMBIGUOUS
# (we know it's "grain" but not which one, and that matters for wagon prep,
# fumigation requirements, etc.)
GENERIC_GRAIN_TERMS = ["зерно", "зерна", "зерновые", "зерновых", "зерновой груз"]

# A non-exhaustive but realistic set of RU railway stations that are
# actually relevant to grain traffic (export terminals in the South,
# Volga/Black-earth production regions, major junctions). Names are
# normalized to nominative case for matching; matching is done
# case-insensitively against morphological variants via simple stemming
# (see rule_extractor._normalize_station).
KNOWN_STATIONS = [
    "Новороссийск", "Новороссийск-Экспортный", "Тамань", "Вышестеблиевская",
    "Ейск", "Азов", "Кавказ", "Темрюк",
    "Ростов-на-Дону", "Ростов-Товарный", "Батайск", "Тихорецкая",
    "Краснодар", "Краснодар-Сортировочный", "Армавир",
    "Ставрополь", "Кавминводы", "Невинномысск",
    "Волгоград", "Волгоград-1", "Волжский",
    "Саратов", "Саратов-2", "Энгельс",
    "Самара", "Кинель",
    "Оренбург", "Орск",
    "Курск", "Воронеж", "Лиски", "Мичуринск", "Кочетовка", "Тамбов",
    "Липецк", "Белгород", "Старый Оскол",
    "Пенза", "Ртищево",
    "Омск", "Барнаул", "Славгород", "Рубцовск",
    "Новосибирск", "Татарская",
    "Москва-Товарная", "Москва-Курская",
    "Санкт-Петербург-Товарный-Витебский",
    "Калининград-Сортировочный",
]

# Legal-entity prefixes used to spot company names.
COMPANY_PREFIXES = [
    "ООО", "ОАО", "ЗАО", "АО", "ПАО", "ИП", "ФГУП", "ГК",
]

WAGON_WORDS = [
    "вагон", "вагона", "вагонов", "вагоны",
    "полувагон", "полувагона", "полувагонов",
    "хоппер", "хоппера", "хопперов", "зерновоз", "зерновоза", "зерновозов",
]

WEIGHT_UNIT_WORDS = ["тонна", "тонны", "тонн", "т.", " т ", "т,"]

MONTHS_RU = {
    "январ": 1, "феврал": 2, "март": 3, "апрел": 4, "ма": 5, "июн": 6,
    "июл": 7, "август": 8, "сентябр": 9, "октябр": 10, "ноябр": 11,
    "декабр": 12,
}

MONTH_NAMES_RU = {
    1: "январь", 2: "февраль", 3: "март", 4: "апрель", 5: "май", 6: "июнь",
    7: "июль", 8: "август", 9: "сентябрь", 10: "октябрь", 11: "ноябрь",
    12: "декабрь",
}

QUARTER_WORDS = ["квартал", "кв."]

CURRENCY_WORDS = {
    "руб": "RUB", "₽": "RUB", "рубл": "RUB",
    "$": "USD", "usd": "USD", "долл": "USD",
    "€": "EUR", "eur": "EUR", "евро": "EUR",
}

LOADING_CONDITION_KEYWORDS = [
    "элеватор", "самопогрузка", "силами отправителя", "силами грузоотправителя",
    "жд тупик", "ж/д тупик", "подъездной путь", "терминал",
    "погрузка", "выгрузка", "фумигация", "своими силами",
    "подача вагонов", "уборка вагонов", "fca", "dap", "cpt", "fob",
    "порт", "элеваторная погрузка", "механизированная погрузка",
]
