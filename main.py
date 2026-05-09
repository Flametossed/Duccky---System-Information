"""Duccky — modern system information viewer. Entry point."""

import multiprocessing
from app import App

if __name__ == "__main__":
    multiprocessing.freeze_support()
    App().run()
