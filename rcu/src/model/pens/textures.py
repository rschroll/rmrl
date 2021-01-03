from PySide2.QtCore import Qt
from PySide2.QtGui import QPen, QBrush, QImage, QBitmap
from pathlib import Path

class PencilTextures:
    def __init__(self):
        # Load textures
        self.textures_linear_pencil = []
        texpath = Path(__file__).parent / Path('pencil_textures_linear')
        texpaths = sorted(texpath.glob('*.ppm'))
        for p in texpaths:
            name = p.stem
            img = QImage()
            img.load(str(p))
            bm = QBitmap().fromImage(img)
            index = int(float(name) * 100)
            self.textures_linear_pencil.append(bm)

        self.textures_log_pencil = []
        texpath = Path(__file__).parent / Path('pencil_textures_log')
        texpaths = sorted(texpath.glob('*.ppm'))
        for p in texpaths:
            name = p.stem
            img = QImage()
            img.load(str(p))
            bm = QBitmap().fromImage(img)
            index = int(float(name) * 100)
            # self.textures_log[index] = bm
            self.textures_log_pencil.append(bm)

        self.textures_log_paintbrush = []
        texpath = Path(__file__).parent / Path('paintbrush_textures_log')
        texpaths = sorted(texpath.glob('*.ppm'))
        for p in texpaths:
            name = p.stem
            img = QImage()
            img.load(str(p))
            bm = QBitmap().fromImage(img)
            index = int(float(name) * 100)
            # self.textures_log[index] = bm
            self.textures_log_paintbrush.append(bm)
            
    def get_linear(self, val):
        scale = len(self.textures_linear_pencil)
        i = int(val * scale)
        if i < 0:
            i = 0
        if i >= scale:
            i = scale - 1
        return self.textures_linear_pencil[i]

    def get_log(self, val):
        scale = len(self.textures_log_pencil)
        # These values were reached by trial-and-error.
        if val < 0:
            val = 0
        i = int(0.25 * (val * scale)**1.21)
        if i < 0:
            i = 0
        if i >= scale:
            i = scale - 1
        return self.textures_log_pencil[i]

    def get_log_paintbrush(self, val):
        scale = len(self.textures_log_paintbrush)
        if val < 0:
            val = 0
        i = int(0.25 * (val * scale)**1.21)
        if i < 0:
            i = 0
        if i >= scale:
            i = scale - 1
        return self.textures_log_paintbrush[i]

