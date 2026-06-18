import os
import json
import threading
from pathlib import Path
from datetime import datetime
from flask import (
    Flask, request, jsonify, render_template,
    Response, stream_with_context, session, redirect, url_for
)
import anthropic

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "cleo-tutor-secret-2024")
PASSWORD = os.environ.get("TUTOR_PASSWORD", "Sassieq1")

TUTOR_DIR = Path(__file__).parent / "cleo_tutor_retry_pack"
PROGRESS_LOG = TUTOR_DIR / "progress-log.md"
SESSION_FILE = Path(__file__).parent / "session.json"
SESSIONS_DIR = Path(__file__).parent / "sessions"

MD_FILES_ORDER = [
    "cleo-maths-tutor-system.md",
    "tone-and-humour-layer.md",
    "topic-map.md",
    "practice-bank.md",
    "progress-log.md",
]

TOPICS = [
    {
        "chapter": "Chapter 4 — Measurement & Surds",
        "sections": [
            {"code": "4E", "name": "Review of Length"},
            {"code": "4F", "name": "Pythagoras' Theorem (2D & 3D)"},
            {"code": "4G", "name": "Area"},
            {"code": "4I", "name": "Surface Area: Prisms & Cylinders"},
            {"code": "4J", "name": "Surface Area: Pyramids & Cones"},
            {"code": "4K", "name": "Volume: Prisms & Cylinders"},
            {"code": "4L", "name": "Volume: Pyramids & Cones"},
            {"code": "4M", "name": "Spheres"},
        ],
    },
    {
        "chapter": "Chapter 6 — Trigonometry",
        "sections": [
            {"code": "6A", "name": "Trig Ratios (SOHCAHTOA)"},
            {"code": "6B", "name": "Finding Unknown Angles"},
            {"code": "6C", "name": "2D Applications"},
            {"code": "6D", "name": "Bearings & Directions"},
            {"code": "6F", "name": "Sine Rule"},
            {"code": "6G", "name": "Cosine Rule"},
        ],
    },
]

# Every concept Cleo must demonstrate for the test.
# Progress = mastered / total.
CONCEPTS = {
    "4E-1": "Converting length units and calculating perimeter",
    "4E-2": "Circumference and arc length of circles",
    "4F-1": "Pythagoras' theorem in 2D problems",
    "4F-2": "Pythagoras' theorem in 3D (space diagonals)",
    "4G-1": "Area of triangles and quadrilaterals",
    "4G-2": "Area of circles and sectors",
    "4G-3": "Area of composite shapes",
    "4I-1": "Surface area of prisms",
    "4I-2": "Surface area of cylinders",
    "4J-1": "Surface area of pyramids",
    "4J-2": "Surface area of cones",
    "4K-1": "Volume of prisms",
    "4K-2": "Volume of cylinders",
    "4L-1": "Volume of pyramids",
    "4L-2": "Volume of cones",
    "4M-1": "Surface area of spheres",
    "4M-2": "Volume of spheres",
    "6A-1": "SOHCAHTOA — finding a missing side in a right triangle",
    "6A-2": "Exact trigonometric values (30°, 45°, 60°)",
    "6A-3": "Trigonometric ratios in all four quadrants",
    "6B-1": "Finding unknown angles using inverse trigonometry",
    "6B-2": "Solving trig equations with two solutions in 0°–360°",
    "6C-1": "Angles of elevation and depression",
    "6C-2": "Multi-step 2D trigonometry problems",
    "6D-1": "True bearings and compass directions",
    "6D-2": "Back-bearings and extracting angles from bearings",
    "6D-3": "Solving triangle problems from bearing descriptions",
    "6F-1": "Sine rule — finding a missing side",
    "6F-2": "Sine rule — finding a missing angle",
    "6G-1": "Cosine rule — finding a missing side",
    "6G-2": "Cosine rule — finding a missing angle from three sides",
    "6G-3": "Area of a triangle using ½ab sin C",
}

_lock = threading.Lock()
_chat_session = None
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))


def blank_mastery():
    return {k: False for k in CONCEPTS}


def load_chat_session():
    global _chat_session
    if SESSION_FILE.exists():
        try:
            data = json.loads(SESSION_FILE.read_text(encoding="utf-8"))
            mastery = data.get("mastery", blank_mastery())
            for k in CONCEPTS:
                if k not in mastery:
                    mastery[k] = False
            _chat_session = {
                "messages": data.get("messages", []),
                "mastery": mastery,
            }
        except Exception:
            _chat_session = {"messages": [], "mastery": blank_mastery()}
    else:
        _chat_session = {"messages": [], "mastery": blank_mastery()}
    return _chat_session


def save_chat_session():
    with _lock:
        SESSION_FILE.write_text(
            json.dumps(_chat_session, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )


def mastery_summary():
    mastery = _chat_session["mastery"]
    mastered = [(k, CONCEPTS[k]) for k, v in mastery.items() if v]
    unmastered = [(k, CONCEPTS[k]) for k, v in mastery.items() if not v]
    total = len(CONCEPTS)
    done = len(mastered)
    lines = [f"\n\n---\n\n## Cleo's current mastery ({done}/{total} concepts)\n"]
    if mastered:
        lines.append("**Demonstrated — do not drill these again unless she asks:**")
        for _, desc in mastered:
            lines.append(f"- ✓ {desc}")
    if unmastered:
        lines.append("\n**Not yet demonstrated — prioritise these:**")
        for _, desc in unmastered:
            lines.append(f"- ✗ {desc}")
    lines.append(
        "\nWhen Cleo asks what she still needs to cover, refer directly to this list. "
        "Prioritise unmastered concepts in practice questions. "
        "Mark nothing as mastered unless she solved it correctly using the right method with minimal prompting."
    )
    return "\n".join(lines)


def run_mastery_check(messages):
    """Background thread: check recent exchange for demonstrated mastery."""
    try:
        unmastered_keys = [k for k, v in _chat_session["mastery"].items() if not v]
        if not unmastered_keys:
            return
        recent = messages[-6:] if len(messages) > 6 else messages
        concept_list = "\n".join([f"{k}: {CONCEPTS[k]}" for k in unmastered_keys])
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            system=(
                "You assess student mastery in a maths tutoring conversation. "
                "Look at the conversation and identify which concepts the STUDENT has clearly "
                "demonstrated correct understanding of — meaning they solved a problem correctly "
                "using the right method with minimal prompting. "
                "Getting an answer right after heavy hints or just recalling a fact does NOT count. "
                "Return ONLY a valid JSON array of concept keys, e.g. [\"6A-1\",\"4F-1\"]. "
                "If none qualify, return []. Be conservative — err on the side of not marking."
            ),
            messages=[{
                "role": "user",
                "content": (
                    f"Recent conversation:\n{json.dumps(recent, indent=2)}\n\n"
                    f"Concepts to check:\n{concept_list}\n\n"
                    "Return JSON array of mastered concept keys only."
                )
            }]
        )
        text = resp.content[0].text.strip()
        start, end = text.find("["), text.rfind("]") + 1
        if start >= 0 and end > start:
            newly = json.loads(text[start:end])
            changed = False
            with _lock:
                for key in newly:
                    if key in _chat_session["mastery"] and not _chat_session["mastery"][key]:
                        _chat_session["mastery"][key] = True
                        changed = True
            if changed:
                save_chat_session()
    except Exception:
        pass


def load_system_prompt():
    parts = []
    for filename in MD_FILES_ORDER:
        path = TUTOR_DIR / filename
        if path.exists():
            parts.append(path.read_text(encoding="utf-8"))
    return "\n\n---\n\n".join(parts)


BASE_SYSTEM_PROMPT = load_system_prompt()


def authenticated():
    return session.get("authenticated") is True


@app.route("/login", methods=["GET", "POST"])
def login():
    error = False
    if request.method == "POST":
        if request.form.get("password") == PASSWORD:
            session["authenticated"] = True
            return redirect(url_for("index"))
        error = True
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
def index():
    if not authenticated():
        return redirect(url_for("login"))
    return render_template("index.html", topics=TOPICS)


@app.route("/session")
def get_session():
    if not authenticated():
        return jsonify({"error": "Unauthorised"}), 401
    return jsonify({
        "messages": _chat_session["messages"],
        "mastery": _chat_session["mastery"],
        "total": len(CONCEPTS),
    })


@app.route("/mastery")
def get_mastery():
    if not authenticated():
        return jsonify({"error": "Unauthorised"}), 401
    mastery = _chat_session["mastery"]
    done = sum(1 for v in mastery.values() if v)
    return jsonify({
        "mastery": mastery,
        "done": done,
        "total": len(CONCEPTS),
        "percent": round(done / len(CONCEPTS) * 100),
    })


@app.route("/chat", methods=["POST"])
def chat():
    if not authenticated():
        return jsonify({"error": "Unauthorised"}), 401

    data = request.json
    messages = data.get("messages", [])
    topic_context = data.get("topic_context", "")

    system = BASE_SYSTEM_PROMPT + mastery_summary()
    if topic_context:
        system += (
            f"\n\n---\n\nThe student has selected **{topic_context}** as their current focus area. "
            "Prioritise questions and explanations from this section unless the student asks otherwise."
        )

    # Handle optional image attachment
    image_data = data.get("image")  # {data: base64str, media_type: "image/jpeg"}
    if image_data and messages:
        # Replace the last user message content with a multipart block
        last = messages[-1]
        if last["role"] == "user":
            text_content = last["content"] if last["content"] else "Here's my working — can you check it?"
            messages = messages[:-1] + [{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": image_data["media_type"],
                            "data": image_data["data"],
                        }
                    },
                    {"type": "text", "text": text_content},
                ]
            }]

    # Use Sonnet for image messages (better handwriting recognition), Haiku for text
    model = "claude-sonnet-4-6" if image_data else "claude-haiku-4-5-20251001"
    full_response = []

    def generate():
        with client.messages.stream(
            model=model,
            max_tokens=2048,
            system=system,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                full_response.append(text)
                yield f"data: {json.dumps({'text': text})}\n\n"

        # Persist session
        assistant_text = "".join(full_response)
        with _lock:
            _chat_session["messages"] = messages + [
                {"role": "assistant", "content": assistant_text}
            ]
        save_chat_session()

        # Background mastery check
        threading.Thread(
            target=run_mastery_check,
            args=(_chat_session["messages"],),
            daemon=True
        ).start()

        yield "data: [DONE]\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/clear-session", methods=["POST"])
def clear_session():
    if not authenticated():
        return jsonify({"ok": False}), 401
    with _lock:
        _chat_session["messages"] = []
    save_chat_session()
    return jsonify({"ok": True})


@app.route("/archive-session", methods=["POST"])
def archive_session():
    if not authenticated():
        return jsonify({"ok": False}), 401
    SESSIONS_DIR.mkdir(exist_ok=True)
    data = request.json or {}
    label = data.get("label", "").strip()
    filename = datetime.now().strftime("%Y-%m-%d-%H-%M") + ".json"
    archive = {
        "filename": filename,
        "label": label,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "messages": _chat_session["messages"],
        "mastery": _chat_session["mastery"],
    }
    with _lock:
        (SESSIONS_DIR / filename).write_text(
            json.dumps(archive, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    return jsonify({"ok": True, "filename": filename})


@app.route("/archived-sessions")
def list_archived_sessions():
    if not authenticated():
        return jsonify({"error": "Unauthorised"}), 401
    SESSIONS_DIR.mkdir(exist_ok=True)
    results = []
    for f in sorted(SESSIONS_DIR.glob("*.json"), reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            results.append({
                "filename": f.name,
                "label": data.get("label", ""),
                "date": data.get("date", ""),
                "message_count": len(data.get("messages", [])),
            })
        except Exception:
            pass
    return jsonify(results)


@app.route("/archived-sessions/<filename>")
def get_archived_session(filename):
    if not authenticated():
        return jsonify({"error": "Unauthorised"}), 401
    import re
    safe = re.sub(r"[^A-Za-z0-9\-.]", "", filename)
    if not safe.endswith(".json"):
        return jsonify({"error": "Invalid filename"}), 400
    path = SESSIONS_DIR / safe
    if not path.exists():
        return jsonify({"error": "Not found"}), 404
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return jsonify({"error": "Could not read file"}), 500
    return jsonify(data)


@app.route("/save-note", methods=["POST"])
def save_note():
    if not authenticated():
        return jsonify({"ok": False}), 401
    data = request.json
    note = data.get("note", "").strip()
    if not note:
        return jsonify({"ok": False})
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = f"\n\n### Session note — {timestamp}\n{note}\n"
    with open(PROGRESS_LOG, "a", encoding="utf-8") as f:
        f.write(entry)
    return jsonify({"ok": True})


if __name__ == "__main__":
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("\n  ERROR: ANTHROPIC_API_KEY environment variable not set.")
        print("  Set it in your terminal before running:\n")
        print("    export ANTHROPIC_API_KEY=sk-ant-...\n")
        exit(1)
    load_chat_session()
    port = int(os.environ.get("PORT", 5000))
    print("\n  Cleo Tutor is running.")
    print(f"  Open http://localhost:{port} in your browser.\n")
    app.run(debug=False, host="0.0.0.0", port=port)
