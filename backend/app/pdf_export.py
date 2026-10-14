"""Printable shopping checklist and recipes, generated without external requests."""
from html import escape
from fractions import Fraction
import re
from io import BytesIO
from pathlib import Path

import reportlab
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, KeepInFrame, NextPageTemplate,
                               PageBreak, PageTemplate, Paragraph, Table)

from .ingredients import strip_ingredient_prices
from .grocery import UNICODE_FRACTIONS, build_grocery_list, parse_ingredient

# ReportLab ships these fonts, so exports also work in the Docker image.
_font_dir = Path(reportlab.__file__).parent / "fonts"
pdfmetrics.registerFont(TTFont("Export", str(_font_dir / "Vera.ttf")))
pdfmetrics.registerFont(TTFont("ExportBold", str(_font_dir / "VeraBd.ttf")))


def pdf_text(value):
    """Use readable ASCII fractions supported by the embedded PDF fonts."""
    text = str(value)
    # Keep mixed numbers distinct: 1⅓ becomes 1 1/3, rather than 11/3.
    text = re.sub(r"(?<=\d)(?=[" + "".join(UNICODE_FRACTIONS) + r"])", " ", text)
    for symbol, quantity in UNICODE_FRACTIONS.items():
        text = text.replace(symbol, str(Fraction(quantity).limit_denominator(16)))
    return escape(text).replace("\n", "<br/>")


def build_meal_plan_pdf(recipes, selections, checked_items=()):
    margin = 36  # 0.5 inches, in PDF points.
    page_width, page_height = letter
    content_width = page_width - 2 * margin
    footer_bottom = margin
    body_bottom = margin + 54  # Reserve space for a wrapped footer and separation from content.
    grocery_top = page_height - margin - 84
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
    accent = colors.HexColor("#9b542d")
    styles["Title"].textColor = accent
    styles["Heading2"].textColor = accent
    description_style = styles["BodyText"].clone("RecipeDescription")
    description_style.backColor = colors.HexColor("#fff5e8")
    description_style.borderColor = colors.HexColor("#e3be91")
    description_style.borderWidth = 0.75
    description_style.borderPadding = 12
    description_style.spaceBefore = 14
    description_style.spaceAfter = 18
    styles.add(description_style)
    story = []

    def paragraph(value, style="BodyText"):
        # Imported recipe text must never be interpreted as PDF markup.
        story.append(Paragraph(pdf_text(value), styles[style]))

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

    for recipe_index, recipe in enumerate(recipes):
        story.append(NextPageTemplate(f"recipe-{recipe_index}"))
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
            paragraph(recipe["description"], "RecipeDescription")
        paragraph("Ingredients", "Heading2")
        multiplier = target / base if base else 1
        if not base:
            paragraph("Original yield is unknown; ingredient amounts are unchanged.")
        ingredient_cells = []
        for line in recipe.get("ingredients", []):
            line = strip_ingredient_prices(line)
            parsed = parse_ingredient(line)
            if multiplier != 1 and parsed["quantity"] is not None:
                amount = f"{parsed['quantity'] * multiplier:.3f}".rstrip("0").rstrip(".")
                line = " ".join(filter(None, [amount, parsed["unit"], parsed["name"]]))
            ingredient_cells.append(Paragraph(
                pdf_text(f"• {line}"), styles["BodyText"]))
        if ingredient_cells:
            # Rows can continue onto another page, including unusually long ingredients.
            rows = [[ingredient_cells[i], "",
                     ingredient_cells[i + 1] if i + 1 < len(ingredient_cells) else ""]
                    for i in range(0, len(ingredient_cells), 2)]
            ingredient_width = (content_width - 18) / 2
            story.append(Table(rows, colWidths=[ingredient_width, 18, ingredient_width],
                               splitInRow=1, style=[
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]))
        paragraph("Instructions", "Heading2")
        if multiplier != 1:
            paragraph("Ingredients above reflect planned servings. Quantities mentioned in the original instructions may need adjusting.")
        instructions = recipe.get("instructions", [])
        for index, step in enumerate(instructions, 1):
            paragraph(f"{index}. {step}")
        if not instructions:
            paragraph("Instructions were not available. See the source link in the footer.")


    def draw_logo(canvas, x, y, size=40):
        """Vector version of frontend/public/favicon.svg."""
        canvas.saveState()
        canvas.translate(x, y)
        canvas.scale(size / 64, size / 64)
        canvas.setFillColor(colors.HexColor("#111315"))
        canvas.roundRect(0, 0, 64, 64, 18, stroke=0, fill=1)
        canvas.setFillColor(colors.HexColor("#efbd78"))
        canvas.circle(32, 32, 24, stroke=0, fill=1)
        canvas.setStrokeColor(colors.HexColor("#20170d"))
        canvas.setLineWidth(3)
        canvas.setLineCap(1)
        canvas.setLineJoin(1)
        path = canvas.beginPath()
        path.moveTo(22, 46)
        path.lineTo(22, 36)
        path.moveTo(17, 46)
        path.lineTo(17, 39)
        path.curveTo(17, 32.3, 27, 32.3, 27, 39)
        path.lineTo(27, 46)
        path.moveTo(22, 34)
        path.lineTo(22, 18)
        path.moveTo(42, 46)
        path.curveTo(35, 42, 35, 32, 42, 32)
        path.lineTo(42, 46)
        path.lineTo(42, 18)
        canvas.drawPath(path)
        canvas.restoreState()

    page_counts = {}

    def decorate(canvas, document):
        template_id = document.pageTemplate.id
        page_counts[template_id] = page_counts.get(template_id, 0) + 1
        canvas.saveState()
        canvas.setFont("Export", 9)
        if template_id == "grocery":
            canvas.drawString(margin, footer_bottom + 3, "The Supper Club")
        else:
            recipe = recipes[int(template_id.removeprefix("recipe-"))]
            footer_style = styles["BodyText"].clone("RecipeFooter")
            footer_style.fontSize = 9
            footer_style.leading = 10
            footer_style.spaceAfter = 0
            title = Paragraph("Recipe: " + pdf_text(recipe["title"]), footer_style)
            source_url = recipe.get("source_url")
            link = None
            if source_url:
                safe_url = escape(str(source_url), quote=True)
                link = Paragraph(f'Link: <link href="{safe_url}" color="#9b542d">{safe_url}</link>', footer_style)
            number_style = footer_style.clone("RecipeFooterNumber")
            number_style.alignment = 2  # Right aligned, with the same text baseline.
            number = Paragraph(f"Page {page_counts[template_id]}", number_style)
            row = Table([[title, number]] + ([[link, ""]] if link else []), colWidths=[content_width - 88, 88], style=[
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ])
            # Keep the title and number together even when a long title wraps.
            footer = KeepInFrame(content_width, 46, [row], mode="shrink")
            footer.wrapOn(canvas, content_width, 46)
            footer.drawOn(canvas, margin, footer_bottom)

        if template_id == "grocery":
            canvas.drawRightString(page_width - margin, footer_bottom + 3, f"Page {page_counts[template_id]}")
        if template_id == "grocery":
            draw_logo(canvas, margin, page_height - margin - 40)
            canvas.setFont("ExportBold", 17)
            canvas.drawString(margin + 52, page_height - margin - 15, "The Supper Club")
            canvas.setFont("Export", 11)
            canvas.drawString(margin + 52, page_height - margin - 34, "Grocery list")
            canvas.setFont("Export", 9)
            canvas.drawString(margin, page_height - margin - 63, "Checked items are marked [x]; all ingredients are included.")
            canvas.setStrokeColor(colors.HexColor("#cccccc"))
            canvas.line(margin, grocery_top + 10, page_width - margin, grocery_top + 10)
        canvas.restoreState()

    document = BaseDocTemplate(output, pagesize=letter, rightMargin=margin, leftMargin=margin,
                               topMargin=margin, bottomMargin=margin,
                               title="The Supper Club — Grocery list & recipes")
    column_gap = 18
    column_width = (content_width - 2 * column_gap) / 3
    document.addPageTemplates(PageTemplate(id="grocery", onPage=decorate, frames=[
        Frame(margin + column * (column_width + column_gap), body_bottom,
              column_width, grocery_top - body_bottom, id=f"grocery-column-{column}",
              leftPadding=0, rightPadding=0)
        for column in range(3)
    ]))
    for index in range(len(recipes)):
        document.addPageTemplates(PageTemplate(id=f"recipe-{index}", onPage=decorate, frames=[
            Frame(margin, body_bottom, content_width, page_height - margin - body_bottom,
                  id=f"recipe-frame-{index}", leftPadding=0, rightPadding=0),
        ]))
    document.build(story)
    return output.getvalue()
