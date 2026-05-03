import os
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Set

curr_dir = os.path.dirname(os.path.abspath(__file__))
texture_path = os.path.join(curr_dir, "jersey_melange_diff_1k.jpg")
texture_path = texture_path.replace("\\", "/")

@dataclass
class StitchToolState:
    selected_mesh: Optional[str] = None
    course_edges: Set[str] = field(default_factory=set)
    wale_edges: Set[str] = field(default_factory=set)
    active_faces: Set[str] = field(default_factory=set)
    face_stitch_types: Dict[str, str] = field(default_factory=dict)
    row_directions: Dict[str, int] = field(default_factory=dict)  # row_id -> 1 or -1
    tessellation_level: int = 1
    selected_pattern: str = "checker"
    yarn_radius: float = 0.02
    mesh_relaxation_enabled: bool = True
    yarn_relaxation_enabled: bool = True
    preview_mesh: Optional[str] = None
    preview_mesh_relaxed: bool = False
    original_mesh_snapshot: Optional[str] = None
    is_tessellated: bool = False
    face_stitch_map: Dict[int, Any] = field(default_factory=dict)
    edge_map: Dict[int, Any] = field(default_factory=dict)
    base_mesh: Optional[str] = None
    t_face_stitch_map: Dict[int, Any] = field(default_factory=dict)
    t_edge_map: Dict[int, Any] = field(default_factory=dict)
    t_mesh: Optional[str] = None
    smoothed_mesh: Optional[str] = None
    yarn_texture_path: str =  texture_path
    yarn_material: Optional[str] = None
    yarn_mesh: Optional[str] = None
    yarn_uvs_clean: bool = False

    def reset(self):
        self.selected_mesh = None
        self.course_edges.clear()
        self.wale_edges.clear()
        self.active_faces.clear()
        self.face_stitch_types.clear()
        self.row_directions.clear()
        self.tessellation_level = 1
        self.selected_pattern = "checker"
        self.yarn_radius = 0.02
        self.mesh_relaxation_enabled = True
        self.yarn_relaxation_enabled = True
        self.preview_mesh = None
        self.preview_mesh_relaxed = False
        self.original_mesh_snapshot = None
        self.is_tessellated = False
        self.face_stitch_map.clear()
        self.edge_map.clear()
        self.base_mesh = None
        self.t_face_stitch_map.clear()
        self.t_edge_map.clear()
        self.t_mesh = None
        self.smoothed_mesh = None
        self.yarn_texture_path = None
        self.yarn_material: Optional[str] = None
        self.yarn_mesh: Optional[str] = None
        self.yarn_uvs_clean: bool = False


STATE = StitchToolState()
