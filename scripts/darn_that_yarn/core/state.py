from dataclasses import dataclass, field
from typing import Dict, Optional, Set


@dataclass
class StitchToolState:
    selected_mesh: Optional[str] = None
    course_edges: Set[str] = field(default_factory=set)
    wale_edges: Set[str] = field(default_factory=set)
    active_faces: Set[str] = field(default_factory=set)
    face_stitch_types: Dict[str, str] = field(default_factory=dict)
    row_directions: Dict[str, int] = field(default_factory=dict)  # row_id -> 1 or -1
    tessellation_level: int = 1
    mesh_relaxation_enabled: bool = True
    yarn_relaxation_enabled: bool = True
    preview_mesh: Optional[str] = None
    original_mesh_snapshot: Optional[str] = None
    is_tessellated: bool = False
    face_stitch_map = {}
    edge_map = {}
    base_mesh = None
    t_face_stitch_map = {}
    t_edge_map = {}
    t_mesh = None
    smoothed_mesh: Optional[str] = None

    def reset(self):
        self.course_edges.clear()
        self.wale_edges.clear()
        self.active_faces.clear()
        self.face_stitch_types.clear()
        self.row_directions.clear()
        self.tessellation_level = 1
        self.mesh_relaxation_enabled = True
        self.yarn_relaxation_enabled = True
        self.preview_mesh = None
        self.original_mesh_snapshot = None
        self.is_tessellated = False
        self.face_stitch_map = {}
        self.edge_map = {}


STATE = StitchToolState()