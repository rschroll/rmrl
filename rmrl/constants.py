from pathlib import Path

# From rcu.py, with comment
# Todo: this should be based on the specific RM model
DISPLAY = {
            'screenwidth': 1404,
            'screenheight': 1872,
            'realwidth': 1408,
            'dpi': 226
            }
# Qt docs say 1 pt is always 1/72 inch
# Multiply ptperpx by pixels to convert to PDF coords
PTPERPX = 72 / DISPLAY['dpi']
PDFHEIGHT = DISPLAY['screenheight'] * PTPERPX
PDFWIDTH = DISPLAY['screenwidth'] * PTPERPX

SPOOL_MAX = 10 * 1024 * 1024

# TODO: parameterize
TEMPLATE_PATH = Path('/home/pi/source-rcu-r2020-003/rcu/src/templates')
