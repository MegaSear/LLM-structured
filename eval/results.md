# Результаты оценки качества

Выборка: 11 размеченных вручную заявок (`data/samples/` + `data/gt/gt.json`).

**Точность решения "заявка полная / неполная": 100%**

## Точность определения статуса поля (found / ambiguous / missing)

| Поле | Точность |
|---|---|
| company | 100% |
| station_from | 91% |
| station_to | 91% |
| cargo | 100% |
| volume | 100% |
| period | 100% |
| loading_conditions | 100% |
| budget | 100% |

## Точность значения (только там, где поле найдено и по золоту, и по системе)

| Поле | Точность |
|---|---|
| company | 100% |
| station_from | 100% |
| station_to | 100% |
| cargo | 100% |
| volume | 100% |
| period | 78% |
| loading_conditions | 100% |
| budget | 80% |

## Расхождения

- sample_10_ambiguous_route.txt / station_from: expected status='ambiguous', got status='found' (value='Ростов-на-Дону')
- sample_10_ambiguous_route.txt / station_to: expected status='found', got status='missing' (value=None)
- sample_10_ambiguous_route.txt / period: value mismatch, expected~'вторая половина октября 2026 года', got 'октябрь 2026'
- sample_11_noise.txt / period: value mismatch, expected~'ноябрь 2026 года', got 'ноябрь 2026'
- sample_11_noise.txt / budget: value mismatch, expected~{'amount': 1400.0, 'currency': 'RUB'}, got {'amount': 1000.0, 'currency': 'RUB', 'per_unit': 'тонна'}
