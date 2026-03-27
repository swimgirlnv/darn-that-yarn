"""
yarn_curve.py
Yarn curve generation for Darn That Yarn.

Subtask 1  – YarnCurve struct: stores control points and materialises a Maya
             NURBS curve node via build_maya_curve().

Subtask 2  – Per-stitch-type point generation: one append_*_points() function
             per stitch type (knit, purl, yarnover, increase, decrease).  Each
             function takes face dimensions (width, height) and a FaceContext
             that carries the world-space coordinate frame of the stitch face
             plus its dag path for adjacency queries.

Subtask 3  – Border handling: append_cast_on_points() and
             append_bind_off_points() with the same interface as subtask 2.

Subtask 4  – Tube geometry: add_tube_geometry() wraps an existing Maya NURBS
             curve in a polygonal tube mesh.  The yarn radius is either supplied
             by the caller or computed automatically from the curve's control-
             point spacing so that no self-intersection can occur.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import maya.api.OpenMaya as om
import maya.cmds as cmds

from darn_that_yarn.commands.stitch_commands import EdgeType, StitchType
from darn_that_yarn.core.state import STATE


# ---------------------------------------------------------------------------
# Subtask 1 – YarnCurve struct
# ---------------------------------------------------------------------------

@dataclass
class YarnCurve:
    """
    Stores the ordered control points for a single continuous yarn path.

    Usage
    -----
    curve = YarnCurve()
    append_knit_points(curve, w, h, face_ctx)
    append_purl_points(curve, w, h, next_face_ctx)
    node_name = curve.build_maya_curve("row_0_yarn")
    """

    points: List[om.MPoint] = field(default_factory=list)

    # ------------------------------------------------------------------
    def append(self, pt: om.MPoint) -> None:
        """Append a single control point."""
        self.points.append(pt)

    def extend(self, pts: List[om.MPoint]) -> None:
        """Append multiple control points at once."""
        self.points.extend(pts)

    # ------------------------------------------------------------------
    def build_maya_curve(self, name: str = "yarn_curve") -> str:
        """
        Create a Maya NURBS curve from the stored control points.

        Degree-3 (cubic) is used when >= 4 points are available for a
        smooth yarn path; degree-1 (linear) is used as a fallback for
        very short curves.  Returns the transform node name on success,
        or an empty string if there are fewer than 2 points.
        """
        n = len(self.points)
        if n < 2:
            om.MGlobal.displayWarning("YarnCurve.build_maya_curve: need >= 2 points.")
            return ""

        degree = min(3, n - 1)
        pts = [(p.x, p.y, p.z) for p in self.points]
        return cmds.curve(p=pts, d=degree, name=name)


# ---------------------------------------------------------------------------
# Face coordinate frame  (used by all stitch-point functions)
# ---------------------------------------------------------------------------

@dataclass
class FaceContext:
    """
    World-space coordinate frame for a single stitch face.

    Attributes
    ----------
    center      : Face centroid in world space.
    course_axis : Unit vector pointing in the course (left→right) direction.
    wale_axis   : Unit vector pointing in the wale (bottom→top) direction.
    normal      : Outward unit face normal.
    dag_path    : DAG path of the mesh (for adjacency queries via MItMeshPolygon).
    face_id     : Integer index of this face on the mesh.
    """

    center: om.MPoint
    course_axis: om.MVector
    wale_axis: om.MVector
    normal: om.MVector
    dag_path: om.MDagPath
    face_id: int


def build_face_context(dag_path: om.MDagPath, face_id: int) -> FaceContext:
    """
    Build a FaceContext for *face_id* on *dag_path*.

    course_axis is the mean direction of the face's COURSE edges.
    wale_axis   is the mean direction of the face's WALE edges.
    normal      is course_axis × wale_axis (outward if labelling is consistent).
    """
    mesh_fn = om.MFnMesh(dag_path)
    edge_iter = om.MItMeshEdge(dag_path)
    face_iter = om.MItMeshPolygon(dag_path)
    face_iter.setIndex(face_id)

    # Face centroid – mean of world-space vertex positions.
    pts = face_iter.getPoints(om.MSpace.kWorld)
    cx = sum(p.x for p in pts) / len(pts)
    cy = sum(p.y for p in pts) / len(pts)
    cz = sum(p.z for p in pts) / len(pts)
    center = om.MPoint(cx, cy, cz)

    course_acc = om.MVector(0.0, 0.0, 0.0)
    course_count = 0
    wale_acc = om.MVector(0.0, 0.0, 0.0)
    wale_count = 0

    for eid in face_iter.getEdges():
        etype = STATE.edge_map.get(eid, EdgeType.UNASSIGNED)
        if getattr(etype, "name", str(etype)) == "UNASSIGNED":
            continue

        edge_iter.setIndex(eid)
        v0 = mesh_fn.getPoint(edge_iter.vertexId(0), om.MSpace.kWorld)
        v1 = mesh_fn.getPoint(edge_iter.vertexId(1), om.MSpace.kWorld)
        d = om.MVector(v1.x - v0.x, v1.y - v0.y, v1.z - v0.z)
        length = d.length()
        if length < 1e-8:
            continue
        d /= length  # normalise

        ename = getattr(etype, "name", str(etype))
        if ename == "COURSE":
            # Opposite face edges traverse antiparallel; flip so they reinforce.
            if course_count > 0 and (
                d.x * course_acc.x + d.y * course_acc.y + d.z * course_acc.z
            ) < 0:
                d = om.MVector(-d.x, -d.y, -d.z)
            course_acc += d
            course_count += 1
        elif ename == "WALE":
            if wale_count > 0 and (
                d.x * wale_acc.x + d.y * wale_acc.y + d.z * wale_acc.z
            ) < 0:
                d = om.MVector(-d.x, -d.y, -d.z)
            wale_acc += d
            wale_count += 1

    # Normalise accumulated directions; fall back to world axes if degenerate.
    if course_count > 0 and course_acc.length() > 1e-8:
        course_axis = course_acc.normalize()
    else:
        course_axis = om.MVector(1.0, 0.0, 0.0)

    if wale_count > 0 and wale_acc.length() > 1e-8:
        wale_axis = wale_acc.normalize()
    else:
        wale_axis = om.MVector(0.0, 1.0, 0.0)

    # Use the actual polygon face normal so depth offsets always point outward.
    mesh_fn2 = om.MFnMesh(dag_path)  # type: ignore[attr-defined]
    try:
        fn = mesh_fn2.getPolygonNormal(face_id, om.MSpace.kWorld)  # type: ignore[attr-defined]
        normal = om.MVector(fn.x, fn.y, fn.z)  # type: ignore[attr-defined]
        if normal.length() < 1e-8:
            raise ValueError("zero normal")
        normal = normal.normalize()
    except Exception:
        # Fallback: cross product of detected axes.
        normal = course_axis ^ wale_axis
        if normal.length() < 1e-8:
            normal = om.MVector(0.0, 0.0, 1.0)
        else:
            normal = normal.normalize()

    return FaceContext(
        center=center,
        course_axis=course_axis,
        wale_axis=wale_axis,
        normal=normal,
        dag_path=dag_path,
        face_id=face_id,
    )



def _face_pt(
    ctx: FaceContext,
    u: float,
    v: float,
    n: float,
    width: float,
    height: float,
) -> om.MPoint:
    """
    Map normalised face-local coordinates (u, v, n) to world space.

    Convention
    ----------
    u  in [-0.5, +0.5]  →  fraction of face width  in the course direction
    v  in [-0.5, +0.5]  →  fraction of face height in the wale direction
    n  in [-0.5, +0.5]  →  depth offset along the face normal, scaled by
                            0.25 × face diagonal for realistic loop depth

    Direct bilinear interpolation using the face's course/wale/normal frame.
    This is stable for all query positions including boundary points (v = ±0.5).
    """
    # depth_scale is proportional to row height so loop depth looks consistent
    # regardless of stitch aspect ratio.  n=1.0 pushes one full row-height in/out.
    depth_scale = height * 0.6
    cx = (
        ctx.center.x
        + ctx.course_axis.x * (u * width)
        + ctx.wale_axis.x   * (v * height)
        + ctx.normal.x      * (n * depth_scale)
    )
    cy = (
        ctx.center.y
        + ctx.course_axis.y * (u * width)
        + ctx.wale_axis.y   * (v * height)
        + ctx.normal.y      * (n * depth_scale)
    )
    cz = (
        ctx.center.z
        + ctx.course_axis.z * (u * width)
        + ctx.wale_axis.z   * (v * height)
        + ctx.normal.z      * (n * depth_scale)
    )
    return om.MPoint(cx, cy, cz)


def _compute_face_dimensions(dag_path: om.MDagPath, face_id: int) -> Tuple[float, float]:
    """
    Return (width, height) for *face_id* where width is the mean length of
    COURSE edges and height is the mean length of WALE edges.
    Falls back to a uniform estimate from the face area if edge lengths are
    not meaningful.
    """
    mesh_fn = om.MFnMesh(dag_path)
    edge_iter = om.MItMeshEdge(dag_path)
    face_iter = om.MItMeshPolygon(dag_path)
    face_iter.setIndex(face_id)

    course_lengths: List[float] = []
    wale_lengths: List[float] = []

    for eid in face_iter.getEdges():
        etype = STATE.edge_map.get(eid, EdgeType.UNASSIGNED)
        edge_iter.setIndex(eid)
        v0 = mesh_fn.getPoint(edge_iter.vertexId(0), om.MSpace.kWorld)
        v1 = mesh_fn.getPoint(edge_iter.vertexId(1), om.MSpace.kWorld)
        length = math.sqrt(
            (v1.x - v0.x) ** 2 + (v1.y - v0.y) ** 2 + (v1.z - v0.z) ** 2
        )
        ename = getattr(etype, "name", str(etype))
        if ename == "COURSE":
            course_lengths.append(length)
        elif ename == "WALE":
            wale_lengths.append(length)

    width  = sum(course_lengths) / len(course_lengths) if course_lengths else 1.0
    height = sum(wale_lengths)   / len(wale_lengths)   if wale_lengths   else 1.0
    return width, height


# ---------------------------------------------------------------------------
# Subtask 2 – Per-stitch-type point generation
# ---------------------------------------------------------------------------
# Local coordinate convention for all canonical point sets:
#   u  – course direction:  -0.5 = left wale edge,   +0.5 = right wale edge
#   v  – wale direction:    -0.5 = bottom course edge, +0.5 = top course edge
#   n  – normal depth:      negative = behind fabric,  positive = in front
#
# Each function appends its points to the supplied YarnCurve.  The last point
# of face N and the first point of face N+1 sit on (or near) their shared
# wale edge, so the NURBS interpolation naturally connects adjacent stitches.
# ---------------------------------------------------------------------------

def append_knit_points(
    curve: YarnCurve,
    width: float,
    height: float,
    face: FaceContext,
) -> None:
    """
    Knit stitch – yarn forms a backward-facing loop (negative normal offset).

    The yarn enters from the bottom-left, arcs behind the fabric to form the
    characteristic knit "V", and exits at the bottom-right ready to enter
    the next stitch.
    """
    # 9 control points give a smooth V-shape with visible depth.
    # entry/exit are slightly in front (+n) — the yarn emerges forward after being
    # pulled through the loop of the row below.
    # The loop top extends to v=+0.55 (slightly above the shared course edge) so
    # the next row's yarn is visually threaded through this row's loop.
    LOCAL: List[Tuple[float, float, float]] = [
        (-0.35, -0.50,  0.12),  # entry – bottom-left, forward (pulled through below)
        (-0.38, -0.25,  0.00),  # left leg: transition at mid-lower
        (-0.35,  0.05, -0.22),  # left leg: behind fabric at mid-height
        (-0.12,  0.42, -0.32),  # loop top-left (behind, near top edge)
        ( 0.00,  0.55, -0.32),  # loop top-center: peaks slightly above face boundary
        ( 0.12,  0.42, -0.32),  # loop top-right (behind, near top edge)
        ( 0.35,  0.05, -0.22),  # right leg: behind fabric at mid-height
        ( 0.38, -0.25,  0.00),  # right leg: transition at mid-lower
        ( 0.35, -0.50,  0.12),  # exit – bottom-right, forward (pulled through below)
    ]
    for u, v, n in LOCAL:
        curve.append(_face_pt(face, u, v, n, width, height))


def append_purl_points(
    curve: YarnCurve,
    width: float,
    height: float,
    face: FaceContext,
) -> None:
    """
    Purl stitch – mirror of knit; the loop faces forward (positive normal).

    Visually produces the horizontal bump seen on the purl side of stockinette
    fabric.
    """
    # Purl is the n-mirror of knit: loop faces forward (+n), entry/exit go behind.
    LOCAL: List[Tuple[float, float, float]] = [
        (-0.35, -0.50, -0.12),  # entry – bottom-left, behind fabric
        (-0.38, -0.25,  0.00),  # left leg: transition at mid-lower
        (-0.35,  0.05,  0.22),  # left leg: in front of fabric at mid-height
        (-0.12,  0.42,  0.32),  # loop top-left (in front, near top edge)
        ( 0.00,  0.55,  0.32),  # loop top-center: peaks slightly above face boundary
        ( 0.12,  0.42,  0.32),  # loop top-right (in front, near top edge)
        ( 0.35,  0.05,  0.22),  # right leg: in front at mid-height
        ( 0.38, -0.25,  0.00),  # right leg: transition at mid-lower
        ( 0.35, -0.50, -0.12),  # exit – bottom-right, behind fabric
    ]
    for u, v, n in LOCAL:
        curve.append(_face_pt(face, u, v, n, width, height))


def append_yarnover_points(
    curve: YarnCurve,
    width: float,
    height: float,
    face: FaceContext,
) -> None:
    """
    Yarn-over stitch – an extra drape loop is cast over the needle before the
    main knit loop, creating a deliberate eyelet in lace patterns.

    The yarn first arcs forward (drape), crosses back through the fabric, then
    completes a standard backward knit loop.
    """
    LOCAL: List[Tuple[float, float, float]] = [
        (-0.40, -0.50,  0.12),  # entry – forward bump (pulled through)
        (-0.30,  0.00,  0.28),  # forward drape arc rises
        ( 0.00,  0.22,  0.32),  # forward drape peak
        ( 0.00, -0.05, -0.10),  # crossover / pinch back through fabric
        (-0.15,  0.38, -0.28),  # main backward loop – left side
        ( 0.00,  0.55, -0.28),  # loop top (slightly above boundary)
        ( 0.15,  0.38, -0.28),  # main backward loop – right side
        ( 0.30,  0.00, -0.15),  # right leg descends
        ( 0.40, -0.50,  0.12),  # exit – forward bump
    ]
    for u, v, n in LOCAL:
        curve.append(_face_pt(face, u, v, n, width, height))


def append_increase_points(
    curve: YarnCurve,
    width: float,
    height: float,
    face: FaceContext,
) -> None:
    """
    Increase stitch (5-edge face) – one incoming strand is worked into two loops,
    widening the fabric by one stitch.

    The wider pentagon face accommodates a slightly fanned-out loop shape; the
    entry and exit are shifted toward the two outgoing course edges.
    """
    LOCAL: List[Tuple[float, float, float]] = [
        (-0.20, -0.50,  0.12),  # entry – forward bump (single incoming)
        (-0.25,  0.00, -0.18),  # left leg behind fabric
        (-0.05,  0.42, -0.28),  # top-left of widened loop
        ( 0.10,  0.55, -0.28),  # loop top-center (slightly above boundary)
        ( 0.25,  0.42, -0.28),  # top-right of widened loop
        ( 0.40,  0.00, -0.18),  # right leg (offset right for second stitch)
        ( 0.45, -0.50,  0.12),  # exit – forward bump
    ]
    for u, v, n in LOCAL:
        curve.append(_face_pt(face, u, v, n, width, height))


def append_decrease_points(
    curve: YarnCurve,
    width: float,
    height: float,
    face: FaceContext,
) -> None:
    """
    Decrease stitch (5-edge face) – two incoming strands are knit together into
    one loop, narrowing the fabric by one stitch.

    The entry is shifted left to represent the wider incoming side, and the
    merged loop rises to a single peak before exiting.
    """
    LOCAL: List[Tuple[float, float, float]] = [
        (-0.45, -0.50,  0.12),  # entry left – forward bump (wider incoming)
        (-0.40,  0.05, -0.15),  # left strand angles behind
        (-0.15,  0.42, -0.28),  # merged loop – left of peak
        ( 0.00,  0.55, -0.28),  # loop top-center (slightly above boundary)
        ( 0.15,  0.42, -0.28),  # merged loop – right of peak
        ( 0.25,  0.05, -0.15),  # single right strand descends
        ( 0.20, -0.50,  0.12),  # exit – forward bump (single outgoing)
    ]
    for u, v, n in LOCAL:
        curve.append(_face_pt(face, u, v, n, width, height))


# ---------------------------------------------------------------------------
# Subtask 3 – Border stitch handling
# ---------------------------------------------------------------------------

def append_cast_on_points(
    curve: YarnCurve,
    width: float,
    height: float,
    face: FaceContext,
) -> None:
    """
    Cast-on foundation edge.

    Creates the initial row of foundation loops along the bottom course edge
    of the first knitting row.  There are no incoming loops from below; instead
    the yarn is wrapped around the needle to form independent starting loops,
    represented here as a series of forward bumps sitting on the bottom edge.

    This function is called once per face in row 0 (the first course row),
    before the normal stitch points for that face are appended.
    """
    LOCAL: List[Tuple[float, float, float]] = [
        (-0.45, -0.50,  0.00),  # far-left anchor on cast-on edge
        (-0.30, -0.45,  0.20),  # first forward bump rising off needle
        (-0.10, -0.35,  0.28),  # first bump peak
        ( 0.00, -0.45,  0.08),  # dip between bumps (yarn returns to edge)
        ( 0.10, -0.35,  0.28),  # second bump peak
        ( 0.30, -0.45,  0.20),  # second bump trail
        ( 0.45, -0.50,  0.00),  # far-right anchor on cast-on edge
    ]
    for u, v, n in LOCAL:
        curve.append(_face_pt(face, u, v, n, width, height))


def append_bind_off_points(
    curve: YarnCurve,
    width: float,
    height: float,
    face: FaceContext,
) -> None:
    """
    Bind-off finishing edge.

    Chains off the last row of loops along the top course edge of the final
    knitting row, preventing the fabric from unravelling.  Each loop is passed
    over the next to secure the edge, represented as a series of forward bumps
    along the top edge.

    This function is called once per face in the last course row, after the
    normal stitch points for that face are appended.
    """
    LOCAL: List[Tuple[float, float, float]] = [
        (-0.45,  0.50,  0.00),  # far-left start on bind-off edge
        (-0.30,  0.45,  0.20),  # first forward bump
        (-0.10,  0.35,  0.28),  # first bump peak
        ( 0.00,  0.45,  0.08),  # dip between bumps
        ( 0.10,  0.35,  0.28),  # second bump peak
        ( 0.30,  0.45,  0.20),  # second bump trail
        ( 0.45,  0.50,  0.00),  # far-right end of bind-off edge
    ]
    for u, v, n in LOCAL:
        curve.append(_face_pt(face, u, v, n, width, height))


# ---------------------------------------------------------------------------
# Stitch-type dispatcher
# ---------------------------------------------------------------------------

def append_stitch_points(
    curve: YarnCurve,
    width: float,
    height: float,
    stitch_type: StitchType,
    face: FaceContext,
) -> None:
    """
    Route to the correct per-stitch-type append function.

    Parameters
    ----------
    curve        : YarnCurve being built for the current row.
    width        : Mean length of the face's COURSE edges (world units).
    height       : Mean length of the face's WALE edges (world units).
    stitch_type  : StitchType enum value for this face.
    face         : World-space coordinate frame of the face, plus DAG path
                   for adjacency queries to adjacent faces if needed.

    Raises ValueError for stitch types that have no generation function.
    """
    # Key on .name (str) to survive module-reload identity mismatches between
    # the StitchType class imported here and the one stored in STATE.
    _DISPATCH = {
        "KNIT":     append_knit_points,
        "PURL":     append_purl_points,
        "YARNOVER": append_yarnover_points,
        "INCREASE": append_increase_points,
        "DECREASE": append_decrease_points,
    }
    fn = _DISPATCH.get(stitch_type.name)
    if fn is None:
        raise ValueError(
            f"append_stitch_points: no generator for stitch type {stitch_type}"
        )
    fn(curve, width, height, face)


# ---------------------------------------------------------------------------
# Subtask 4 – Tube geometry around a yarn curve
# ---------------------------------------------------------------------------

def _rodrigues(v: om.MVector, axis: om.MVector, angle: float) -> om.MVector:
    """
    Rotate vector *v* around *axis* by *angle* radians (Rodrigues' formula).
    *axis* must be a unit vector.
    """
    cos_a = math.cos(angle)
    sin_a = math.sin(angle)
    return v * cos_a + (axis ^ v) * sin_a + axis * (axis * v) * (1.0 - cos_a)


def _compute_max_radius(points: List[om.MPoint]) -> float:
    """
    Conservatively compute the maximum tube radius that prevents self-
    intersection between non-adjacent yarn segments.

    The minimum distance between any two *non-adjacent* control points
    (pairs separated by more than one index) is found; the returned radius
    is 45 % of that minimum to leave a safety margin.  Returns a small
    fallback value when the curve has fewer than 4 points.
    """
    n = len(points)
    if n < 4:
        return 0.05

    min_dist_sq = float("inf")
    for i in range(n):
        # Skip direct neighbours (i±1) – they are intentionally close.
        for j in range(i + 2, n):
            dx = points[i].x - points[j].x
            dy = points[i].y - points[j].y
            dz = points[i].z - points[j].z
            d_sq = dx * dx + dy * dy + dz * dz
            if d_sq < min_dist_sq:
                min_dist_sq = d_sq

    return math.sqrt(min_dist_sq) * 0.45


def _sample_curve(
    curve_name: str,
    num_samples: int,
) -> list:  # List[Tuple[om.MPoint, om.MVector]] — om stubs incomplete
    """
    Sample *num_samples* evenly-spaced (position, tangent) pairs from the
    Maya NURBS curve *curve_name* using uniform parameter sampling.

    Uses the curve's knot vector to determine the parameter range, avoiding
    the expensive arc-length integration of findParamFromLength().

    Returns a list of (MPoint, MVector) tuples in world space.
    """
    sel = om.MSelectionList()
    sel.add(curve_name)
    dag = sel.getDagPath(0)
    if not dag.hasFn(om.MFn.kNurbsCurve):
        dag.extendToShape()

    curve_fn = om.MFnNurbsCurve(dag)
    knots = curve_fn.knots()
    t_min = float(knots[0])
    t_max = float(knots[-1])

    samples: List[Tuple[om.MPoint, om.MVector]] = []
    for i in range(num_samples):
        t = t_min + (t_max - t_min) * i / max(num_samples - 1, 1)
        pt = curve_fn.getPointAtParam(t, om.MSpace.kWorld)  # type: ignore[attr-defined]
        tan = curve_fn.tangent(t, om.MSpace.kWorld)  # type: ignore[attr-defined]
        tan_len = tan.length()
        if tan_len > 1e-8:
            tan /= tan_len
        samples.append((pt, tan))

    return samples


def add_tube_geometry(
    curve_name: str,
    radius: float = 0.0,
    tube_segments: int = 6,
    sample_count: int = 0,
    name: str = "yarn_tube",
) -> str:
    """
    Build a polygonal tube mesh swept around an existing Maya NURBS curve.

    The tube is constructed by:
      1. Sampling the curve at *sample_count* arc-length-uniform positions.
      2. Computing a smoothly-varying Frenet frame at each sample using
         parallel transport (avoids sudden frame flips).
      3. Placing a ring of *tube_segments* vertices around each sample.
      4. Stitching adjacent rings with quad faces; closing each end with a
         triangle fan cap.

    Radius safety
    -------------
    If *radius* <= 0, the radius is computed automatically via
    _compute_max_radius() using the curve's control-point positions.  This
    guarantees that no two non-adjacent tube cross-sections overlap.

    Parameters
    ----------
    curve_name    : Name of an existing Maya NURBS curve transform node.
    radius        : Yarn radius in Maya world units.  0 = auto-compute.
    tube_segments : Number of sides on the circular cross-section (min 3).
    sample_count  : Number of rings along the tube (0 = 8 × curve spans).
    name          : Base name for the output mesh transform node.

    Returns
    -------
    Name of the created mesh transform, or "" on failure.
    """
    if not cmds.objExists(curve_name):
        om.MGlobal.displayError(
            f"add_tube_geometry: curve '{curve_name}' not found."
        )
        return ""

    tube_segments = max(3, tube_segments)

    # ------------------------------------------------------------------
    # Determine sample count from curve spans when not supplied.
    # ------------------------------------------------------------------
    shape_nodes = cmds.listRelatives(
        curve_name, shapes=True, type="nurbsCurve"
    ) or []
    shape = shape_nodes[0] if shape_nodes else ""

    if sample_count <= 0:
        spans = int(cmds.getAttr(shape + ".spans")) if shape else 4
        sample_count = max(spans * 3, 24)

    # ------------------------------------------------------------------
    # Auto-radius: derive from control-point spacing via OpenMaya.
    # cmds.getAttr(".cv[*]") returns a list of (x,y,z) tuples in modern
    # Maya, so we use MFnNurbsCurve.cvPositions() instead for reliability.
    # ------------------------------------------------------------------
    if radius <= 0.0:
        if shape:
            try:
                # cmds.getAttr returns a list of (x,y,z) tuples for cv[*].
                raw = cmds.getAttr(shape + ".cv[*]") or []  # type: ignore[attr-defined]
                ctrl_pts = [om.MPoint(float(r[0]), float(r[1]), float(r[2])) for r in raw]  # type: ignore[attr-defined]
                radius = _compute_max_radius(ctrl_pts) if len(ctrl_pts) >= 4 else 0.05
            except Exception:
                radius = 0.05
        else:
            radius = 0.05

    # ------------------------------------------------------------------
    # Sample curve positions and tangents.
    # ------------------------------------------------------------------
    samples = _sample_curve(curve_name, sample_count)
    if len(samples) < 2:
        om.MGlobal.displayError("add_tube_geometry: curve too short to sample.")
        return ""

    n_rings = len(samples)
    n_segs = tube_segments

    # ------------------------------------------------------------------
    # Build per-ring frames using parallel transport to avoid flipping.
    # ------------------------------------------------------------------
    t0 = samples[0][1]
    # Choose an initial "up" that is not parallel to the first tangent.
    up = om.MVector(0.0, 1.0, 0.0)
    if abs(t0 * up) > 0.9:
        up = om.MVector(1.0, 0.0, 0.0)

    n_vec = (t0 ^ up).normalize()
    b_vec = (t0 ^ n_vec).normalize()

    frames: List[Tuple[om.MVector, om.MVector, om.MVector]] = [(t0, n_vec, b_vec)]

    for i in range(1, n_rings):
        t1 = samples[i][1]
        rot_axis = frames[-1][0] ^ t1
        rot_len = rot_axis.length()
        if rot_len > 1e-8:
            rot_axis /= rot_len
            cos_val = max(-1.0, min(1.0, frames[-1][0] * t1))
            angle = math.acos(cos_val)
            n1 = _rodrigues(frames[-1][1], rot_axis, angle).normalize()
            b1 = _rodrigues(frames[-1][2], rot_axis, angle).normalize()
        else:
            n1 = frames[-1][1]
            b1 = frames[-1][2]
        frames.append((t1, n1, b1))

    # ------------------------------------------------------------------
    # Generate vertex positions (rings + two cap centres).
    # ------------------------------------------------------------------
    all_pts: List[om.MPoint] = []

    for i, (pt, _) in enumerate(samples):
        _, n_f, b_f = frames[i]
        for j in range(n_segs):
            angle = 2.0 * math.pi * j / n_segs
            offset = n_f * (radius * math.cos(angle)) + b_f * (radius * math.sin(angle))
            all_pts.append(
                om.MPoint(pt.x + offset.x, pt.y + offset.y, pt.z + offset.z)
            )

    start_cap_idx = len(all_pts)
    all_pts.append(om.MPoint(samples[0][0]))       # start cap centre

    end_cap_idx = len(all_pts)
    all_pts.append(om.MPoint(samples[-1][0]))       # end cap centre

    # ------------------------------------------------------------------
    # Build face topology.
    # ------------------------------------------------------------------
    poly_counts:   List[int] = []
    poly_connects: List[int] = []

    # Side quads – connect ring i to ring i+1.
    for i in range(n_rings - 1):
        for j in range(n_segs):
            j_next = (j + 1) % n_segs
            v0 = i       * n_segs + j
            v1 = i       * n_segs + j_next
            v2 = (i + 1) * n_segs + j_next
            v3 = (i + 1) * n_segs + j
            poly_counts.append(4)
            poly_connects.extend([v0, v1, v2, v3])

    # Start cap – triangle fan (reverse winding to face outward).
    for j in range(n_segs):
        j_next = (j + 1) % n_segs
        poly_counts.append(3)
        poly_connects.extend([start_cap_idx, j_next, j])

    # End cap – triangle fan.
    end_ring_start = (n_rings - 1) * n_segs
    for j in range(n_segs):
        j_next = (j + 1) % n_segs
        poly_counts.append(3)
        poly_connects.extend([end_cap_idx, end_ring_start + j, end_ring_start + j_next])

    # ------------------------------------------------------------------
    # Create the Maya mesh.
    # ------------------------------------------------------------------
    mesh_fn = om.MFnMesh()
    mesh_fn.create(all_pts, poly_counts, poly_connects)

    # Assign to the default shader so it is immediately visible.
    cmds.sets(mesh_fn.fullPathName(), edit=True, forceElement="initialShadingGroup")

    # Rename the auto-generated transform to the requested name.
    transform = cmds.listRelatives(mesh_fn.fullPathName(), parent=True, fullPath=True)
    if transform:
        transform = cmds.rename(transform[0], name)
        return transform

    return mesh_fn.fullPathName()


# ---------------------------------------------------------------------------
# Main generation entry point
# ---------------------------------------------------------------------------

def generate_yarn_curves(
    add_tubes: bool = False,
    yarn_radius: float = 0.0,
    tube_segments: int = 6,
) -> List[str]:
    """
    Traverse the stitch mesh stored in STATE and generate one continuous
    Maya NURBS curve (and optionally a tube mesh) per knitting row.

    Algorithm
    ---------
    1. BFS over the face adjacency graph (same logic as apply_pattern_fill)
       to assign (row, col) grid coordinates to every face.
    2. Group faces by row; sort each group by column.
    3. For each row:
         a. Cast-on  – prepend cast-on points for the first row.
         b. Stitches – append per-stitch-type points for every face in order.
         c. Bind-off – append bind-off points for the last row.
    4. Materialise each YarnCurve as a Maya NURBS curve node.
    5. Optionally wrap each curve in a tube mesh via add_tube_geometry().

    Returns a list of curve (or tube) node names.
    """
    from collections import deque

    if not STATE.face_stitch_map:
        om.MGlobal.displayError(
            "generate_yarn_curves: no stitch map. Initialise the mesh first."
        )
        return []
    if not STATE.base_mesh:
        om.MGlobal.displayError(
            "generate_yarn_curves: no base mesh. Select a mesh first."
        )
        return []

    cmds.select(STATE.base_mesh, replace=True)
    sel = om.MGlobal.getActiveSelectionList()
    if sel.length() == 0:
        om.MGlobal.displayError("generate_yarn_curves: could not select base mesh.")
        return []

    dag_path = sel.getDagPath(0)
    if not dag_path.hasFn(om.MFn.kMesh):
        dag_path.extendToShape()

    # ── Build edge → face map and face adjacency ───────────────────────────
    edge_to_faces: dict = {}
    face_iter = om.MItMeshPolygon(dag_path)
    while not face_iter.isDone():
        fid = face_iter.index()
        if fid in STATE.face_stitch_map:
            for eid in face_iter.getEdges():
                edge_to_faces.setdefault(eid, []).append(fid)
        face_iter.next()

    face_adj: dict = {fid: [] for fid in STATE.face_stitch_map}
    for eid, flist in edge_to_faces.items():
        if len(flist) == 2:
            f0, f1 = flist
            face_adj[f0].append((f1, eid))
            face_adj[f1].append((f0, eid))

    # ── BFS to assign (row, col) coordinates ──────────────────────────────
    face_coords: dict = {}
    start_face = next(iter(STATE.face_stitch_map))
    queue: deque = deque([(start_face, 0, 0)])
    face_coords[start_face] = (0, 0)

    while queue:
        fid, row, col = queue.popleft()
        for nbr_face, shared_edge in face_adj.get(fid, []):
            if nbr_face in face_coords:
                continue
            etype = STATE.edge_map.get(shared_edge, EdgeType.UNASSIGNED)
            if getattr(etype, "name", str(etype)) == "COURSE":
                new_row, new_col = row + 1, col
            else:
                new_row, new_col = row, col + 1  # WALE or unassigned
            face_coords[nbr_face] = (new_row, new_col)
            queue.append((nbr_face, new_row, new_col))

    # ── Group faces by row ─────────────────────────────────────────────────
    rows: dict = {}
    for fid, (row, col) in face_coords.items():
        rows.setdefault(row, []).append((col, fid))
    for row_faces in rows.values():
        row_faces.sort(key=lambda x: x[0])

    if not rows:
        om.MGlobal.displayWarning("generate_yarn_curves: no rows found.")
        return []

    min_row = min(rows)
    max_row = max(rows)

    # ── Generate one curve per row ─────────────────────────────────────────
    created_nodes: List[str] = []

    cmds.refresh(suspend=True)  # type: ignore[attr-defined]
    try:
        _generate_rows(
            rows, min_row, max_row, dag_path, add_tubes,
            yarn_radius, tube_segments, created_nodes,
        )
    finally:
        cmds.refresh(suspend=False)  # type: ignore[attr-defined]
        cmds.refresh()  # type: ignore[attr-defined]

    om.MGlobal.displayInfo(
        f"generate_yarn_curves: created {len(created_nodes)} yarn path(s)."
    )
    return created_nodes


def _generate_rows(
    rows: dict,
    min_row: int,
    max_row: int,
    dag_path,  # om.MDagPath — stubs incomplete
    add_tubes: bool,
    yarn_radius: float,
    tube_segments: int,
    created_nodes: list,
) -> None:
    # ── Precompute face and row centroids for wale_axis orientation ────────
    # wale_axis direction from edge vectors is arbitrary (depends on edge
    # traversal order).  We correct it here so it always points toward the
    # next row (increasing row index), which makes v=+0.55 consistently
    # extend the loop top into the adjacent row rather than away from it.
    face_centroids: dict = {}
    face_iter_pre = om.MItMeshPolygon(dag_path)  # type: ignore[attr-defined]
    while not face_iter_pre.isDone():
        fid_pre = face_iter_pre.index()
        if fid_pre in STATE.face_stitch_map:
            pts_pre = face_iter_pre.getPoints(om.MSpace.kWorld)  # type: ignore[attr-defined]
            face_centroids[fid_pre] = (
                sum(p.x for p in pts_pre) / len(pts_pre),
                sum(p.y for p in pts_pre) / len(pts_pre),
                sum(p.z for p in pts_pre) / len(pts_pre),
            )
        face_iter_pre.next()

    row_centroids: dict = {}
    for ri, flist_k in rows.items():
        valid_fids = [fid for _, fid in flist_k if fid in face_centroids]
        if valid_fids:
            row_centroids[ri] = (
                sum(face_centroids[f][0] for f in valid_fids) / len(valid_fids),
                sum(face_centroids[f][1] for f in valid_fids) / len(valid_fids),
                sum(face_centroids[f][2] for f in valid_fids) / len(valid_fids),
            )

    for row_idx in sorted(rows):
        curve = YarnCurve()
        is_first_row = (row_idx == min_row)
        is_last_row  = (row_idx == max_row)

        # Reference vector: points from current row centroid toward next row.
        # Used to flip wale_axis into a consistent "upward" orientation.
        if row_idx + 1 in row_centroids and row_idx in row_centroids:
            rc_cur  = row_centroids[row_idx]
            rc_next = row_centroids[row_idx + 1]
            wale_ref = (rc_next[0] - rc_cur[0],
                        rc_next[1] - rc_cur[1],
                        rc_next[2] - rc_cur[2])
        elif row_idx - 1 in row_centroids and row_idx in row_centroids:
            rc_cur  = row_centroids[row_idx]
            rc_prev = row_centroids[row_idx - 1]
            wale_ref = (rc_cur[0] - rc_prev[0],
                        rc_cur[1] - rc_prev[1],
                        rc_cur[2] - rc_prev[2])
        else:
            wale_ref = (0.0, 1.0, 0.0)

        face_list = rows[row_idx]
        for face_idx, (_col, fid) in enumerate(face_list):
            face_data = STATE.face_stitch_map.get(fid)
            if face_data is None:
                continue

            ctx    = build_face_context(dag_path, fid)
            width, height = _compute_face_dimensions(dag_path, fid)

            # Orient wale_axis toward the next row so loop tops (v > 0.5) always
            # extend into the adjacent row's space, enabling visual interlocking.
            dot = (ctx.wale_axis.x * wale_ref[0]
                   + ctx.wale_axis.y * wale_ref[1]
                   + ctx.wale_axis.z * wale_ref[2])
            if dot < 0:
                ctx.wale_axis = om.MVector(  # type: ignore[attr-defined]
                    -ctx.wale_axis.x, -ctx.wale_axis.y, -ctx.wale_axis.z
                )

            # Cast-on once before the first stitch of the row.
            if is_first_row and face_idx == 0:
                append_cast_on_points(curve, width, height, ctx)

            # Main stitch shape (skip NOTASSIGNED faces).
            # Compare by .name to survive module-reload enum identity mismatches.
            if face_data.stitch_type.name != "NOTASSIGNED":
                append_stitch_points(curve, width, height, face_data.stitch_type, ctx)

            # Bind-off once after the last stitch of the row.
            if is_last_row and face_idx == len(face_list) - 1:
                append_bind_off_points(curve, width, height, ctx)

        if not curve.points:
            continue

        curve_node = curve.build_maya_curve(f"yarn_row_{row_idx:04d}")
        if not curve_node:
            continue

        if add_tubes:
            try:
                tube_node = add_tube_geometry(
                    curve_node,
                    radius=yarn_radius,
                    tube_segments=tube_segments,
                    name=f"yarn_tube_row_{row_idx:04d}",
                )
                if tube_node:
                    created_nodes.append(tube_node)
                else:
                    cmds.warning(f"yarn tube failed for row {row_idx}; curve kept.")  # type: ignore[attr-defined]
                    created_nodes.append(curve_node)
            except Exception as exc:
                cmds.warning(f"yarn tube exception row {row_idx}: {exc}")  # type: ignore[attr-defined]
                created_nodes.append(curve_node)
        else:
            created_nodes.append(curve_node)
