# darn-that-yarn
## Alpha Version
[<img width="1270" height="711" alt="alpha-demo" src="https://github.com/user-attachments/assets/03f8a0ea-6eba-42ab-8461-5cef61dcae6d" />](https://drive.google.com/file/d/1h9OSULZsN4nW3lyelUBjcsg1Rr8BpaoK/view?usp=sharing)
## Beta Version
[<img width="1266" height="710" alt="beta-demo" src="https://github.com/user-attachments/assets/99b3f4b3-b8b6-40ed-8a21-37d3a80c26e8" />](https://drive.google.com/file/d/1qH-cpSrs-aGvBIXuD7AKtlp7Ph21PNTM/view?usp=sharing)

## Overview

**Darn that Yarn!** is a Maya plugin for converting a low-resolution polygon mesh into a
high-fidelity knitted garment with yarn-level detail. It is based on the SIGGRAPH paper
[*Stitch Meshes for Modeling Knitted Clothing with Yarn-Level Detail*](https://www.cs.cornell.edu/projects/stitchmeshes/)
(Yuksel et al. 2012).

The tool is designed for character artists and technical directors in animation, VFX, and
games who need knitted garments with controllable stitch patterns and close-up render
quality. Rather than manually modeling yarn curves, artists define knit direction and stitch
patterns on a lightweight stitch mesh, then generate physically plausible yarn geometry
through offline relaxation.

## Pipeline

Base Mesh → Course/Wale Labeling → Stitch Mesh Tessellation
→ Stitch Pattern Authoring → Mesh-Based Relaxation
→ Yarn Curve Generation → Yarn-Level Relaxation → Final Knit Mesh

## Features

- **Stitch mesh generation** from any quad-dominant polygon mesh
- **Interactive course/wale edge labeling** directly in the Maya viewport
- **Per-face stitch type assignment** — knit, purl, yarn-over, increase, decrease, cast-on, bind-off
- **Ribbing pattern** via one-click alternating k/p fill over selected faces
- **Tessellation control** to set stitch density (number of knit rows)
- **Mesh-based relaxation** for physically plausible stitch distribution
- **Yarn curve generation** producing a continuous spline through the full garment
- **Yarn-level relaxation** for realistic final yarn rest shape (optional, computationally intensive)
- **Viewport preview** with color-coded rows, stitch types, and knit direction

## Usage

### Basic Workflow

1. Create or load a quad-dominant polygon mesh in Maya representing the garment shape
2. Select the mesh and open the plugin via **Darn that Yarn!** in the Maya menu bar
3. Select each horizontal edge loop and click **Set Course Edge Loop** — repeat working
   down the garment
4. Optionally assign stitch types per face, flip row directions, or apply ribbing patterns
5. Set tessellation level and click **Tessellate**
6. Enable relaxation options as desired and click **Generate Knit Mesh**
7. Export or render the resulting yarn-level mesh

### GUI Reference

| Control | Description |
|---|---|
| **Set Course Edge Loop** | Marks selected edges as course (row) edges; adjacent edges become wale edges automatically |
| **Reset Edge Loop** | Clears course assignment from selected edges |
| **Set Stitch Type** | Assigns a stitch type to the selected face(s) |
| **Flip Row Direction** | Reverses wale direction for all faces in a row |
| **Apply Ribbing Pattern** | Applies alternating knit/purl to a contiguous selection of faces |
| **Tessellation Level** | Controls how many stitch rows each base mesh row subdivides into |
| **Tessellate** | Subdivides the stitch mesh according to the tessellation level |
| **Stitch Mesh Relaxation** | Toggles mesh-based relaxation before yarn generation |
| **Yarn Level Relaxation** | Toggles yarn-level relaxation after yarn generation |
| **Generate Knit Mesh** | Runs the full pipeline to produce the final yarn mesh |
| **Reset Stitch Mesh** | Clears all assignments and restores the original base mesh |

### Base Mesh Guidelines

- Prefer clean, quad-dominant topology with consistent horizontal edge loops
- Pentagon faces are supported for increase/decrease stitches; triangles are not handled
- Edge loops should run in the intended course (row) direction of the knit

## Requirements

- **OS:** Windows or macOS
- **DCC:** Autodesk Maya
- **Hardware:** Modern multi-core CPU, 32 GB RAM recommended (stitch meshes and yarn curves can be large)

## Implementation Notes

The plugin is implemented as a Maya plugin with a Python UI layer. The pipeline follows
the six stages from Yuksel et al.: labeling → stitch mesh tessellation → pattern authoring
→ mesh-based relaxation → yarn generation → yarn-level relaxation.

Stitch mesh and yarn curve data persist within a session for iterative editing but are not
currently saved or exported between sessions.

## Authors

Rose Kelly, Rebecca Waterson — CIS 6600, Spring 2026

## Reference

C. Yuksel, J. Kaldor, D. L. James, S. Marschner. *Stitch Meshes for Modeling Knitted
Clothing with Yarn-Level Detail.* ACM SIGGRAPH 2012.
