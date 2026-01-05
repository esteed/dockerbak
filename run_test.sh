#!/bin/bash
# Interactive test script for Dockerbak

echo "================================================"
echo "Dockerbak Live Test"
echo "================================================"
echo ""
echo "This will test Dockerbak with a real Docker host."
echo ""
echo "You will need:"
echo "  - A Docker host accessible via SSH"
echo "  - SSH credentials (password or key)"
echo "  - Docker running on the remote host"
echo ""
read -p "Press Enter to start Dockerbak or Ctrl+C to cancel..."
echo ""

# Run dockerbak
python3 dockerbak.py
