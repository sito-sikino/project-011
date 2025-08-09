#!/bin/bash
# Discord Multi-Agent System - Virtual Environment Activation Script
# Usage: source activate.sh

if [ -d "venv" ]; then
    source venv/bin/activate
    echo "✓ Virtual environment activated"
    echo "Python version: $(python --version)"
    echo "Virtual environment: $VIRTUAL_ENV"
else
    echo "❌ Virtual environment not found. Please run:"
    echo "python3 -m venv venv"
    echo "source activate.sh"
    exit 1
fi