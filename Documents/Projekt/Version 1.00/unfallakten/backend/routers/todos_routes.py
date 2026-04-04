"""
backend/routers/todos_routes.py
=================================
PRD-01: To-Do-System je Akte

  GET    /akten/<az>/todos           Alle To-Dos der Akte
  POST   /akten/<az>/todos           Neues To-Do anlegen
  PATCH  /akten/<az>/todos/<id>      Erledigt-Status / Text ändern
  DELETE /akten/<az>/todos/<id>      Nur manuelle To-Dos löschbar
"""

import logging
from flask import Blueprint, request, jsonify, g
from ..auth.middleware import login_erforderlich
from ..models.akte import hole_akte_by_id
from ..db.database import get_connection

logger = logging.getLogger(__name__)

# Fester url_prefix – <path:akte_id> pro Route (Lerneffekt v14d)
todos_bp = Blueprint("todos", __name__, url_prefix="/akten")


def _j(d, s=200):
    return jsonify(d), s

def _err(msg, s=400, **kw):
    return jsonify({"fehler": msg, "status": s, **kw}), s

def _body():
    return request.get_json(silent=True) or {}

def _todo_dict(row) -> dict:
    return {
        "id":          row["id"],
        "akte_az":     row["akte_az"],
        "text":        row["text"],
        "erstellt_am": row["erstellt_am"],
        "faellig_am":  row["faellig_am"],
        "frist_typ":   row["frist_typ"],
        "erledigt_am": row["erledigt_am"],
        "erledigt":    bool(row["erledigt"]),
        "quelle":      row["quelle"],
        "dok_id":      row["dok_id"],
        "regel_key":   row["regel_key"],
        "sortierung":  row["sortierung"],
    }


@todos_bp.route("/<path:akte_id>/todos", methods=["GET"])
@login_erforderlich
def liste_todos(akte_id: str):
    """GET /akten/<az>/todos – Alle To-Dos der Akte."""
    akte = hole_akte_by_id(akte_id)
    if not akte:
        return _err(f"Akte '{akte_id}' nicht gefunden.", 404)
    az = akte.aktenzeichen

    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM todos WHERE akte_az = ?
               ORDER BY erledigt ASC, faellig_am ASC NULLS LAST,
                        erstellt_am DESC""",
            (az,)
        ).fetchall()

    return _j({"todos": [_todo_dict(r) for r in rows], "anzahl": len(rows)})


@todos_bp.route("/<path:akte_id>/todos", methods=["POST"])
@login_erforderlich
def erstelle_todo(akte_id: str):
    """POST /akten/<az>/todos – Neues To-Do anlegen."""
    akte = hole_akte_by_id(akte_id)
    if not akte:
        return _err(f"Akte '{akte_id}' nicht gefunden.", 404)
    az = akte.aktenzeichen

    daten = _body()
    text = (daten.get("text") or "").strip()
    if not text:
        return _err("text ist erforderlich.", 422)

    faellig_am = daten.get("faellig_am") or None
    frist_typ  = daten.get("frist_typ")  or None
    quelle     = daten.get("quelle", "benutzer")
    if quelle not in ("benutzer", "system"):
        quelle = "benutzer"
    dok_id     = daten.get("dok_id")     or None
    regel_key  = daten.get("regel_key")  or None
    sortierung = int(daten.get("sortierung", 0))

    with get_connection() as conn:
        cursor = conn.execute(
            """INSERT INTO todos
               (akte_az, text, faellig_am, frist_typ, quelle, dok_id, regel_key, sortierung)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (az, text, faellig_am, frist_typ, quelle, dok_id, regel_key, sortierung)
        )
        todo_id = cursor.lastrowid
        row = conn.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()

    return _j({"todo": _todo_dict(row)}, 201)


@todos_bp.route("/<path:akte_id>/todos/<int:todo_id>", methods=["PATCH"])
@login_erforderlich
def update_todo(akte_id: str, todo_id: int):
    """PATCH /akten/<az>/todos/<id> – Erledigt-Status oder Text ändern."""
    akte = hole_akte_by_id(akte_id)
    if not akte:
        return _err(f"Akte '{akte_id}' nicht gefunden.", 404)
    az = akte.aktenzeichen

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM todos WHERE id = ? AND akte_az = ?", (todo_id, az)
        ).fetchone()
        if not row:
            return _err(f"To-Do {todo_id} nicht gefunden.", 404)

        daten  = _body()
        felder = {}

        if "text" in daten:
            t = (daten["text"] or "").strip()
            if not t:
                return _err("text darf nicht leer sein.", 422)
            if row["quelle"] == "system":
                return _err("System-To-Dos können nicht bearbeitet werden.", 403)
            felder["text"] = t

        if "erledigt" in daten:
            erledigt = bool(daten["erledigt"])
            felder["erledigt"]    = 1 if erledigt else 0
            felder["erledigt_am"] = (
                "datetime('now','localtime')" if erledigt else None
            )

        if "faellig_am" in daten:
            felder["faellig_am"] = daten["faellig_am"] or None

        if "frist_typ" in daten:
            felder["frist_typ"] = daten["frist_typ"] or None

        if not felder:
            return _j({"todo": _todo_dict(row)})

        # erledigt_am ist ein SQL-Ausdruck, separat behandeln
        erledigt_am_expr = felder.pop("erledigt_am", "SKIP")
        set_parts  = [f"{k} = ?" for k in felder]
        set_values = list(felder.values())

        if erledigt_am_expr != "SKIP":
            if erledigt_am_expr is None:
                set_parts.append("erledigt_am = NULL")
            else:
                set_parts.append(f"erledigt_am = {erledigt_am_expr}")

        conn.execute(
            f"UPDATE todos SET {', '.join(set_parts)} WHERE id = ?",
            set_values + [todo_id]
        )
        updated = conn.execute(
            "SELECT * FROM todos WHERE id = ?", (todo_id,)
        ).fetchone()

    return _j({"todo": _todo_dict(updated)})


@todos_bp.route("/<path:akte_id>/todos/<int:todo_id>", methods=["DELETE"])
@login_erforderlich
def loesche_todo(akte_id: str, todo_id: int):
    """DELETE /akten/<az>/todos/<id> – Nur manuelle To-Dos löschbar."""
    akte = hole_akte_by_id(akte_id)
    if not akte:
        return _err(f"Akte '{akte_id}' nicht gefunden.", 404)
    az = akte.aktenzeichen

    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM todos WHERE id = ? AND akte_az = ?", (todo_id, az)
        ).fetchone()
        if not row:
            return _err(f"To-Do {todo_id} nicht gefunden.", 404)
        if row["quelle"] == "system":
            return _err("System-To-Dos können nicht gelöscht werden.", 403)
        conn.execute("DELETE FROM todos WHERE id = ?", (todo_id,))

    return _j({"geloescht": True, "id": todo_id})
