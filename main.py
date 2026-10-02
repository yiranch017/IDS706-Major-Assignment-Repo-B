"""Canonical Stage 1 entry point: python main.py"""
import sys

from src.pipeline import run_pipeline


if __name__ == "__main__":
    sys.exit(run_pipeline())
