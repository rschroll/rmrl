'''
Copyright 2021 Robert Schroll

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
'''

import io
from pathlib import Path
import zipfile


# A Source should implement two methods:
#
# open(filename, mode)
#    Returns a file handled for the filename, opened in specified mode.
#
# exists(filename)
#    Returns a boolean indicating whether the file exists.
#
# In both cases, the filename may include the string `{ID}`, which indicates
# the Remarkable ID for that particular document (a UUID).  Thus, the caller
# of these methods does not have to know the ID of a document; the Source is
# responsible for filling that in appropriately.

class FSSource:

    def __init__(self, base_dir, doc_id):
        self.base_dir = Path(base_dir)
        self.doc_id = doc_id

    def format_name(self, name):
        return self.base_dir / name.format(ID=self.doc_id)

    def open(self, fn, mode='r'):
        return self.format_name(fn).open(mode)

    def exists(self, fn):
        return self.format_name(fn).exists()


class ZipSource:

    def __init__(self, zip_file, encoding='utf-8'):
        self.zip_file = zip_file
        self.encoding = encoding
        for fn in self.zip_file.namelist():
            if fn.endswith('.content'):
                self.doc_id = fn[:-8]
                break
        else:
            raise FileNotFoundError('Could not find .content file')

    def format_name(self, name):
        return name.format(ID=self.doc_id)

    def open(self, fn, mode='r'):
        f = self.zip_file.open(self.format_name(fn), mode.strip('b'))
        if mode.endswith('b'):
            return f
        return io.TextIOWrapper(f, encoding=self.encoding)

    def exists(self, fn):
        try:
            self.zip_file.getinfo(self.format_name(fn))
            return True
        except KeyError:
            return False


def get_source(source):
    # Pass through objects that implement the source API
    if hasattr(source, 'open') and hasattr(source, 'exists'):
        return source

    error = FileNotFoundError(f"Could not find a source file from {source!r}")
    try:
        source_p = Path(source)
    except TypeError:
        raise error from None

    # Check if it's a zip file
    if source_p.is_file():
        with source_p.open('rb') as f:
            if f.read(4) == b'PK\x03\x04':
                zf = zipfile.ZipFile(source_p)
                return ZipSource(zf)

    # If there's a .content file, assume it's unpacked
    if source_p.with_suffix('.content').is_file():
        return FSSource(source_p.parent, source_p.stem)

    raise error
