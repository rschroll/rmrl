'''
lines.py
This is the model for Lines, which come from RM files.

This file was written originally for the reMy project and modified for
RCU.

reMy is a file manager for the reMarkable tablet.
Copyright (C) 2020  Emanuele D'Osualdo.

RCU is a synchronization tool for the reMarkable Tablet.
Copyright (C) 2020  Davis Remmel

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


from collections import namedtuple
import struct
import json

Layer = namedtuple('Layer', ['strokes', 'name'])

Stroke = namedtuple(
    'Stroke',
    ['pen', 'color', 'unk1', 'width', 'unk2', 'segments']
)
Segment = namedtuple(
    'Segment',
    ['x', 'y', 'speed', 'direction', 'width', 'pressure']
)

HEADER_START = b'reMarkable .lines file, version='
S_HEADER_PAGE = struct.Struct('<{}ss10s'.format(len(HEADER_START)))
S_PAGE = struct.Struct('<BBH')    # TODO: might be 'I'
S_LAYER = struct.Struct('<I')
S_STROKE_V3 = struct.Struct('<IIIfI')
S_STROKE_V5 = struct.Struct('<IIIfII')
S_SEGMENT = struct.Struct('<ffffff')


class UnsupportedVersion(Exception):
    pass
class InvalidFormat(Exception):
    pass

def readStruct(fmt, source):
    buff = source.read(fmt.size)
    return fmt.unpack(buff)

def readStroke3(source):
    pen, color, unk1, width, n_segments = readStruct(S_STROKE_V3, source)
    return (pen, color, unk1, width, 0, n_segments)

def readStroke5(source):
    return readStruct(S_STROKE_V5, source)

# source is a filedescriptor from which we can .read(N)
def readLines(source):
    try:

        header, ver, *_ = readStruct(S_HEADER_PAGE, source)
        if not header.startswith(HEADER_START):
            raise InvalidFormat("Header is invalid")
        ver = int(ver)
        if ver == 3:
            readStroke = readStroke3
        elif ver == 5:
            readStroke = readStroke5
        else:
            raise UnsupportedVersion("Remy supports notebooks in the version 3 and 5 format only")
        n_layers, _, _ = readStruct(S_PAGE, source)
        layers = []
        for l in range(n_layers):
            n_strokes, = readStruct(S_LAYER, source)
            strokes = []
            for s in range(n_strokes):
                pen, color, unk1, width, unk2, n_segments = readStroke(source)
                segments = []
                for i in range(n_segments):
                    x, y, speed, direction, width, pressure = readStruct(S_SEGMENT, source)
                    segments.append(Segment(x, y, speed, direction, width, pressure))
                strokes.append(Stroke(pen, color, unk1, width, unk2, segments))
            layers.append(strokes)

        return (ver, layers)

    except struct.error:
        raise InvalidFormat("Error while reading page")
