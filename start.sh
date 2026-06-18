#!/bin/bash
# Cleo Tutor launcher

if [ -z "$ANTHROPIC_API_KEY" ]; then
  echo ""
  echo "  Set your API key first:"
  echo "  export ANTHROPIC_API_KEY=sk-ant-..."
  echo ""
  exit 1
fi

# Install dependencies if needed
if ! python3 -c "import flask, anthropic" 2>/dev/null; then
  echo "Installing dependencies..."
  pip3 install -r requirements.txt -q
fi

python3 app.py
