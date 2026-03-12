# Darn that Yarn! — Authoring Tool Design Document

## Project Summary

**Darn that Yarn!** is a Maya authoring tool for rapidly converting a low-resolution garment **shape mesh** into a high-fidelity knitted garment with **yarn-level detail**, based on **stitch meshes**. The production need is to author realistic knitted clothing without manually modeling yarn curves or risking topological errors that would unravel under simulation, enabling close-up hero garment rendering.

Our design goal is to provide an artist-friendly workflow to define knitting direction (**course/wale**), assign stitch types and patterns, preview stitch density via tessellation, and optionally run relaxation for more realistic distribution and drape. The target users are character artists and technical designers working in animation, VFX, and games who need knit garments with controllable stitch patterns and offline-quality realism.

The tool takes a base polygon mesh and interactive row labeling as input, produces a stitch-mesh preview and optionally yarn curves / a yarn-level mesh as output, and supports pattern edits at both per-stitch and region/tiling scales. The implementation is a Maya plugin with a Python UI layer and performance-critical C++ geometry/simulation operators, following the paper’s pipeline:

**labeling → stitch mesh tessellation → pattern edits → mesh-based relaxation → yarn generation → yarn-level relaxation**

Development schedule:
- **Alpha:** end-to-end stitch mesh generation, knit/purl patterning, and a stable preview workflow
- **Beta:** yarn curve generation, borders, additional stitch types, and at least simplified relaxation/caching

---

# 1. Authoring Tool Design

## 1.1 Significance of Problem or Production / Development Need

Garment creation is essential in animation and video game development for almost any project involving humans or characters that have clothing. As such, this process is relevant in a significant portion of productions and continues to matter across large studios and independent development. As realistic graphics improve, there is increasing demand for highly detailed garments.

Our tool offers a procedural, topology-safe way to generate knitted garments with controllable stitch patterns and high-frequency yarn detail. By separating pattern authoring from yarn geometry generation, artists can quickly iterate on knit direction and stitch assignments on a lightweight stitch mesh, then produce physically plausible yarn geometry through offline relaxation. This reduces manual labor and eliminates common failure modes such as inconsistent yarn topology.

## 1.2 Technology

Our tool is based on the SIGGRAPH paper **“Stitch Meshes for Modeling Knitted Clothing with Yarn-level Detail.”** This method begins with a simple base polygon mesh in the shape of the desired garment and converts it into a **stitch mesh** representing the knit pattern, where each face represents a stitch in the knit. The stitch mesh is then relaxed to simulate global shape change caused by physical forces. Finally, the stitch mesh is converted to yarn geometry and yarn-level relaxation is simulated to produce a final high-fidelity knit mesh.

We chose this paper because of its potential to create high-quality garments in a tooling area that is increasingly relevant with the rise of 3D garment design in fashion, games, animation, and VFX.

## 1.3 Design Goals

### 1.3.1 Target Audience

The primary users are character artists, technical directors, and technical artists working in animation, games, or VFX who need garments with customizable knit patterns and close-up fidelity. Since yarn-level physical simulation is computationally expensive, the output is intended for high-quality offline rendering rather than real-time graphics.

### 1.3.2 User Goals and Objectives

Typical applications include sweaters, dresses, gloves, scarves, and other knitted wardrobe pieces for hero characters where stitch detail matters. The tool is primarily focused on high-quality knit garment creation, but it could also be used to create knit versions of other shapes, such as stuffed animals or knit covers.

### 1.3.3 Tool Features and Functionality

Core functionality:
- Generate knit meshes in arbitrary user-defined shapes
- Allow control over knit pattern through selection interaction and GUI controls
- Allow control over knit density through tessellation
- Allow users to decide whether relaxation processes are applied

### 1.3.4 Tool Input and Output

**Input**
- A base polygon mesh in the desired garment/object shape
- Interactive row labeling through edge loop selection
- Optional per-face stitch type overrides
- Tessellation level
- Relaxation toggles

**Output**
- A knitted version of the input object, including yarn-level geometry and optional physically simulated relaxation

## 1.4 User Interface

### 1.4.1 GUI Components and Layout

#### Stitch Mesh Generation Section
- **Selected Edges Section**  
  Enabled only when the user has selected edges on the base mesh
- **Set Course Edge button**  
  Sets selected edges to be course edges in the stitch mesh data structure
- **Selected Face Section**  
  Enabled only when the user has selected faces that have been activated as stitch faces
- **Set Stitch Type button**  
  Sets the stitch type for selected faces using the selected dropdown value
- **Flip Row Direction**  
  Flips direction of all stitches in the selected face’s row
- **RESET Stitch Mesh**  
  Clears all stitch mesh data and restores the base mesh to its initial state

#### Knit Mesh Generation Section
- **Tessellation Level slider**  
  Controls how finely each stitch face is subdivided
- **Tessellate button**  
  Subdivides the stitch mesh to increase the number of stitches
- **Stitch Mesh Relaxation checkbox**
- **Yarn Level Relaxation checkbox**
- **Generate Knit Mesh**  
  Executes tessellation, optional stitch mesh relaxation, yarn generation, and optional yarn relaxation

### 1.4.2 User Tasks

#### Start Process
With the base mesh selected in the viewport, the user clicks the Maya menu bar item **“Darn that Yarn!”** to open the GUI.

#### Stitch Mesh Workflow
- Select a loop of edges and click **Set Course Edge Loop**
- Touch a face in an activated stitch face row and click **Flip Row Direction**
- Set tessellation value using the GUI slider
- Click **Tessellate**
- Click **Generate Knit Mesh**
- Toggle **Yarn Level Relaxation** if desired
- Toggle **Mesh Level Relaxation** if desired
- Click **RESET Stitch Mesh** to restore the original state

The user must understand the high-level workflow:
1. Select a mesh
2. Open the GUI
3. Label course edge loops in the desired knit direction
4. Tessellate
5. Generate the final knit mesh

The tool works best when the base mesh has clean edge loops. Familiarity with knitting concepts and stitch types (knit, purl, yarn-over, increase, decrease) will improve the user’s ability to author patterns effectively.

### 1.4.3 Workflow

#### User Process
1. Select the base mesh and begin the process from the Maya menu
2. Create the stitch mesh by selecting course edge loops
3. Activated stitch rows become visible through coloring
4. Set tessellation and click **Tessellate**
5. Enable or disable relaxation options
6. Click **Generate Knit Mesh**

#### Example Session
1. User loads the plugin
2. User creates a basic polygon mesh of a turtleneck sweater
3. User opens the GUI
4. User selects edge loops from the neck downward and assigns them as course edges
5. User repeats this for sleeves
6. User flips a row direction if desired
7. User tessellates
8. User generates the final knit mesh

This workflow solves the time cost and topological complexity of creating yarn-level knitted garments manually.

---

# 2. Authoring Tool Development

## 2.1 Technical Approach

### 2.1.1 Algorithm Details

High-level pipeline:
1. Input garment **shape mesh**
2. Label mesh with knitting directions (**course** vs **wale**)
3. Generate a high-resolution **stitch mesh**
4. Allow interactive stitch editing / pattern assignment
5. Perform offline relaxation:
   - mesh-based relaxation
   - yarn generation
   - yarn-level relaxation

Key data structures:
- **Stitch Mesh:** polygonal mesh where each face corresponds to a stitch unit
- **Per-face stitch metadata**
- **2.5D curve embedding** storing yarn control points via face coordinates + normal offsets

Assumptions / simplifications:
- Initial stitch types limited to knit, purl, yarn-over, and minimal increase/decrease support
- Alpha begins with quad-only stitch meshes
- Cables may be omitted from alpha
- Mesh-based relaxation comes before full yarn-level relaxation
- Tube knitting uses separate ring rows instead of spiral knitting

### 2.1.2 Maya Interface and Integration

The tool operates as an interactive modeling operator inside Maya.

**Input**
- User-selected base polygon mesh

**Outputs**
- Stitch mesh preview
- Optional yarn curve set
- Optional final yarn-level mesh

#### Python
- Dockable UI
- Selection-driven commands
- Scene management
- Preset and metadata handling

#### C++ plugin
- Stitch mesh tessellation
- Mesh-based relaxation solver
- Yarn curve instantiation

Planned Maya-side architecture:
- A custom generator/deformer node: `darnThatYarnNode`
- A cache node or file-based cache for offline relaxation results

### 2.1.3 Software Design and Development

#### MeshLabeler
- Stores course/wale edge labels and row groups
- Validates that each face has exactly two wale edges

#### StitchMeshBuilder
- Computes tessellation counts and generates stitch mesh topology
- Handles increases/decreases near seam edges

#### PatternAuthoring
- Stores per-face stitch assignments
- Applies tiled patterns to selected regions

#### StitchMeshRelaxer
- Projects stitch mesh vertices to a subdivision surface
- Runs mesh-based relaxation using stretch, shear, and wale-strut forces

#### YarnGenerator
- Converts stitch mesh to yarn curves using embedded stitch models
- Handles borders and cable conversion

#### YarnRelaxer
- Runs yarn-level relaxation with shape preservation and pull-through prevention

Third-party dependencies may include:
- Maya API
- Eigen or host-side math libraries
- Alembic or similar cache format
- Potential simulation framework for full yarn relaxation

## 2.2 Target Platforms

### 2.2.1 Hardware
- Modern multi-core CPU
- 32 GB RAM
- GPU mainly for viewport display

### 2.2.2 Software
- Windows or macOS
- Maya
- Compiler toolchain compatible with the Maya SDK

## 2.3 Software Versions

### 2.3.1 Alpha Version Features

Goals:
- End-to-end stitch mesh + patterning workflow
- At least one offline step

Alpha features:
- Select / import base mesh
- Manual or semi-automatic labeling of course/wale edges
- Stitch mesh tessellation
- Per-face knit/purl assignment
- Basic region fill patterning
- Export stitch mesh + metadata
- Mesh-based relaxation preview if possible

Demo targets:
- Hero swatch
- Simple garment section such as a sleeve or tube

### 2.3.2 Beta Version Features

Goals:
- Add realism and output quality

Beta features:
- Additional stitch types beyond knit/purl
- Yarn curve generation
- Border handling
- More robust mesh-based relaxation
- Potential cable workflow
- Offline or approximate yarn relaxation

Demo target:
- One garment with at least two pattern regions, showing stitch mesh, yarn curves, and relaxed output

### 2.3.3 Demos / Tutorials
- 3–5 minute tutorial showing:
  - base mesh requirements
  - row labeling
  - stitch mesh generation
  - pattern painting / tiling
  - export + relaxation

---

# 3. Work Plan

## 3.1 Tasks and Subtasks

### Alpha Tasks

#### Task 1 – Python GUI [Rebecca]
**Duration:** 7 days  
- Create the GUI layout and fields
- Add menu bar integration and selected object capture
- Add selection-aware functionality to enable/disable GUI components

#### Task 2 – Stitch Mesh Edge Labeling [Rose]
**Duration:** 14 days  
- Create edge data structure
- Write edge assignment function
- Connect labeling to GUI

#### Task 3 – Stitch Mesh Row Building and Color Indicators [Rose]
**Duration:** 12 days  
- Automatic stitch assignment
- Face coloring based on knit direction
- Connect to GUI

#### Task 4 – Stitch Mesh Tessellation [Rebecca]
**Duration:** 12 days  
- Tessellation functionality
- Restore un-tessellated mesh
- Connect tessellation to GUI

#### Task 5 – Alpha Stabilization [Rebecca & Rose]
**Duration:** 2 days  
- Bug identification
- Bug resolution
- Demo scene preparation

### Beta Tasks

#### Task 6 – Refinements and Performance [Rose]
**Duration:** 9 days

#### Task 7 – Pattern Customization [Rose]
**Duration:** 13 days  
- Per-face stitch assignment
- Knit/purl ribbing

#### Task 8 – Create Yarn Curve Functionality [Rebecca]
**Duration:** 16 days  
- Curve struct
- Stitch-type point generation
- Border handling
- Geometry around curve

#### Task 9 – Beta Stabilization [Rebecca]
**Duration:** 2 days

### Final Stage Tasks

#### Task 10 – Mesh-Based Relaxation [Rose]
**Duration:** 12 days

#### Task 11 – Finish Remaining Stitches [Rebecca]
**Duration:** 7 days

#### Task 12 – QA and Bug Fixing [Rebecca]
**Duration:** 10 days

#### Task 13 – Final Demo Prep, Sample Assets, Documentation [Rose & Rebecca]
**Duration:** 10 days

#### Task X – Yarn-Level Relaxation (Bonus)
**Duration:** 14 days

## 3.2 Milestones

### 3.2.1 Alpha Version
- Python GUI
- Stitch Mesh Edge Labeling
- Stitch Mesh Row Building
- Stitch Mesh Tessellation
- Alpha Stabilization

### 3.2.2 Beta Version
- Refinements & Performance
- Pattern Customization
- Yarn Curve Functionality
- Beta Stabilization

### Final Demo
- Mesh-Based Relaxation
- Remaining Stitches
- QA and Bug Fixing
- Final Demo Prep

---

# 4. Related Research

This section traces the research lineage leading to **“Stitch Meshes for Modeling Knitted Clothing with Yarn-Level Detail.”** It begins with deformable models, advances through cloth simulation and inextensibility, and culminates in yarn-level knitted cloth simulation and stitch-mesh authoring.

This section can be paired with the separate `references.md` / literature survey file for a complete survey of prior work.
