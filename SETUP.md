# Cleo Tutor — Setup

A local tutoring app for NSW Year 10 Advanced Maths (Chapters 4 & 6).

## Requirements

- Python 3.9 or later
- An Anthropic API key

## First-time setup

**1. Install Python** (if not already installed)
Download from python.org. Tick "Add to PATH" during install on Windows.

**2. Set your API key**

Mac/Linux — open Terminal and run:
```
export ANTHROPIC_API_KEY=sk-ant-YOUR_KEY_HERE
```

Windows — open Command Prompt and run:
```
set ANTHROPIC_API_KEY=sk-ant-YOUR_KEY_HERE
```

To avoid doing this every session, add the export line to your `~/.zshrc` or `~/.bash_profile` (Mac), or set it as a system environment variable (Windows).

**3. Launch**

Mac/Linux:
```
cd path/to/CLEO
bash start.sh
```

Windows:
```
cd path\to\CLEO
start.bat
```

**4. Open in browser**

Go to: http://localhost:5000

---

## Usage

- Pick a topic from the left sidebar to focus the session
- Ask anything: "explain sine rule", "give me a practice problem", "where am I going wrong?"
- The tutor never just gives the answer — it guides you through
- Use "Save session note" to log what clicked or what needs more work (saved to `cleo_tutor_retry_pack/progress-log.md`)
- "New session" clears the conversation but keeps the knowledge base

## Updating the knowledge base

All tutor content lives in `cleo_tutor_retry_pack/`. Edit any `.md` file and restart the app — changes load automatically on startup.

- `cleo-maths-tutor-system.md` — core teaching rules and chapter guidance
- `practice-bank.md` — add more practice questions here
- `progress-log.md` — session notes and mastery tracking
- `tone-and-humour-layer.md` — voice and tone guidelines
- `topic-map.md` — curriculum structure

## Cost

Each message costs roughly $0.001–0.003 AUD using the Haiku model. A full hour-long study session is typically under $0.20.
