'''
document.py
This is the model for a document.

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

import log
import tempfile
from datetime import datetime
import tarfile
from pathlib import Path
import uuid
import json
import gc
import shutil
import time
import os
import re

#from PySide2.QtWidgets import QGraphicsScene
from PySide2.QtGui import QPainter, QImage, QColor#, QPen, QPixmap, \
    #QPageSize, QColor, QBrush, QPainterPath
from PySide2.QtCore import Qt, QByteArray, QIODevice, QBuffer, QSizeF, \
    QSettings
from PySide2.QtPrintSupport import QPrinter

from pdfrw import PdfReader, PdfWriter, PageMerge, PdfDict, PdfArray, PdfName, \
    IndirectPdfDict, uncompress, compress

import svgtools
#from model.template import Template -- disable template for now....
from model import lines

def rmdir(path):
    if path.is_file() and path.exists():
        path.unlink()
    try:
        for child in path.glob('*'):
            if child.is_file():
                child.unlink()
            else:
                rmdir(child)
        path.rmdir()
    except:
        pass

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


def save_pdf(filepath,  # Output?
             source_dir,  # Added - directory with all extracted files
             uuid,  # Added
             vector=True,
             prog_cb=lambda x: (),
             abort_func=lambda: False):
    # Exports the self as a PDF document to disk

    # prog_cb should emit between 0-100 (percent complete).
    # Percentages are split between three processes. Downloading the
    # archive takes the first 50%. If there is not a base PDF, the
    # RM page rasterization takes the next 50%. If there is a base
    # PDF, then the page rasterization takes 25% and the PDF
    # merging takes another 25%.

    # This holds stuff to clean up
    cleanup_stuff = set()

    def cleanup():
        for thing in cleanup_stuff:
            rmdir(thing)

    if abort_func():
        return

    # Load pencil textures (shared for brushes, takes a lot of time
    # because there are many)
    from model.pens.textures import PencilTextures
    pencil_textures = PencilTextures()

    tmpdir = source_dir

    # If this is using a base PDF, the percentage is calculated
    # differently.
    pdfpath = Path(tmpdir / Path(uuid + '.pdf'))
    uses_base_pdf = pdfpath.exists()

    # Document metadata should already be loaded (from device)
    # ...

    # Generate page information
    contentpath = Path(tmpdir / Path(uuid + '.content'))
    contentdict = {}
    if contentpath.exists():
        with open(contentpath, 'r') as f:
            contentdict = json.load(f)
            f.close()
    # If a PDF file was uploaded, but never opened, there may not be
    # a .content file. So, just load a barebones one with a 'pages'
    # key of zero length, so it doesn't break the rest of the
    # process. This is here, instead of in __init__, because it is
    # more explainable/straightforward here.
    if not 'pages' in contentdict:
        contentdict['pages'] = []

    # Render each page as a pdf
    th, tmp = tempfile.mkstemp()
    os.close(th)
    tmprmpdf = Path(tmp)
    cleanup_stuff.add(tmprmpdf)
    pdf = QPrinter()
    res = DISPLAY['dpi']
    width = DISPLAY['screenwidth']
    height = DISPLAY['screenheight']
    pdf.setPaperSize(QSizeF(width / res, height / res), QPrinter.Inch)
    pdf.setResolution(res)
    pdf.setOutputFormat(QPrinter.PdfFormat)
    pdf.setPageMargins(0, 0, 0, 0, QPrinter.Inch)
    pdf.setOutputFileName(str(tmprmpdf))

    # Don't load all the pages into memory, because large notebooks
    # about 500 pages could use up to 3 GB of RAM. Create them by
    # iteration so they get released by garbage collector.
    changed_pages = []
    painter = QPainter(pdf)
    annotations = []
    for i in range(0, len(contentdict['pages'])):
        if abort_func():
            painter.end()
            cleanup()
            return

        page = DocumentPage(contentdict, uuid, i, tmpdir,
                            pencil_textures=pencil_textures)
        if page.rmpath.exists():
            changed_pages.append(i)
        page.render_to_painter(painter, vector)
        annotations.append(page.get_grouped_annotations())
        if i < len(contentdict['pages'])-1:
            pdf.newPage()
        progpct = (i + 1) / len(contentdict['pages']) * 25 + 50
        prog_cb(progpct)
    painter.end()

    if abort_func():
        cleanup()
        return

    # This new PDF represents just the notebook. If there was a
    # parent PDF, merge it now.
    if uses_base_pdf and not changed_pages:
        # Since there is no stroke data, verbatim copy the PDF.
        # pdfpath.rename(filepath)
        shutil.move(pdfpath, filepath)
        prog_cb(100)
        cleanup()

        log.info('exported pdf')
        return

    # PDF exists, stroke data exists, so mix them together.
    if uses_base_pdf:
        rmpdfr = PdfReader(tmprmpdf)
        basepdfr = PdfReader(pdfpath)
    else:
        basepdfr = PdfReader(tmprmpdf)
        # Alias, which is used for annotations and layers.
        rmpdfr = basepdfr

    # If making a 'layered' PDF (with optional content groups,
    # OCGs), associate the annoatations with the layer.

    # This property list is put into the rmpdfr document, which
    # will not have any existing properties.
    ocgprop = IndirectPdfDict(
        OCGs=PdfArray(),
        D=PdfDict(Order=PdfArray()))

    for i in range(0, len(basepdfr.pages)):
        if abort_func():
            cleanup()
            return

        def release_progress():
            # This emits the other 25% of the progress. Only
            # run this method when this page is finished
            # processing.
            progpct = ((i + 1) / rmpdfr.numPages * 25) + 75
            prog_cb(progpct)

        basepage = basepdfr.pages[i]
        rmpage = rmpdfr.pages[i]

        # Apply OCGs
        apply_ocg = False #TODO configurable? bool(int(QSettings().value(
            #'pane/notebooks/export_pdf_ocg')))
        if apply_ocg:
            ocgorderinner = do_apply_ocg(basepage, rmpage, i, uses_base_pdf, ocgprop, annotations)
        else:
            ocgorderinner = None

        # Apply annotations to the rmpage. This must come after
        # applying OCGs, because the annotation may belong to
        # one of those groups.
        apply_annotations(rmpage, annotations[i], ocgorderinner)

        # If this is a normal notebook with highlighting,
        # just add the annotations and forget about the rest,
        # which are page geometry transformations.
        if uses_base_pdf:
            merge_pages(basepage, rmpage, i in changed_pages)

        release_progress()

    # Apply the OCG order. The basepdf may have already had OCGs
    # and so we must not overwrite them. NOTE: there are other
    # properties that ought to be carried over, but this is the
    # minimum required.
    if apply_ocg:
        if '/OCProperties' in basepdfr.Root:
            basepdfr.Root.OCProperties.OCGs += ocgprop.OCGs
            basepdfr.Root.OCProperties.D.Order += ocgprop.D.Order
        else:
            basepdfr.Root.OCProperties = ocgprop

    pdfw = PdfWriter()
    pdfw.write(filepath, basepdfr)
    tmprmpdf.unlink()

    # Cleanup
    cleanup()

    log.info('exported pdf')


def do_apply_ocg(basepage, rmpage, i, uses_base_pdf, ocgprop, annotations):
    ocgpage = IndirectPdfDict(
        Type=PdfName('OCG'),
        Name='Page ' + str(i+1))
    ocgprop.OCGs.append(ocgpage)

    # The Order dict is a Page, followed by Inner
    ocgorderinner = PdfArray()


    # Add Template OCG layer
    # If this uses a basepdf, the template is located
    # elsewhere.


    # If using a basepdf, assign its stream as a
    # 'Background' layer under this page. When the page
    # primary OCG is disabled, the background will
    # remain, making it easy to disable all annotations.
    if uses_base_pdf:
        ocgorigdoc = IndirectPdfDict(
            Type=PdfName('OCG'),
            Name='Background')
        ocgprop.OCGs.append(ocgorigdoc)
        ocgorderinner.append(ocgorigdoc)

        uncompress.uncompress([basepage.Contents])
        stream = basepage.Contents.stream
        stream = '/OC /ocgorigdoc BDC\n' \
            + stream \
            + 'EMC\n'
        basepage.Contents.stream = stream
        compress.compress([basepage.Contents])

        if '/Properties' in basepage.Resources:
            props = basepage.Resources.Properties
        else:
            props = PdfDict()
        props.ocgorigdoc = ocgorigdoc
        basepage.Resources.Properties = props


    # If not using a basepdf, assign the rmpage's stream
    # as a 'Template' layer under this page. It will be
    # affected by disabling the primary Page OCG (which
    # by itself is kind of useless for exported
    # notebooks).

    # Regardless of using a basepdf or not, put the
    # rmpage layers into their own OCGs.

    # If the template has an XObject, we want to skip
    # the first one. This happens when the template
    # contains a PNG. Question--what happens when the
    # template contains more than one PNG? How do we
    # detect all of those?

    template_xobj_keys = []
    vector_layers = []
    uncompress.uncompress([rmpage.Contents])
    if uses_base_pdf:
        # The entire thing is the page ocg
        stream = '/OC /ocgpage BDC\n'
        stream += rmpage.Contents.stream
        stream += 'EMC\n'
        rmpage.Contents.stream = stream
    else:
        stream = rmpage.Contents.stream
        # Mark the template ocg separate from page ocg
        template_endpos = 0
        page_inatpos = 0
        findkey = '1 w 2 J 2 j []0  d\nq\n'
        # Finds only the first instance, which should be
        # for the template.
        findloc = stream.find(findkey)
        if findloc < 0:
            # May be a vector, which we stick a marker
            # in for.
            # ?? Why is this a half-point off ??
            findkey = '799.500000 85 l\n'
            m = re.search(
                findkey,
                rmpage.Contents.stream)
            if m:
                findloc = m.start()
        if findloc > 0:
            template_endpos = findloc + len(findkey)
            # Add vector template OCG
            stream = '/OC /ocgtemplate BDC\n'
            stream += rmpage.Contents.stream[:template_endpos]
            stream += 'EMC\n'
            page_inatpos = len(stream)
            stream += rmpage.Contents.stream[template_endpos:]
            # Save stream
            rmpage.Contents.stream = stream

        # Add template ocg
        ocgtemplate = IndirectPdfDict(
            Type=PdfName('OCG'),
            Name='Template')
        ocgprop.OCGs.append(ocgtemplate)
        ocgorderinner.append(ocgtemplate)

        # If a template (which is SVG) has embedded PNG
        # images, those appear as XObjects. This will
        # mess up the layer order, so we will ignore
        # them later.
        template_xobj_keys = \
            re.findall('(\/Im[0-9]+)\s',
                        stream[:template_endpos])

        # Page ocg
        stream = rmpage.Contents.stream[:page_inatpos]
        stream += '/OC /ocgpage BDC\n'
        stream += rmpage.Contents.stream[page_inatpos:]
        stream += 'EMC\n'
        # Save stream
        rmpage.Contents.stream = stream

    # Find all other vector layers using the magic
    # point (DocumentPageLayer.render_to_painter()).
    # ?? Why is this a half-point off ??
    while True:
        m = re.search(
            '420.500000 69 m\n',
            rmpage.Contents.stream)
        if not m:
            break
        stream = ''
        layerid = 'ocglayer{}'.format(
            len(vector_layers) + 1)
        stream = rmpage.Contents.stream[:m.start()]
        if len(vector_layers):
            # close previous layer
            stream += 'EMC\n'
        stream += '/OC /{} BDC\n'.format(layerid)
        stream += rmpage.Contents.stream[m.end():]
        vector_layers.append(layerid)
        rmpage.Contents.stream = stream
    # If we added vector layers, have to end the
    # first one.
    if len(vector_layers):
        stream = rmpage.Contents.stream + 'EMC\n'
        rmpage.Contents.stream = stream

    # Done--recompress the stream.
    compress.compress([rmpage.Contents])

    # There shouldn't be any Properties there since we
    # generated the rmpage ourselves, so don't bother
    # checking.
    rmpage.Resources.Properties = PdfDict(
        ocgpage=ocgpage)
    if not uses_base_pdf:
        rmpage.Resources.Properties.ocgtemplate = ocgtemplate

    # Add individual OCG layers (Bitmap)
    was_vector = True
    for n, key in enumerate(rmpage.Resources.XObject):
        if str(key) in template_xobj_keys:
            continue
        was_vector = False
        l = n - len(template_xobj_keys)
        # This would indicate a bug in the handling of a
        # notebook.
        try:
            layer = annotations[i][l]
        except:
            log.error('could not associate XObject with layer: (i, l) ({}, {})'.format(i, l))
            log.error(str(annotations))
            log.error('document: {} ()').format(
                uuid,
                'self.visible_name')
            continue
        layername = layer[0]
        ocg = IndirectPdfDict(
            Type=PdfName('OCG'),
            Name=layername)
        ocgprop.OCGs.append(ocg)
        ocgorderinner.append(ocg)
        rmpage.Resources.XObject[key].OC = ocg

    # Add individual OCG layers (Vector)
    if was_vector:
        for l, layerid in enumerate(vector_layers):
            # This would indicate a bug in the handling of a
            # notebook.
            try:
                layer = annotations[i][l]
            except:
                log.error('could not associate layerid with layer: (i, l, layerid) ({}, {}, {})'.format(i, l, layerid))
                log.error('document: {} ()').format(
                    uuid,
                    'self.visible_name')
                log.error(str(annotations))
                continue
            layername = layer[0]
            ocg = IndirectPdfDict(
                Type=PdfName('OCG'),
                Name=layername)
            ocgprop.OCGs.append(ocg)
            ocgorderinner.append(ocg)
            rmpage.Resources.Properties[PdfName(layerid)] = \
                ocg

    # Add order of OCGs to primary document
    ocgprop.D.Order.append(ocgpage)
    ocgprop.D.Order.append(ocgorderinner)

    return ocgorderinner


def apply_annotations(rmpage, page_annot, ocgorderinner):
    for k, layer_a in enumerate(page_annot):
        layerannots = layer_a[1]
        for a in layerannots:
            # PDF origin is in bottom-left, so invert all
            # y-coordinates.
            author = 'RCU' #self.model.device_info['rcuname']
            pdf_a = PdfDict(Type=PdfName('Annot'),
                            Rect=PdfArray([
                                (a[1] * PTPERPX),
                                PDFHEIGHT - (a[2] * PTPERPX),
                                (a[3] * PTPERPX),
                                PDFHEIGHT - (a[4] * PTPERPX)]),
                            T=author,
                            ANN='pdfmark',
                            Subtype=PdfName(a[0]),
                            P=rmpage)
            # Set to indirect because it makes a cleaner PDF
            # output.
            pdf_a.indirect = True
            if ocgorderinner:
                pdf_a.OC = ocgorderinner[k]
            if not '/Annots' in rmpage:
                rmpage.Annots = PdfArray()
            rmpage.Annots.append(pdf_a)


def merge_pages(basepage, rmpage, changed_page):
    # The general appraoch is to keep the base PDF. So, all
    # operations must be made upon the basepage. PyPDF2 will
    # keep all those pages' metadata and annotations,
    # including the paper size. However, a few things must
    # also occur.

    # The basepage must be reisized to the ratio of the rM
    # page so that no brush strokes get cut.

    # The new (rM) page must be resized to the dimensions of
    # the basepage. The PDF standard allows different page
    # sizes in one document, so each page must be measured.

    # ...

    # There is a bug here that can be seen with the NH file
    # It is possible (why?) for a page not to have a
    # MediaBox, so one must be taken from the parent. The
    # rM adds a bit to the width AND the height on this
    # file.
    bpage_box = basepage.MediaBox
    if not bpage_box:
        # Should probably check if the parent has a mediabox
        bpage_box = basepage.Parent.MediaBox
    bpage_w = float(bpage_box[2]) - float(bpage_box[0])
    bpage_h = float(bpage_box[3]) - float(bpage_box[1])
    # Round because floating point makes it prissy
    bpage_ratio = round(bpage_w / bpage_h * 10000) / 10000
    landscape_bpage = False
    if bpage_w > bpage_h:
        landscape_bpage = True

    # If the base PDF page was really wide, the rM rotates
    # it -90deg (CCW) on the screen, but doesn't actually
    # rotate it in the PDF. Also, if a notebook is in
    # landscape format, it remains in portrait mode during
    # the Web UI export. So, we must actually rotate the rM
    # page 90deg (CW) to fit on these wide pages.

    rpage_box = rmpage.MediaBox
    rpage_w = float(rpage_box[2]) - float(rpage_box[0])
    rpage_h = float(rpage_box[3]) - float(rpage_box[1])
    rpage_ratio = rpage_w / rpage_h
    if landscape_bpage:
        rmpage.Rotate = 90
        rpage_ratio = rpage_h / rpage_w

        # Annotations must be rotated because this rotation
        # statement won't hit until the page merge, and
        # pdfrw is unaware of annotations.
        if '/Annots' in rmpage:
            for a, annot in enumerate(rmpage.Annots):
                rect = annot.Rect
                rmpage.Annots[a].Rect = PdfArray([
                    rect[1],
                    PDFWIDTH - rect[0],
                    rect[3],
                    PDFWIDTH - rect[2]])


    # Resize the base page to the notebook page ratio by
    # adjusting the trimBox. If the basepage was landscape,
    # the trimbox must expand laterally, because the rM
    # rotates the page on-screen into portrait. If the
    # basepage was already portrait, it must expand
    # laterally.

    adjust = 0
    if bpage_ratio <= rpage_ratio:
        # Basepage is taller, so need to expand the width.
        # The basepage should be pushed to the right, which
        # is also the top of the rM in portrait mode. A
        # push to the right is really just decreasing the
        # left side.
        new_width = rpage_ratio * bpage_h
        if landscape_bpage:
            adjust = float(bpage_box[2]) - new_width
            bpage_box[0] = adjust
        else:
            # Portrait documents get pushed to the left, so
            # expand the right side.
            adjust = float(bpage_box[0])
            bpage_box[2] = new_width + float(bpage_box[0])
    elif bpage_ratio > rpage_ratio:
        # Basepage is fatter, so need to expand the height.
        # The basepage should be pushed to the top, which is
        # also the top of the rM in portrait mode. A push to
        # the top is really decreasing the bottom side.
        new_height = (1 / rpage_ratio) * bpage_w
        adjust = float(bpage_box[3]) - new_height
        bpage_box[1] = adjust

    # If this wasn't a changed page, don't bother with the
    # following.
    if not changed_page:
        return

    # Scale and (if necesssary) rotate the notebook page
    # and overlay it to the basepage. Might have to push
    # it a bit, depending on the direction.
    #basepage.Rotate = -90
    np = PageMerge(basepage).add(rmpage)

    annot_adjust = [0, 0]

    if bpage_ratio <= rpage_ratio:
        scale = bpage_h / np[1].h
        np[1].scale(scale)
        np[1].x = adjust
        annot_adjust[0] = adjust
    elif bpage_ratio > rpage_ratio:
        scale = bpage_w / np[1].w
        np[1].scale(scale)
        np[1].y = adjust
        annot_adjust[1] = adjust

    if '/Annots' in rmpage:
        for a, annot in enumerate(rmpage.Annots):
            rect = annot.Rect
            newrect = PdfArray([
                rect[0] * scale + annot_adjust[0],
                rect[1] * scale + annot_adjust[1],
                rect[2] * scale + annot_adjust[0],
                rect[3] * scale + annot_adjust[1]])
            rmpage.Annots[a].Rect = newrect

    # Gives the basepage the rmpage as a new object
    np.render()

    # Annots aren't carried over--pdfrw isn't aware.
    if '/Annots' in rmpage:
        if not '/Annots' in basepage:
            basepage.Annots = PdfArray()
        basepage.Annots += rmpage.Annots


class DocumentPage:
    # A single page in a document
    # From local disk!! When making agnostic later, only keep the
    # document and pagenum args.
    def __init__(self,
                 #document,
                 doc_contentdict,  # Added
                 doc_uuid,  # Added
                 pagenum,
                 archivepath,
                 #displaydict,
                 pencil_textures=None):
        # Page 0 is the first page!
        #self.document = document
        self.num = pagenum
        #self.display = displaydict  # Carried from model, but not used?
        self.pencil_textures = pencil_textures

        # get page id
        self.uuid = str(pagenum) #??? doc_contentdict['pages'][pagenum]

        self.rmpath = Path(
            archivepath / \
            Path(doc_uuid) / Path(self.uuid + '.rm'))

        # Try to load page metadata
        self.metadict = None
        self.metafilepath = Path(
            archivepath / Path(doc_uuid) / \
            Path(self.uuid + '-metadata.json'))
        if self.metafilepath.exists():
            with open(self.metafilepath, 'r') as f:
                self.metadict = json.load(f)
                f.close()

        # Try to load template
        self.template = None
        tmpnamearray = []
        pagedatapath = Path(
            archivepath / Path(doc_uuid + '.pagedata'))
        if pagedatapath.exists():
            f = open(pagedatapath, 'r')
            lines = f.read()
            for line in lines.splitlines():
                tmpnamearray.append(line)
            f.close()

        '''if len(tmpnamearray):
            # I have encountered an issue with some PDF files, where the
            # rM won't save the page template for later pages. In this
            # case, just take the last-available page template, which
            # is usually 'Blank'.
            tmpname = tmpnamearray[-1]
            if self.num < len(tmpnamearray):
                tmpname = tmpnamearray[self.num]
            tmparchivepath = Path(
                    archivepath / Path(tmpname + '.rmt'))
            if tmparchivepath.exists():
                self.template = Template(
                    self.document.model).from_archive(tmparchivepath)'''

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

        if not self.rmpath.exists():
            # no layers, obv
            return

        # Load reMy version of page layers
        pagever = None
        pagelayers = None
        with open(self.rmpath, 'rb') as f:
            pagever, pagelayers = lines.readLines(f)
            f.close()

        # Load layer data
        for i in range(0, len(pagelayers)):
            layerstrokes = pagelayers[i]

            try:
                name = self.metadict['layers'][i]['name']
            except:
                name = 'Layer ' + str(i + 1)

            layer = DocumentPageLayer(self,
                                      name=name,
                                      pencil_textures=self.pencil_textures)
            layer.strokes = layerstrokes
            self.layers.append(layer)

    def render_to_painter(self, painter, vector):
        # Render template layer
        if self.template and self.template.name != 'Blank':
            svgtools.template_to_painter(painter, self.template)
            # Bitmaps are rendered into the PDF as XObjects, which are
            # easy to pick out for layers. Vectors will render
            # everything inline, and so we need to add a 'magic point'
            # to mark the end of the template layer.
            if vector:
                pen = GenericPen(vector=vector)
                pen.setColor(Qt.transparent)
                painter.setPen(pen)
                painter.drawPoint(800, 85)

        # Render user layers
        for i, layer in enumerate(self.layers):
            # Bitmaps are rendered into the PDF as XObjects, which are
            # easy to pick out for layers. Vectors will render
            # everything inline, and so we need to add a 'magic point'
            # to mark the beginning of layers.
            if vector:
                pen = GenericPen(vector=vector)
                pen.setColor(Qt.transparent)
                painter.setPen(pen)
                painter.drawPoint(420, 69)
            layer.render_to_painter(painter, vector)


from model.pens import *
class DocumentPageLayer:
    pen_widths = []

    def __init__(self, page, name=None, pencil_textures=None):
        self.page = page
        self.name = name
        self.pencil_textures = pencil_textures

        self.colors = [
            #QSettings().value('pane/notebooks/export_pdf_blackink'),
            #QSettings().value('pane/notebooks/export_pdf_grayink'),
            #QSettings().value('pane/notebooks/export_pdf_whiteink')
            QColor(0, 0, 0),
            QColor(128, 128, 128),
            QColor(255, 255, 255)
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

    def paint_strokes(self, painter, vector):
        # These pen codes probably refer to different versions through
        # various system software updates. We'll just render them all
        # the same (across all versions).
        pen_lookup = [
            PaintbrushPen,       # Brush
            PencilPen,           # Pencil
            BallpointPen,        # Ballpoint
            MarkerPen,           # Marker
            FinelinerPen,        # Fineliner
            HighlighterPen,      # Highlighter
            EraserPen,           # Eraser
            MechanicalPencilPen, # Mechanical Pencil
            EraseAreaPen,        # Erase Area
            None,                # unknown
            None,                # unknown
            None,                # unknown
            PaintbrushPen,       # Brush
            MechanicalPencilPen, # Mechanical Pencil
            PencilPen,           # Pencil
            BallpointPen,        # Ballpoint
            MarkerPen,           # Marker
            FinelinerPen,        # Fineliner
            HighlighterPen,      # Highlighter
            EraserPen,           # Eraser
            None,                # unknown
            CalligraphyPen       # Calligraphy
        ]

        for stroke in self.strokes:
            pen, color, unk1, width, unk2, segments = stroke

            qpen = None

            try:
                penclass = pen_lookup[pen]
                assert penclass != None
            except:
                log.error("Unknown pen code %d" % pen)
                penclass = GenericPen

            qpen = penclass(pencil_textures=self.pencil_textures,
                            vector=vector,
                            layer=self)
            qpen.setColor(self.colors[color])

            # Do the needful
            qpen.paint_stroke(painter, stroke)

    def render_to_painter(self, painter, vector):
        if vector: # Turn this on with vector otherwise off to get hybrid
            self.paint_strokes(painter, vector=vector)
            return

        # I was having problems with QImage corruption (garbage data)
        # and memory leaking on large notebooks. I fixed this by giving
        # the QImage a reference array to pre-allocate RAM, then reset
        # the reference count after I'm done with it, so that it gets
        # cleaned up by the python garbage collector.

        image_ref = QByteArray()
        devpx = DISPLAY['screenwidth'] \
            * DISPLAY['screenheight']
        bytepp = 4  # ARGB32
        image_ref.fill('\0', devpx * bytepp)
        qimage = QImage(b'\0' * devpx * bytepp,
                        DISPLAY['screenwidth'],
                        DISPLAY['screenheight'],
                        QImage.Format_ARGB32)

        # This is a fix for a bug that still exists in PySide2
        # https://github.com/matplotlib/matplotlib/issues/4283#issuecomment-95950441
        import ctypes
        ctypes.c_long.from_address(id(image_ref)).value=1

        imgpainter = QPainter(qimage)
        imgpainter.setRenderHint(QPainter.Antialiasing)
        #imgpainter.setRenderHint(QPainter.LosslessImageRendering)
        self.paint_strokes(imgpainter, vector=vector)
        imgpainter.end()

        painter.drawImage(0, 0, qimage)

        del imgpainter
        del qimage
        del image_ref
        gc.collect()


from PySide2 import QtCore

if __name__ == '__main__':
    import sys
    app = QtCore.QCoreApplication(sys.argv)
    # Demo
    save_pdf('testing/output-vector.pdf', 'testing/samples', 'cb736ad2-b869-4253-979a-dbc5c01a9000', True, lambda x: print(x))
    # PDF
    save_pdf('testing/output-pdf-vector.pdf', 'testing/samples', '67917ebb-3664-4a7c-b243-6db4e10190b2', True, lambda x: print(x))
