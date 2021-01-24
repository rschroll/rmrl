'''
Copyright (C) 2020  Davis Remmel
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

import gc
import json
import logging

from reportlab.graphics import renderPDF
from svglib.svglib import svg2rlg

from . import lines, pens
from .constants import DISPLAY, PDFHEIGHT, PDFWIDTH, PTPERPX, TEMPLATE_PATH


log = logging.getLogger(__name__)

class DocumentPage:
    # A single page in a document
    def __init__(self, source, pid, pagenum):
        # Page 0 is the first page!
        self.source = source
        self.num = pagenum

        # On disk, these files are named by a UUID
        self.rmpath = f'{{ID}}/{pid}.rm'
        if not source.exists(self.rmpath):
            # From the API, these files are just numbered
            pid = str(pagenum)
            self.rmpath = f'{{ID}}/{pid}.rm'

        # Try to load page metadata
        self.metadict = None
        metafilepath = f'{{ID}}/{pid}-metadata.json'
        if source.exists(metafilepath):
            with source.open(metafilepath, 'r') as f:
                self.metadict = json.load(f)

        # Try to load template
        self.template = None
        template_names = []
        pagedatapath = '{ID}.pagedata'
        if source.exists(pagedatapath):
            with source.open(pagedatapath, 'r') as f:
                template_names = f.read().splitlines()

        if template_names:
            # I have encountered an issue with some PDF files, where the
            # rM won't save the page template for later pages. In this
            # case, just take the last-available page template, which
            # is usually 'Blank'.
            template_name = template_names[max(self.num, len(template_names) - 1)]
            template_path = TEMPLATE_PATH / f'{template_name}.svg'
            if template_name != 'Blank' and template_path.exists():
                self.template = str(template_path)

        # Load layers
        self.layers = []
        self.load_layers()

    def get_grouped_annotations(self):
        # Return the annotations grouped by proximity. If they are
        # within a distance of each other, count them as a single
        # annotation.

        # Annotations should be delivered in an array, where each
        # index is a tuple (LayerName,
        annotations = []
        for layer in self.layers:
            annotations.append(layer.get_grouped_annotations())
        return annotations

    def load_layers(self):
        # Loads layers from the .rm files

        if not self.source.exists(self.rmpath):
            # no layers, obv
            return

        # Load reMy version of page layers
        pagelayers = None
        with self.source.open(self.rmpath, 'rb') as f:
            _, pagelayers = lines.readLines(f)

        # Load layer data
        for i in range(0, len(pagelayers)):
            layerstrokes = pagelayers[i]

            try:
                name = self.metadict['layers'][i]['name']
            except:
                name = 'Layer ' + str(i + 1)

            layer = DocumentPageLayer(self, name=name)
            layer.strokes = layerstrokes
            self.layers.append(layer)

    def render_to_painter(self, canvas, vector):
        # Render template layer
        if self.template:
            background = svg2rlg(self.template)
            background.scale(PDFWIDTH / background.width, PDFWIDTH / background.width)
            renderPDF.draw(background, canvas, 0, 0)
            # Bitmaps are rendered into the PDF as XObjects, which are
            # easy to pick out for layers. Vectors will render
            # everything inline, and so we need to add a 'magic point'
            # to mark the end of the template layer.
            if False and vector:  #TODO
                pen = GenericPen(color=Qt.transparent, vector=vector)
                painter.setPen(pen)
                painter.drawPoint(800, 85)

        # The annotation coordinate system is upside down compared to the PDF
        # coordinate system, so offset the bottom to the top and then flip
        # vertically along the old bottom / new top to place the annotations
        # correctly.
        canvas.translate(0, PDFHEIGHT)
        canvas.scale(PTPERPX, -PTPERPX)
        # Render user layers
        for layer in self.layers:
            # Bitmaps are rendered into the PDF as XObjects, which are
            # easy to pick out for layers. Vectors will render
            # everything inline, and so we need to add a 'magic point'
            # to mark the beginning of layers.
            if False and vector:  #TODO
                pen = GenericPen(color=Qt.transparent, vector=vector)
                painter.setPen(pen)
                painter.drawPoint(420, 69)
            layer.render_to_painter(canvas, vector)
        canvas.showPage()


class DocumentPageLayer:
    pen_widths = []

    def __init__(self, page, name=None):
        self.page = page
        self.name = name

        self.colors = [
            #QSettings().value('pane/notebooks/export_pdf_blackink'),
            #QSettings().value('pane/notebooks/export_pdf_grayink'),
            #QSettings().value('pane/notebooks/export_pdf_whiteink')
            (0, 0, 0),
            (0.5, 0.5, 0.5),
            (1, 1, 1)
        ]

        # Set this from the calling func
        self.strokes = None

        # Store PDF annotations with the layer, in case actual
        # PDF layers are ever implemented.
        self.annot_paths = []

    def get_grouped_annotations(self):
        # return: (LayerName, [(AnnotType, minX, minY, maxX, maxY)])

        # Compare all the annot_paths to each other. If any overlap,
        # they will be grouped together. This is done recursively.
        def grouping_func(pathset):
            newset = []

            for p in pathset:
                annotype = p[0]
                path = p[1]
                did_fit = False
                for i, g in enumerate(newset):
                    gannotype = g[0]
                    group = g[1]
                    # Only compare annotations of the same type
                    if gannotype != annotype:
                        continue
                    if path.intersects(group):
                        did_fit = True
                        newset[i] = (annotype, group.united(path))
                        break
                if did_fit:
                    continue
                # Didn't fit, so place into a new group
                newset.append(p)

            if len(newset) != len(pathset):
                # Might have stuff left to group
                return grouping_func(newset)
            else:
                # Nothing was grouped, so done
                return newset

        grouped = grouping_func(self.annot_paths)

        # Get the bounding rect of each group, which sets the PDF
        # annotation geometry.
        annot_rects = []
        for p in grouped:
            annotype = p[0]
            path = p[1]
            rect = path.boundingRect()
            annot = (annotype,
                     float(rect.x()),
                     float(rect.y()),
                     float(rect.x() + rect.width()),
                     float(rect.y() + rect.height()))
            annot_rects.append(annot)

        return (self.name, annot_rects)

    def paint_strokes(self, canvas, vector):
        for stroke in self.strokes:
            pen, color, unk1, width, unk2, segments = stroke

            penclass = pens.PEN_MAPPING.get(pen)
            if penclass is None:
                log.error("Unknown pen code %d" % pen)
                penclass = pens.GenericPen

            qpen = penclass(vector=vector,
                            layer=self,
                            color=self.colors[color])

            # Do the needful
            qpen.paint_stroke(canvas, stroke)

    def render_to_painter(self, painter, vector):
        if vector: # Turn this on with vector otherwise off to get hybrid
            self.paint_strokes(painter, vector=vector)
            return

        assert False

        # I was having problems with QImage corruption (garbage data)
        # and memory leaking on large notebooks. I fixed this by giving
        # the QImage a reference array to pre-allocate RAM, then reset
        # the reference count after I'm done with it, so that it gets
        # cleaned up by the python garbage collector.

        devpx = DISPLAY['screenwidth'] \
            * DISPLAY['screenheight']
        bytepp = 4  # ARGB32
        qimage = QImage(b'\0' * devpx * bytepp,
                        DISPLAY['screenwidth'],
                        DISPLAY['screenheight'],
                        QImage.Format_ARGB32)

        imgpainter = QPainter(qimage)
        imgpainter.setRenderHint(QPainter.Antialiasing)
        #imgpainter.setRenderHint(QPainter.LosslessImageRendering)
        self.paint_strokes(imgpainter, vector=vector)
        imgpainter.end()

        painter.drawImage(0, 0, qimage)

        del imgpainter
        del qimage
        gc.collect()
