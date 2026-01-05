#!/usr/bin/env python3
"""
Dockerbak - Docker Container Backup and Restore Tool

A comprehensive tool for backing up Docker containers and stacks from remote hosts,
including volumes, configurations, and generating detailed restore instructions.
"""

import sys
import os
import logging
from src.cli import DockerBakCLI


def setup_logging():
    """Setup logging based on DEBUG environment variable."""
    debug = os.environ.get('DEBUG', '').lower() in ('1', 'true', 'yes')

    if debug:
        logging.basicConfig(
            level=logging.DEBUG,
            format='[%(levelname)s] %(name)s:%(lineno)d - %(message)s',
            stream=sys.stderr
        )
        logging.getLogger('dockerbak').debug("Debug logging enabled")
        logging.getLogger('dockerbak.backup').debug("Backup debug logging enabled")
        logging.getLogger('dockerbak.sudo').debug("Sudo debug logging enabled")
    else:
        logging.basicConfig(
            level=logging.WARNING,
            format='[%(levelname)s] %(message)s',
            stream=sys.stderr
        )


def main():
    """Main entry point for Dockerbak."""
    setup_logging()

    cli = DockerBakCLI()
    exit_code = cli.run()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
