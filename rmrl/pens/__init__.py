from .generic import GenericPen
from .pencil import PencilPen
from .mechanicalpencil import MechanicalPencilPen
from .paintbrush import PaintbrushPen
from .ballpoint import BallpointPen
from .marker import MarkerPen
from .fineliner import FinelinerPen
from .highlighter import HighlighterPen
from .eraser import EraserPen
from .calligraphy import CalligraphyPen

# These pen codes probably refer to different versions through
# various system software updates. We'll just render them all
# the same (across all versions).
PEN_MAPPING = dict(enumerate([
    PaintbrushPen,       # Brush
    PencilPen,           # Pencil
    BallpointPen,        # Ballpoint
    MarkerPen,           # Marker
    FinelinerPen,        # Fineliner
    HighlighterPen,      # Highlighter
    EraserPen,           # Eraser
    MechanicalPencilPen, # Mechanical Pencil
    EraserPen,           # Erase Area
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
]))
