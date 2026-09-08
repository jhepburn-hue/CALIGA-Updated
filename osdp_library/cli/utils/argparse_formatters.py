"""Argparse formatter utilities."""

import argparse


class HelpFormatter(
    argparse.RawDescriptionHelpFormatter,
    argparse.ArgumentDefaultsHelpFormatter,
):
    """Formatter that preserves raw description and shows argument defaults."""

    pass
