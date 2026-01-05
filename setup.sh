#!/bin/bash
# Dockerbak Setup Script

echo "======================================"
echo "Dockerbak Setup"
echo "======================================"
echo ""

# Check Python version
echo "Checking Python version..."
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "Found Python $PYTHON_VERSION"

# Check if pip is available
echo ""
echo "Checking pip..."
if ! command -v pip3 &> /dev/null; then
    echo "Error: pip3 is not installed"
    exit 1
fi

# Install dependencies
echo ""
echo "Installing dependencies..."
pip3 install -r requirements.txt

if [ $? -eq 0 ]; then
    echo ""
    echo "======================================"
    echo "Setup completed successfully!"
    echo "======================================"
    echo ""
    echo "To run Dockerbak:"
    echo "  ./dockerbak.py"
    echo ""
    echo "Or:"
    echo "  python3 dockerbak.py"
    echo ""
else
    echo ""
    echo "Error: Failed to install dependencies"
    exit 1
fi
