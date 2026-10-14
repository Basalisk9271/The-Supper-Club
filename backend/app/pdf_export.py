"""Printable shopping checklist and recipes, generated without external requests."""
from html import escape
from io import BytesIO
from pathlib import Path

import reportlab
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

from .grocery import build_grocery_list, parse_ingredient

# ReportLab ships these fonts, so exports also work in the Docker image.
_font_dir = Path(reportlab.__file__).parent / "fonts"
pdfmetrics.registerFont(TTFont("Export", str(_font_dir / "Vera.ttf")))
pdfmetrics.registerFont(TTFont("ExportBold", str(_font_dir / "VeraBd.ttf")))


def build_meal_plan_pdf(recipes, selections, checked_items=()):
    output = BytesIO()
    styles = getSampleStyleSheet()
    for style in styles.byName.values():
        style.fontName = "Export"
        style.textColor = colors.HexColor("#222222")
    for name in ("Title", "Heading1", "Heading2"):
        styles[name].fontName = "ExportBold"
    styles["BodyText"].leading = 15
    styles["BodyText"].spaceAfter = 7
    styles["Heading2"].spaceBefore = 14
    story = []

    def paragraph(value, style="BodyText"):
        # Imported recipe text must never be interpreted as PDF markup.
        story.append(Paragraph(escape(str(value)).replace("\n", "<br/>"), styles[style]))

    paragraph("Grocery list", "Title")
    paragraph(f"The Supper Club | {len(recipes)} planned meals")
    for recipe in recipes:
        servings = selections[str(recipe["id"])].get("servings") or recipe.get("servings") or 1
        paragraph(f"{recipe['title']} — {servings:g} servings")
    paragraph("Checked items are marked [x]; all ingredients are included.")
    checked = set(checked_items)
    category = None
    items = build_grocery_list(recipes, selections)
    if not items:
        paragraph("No grocery ingredients available for these meals.")
    for item in items:
        if item["category"] != category:
            category = item["category"]
            paragraph(category, "Heading2")
        mark = "[x]" if (item["name"], item["unit"] or "") in checked else "[ ]"
        amount = " ".join(filter(None, [item["quantity_display"], item["unit"]]))
        paragraph(f"{mark} {amount} {item['name']}".strip())
        for note in dict.fromkeys(item["notes"]):
            paragraph(f"    Note: {note}")

    for recipe in recipes:
        story.append(PageBreak())
        paragraph(recipe["title"], "Title")
        base = recipe.get("servings")
        target = selections[str(recipe["id"])].get("servings") or base or 1
        paragraph(f"Planned servings: {target:g}" + (f" | Original servings: {base:g}" if base else ""))
        times = [f"{label}: {recipe[key]} minutes" for label, key in
                 (("Prep", "prep_minutes"), ("Cook", "cook_minutes"), ("Total", "total_minutes")) if recipe.get(key)]
        if times:
            paragraph(" | ".join(times))
        if recipe.get("description"):
            paragraph(recipe["description"])
        paragraph("Ingredients", "Heading2")
        multiplier = target / base if base else 1
        if not base:
            paragraph("Original yield is unknown; ingredient amounts are unchanged.")
        for line in recipe.get("ingredients", []):
            parsed = parse_ingredient(line)
            if multiplier != 1 and parsed["quantity"] is not None:
                amount = f"{parsed['quantity'] * multiplier:.3f}".rstrip("0").rstrip(".")
                line = " ".join(filter(None, [amount, parsed["unit"], parsed["name"]]))
            paragraph(f"• {line}")
        paragraph("Instructions", "Heading2")
        if multiplier != 1:
            paragraph("Ingredients above reflect planned servings. Quantities mentioned in the original instructions may need adjusting.")
        instructions = recipe.get("instructions", [])
        for index, step in enumerate(instructions, 1):
            paragraph(f"{index}. {step}")
        if not instructions:
            paragraph("Instructions were not available. See the original recipe below.")
        story.append(Spacer(1, 12))
        if recipe.get("source_url"):
            paragraph(f"Original recipe: {recipe['source_url']}")

    def footer(canvas, document):
        canvas.saveState()
        canvas.setFont("Export", 9)
        canvas.drawString(42, 24, "The Supper Club")
        canvas.drawRightString(letter[0] - 42, 24, f"Page {document.page}")
        canvas.restoreState()

    SimpleDocTemplate(output, pagesize=letter, rightMargin=42, leftMargin=42,
                      topMargin=42, bottomMargin=42, title="The Supper Club — Grocery list & recipes").build(
                          story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
