# -*- coding: utf-8 -*-
"""
Regenerates the binary-format sample requests (.eml/.docx/.pdf/.xlsx) in this
folder. The .txt samples are plain files and are committed directly -- this
script only exists because docx/pdf/xlsx are binary and easier to produce
than to hand-craft.

Run from the repo root:  python data/samples/make_samples.py
"""
from email.message import EmailMessage
from pathlib import Path

import docx
import openpyxl
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

HERE = Path(__file__).parent


def make_email():
    msg = EmailMessage()
    msg["Subject"] = "Заявка на перевозку — ООО Восток-Агро"
    msg["From"] = "logistics@vostok-agro.ru"
    msg["To"] = "sales@carrier.ru"
    msg.set_content(
        'Добрый день!\n\n'
        'Просим рассчитать перевозку. Компания — ООО "Восток-Агро".\n'
        'Груз: рожь. Объём: 25 вагонов.\n'
        'Отправление со станции Волгоград-1.\n'
        'Срок: сентябрь 2026.\n\n'
        'Условия и станцию назначения обсудим отдельно, пока не определились.\n'
        'Бюджет пока не готовы озвучить.\n\n'
        'С уважением, отдел логистики\n'
    )
    (HERE / "sample_05_email_missing_destination_budget.eml").write_bytes(bytes(msg))


def make_docx():
    d = docx.Document()
    for line in [
        "Заявка на перевозку",
        'Компания: ПАО "СибЗернопродукт-Восток"',
        "Груз: соя",
        "Отправление со станции Барнаул, назначение — станция Новороссийск",
        "Объём: 30 вагонов",
        "Срок перевозки: 01.11.2026 - 30.11.2026",
        "Погрузка: элеватор, силами отправителя",
        "Бюджет: 1500 руб. за тонну",
    ]:
        d.add_paragraph(line)
    d.save(HERE / "sample_06_full.docx")


def make_pdf():
    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    c = canvas.Canvas(str(HERE / "sample_07_partial_no_company.pdf"), pagesize=A4)
    try:
        pdfmetrics.registerFont(TTFont("DejaVu", font_path))
        c.setFont("DejaVu", 12)
    except Exception:
        c.setFont("Helvetica", 12)  # no Cyrillic glyphs, but keeps the script runnable anywhere
    lines = [
        "Заявка на перевозку зерновых", "",
        "Груз: пшеница",
        "Отправление со станции Курск",
        "Назначение: станция Новороссийск",
        "Объём: 40 вагонов",
        "Срок: 1 квартал 2027", "",
        "Компанию и условия погрузки уточним позже.",
    ]
    y = 800
    for line in lines:
        c.drawString(50, y, line)
        y -= 20
    c.save()


def make_xlsx():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Заявка"
    for row in [
        ("Поле", "Значение"),
        ("Компания", 'ООО "ЮгХлебТрейд"'),
        ("Груз", "ячмень"),
        ("Станция отправления", "Ставрополь"),
        ("Станция назначения", "Новороссийск-Экспортный"),
        ("Объём", "18 вагонов"),
        ("Период", "10.09.2026 - 25.09.2026"),
        ("Условия погрузки", "элеватор, погрузка силами отправителя"),
        ("Бюджет", "1100 руб. за тонну"),
    ]:
        ws.append(row)
    wb.save(HERE / "sample_09_full.xlsx")


if __name__ == "__main__":
    make_email()
    make_docx()
    make_pdf()
    make_xlsx()
    print("Samples (re)generated in", HERE)
