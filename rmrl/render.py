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

import logging
import tempfile
from pathlib import Path
import json
import re

from pdfrw import PdfReader, PdfWriter, PageMerge, PdfDict, PdfArray, PdfName, \
    IndirectPdfDict, uncompress, compress

from reportlab.pdfgen import canvas

from . import document, sources
from .constants import PDFHEIGHT, PDFWIDTH, PTPERPX, SPOOL_MAX


log = logging.getLogger(__name__)

def render(source, *, progress_cb=lambda x: None):
    # Exports the self as a PDF document to disk

    # progress_cb will be called with a progress percentage between 0 and
    # 100.  This percentage calculation is split 50% for the rendering
    # of the lines and 50% merging with the base PDF file.  This callback
    # also provides an opportunity to abort the process. If the callback
    # raises an error, this function will take steps to abort gracefullly
    # and pass the error upwards.

    vector=True  # TODO: Different rendering styles
    source = sources.get_source(source)

    # If this is using a base PDF, the percentage is calculated
    # differently.
    uses_base_pdf = source.exists('{ID}.pdf')

    # Document metadata should already be loaded (from device)
    # ...

    # Generate page information
    # If a PDF file was uploaded, but never opened, there may not be
    # a .content file. So, just load a barebones one with a 'pages'
    # key of zero length, so it doesn't break the rest of the
    # process.
    pages = []
    if source.exists('{ID}.content'):
        with source.open('{ID}.content', 'r') as f:
            pages = json.load(f).get('pages', [])

    # Render each page as a pdf
    tmpfh = tempfile.TemporaryFile()
    pdf_canvas = canvas.Canvas(tmpfh, (PDFWIDTH, PDFHEIGHT))
    # TODO: check pageCompression

    # Don't load all the pages into memory, because large notebooks
    # about 500 pages could use up to 3 GB of RAM. Create them by
    # iteration so they get released by garbage collector.
    changed_pages = []
    annotations = []
    for i in range(0, len(pages)):
        page = document.DocumentPage(source, pages[i], i)
        if source.exists(page.rmpath):
            changed_pages.append(i)
        page.render_to_painter(pdf_canvas, vector)
        annotations.append(page.get_grouped_annotations())
        progress_cb((i + 1) / len(pages) * 50)
    pdf_canvas.save()
    tmpfh.seek(0)

    # This new PDF represents just the notebook. If there was a
    # parent PDF, merge it now.
    if uses_base_pdf and not changed_pages:
        # Since there is no stroke data, just return the PDF data
        progress_cb(100)

        log.info('exported pdf')
        return source.open('{ID}.pdf', 'rb')

    # PDF exists, stroke data exists, so mix them together.
    if uses_base_pdf:
        rmpdfr = PdfReader(tmpfh)
        basepdfr = PdfReader(source.open('{ID}.pdf', 'rb'))
    else:
        basepdfr = PdfReader(tmpfh)
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

        progress_cb(((i + 1) / rmpdfr.numPages * 50) + 50)

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
    stream = tempfile.SpooledTemporaryFile(SPOOL_MAX)
    pdfw.write(stream, basepdfr)
    stream.seek(0)

    log.info('exported pdf')
    return stream


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
            re.findall(r'(\/Im[0-9]+)\s',
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
                'uuid',
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
                    'uuid',
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
