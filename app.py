import os
import json
from pathlib import Path
from datetime import datetime
from flask import Flask, request, jsonify, render_template, Response, stream_with_context
import anthropic

app = Flask(__name__)

TUTOR_DIR = Path(__file__).parent / "cleo_tutor_retry_pack"
PROGRESS_LOG = TUTOR_DIR / "progress-log.md"

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


def load_system_prompt():
    parts = []
    for filename in MD_FILES_ORDER:
        path = TUTOR_DIR / filename
        if path.exists():
            parts.append(path.read_text(encoding="utf-8"))
    return "\n\n---\n\n".join(parts)


SYSTEM_PROMPT = load_system_prompt()
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))


@app.route("/")
def index():
    return render_template("index.html", topics=TOPICS)


@app.route("/topics")
def topics():
    return jsonify(TOPICS)


@app.route("/chat", methods=["POST"])
def chat():
    data = request.json
    messages = data.get("messages", [])
    topic_context = data.get("topic_context", "")

    system = SYSTEM_PROMPT
    if topic_context:
        system += f"\n\n---\n\nThe student has selected **{topic_context}** as their current focus area. Prioritise questions and explanations from this section unless the student asks otherwise."

    def generate():
        with client.messages.stream(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=system,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                yield f"data: {json.dumps({'text': text})}\n\n"
        yield "data: [DONE]\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.route("/save-note", methods=["POST"])
def save_note():
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
    port = int(os.environ.get("PORT", 5000))
    print("\n  Cleo Tutor is running.")
    print(f"  Open http://localhost:{port} in your browser.\n")
    app.run(debug=False, host="0.0.0.0", port=port)
