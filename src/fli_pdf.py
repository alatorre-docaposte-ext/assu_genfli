"""
fli_pdf.py — Génération des Fiches de Livraison (FLI) au format PDF.

Une FLI est générée par dépôt cible (WFD, RESS, COMMUN).
Structure (3 pages type) :
  Page 1 : En-tête société, Objet, Signatures, début Livraison/Description
  Page n : Suite Description, Stockage, Identification (chemins + Tag Git)
"""
from __future__ import annotations

import logging
import os
from typing import Any

_log = logging.getLogger("assu_genfli")

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas as _RLCanvas
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle,
    Paragraph, Spacer, KeepTogether, Image,
)

_LOGO_PATH = os.path.join(os.path.dirname(__file__), "assets", "coexya.png")
_LOGO_W    = 5.87 * cm

# ---------------------------------------------------------------------------
# Page geometry
# ---------------------------------------------------------------------------
PAGE_W, PAGE_H = A4
MARGIN_H = 15 * mm
MARGIN_V = 15 * mm
INNER_W  = PAGE_W - 2 * MARGIN_H

# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------
C_TEAL      = colors.HexColor("#5580b9")   # section headers
C_LGRAY     = colors.HexColor("#F2F3F4")   # alternating rows
C_WHITE     = colors.white
C_BLACK     = colors.black
C_BORDER    = colors.HexColor("#CCCCCC")
C_FOOTER    = colors.HexColor("#888888")

# ---------------------------------------------------------------------------
# Paragraph styles
# ---------------------------------------------------------------------------
def _ps(name: str, **kw) -> ParagraphStyle:
    from reportlab.lib.styles import getSampleStyleSheet
    base = getSampleStyleSheet()["Normal"]
    kw.setdefault("fontSize", 8)
    kw.setdefault("leading", 11)
    return ParagraphStyle(name, parent=base, **kw)


S_NORMAL   = _ps("n")
S_BOLD     = _ps("b",   fontName="Helvetica-Bold")
S_COMPANY  = _ps("co",  fontName="Helvetica-Bold", fontSize=16, leading=20,
                        textColor=C_TEAL, alignment=TA_RIGHT)
S_TITLE    = _ps("ti",  fontName="Helvetica-Bold", fontSize=15, leading=20,
                        textColor=C_TEAL)
S_HDR_WH   = _ps("hw",  fontName="Helvetica-Bold", textColor=C_WHITE)
S_SMALL    = _ps("sm",  fontSize=6,  leading=8)
S_FOOTER   = _ps("ft",  fontSize=6,  leading=8, textColor=C_FOOTER)
S_GRAY     = _ps("gr",  fontSize=7,  leading=9, textColor=C_FOOTER)

# Checkbox symbols — inline images dans les Paragraphs
_ASSETS = os.path.join(os.path.dirname(__file__), "assets")
ON  = f'<img src="{os.path.join(_ASSETS, "checked.gif")}"   width="8" height="8" valign="middle"/>'
OFF = f'<img src="{os.path.join(_ASSETS, "unchecked.gif")}" width="8" height="8" valign="middle"/>'


# ---------------------------------------------------------------------------
# Numbered canvas (footer with page X/Y)
# ---------------------------------------------------------------------------
class _NumberedCanvas(_RLCanvas):
    def __init__(self, *args, **kwargs):
        _RLCanvas.__init__(self, *args, **kwargs)
        self._saved: list[dict] = []
        self._footer_text: str = ""

    def showPage(self) -> None:
        self._saved.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        total = len(self._saved)
        for state in self._saved:
            self.__dict__.update(state)
            self._draw_footer(total)
            _RLCanvas.showPage(self)
        _RLCanvas.save(self)

    def _draw_footer(self, total: int) -> None:
        page = self._pageNumber
        self.setFont("Helvetica", 6)
        self.setFillColor(C_FOOTER)
        y = MARGIN_V
        self.drawString(MARGIN_H, y, "Réf. modèle : ISOPRO/MOD_001/1.1")
        self.drawString(
            MARGIN_H, y - 4 * mm,
            "Toute reproduction, même partielle, tout transfert à un tiers, "
            "sous quelque forme que ce soit, sont strictement interdits "
            "sans autorisation écrite de COEXYA.",
        )
        self.drawRightString(PAGE_W - MARGIN_H, y - 4 * mm, f"({page}/{total})")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _section_hdr(text: str) -> Table:
    """Bande colorée pour les titres de section."""
    t = Table([[Paragraph(text, S_HDR_WH)]], colWidths=[INNER_W])
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), C_TEAL),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
    ]))
    return t


def _simple_table(data: list, col_ratios: list[float],
                  label_col: bool = True) -> Table:
    """Table 2-colonnes label/valeur avec bordures légères."""
    col_w = [INNER_W * r for r in col_ratios]
    t = Table(data, colWidths=col_w)
    style = [
        ("FONTSIZE",      (0, 0), (-1, -1), 8),
        ("GRID",          (0, 0), (-1, -1), 0.5, C_BORDER),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
    ]
    if label_col:
        style += [
            ("BACKGROUND",  (0, 0), (0, -1), C_LGRAY),
            ("FONTNAME",    (0, 0), (0, -1), "Helvetica-Bold"),
        ]
    t.setStyle(TableStyle(style))
    return t


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def generate_fli(
    output_path: str,
    repo: str,
    fli_id_str: str,
    context: dict,
    files: list[dict],
) -> None:
    """
    Génère le PDF de la Fiche de Livraison pour un dépôt donné.

    :param output_path:  Chemin complet du PDF à écrire.
    :param repo:         "WFD" | "RESS" | "COMMUN"
    :param fli_id_str:   Identifiant complet, e.g. "FLI_SGK_EXT_RESS_LIV_00597"
    :param context:      Dict pré-extrait des prefs/session (voir build_context).
    :param files:        Fichiers destinés à ce repo (déjà filtrés, checked=True).
    """
    story: list = []

    _log.debug("[generate_fli] repo=%s  fli_id=%s  fichiers=%d", repo, fli_id_str, len(files))
    _log.debug("[generate_fli] context keys: %s", list(context.keys()))
    for i, f in enumerate(files):
        _log.debug("[generate_fli] fichier[%d]: %s", i, f)

    em   = context.get("emettrice", {}) or {}
    dest = context.get("destinataire", {}) or {}
    tag  = context.get(f"tag_{repo.lower()}") or ""
    _log.debug("[generate_fli] em=%s  dest=%s  tag=%s", em, dest, tag)

    fli_num = fli_id_str.split("_")[-1]   # "00597"
    _log.debug("[generate_fli] fli_num=%s", fli_num)

    # -----------------------------------------------------------------------
    # En-tête société
    # -----------------------------------------------------------------------
    _log.debug("[generate_fli] section: en-tête")
    if os.path.isfile(_LOGO_PATH):
        _ir      = ImageReader(_LOGO_PATH)
        _nw, _nh = _ir.getSize()
        _logo_h  = _LOGO_W * (_nh / _nw)
        story.append(Image(_LOGO_PATH, width=_LOGO_W, height=_logo_h, hAlign="RIGHT"))
    else:
        story.append(Paragraph(em.get("nom", ""), S_COMPANY))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph("Fiche de livraison", S_TITLE))
    story.append(Spacer(1, 4 * mm))

    # -----------------------------------------------------------------------
    # OBJET
    # -----------------------------------------------------------------------
    _log.debug("[generate_fli] section: objet")
    story.append(_section_hdr("Objet"))
    objet_data = [
        [Paragraph("Client",             S_BOLD),
         Paragraph(em.get("client", ""), S_NORMAL),
         Paragraph("Id. Fiche",          S_BOLD),
         Paragraph(fli_id_str,           S_NORMAL)],
        [Paragraph("Entité",             S_BOLD),
         Paragraph(em.get("nom", ""),    S_NORMAL),
         Paragraph("Projet",             S_BOLD),
         Paragraph(context.get("project_name", ""), S_NORMAL)],
        [Paragraph("Date de référence",  S_BOLD),
         Paragraph(context.get("date_reference", ""), S_NORMAL), "", ""],
        [Paragraph("Mode de livraison",  S_BOLD),
         Paragraph(em.get("mode", "Livraison par Mail"), S_NORMAL), "", ""],
    ]
    q1, q2 = INNER_W * 0.2, INNER_W * 0.2
    objet_t = Table(objet_data, colWidths=[q1, q2, q1, INNER_W - 2 * q1 - q2])
    objet_t.setStyle(TableStyle([
        ("FONTSIZE",      (0, 0), (-1, -1), 8),
        ("GRID",          (0, 0), (-1, -1), 0.5, C_BORDER),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("BACKGROUND",    (0, 0), (0, -1), C_LGRAY),
        ("BACKGROUND",    (2, 0), (2, 1),  C_LGRAY),
        ("SPAN",          (1, 2), (3, 2)),
        ("SPAN",          (1, 3), (3, 3)),
    ]))
    story.append(objet_t)
    story.append(Spacer(1, 3 * mm))

    # -----------------------------------------------------------------------
    # Signatures
    # -----------------------------------------------------------------------
    _log.debug("[generate_fli] section: signatures")
    sig_data = [
        [Paragraph("Objet",                S_HDR_WH),
         Paragraph("Client / Entité",      S_HDR_WH),
         Paragraph("Nom",                  S_HDR_WH),
         Paragraph("Date",                 S_HDR_WH),
         Paragraph("Visa",                 S_HDR_WH)],
        [Paragraph("Livraison effectuée",  S_BOLD),
         Paragraph(em.get("nom", ""),      S_NORMAL),
         Paragraph(context.get("livreur", ""),   S_NORMAL),
         Paragraph(context.get("date_livraison", ""), S_NORMAL),
         Paragraph("",                     S_NORMAL)],
        [Paragraph("Prise en compte", S_BOLD),
         Paragraph(dest.get("nom", ""),    S_NORMAL),
         Paragraph(context.get("reception_par", ""), S_NORMAL),
         Paragraph("",                     S_NORMAL),
         Paragraph("",                     S_NORMAL)],
    ]
    cw = INNER_W
    sig_t = Table(sig_data,
                  colWidths=[cw*0.25, cw*0.22, cw*0.22, cw*0.18, cw*0.13])
    sig_t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), C_TEAL),
        ("TEXTCOLOR",     (0, 0), (-1, 0), C_WHITE),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 8),
        ("GRID",          (0, 0), (-1, -1), 0.5, C_BORDER),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("BACKGROUND",    (0, 1), (0, -1), C_LGRAY),
        ("FONTNAME",      (0, 1), (0, -1), "Helvetica-Bold"),
    ]))
    story.append(sig_t)
    story.append(Spacer(1, 3 * mm))

    # -----------------------------------------------------------------------
    # LIVRAISON — métadonnées
    # -----------------------------------------------------------------------
    _log.debug("[generate_fli] section: livraison")
    story.append(_section_hdr("Livraison"))
    _lw  = INNER_W * 0.28          # largeur colonne label
    _vw  = (INNER_W - _lw) / 4    # largeur d'une cellule valeur
    livr_data = [
        [Paragraph("Objet concerné",        S_BOLD),
         Paragraph(f"{OFF} Documentation",  S_NORMAL),
         Paragraph(f"{ON}  Logiciel",       S_NORMAL),
         Paragraph(f"{OFF} Données",        S_NORMAL),
         Paragraph(f"{OFF} Autre",          S_NORMAL)],
        [Paragraph("Type de livraison",     S_BOLD),
         Paragraph(f"{OFF} Initiale",       S_NORMAL),
         Paragraph(f"{ON}  Evolution",      S_NORMAL),
         Paragraph(f"{OFF} Correction",     S_NORMAL),
         Paragraph(f"{OFF} Autre",          S_NORMAL)],
        [Paragraph("Version",               S_BOLD),
         Paragraph(fli_num,                 S_NORMAL),
         Paragraph(f"{ON}  Totale",         S_NORMAL),
         Paragraph(f"{OFF} Partielle",      S_NORMAL),
         Paragraph("",                      S_NORMAL)],
        [Paragraph("Titre de la livraison", S_BOLD),
         Paragraph(fli_id_str,              S_NORMAL),
         "", "", ""],
    ]
    livr_t = Table(livr_data, colWidths=[_lw, _vw, _vw, _vw, _vw])
    livr_t.setStyle(TableStyle([
        ("FONTSIZE",      (0, 0), (-1, -1), 8),
        ("GRID",          (0, 0), (-1, -1), 0.5, C_BORDER),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("BACKGROUND",    (0, 0), (0, -1), C_LGRAY),
        ("FONTNAME",      (0, 0), (0, -1), "Helvetica-Bold"),
        # Titre de la livraison : fusion des 4 cellules valeur
        ("SPAN",          (1, 3), (4, 3)),
    ]))
    story.append(livr_t)
    story.append(Spacer(1, 2 * mm))

    # -----------------------------------------------------------------------
    # Description (tableau Workflow / Version / Descriptif)
    # -----------------------------------------------------------------------
    _log.debug("[generate_fli] section: description (%d lignes)", len(files))
    story.append(Paragraph("Description :", S_BOLD))
    story.append(Spacer(1, 1 * mm))

    wf_hdr = [[Paragraph("Workflow",   S_HDR_WH),
               Paragraph("Version",    S_HDR_WH),
               Paragraph("Descriptif", S_HDR_WH)]]
    wf_rows = []
    for f in files:
        src  = f["path"]
        dest = f.get("dest_path") or src
        wf_rows.append([Paragraph(dest, S_NORMAL),
                        Paragraph("",       S_NORMAL),
                        Paragraph("",       S_NORMAL)])

    wf_data = wf_hdr + wf_rows
    wf_t = Table(wf_data, colWidths=[INNER_W * 0.45, INNER_W * 0.28, INNER_W * 0.27])
    wf_style: list = [
        ("BACKGROUND",    (0, 0), (-1, 0), C_TEAL),
        ("TEXTCOLOR",     (0, 0), (-1, 0), C_WHITE),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 8),
        ("GRID",          (0, 0), (-1, -1), 0.5, C_BORDER),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [C_WHITE, C_LGRAY]),
    ]
    wf_t.setStyle(TableStyle(wf_style))
    story.append(wf_t)
    story.append(Spacer(1, 3 * mm))

    # -----------------------------------------------------------------------
    # Stockage
    # -----------------------------------------------------------------------
    _log.debug("[generate_fli] section: stockage")
    depot_name = context.get(f"depot_{repo.lower()}") or ""
    if not depot_name:
        # fallback si l'URL distante n'est pas renseignée
        proj_raw = context.get("project_name", "").lower().replace(" ", "_")
        depot_name = f"{proj_raw}_{repo.lower()}"
    story.append(_simple_table(
        [
            [Paragraph("Nom de l'archive",          S_BOLD),
             Paragraph("Non applicable",             S_NORMAL)],
            [Paragraph("Nom du serveur de stockage", S_BOLD),
             Paragraph("Non applicable",             S_NORMAL)],
            [Paragraph("Répertoire de stockage",     S_BOLD),
             Paragraph(f"Projet {depot_name} sous GIT", S_NORMAL)],
        ],
        [0.35, 0.65],
    ))
    story.append(Spacer(1, 3 * mm))

    # -----------------------------------------------------------------------
    # IDENTIFICATION
    # -----------------------------------------------------------------------
    _log.debug("[generate_fli] section: identification (n_paths=%d, tag=%r)", len(files), tag)
    story.append(_section_hdr("Identification"))

    n_paths = len(files)
    id_data = []
    for i, f in enumerate(files):
        label_cell = Paragraph("Référence des objets livrés", S_BOLD) if i == 0 else ""
        src  = f["path"]
        dest = f.get("dest_path") or src
        id_data.append([label_cell, Paragraph(dest, S_NORMAL)])
    id_data.append([Paragraph("Tag Git", S_BOLD), Paragraph(tag, S_BOLD)])

    id_t = Table(id_data, colWidths=[INNER_W * 0.30, INNER_W * 0.70],
                 repeatRows=0)
    id_style = [
        ("FONTSIZE",      (0, 0), (-1, -1), 8),
        ("GRID",          (0, 0), (-1, -1), 0.5, C_BORDER),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("BACKGROUND",    (0, 0), (0, -1), C_LGRAY),
        ("FONTNAME",      (0, 0), (0, -1), "Helvetica-Bold"),
        # Masquer les bordures horizontales internes de la colonne label (gris sur gris)
        ("LINEBELOW",     (0, 0), (0, n_paths - 2), 0.5, C_LGRAY),
        # Bordures haute et basse visibles sur la ligne "Tag Git"
        ("LINEABOVE",     (0, n_paths), (-1, n_paths), 0.5, C_BORDER),
        ("LINEBELOW",     (0, n_paths), (-1, n_paths), 0.5, C_BORDER),
    ]
    id_t.setStyle(TableStyle(id_style))
    story.append(id_t)

    # -----------------------------------------------------------------------
    # Build PDF
    # -----------------------------------------------------------------------
    _log.debug("[generate_fli] build PDF -> %s", output_path)
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=MARGIN_H,
        rightMargin=MARGIN_H,
        topMargin=MARGIN_V,
        bottomMargin=MARGIN_V + 6 * mm,
    )
    doc.build(story, canvasmaker=_NumberedCanvas)


# ---------------------------------------------------------------------------
# JSON companion
# ---------------------------------------------------------------------------
def generate_fli_json(
    output_path: str,
    repo: str,
    fli_id_str: str,
    context: dict,
    files: list[dict],
) -> None:
    """
    Génère le fichier JSON accompagnateur d'une FLI.
    Même structure que le PDF mais en données brutes.
    """
    import json

    em   = context.get("emettrice",   {}) or {}
    dest = context.get("destinataire", {}) or {}

    depot_name = context.get(f"depot_{repo.lower()}") or ""
    if not depot_name:
        proj_raw   = context.get("project_name", "").lower().replace(" ", "_")
        depot_name = f"{proj_raw}_{repo.lower()}"

    data = {
        "fli_id":          fli_id_str,
        "depot":           depot_name,
        "objet": {
            "client":          em.get("client", ""),
            "entite":          em.get("nom", ""),
            "projet":          context.get("project_name", ""),
            "date_reference":  context.get("date_reference", ""),
            "mode_livraison":  em.get("mode", ""),
        },
        "signatures": {
            "livraison": {
                "entite": em.get("nom", ""),
                "nom":    context.get("livreur", ""),
                "date":   context.get("date_livraison", ""),
            },
            "prise_en_compte": {
                "entite": dest.get("nom", ""),
                "nom":    context.get("reception_par", ""),
            },
        },
        "livraison": {
            "objet_concerne":    "Logiciel",
            "type_livraison":    "Evolution",
            "version":           fli_id_str.split("_")[-1],
            "titre":             fli_id_str,
        },
        "tag_git":  context.get(f"tag_{repo.lower()}") or "",
        "stockage": {
            "archive":          "Non applicable",
            "serveur":          "Non applicable",
            "repertoire":       f"Projet {depot_name} sous GIT",
        },
        "fichiers": [
            {
                "chemin_dev":  f["path"],
                "chemin_dest": f.get("dest_path") or f["path"],
                "statut": f.get("status", ""),
                "source": f.get("source", ""),
                "cible":  f.get("cible",  ""),
            }
            for f in files
        ],
    }

    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    _log.info("[fli_pdf] JSON généré : %s", output_path)


# ---------------------------------------------------------------------------
# Context builder helper (called from screen3_delivery)
# ---------------------------------------------------------------------------
def build_context(prefs: dict, delivery: dict) -> dict:
    """
    Extrait les données nécessaires à generate_fli depuis prefs + delivery.
    Retourne un dict 'context' passé à generate_fli.
    """
    from datetime import datetime

    def _fmt_date(raw: str) -> str:
        """Convertit YYYY-MM-DD en jj/mm/aaaa ; laisse passer les autres formats."""
        try:
            return datetime.strptime(raw, "%Y-%m-%d").strftime("%d/%m/%Y")
        except (ValueError, TypeError):
            return raw or ""

    lv      = prefs.get("livraison", {})
    project = prefs.get("session", {}).get("selected_project", {})

    def _depot_name(key: str) -> str:
        """Extrait le nom du dépôt depuis l'URL distante (sans .git)."""
        url = project.get(key, "") or ""
        basename = url.rstrip("/").split("/")[-1]
        return basename[:-4] if basename.endswith(".git") else basename

    return {
        "emettrice":      lv.get("emettrice",  {}) or {},
        "destinataire":   lv.get("destinataire", {}) or {},
        "project_name":   project.get("name", "") or "",
        "livreur":        delivery.get("livreur", "") or "",
        "reception_par":  delivery.get("reception_par", "") or "",
        "date_reference": _fmt_date(delivery.get("date_reference") or ""),
        "date_livraison": _fmt_date(delivery.get("date_livraison") or ""),
        "tag_wfd":        delivery.get("tag_wfd", "") or "",
        "tag_ress":       delivery.get("tag_ressources", "") or "",
        "tag_commun":     delivery.get("tag_commun", "") or "",
        "depot_wfd":      _depot_name("depot_wfd_distant"),
        "depot_ress":     _depot_name("depot_ress_distant"),
        "depot_commun":   _depot_name("depot_commun_distant"),
    }
