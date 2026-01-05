#!/bin/bash

# Git Credentials Setup Script
# This script configures git to cache your GitHub credentials

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=== Git Credentials Setup ===${NC}\n"

# Configure credential helper to cache for 24 hours (86400 seconds)
echo -e "${YELLOW}Configuring credential helper (24-hour cache)...${NC}"
git config --global credential.helper 'cache --timeout=86400'

echo -e "${GREEN}✓ Credential caching enabled${NC}\n"

# Prompt for token and test connection
echo -e "${YELLOW}Enter your GitHub Personal Access Token:${NC}"
read -s TOKEN
echo ""

echo -e "${YELLOW}Testing connection and caching credentials...${NC}"

# Set up credential helper to store this token
git credential approve <<EOF
protocol=https
host=github.com
username=esteed
password=$TOKEN
EOF

# Test with a pull
if git pull origin main 2>&1 | grep -q "Already up to date\|Updating"; then
    echo -e "${GREEN}✓ Connection successful! Credentials cached for 24 hours.${NC}"
else
    echo -e "${GREEN}✓ Credentials cached for 24 hours.${NC}"
fi

echo -e "\n${GREEN}=== Setup Complete ===${NC}"
echo -e "${YELLOW}You can now use ./gitsync without entering credentials for 24 hours.${NC}"
echo -e "${YELLOW}After 24 hours, run this script again or just use ./gitsync (it will prompt for credentials).${NC}"
