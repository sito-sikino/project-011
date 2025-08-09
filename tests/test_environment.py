"""
Environment setup tests for Discord Multi-Agent System.
Tests Python 3.11+ and venv activation requirements.
"""

import sys
import os
import subprocess
from pathlib import Path


def test_python_version():
    """Test that Python version is 3.11 or higher."""
    version_info = sys.version_info
    assert version_info.major == 3, f"Python major version must be 3, got {version_info.major}"
    assert version_info.minor >= 11, f"Python minor version must be 11+, got {version_info.minor}"
    print(f"✓ Python version: {version_info.major}.{version_info.minor}.{version_info.micro}")


def test_venv_activated():
    """Test that virtual environment is activated."""
    # Check if we're in a virtual environment
    virtual_env = os.environ.get('VIRTUAL_ENV')
    assert virtual_env is not None, "Virtual environment not activated (VIRTUAL_ENV not set)"
    
    # Verify virtual environment path exists
    venv_path = Path(virtual_env)
    assert venv_path.exists(), f"Virtual environment path does not exist: {virtual_env}"
    
    # Check that python executable is from venv
    python_executable = sys.executable
    assert str(venv_path) in python_executable, f"Python executable not from venv: {python_executable}"
    
    print(f"✓ Virtual environment active: {virtual_env}")
    print(f"✓ Python executable: {python_executable}")


def test_pip_available():
    """Test that pip is available in the virtual environment."""
    try:
        result = subprocess.run([sys.executable, "-m", "pip", "--version"], 
                              capture_output=True, text=True, check=True)
        print(f"✓ Pip available: {result.stdout.strip()}")
    except subprocess.CalledProcessError as e:
        assert False, f"Pip not available in virtual environment: {e}"


if __name__ == "__main__":
    test_python_version()
    test_venv_activated()
    test_pip_available()
    print("All environment tests passed!")