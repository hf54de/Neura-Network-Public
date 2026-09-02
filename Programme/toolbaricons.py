# -------------------------------------------------------------------------------------------------
# Datei: toolbaricons.py
# Zweck: Erzeugt und verwaltet die Symbole der Werkzeugleisten.
# Letzte Änderung: 02.09.2026
# Copyright © 2026 Helwig Fülling
# Licensed under the GNU General Public License v3.0
# -------------------------------------------------------------------------------------------------
from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer


class ToolbarIcons:
    """Erzeugt einen einheitlichen, programmeigenen SVG-Symbolsatz."""

    SYMBOLS = {
        "new": """
            <path d="M5 3h9l5 5v13H5z"/><path d="M14 3v5h5"/>
            <path d="M12 11v7M8.5 14.5h7" class="accent"/>
        """,
        "open": """
            <path d="M3 7h7l2 2h9l-2 11H5z"/>
            <path d="M3 7v-2h7l2 2h7v2" class="accent"/>
        """,
        "save": """
            <path d="M4 3h14l2 2v16H4z"/><path d="M7 3v6h9V3"/>
            <path d="M8 14h8v7H8z" class="accent"/>
        """,
        "save_as": """
            <path d="M3 3h13l2 2v10"/><path d="M6 3v6h8V3"/>
            <path d="M7 13h7v8H3V7"/><path d="M15 19l5-5 2 2-5 5-3 1z" class="accent"/>
        """,
        "project_description": """
            <path d="M5 3h11l4 4v14H5z"/><path d="M16 3v5h4"/>
            <path d="M8 11h8M8 15h8M8 19h5" class="accent"/>
        """,
        "project_overview": """
            <rect x="3" y="4" width="18" height="16" rx="2"/>
            <path d="M7 8h4M7 12h10M7 16h10"/>
            <circle cx="16" cy="8" r="2" class="accent"/>
        """,
        "pdf_report": """
            <path d="M5 3h11l4 4v14H5z"/><path d="M16 3v5h4"/>
            <path d="M8 11v7M8 11h3a2 2 0 010 4H8M14 11v7M14 11h3M14 15h2"
                  class="accent"/>
        """,
        "word_report": """
            <path d="M5 3h11l4 4v14H5z"/><path d="M16 3v5h4"/>
            <path d="M8 11l1.5 7 2.5-5 2.5 5 1.5-7" class="accent"/>
        """,
        "project_image": """
            <rect x="3" y="4" width="18" height="16" rx="2"/>
            <circle cx="8" cy="9" r="2" class="accent"/>
            <path d="M5 18l5-5 3 3 2-2 4 4" class="accent"/>
        """,
        "undo": """
            <path d="M9 7L4 12l5 5" class="accent"/><path d="M5 12h8a6 6 0 016 6"/>
        """,
        "redo": """
            <path d="M15 7l5 5-5 5" class="accent"/><path d="M19 12h-8a6 6 0 00-6 6"/>
        """,
        "cut": """
            <circle cx="6" cy="18" r="3"/><circle cx="18" cy="18" r="3"/>
            <path d="M8.5 16.5L18 3M15.5 16.5L6 3" class="accent"/>
        """,
        "copy": """
            <rect x="8" y="8" width="12" height="13" rx="2" class="accent"/>
            <path d="M16 8V5a2 2 0 00-2-2H5a2 2 0 00-2 2v11a2 2 0 002 2h3"/>
        """,
        "paste": """
            <path d="M8 5H5v16h14V5h-3"/><rect x="8" y="3" width="8" height="5" rx="2" class="accent"/>
            <path d="M9 13h6M9 17h5"/>
        """,
        "select": """
            <path d="M4 8V4h4M16 4h4v4M20 16v4h-4M8 20H4v-4"/>
            <rect x="8" y="8" width="8" height="8" rx="1" class="accent"/>
        """,
        "delete": """
            <path d="M4 7h16M9 7V4h6v3M7 7l1 14h8l1-14"/>
            <path d="M10 11v6M14 11v6" class="accent"/>
        """,
        "display": """
            <path d="M2 12s4-6 10-6 10 6 10 6-4 6-10 6S2 12 2 12z"/>
            <circle cx="12" cy="12" r="3" class="accent"/>
        """,
        "zoom_in": """
            <circle cx="10" cy="10" r="6"/><path d="M14.5 14.5L21 21"/>
            <path d="M10 7v6M7 10h6" class="accent"/>
        """,
        "zoom_out": """
            <circle cx="10" cy="10" r="6"/><path d="M14.5 14.5L21 21"/>
            <path d="M7 10h6" class="accent"/>
        """,
        "zoom_reset": """
            <path d="M7 8l3-3v14M14 7v10M14 7h5v10h-5" class="accent"/>
            <circle cx="12" cy="12" r="10"/>
        """,
        "fit": """
            <path d="M3 9V3h6M15 3h6v6M21 15v6h-6M9 21H3v-6" class="accent"/>
            <rect x="8" y="8" width="8" height="8" rx="2"/>
        """,
        "network_create": """
            <circle cx="5" cy="6" r="2"/><circle cx="5" cy="18" r="2"/>
            <circle cx="13" cy="12" r="2"/><path d="M7 6l4 5M7 18l4-5"/>
            <path d="M19 7v6M16 10h6" class="accent"/>
        """,
        "network_from_data": """
            <rect x="2" y="4" width="8" height="16" rx="1"/>
            <path d="M2 9h8M6 9v11"/>
            <circle cx="15" cy="7" r="2"/><circle cx="15" cy="17" r="2"/>
            <circle cx="21" cy="12" r="2"/>
            <path d="M10 12h3M17 7l2.5 4M17 17l2.5-4" class="accent"/>
        """,
        "network_layout": """
            <circle cx="4" cy="6" r="2"/><circle cx="4" cy="18" r="2"/>
            <circle cx="12" cy="6" r="2"/><circle cx="12" cy="18" r="2"/>
            <circle cx="20" cy="12" r="2"/>
            <path d="M6 6h4M6 18h4M14 6l4 5M14 18l4-5" class="accent"/>
        """,
        "network_structure": """
            <circle cx="4" cy="6" r="2"/><circle cx="4" cy="18" r="2"/>
            <circle cx="12" cy="6" r="2"/><circle cx="12" cy="18" r="2"/>
            <circle cx="20" cy="12" r="2"/>
            <path d="M6 6h4M6 18h4M14 6l4 5M14 18l4-5"/>
            <path d="M9 12h6M12 9v6" class="accent"/>
        """,
        "validate": """
            <circle cx="9" cy="8" r="2"/><circle cx="9" cy="16" r="2"/>
            <circle cx="16" cy="12" r="2"/><path d="M11 8l3 3M11 16l3-3"/>
            <path d="M15 19l2 2 5-6" class="accent"/>
        """,
        "forward": """
            <circle cx="4" cy="7" r="2"/><circle cx="4" cy="17" r="2"/>
            <circle cx="12" cy="12" r="2"/><path d="M6 7l4 4M6 17l4-4"/>
            <path d="M14 12h7M18 9l3 3-3 3" class="accent"/>
        """,
        "graphical_experiment": """
            <rect x="3" y="4" width="18" height="16" rx="2"/>
            <path d="M7 8h10M7 12h10M7 16h10"/>
            <circle cx="10" cy="8" r="1.5" class="accent fill"/>
            <circle cx="15" cy="12" r="1.5" class="accent fill"/>
            <circle cx="12" cy="16" r="1.5" class="accent fill"/>
        """,
        "train": """
            <circle cx="6" cy="7" r="2"/><circle cx="6" cy="17" r="2"/>
            <circle cx="13" cy="12" r="2"/><path d="M8 7l3 4M8 17l3-4"/>
            <circle cx="19" cy="17" r="3" class="accent"/><path d="M19 12v2M19 20v2M14 17h2M22 17h2" class="accent"/>
        """,
        "math": """
            <path d="M18 4H7l5 8-5 8h11"/>
            <path d="M4 6h3M4 12h5M4 18h3" class="accent"/>
        """,
        "history": """
            <path d="M4 19V5M4 19h17"/>
            <path d="M7 16l4-5 3 2 6-7" class="accent"/>
            <circle cx="7" cy="16" r="1"/><circle cx="11" cy="11" r="1"/>
            <circle cx="14" cy="13" r="1"/><circle cx="20" cy="6" r="1"/>
        """,
        "training_data": """
            <rect x="3" y="4" width="18" height="16" rx="2"/>
            <path d="M3 9h18M9 9v11M15 9v11"/>
            <path d="M5 6h8" class="accent"/>
        """,
        "project_assistant": """
            <path d="M5 3h11l4 4v14H5z"/><path d="M16 3v5h4"/>
            <path d="M8 11h8M8 15h6M8 19h5"/>
            <path d="M19 12v5M16.5 14.5h5" class="accent"/>
        """,
        "test_data": """
            <rect x="3" y="4" width="14" height="16" rx="2"/>
            <path d="M3 9h14M8 9v11M13 9v7"/>
            <circle cx="17" cy="17" r="3" class="accent"/><path d="M19.5 19.5L22 22" class="accent"/>
        """,
        "test": """
            <circle cx="5" cy="7" r="2"/><circle cx="5" cy="17" r="2"/>
            <circle cx="12" cy="12" r="2"/><path d="M7 7l3 4M7 17l3-4"/>
            <path d="M15 17l2 2 5-6" class="accent"/>
        """,
        "help": """
            <circle cx="12" cy="12" r="10"/>
            <path d="M9 9a3 3 0 116 0c0 2-3 2-3 5" class="accent"/>
            <circle cx="12" cy="18" r=".8" class="accent fill"/>
        """,
        "tutorial": """
            <path d="M3 5c3-1 6-.5 9 2v13c-3-2.5-6-3-9-2z"/>
            <path d="M21 5c-3-1-6-.5-9 2v13c3-2.5 6-3 9-2z"/>
            <path d="M6 9h3M6 12h3M15 9h3M15 12h3" class="accent"/>
        """,
        "layer_front": """
            <rect x="8" y="8" width="11" height="11" rx="1"/>
            <rect x="4" y="4" width="11" height="11" rx="1" class="accent"/>
        """,
        "layer_back": """
            <rect x="8" y="8" width="11" height="11" rx="1" class="accent"/>
            <rect x="4" y="4" width="11" height="11" rx="1"/>
        """,
        "lock": """
            <rect x="5" y="10" width="14" height="11" rx="2"/>
            <path d="M8 10V7a4 4 0 018 0v3" class="accent"/>
            <circle cx="12" cy="15" r="1.3" class="accent fill"/>
        """,
        "unlock": """
            <rect x="5" y="10" width="14" height="11" rx="2"/>
            <path d="M16 10V7a4 4 0 00-7.5-2" class="accent"/>
            <circle cx="12" cy="15" r="1.3" class="accent fill"/>
        """,
        "color": """
            <path d="M12 3a9 9 0 100 18c2 0 2.5-1.5 1.5-2.5-.8-.8-.2-2.5 1.3-2.5H18a3 3 0 003-3c0-5.5-4-10-9-10z"/>
            <circle cx="8" cy="9" r="1" class="accent fill"/>
            <circle cx="12" cy="7" r="1" class="accent fill"/>
            <circle cx="16" cy="10" r="1" class="accent fill"/>
        """,
        "line_width": """
            <path d="M4 6h16M4 12h16"/><path d="M4 18h16" class="accent"/>
        """,
        "arrow": """
            <path d="M3 12h17M15 7l5 5-5 5" class="accent"/>
        """,
        "reverse": """
            <path d="M5 8h15M16 4l4 4-4 4"/>
            <path d="M19 16H4M8 12l-4 4 4 4" class="accent"/>
        """,
        "transparent": """
            <rect x="4" y="4" width="16" height="16" rx="2"/>
            <path d="M4 12h16M12 4v16M4 4l16 16M20 4L4 20" class="accent"/>
        """,
        "align": """
            <path d="M4 4v16"/><rect x="7" y="6" width="12" height="4"/>
            <rect x="7" y="14" width="8" height="4" class="accent"/>
        """,
        "align_left": """
            <path d="M4 4v16"/><rect x="7" y="6" width="12" height="4"/>
            <rect x="7" y="14" width="8" height="4" class="accent"/>
        """,
        "align_right": """
            <path d="M20 4v16"/><rect x="5" y="6" width="12" height="4"/>
            <rect x="9" y="14" width="8" height="4" class="accent"/>
        """,
        "align_top": """
            <path d="M4 4h16"/><rect x="6" y="7" width="4" height="12"/>
            <rect x="14" y="7" width="4" height="8" class="accent"/>
        """,
        "align_bottom": """
            <path d="M4 20h16"/><rect x="6" y="5" width="4" height="12"/>
            <rect x="14" y="9" width="4" height="8" class="accent"/>
        """,
        "distribute_horizontal": """
            <path d="M3 4v16M21 4v16"/><rect x="6" y="8" width="4" height="8"/>
            <rect x="14" y="8" width="4" height="8" class="accent"/>
            <path d="M10 12h4"/>
        """,
        "distribute_vertical": """
            <path d="M4 3h16M4 21h16"/><rect x="8" y="6" width="8" height="4"/>
            <rect x="8" y="14" width="8" height="4" class="accent"/>
            <path d="M12 10v4"/>
        """,
        "equal_width": """
            <rect x="4" y="5" width="16" height="5"/><rect x="4" y="14" width="16" height="5" class="accent"/>
        """,
        "equal_height": """
            <rect x="5" y="4" width="5" height="16"/><rect x="14" y="4" width="5" height="16" class="accent"/>
        """,
        "equal_size": """
            <rect x="3" y="5" width="8" height="7"/><rect x="13" y="12" width="8" height="7" class="accent"/>
            <path d="M7 15v4h4M17 9V5h-4"/>
        """,
        "grid": """
            <rect x="3" y="3" width="18" height="18"/><path d="M9 3v18M15 3v18M3 9h18M3 15h18" class="accent"/>
        """,
        "grid_spacing": """
            <path d="M4 5h16M4 12h16M4 19h16"/><path d="M7 3v4M17 10v4M11 17v4" class="accent"/>
        """,
        "edit": """
            <path d="M5 19l1-5L17 3l4 4L10 19z" class="accent"/>
            <path d="M14 6l4 4M5 19h14"/>
        """,
        "comment": """
            <path d="M4 4h16v13H9l-5 4z"/><path d="M8 8h8M8 12h6" class="accent"/>
        """,
        "line": """
            <circle cx="5" cy="18" r="2"/><circle cx="19" cy="6" r="2"/>
            <path d="M7 17L17 7" class="accent"/>
        """,
        "curve": """
            <circle cx="4" cy="18" r="2"/><circle cx="20" cy="6" r="2"/>
            <path d="M6 18C8 5 14 19 18 6" class="accent"/>
        """,
        "rectangle": """
            <rect x="4" y="6" width="16" height="12" rx="1" class="accent"/>
        """,
        "ellipse": """
            <ellipse cx="12" cy="12" rx="9" ry="7" class="accent"/>
        """,
        "input": """
            <path d="M3 12h15M13 7l5 5-5 5" class="accent"/><rect x="18" y="6" width="3" height="12"/>
        """,
        "output": """
            <rect x="3" y="6" width="3" height="12"/><path d="M6 12h15M16 7l5 5-5 5" class="accent"/>
        """,
        "add_all": """
            <rect x="3" y="5" width="12" height="14" rx="2"/><path d="M9 8v8M5 12h8" class="accent"/>
            <path d="M18 8v8M14 12h8" class="accent"/>
        """,
        "binary_array": """
            <rect x="3" y="5" width="18" height="14" rx="2"/>
            <path d="M8 8v8M5 12h6M16 8v8M13 8h6M13 16h6" class="accent"/>
        """,
        "bar_display": """
            <path d="M4 20V4M4 20h17"/><rect x="7" y="13" width="3" height="5" class="accent"/>
            <rect x="12" y="9" width="3" height="9" class="accent"/><rect x="17" y="5" width="3" height="13" class="accent"/>
        """,
        "pointer_display": """
            <path d="M4 17a8 8 0 0116 0"/><path d="M12 16l5-6" class="accent"/>
            <circle cx="12" cy="16" r="1.5" class="accent fill"/>
        """,
        "sps_export": """
            <rect x="3" y="4" width="18" height="16" rx="2"/>
            <path d="M7 8h10M7 12h10M7 16h10"/>
            <circle cx="5" cy="8" r="1" class="accent fill"/>
            <circle cx="5" cy="12" r="1" class="accent fill"/>
            <circle cx="5" cy="16" r="1" class="accent fill"/>
            <path d="M18 7l3 3-3 3" class="accent"/>
        """
    }

    @classmethod
    def icon(
        cls,
        symbol_name,
        color="#34495e",
        accent="#2483c5"
    ):
        body = cls.SYMBOLS[symbol_name]
        svg = f"""
            <svg xmlns="http://www.w3.org/2000/svg"
                 width="64" height="64" viewBox="0 0 24 24">
                <style>
                    path, rect, circle, ellipse {{
                        fill: none;
                        stroke: {color};
                        stroke-width: 1.8;
                        stroke-linecap: round;
                        stroke-linejoin: round;
                    }}
                    .accent {{ stroke: {accent}; }}
                    .fill {{ fill: {accent}; stroke: {accent}; }}
                </style>
                {body}
            </svg>
        """

        renderer = QSvgRenderer(
            QByteArray(svg.encode("utf-8"))
        )
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()

        return QIcon(pixmap)
