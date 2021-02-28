# Copyright 2021 Robert Schroll
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import argparse
import io
import sys
import zipfile

from . import render
from .constants import VERSION
from .sources import ZipSource

def main():
    parser = argparse.ArgumentParser(description="Render a PDF file from a Remarkable document.")
    parser.add_argument('input', help="Filename of zip file, or root-level unpacked file of document.  Use '-' to read zip file from stdin.")
    parser.add_argument('output', nargs='?', default='', help="Filename where PDF file should be written.  Omit to write to stdout.")
    parser.add_argument('--alpha', default=0.3, help="Opacity for template background (0 for no background).")
    parser.add_argument('--no-expand', action='store_true', help="Don't expand pages to margins on device.")
    parser.add_argument('--only-annotated', action='store_true', help="Only render pages with annotations.")
    parser.add_argument('--version', action='version', version=VERSION)
    args = parser.parse_args()

    source = args.input
    if source == '-':
        # zipfile needs to seek, so we need to read this all in
        source = ZipSource(zipfile.ZipFile(io.BytesIO(sys.stdin.buffer.read())))
    if args.output:
        fout = open(args.output, 'wb')
    else:
        fout = sys.stdout.buffer

    stream = render(source,
                    template_alpha=float(args.alpha),
                    expand_pages=not args.no_expand,
                    only_annotated=args.only_annotated)
    fout.write(stream.read())
    fout.close()
    return 0

if __name__ == '__main__':
    sys.exit(main())
