# Darn that Yarn! — References and Literature Survey

## Literature Survey

**Project:** Darn that Yarn!  
**By:** Rose Kelly, Rebecca Waterson

### Introduction

Knitted fabric forces computer graphics to confront a paradox: the material looks soft and continuous at a distance, but its behavior and appearance come from a rigidly structured world of loops, contacts, and near-inextensible strands. If we want yarn-level detail, where individual strands can slide, tighten, and collide, we cannot treat the cloth as a smooth sheet for very long. At the same time, we cannot jump straight to yarn curves without inheriting the numerical and modeling challenges that come with constraints, stiffness, and dense contact.

To build **Darn that Yarn!**, we traced a focused line of research that gradually provided the tools needed to make that jump. We begin with the physically based viewpoint that deformable shapes can be simulated by defining energies and letting dynamics follow from them **[TPBF87]**. As cloth simulation becomes its own problem, the emphasis shifts from general elasticity to fabric-specific behavior: **[Pro95]** shows that believable cloth requires explicit limits on deformation and stretch rather than relying on unconstrained springs. However, enforcing these limits raises a computational problem: stiff constraints make simulations fragile unless the solver is designed for them. **[BW98]** responds with a formulation that remains stable at larger time steps, making constrained cloth simulation practical rather than just possible. With numerical stability in place, **[GHD+03]** pushes the modeling side forward by treating cloth as a thin shell with principled discrete stretching and bending energies, reducing dependence on spring networks and improving physical consistency across meshes.

From there, the research turns inward from surfaces to structure. The previous advancements in cloth simulation lead into **[GHFBG07]**, which advances simulation for inextensible cloth, an important contribution for handling constraints when simulating the inextensible yarn making up the knit in **[KJM08]**. This work is the first yarn-level simulation of knitted fabrics and serves as the foundation for later knitted cloth papers in our survey: **[KJM10]**, focused on improving yarn collision processing performance, and **[YKM+12]**, which bundles the entire knit generation process into a usable workflow for garment creation and improves safe yarn collision handling. This lineage shows how each step tightens the connection between physical realism and practical computation, and why stitch meshes emerge as a compelling intermediate representation. They preserve stitch topology and garment shape while still enabling yarn-level relaxation and detail.

---

## Annotated Research Lineage

### [TPBF87] Terzopoulos et al. (1987) — *Elastically Deformable Models*

This paper provides one of the earliest and most influential templates for computer graphics simulation: represent a shape as a deformable object driven by physical energies and constraints, then evolve it over time by solving the resulting dynamics. The approach forms the backbone of later cloth and fabric simulation. In the context of cloth, the energy + constraints + numerical integration viewpoint becomes the conceptual root that motivates increasingly specialized work.

### [Pro95] Provot (1995) — *Deformation Constraints in a Mass-Spring Model to Describe Rigid Cloth Behavior*

Provot addresses a key weakness in early cloth simulation: mass-spring cloth tends to stretch too much and behave like rubber unless deformation is carefully controlled. The paper proposes deformation constraints that curb unrealistic stretch and guide simulation toward more fabric-like behavior. This moves cloth simulation from “apply forces and hope” toward explicit enforcement of cloth material limits.

### [BW98] Baraff & Witkin (1998) — *Large Steps in Cloth Simulation*

Baraff and Witkin address the computational bottleneck created by stiff cloth constraints. Their work demonstrates that cloth models with strong stretching and bending behavior can still be simulated stably with larger time steps by using implicit integration and efficient linear solves. This paper is a major turning point because it makes constrained cloth simulation practical at meaningful scales.

### [GHD+03] Grinspun et al. (2003) — *Discrete Shells*

This paper improves the underlying cloth representation by modeling fabric as a thin shell with energies derived from differential geometry rather than as a spring network. This leads to more principled behavior, especially for bending, across arbitrary meshes. It marks a shift from pragmatic spring models toward a more coherent geometric and physical foundation for cloth simulation.

### [GHFBG07] Goldenthal et al. (2007) — *Efficient Simulation of Inextensible Cloth*

Goldenthal and collaborators focus on efficiently simulating nearly inextensible cloth, treating in-plane inextensibility as a primary material property rather than as an approximation via very stiff springs. This is an important step because yarn-based textiles are fundamentally close to inextensible, and preserving that property without instability is critical for later knit simulation work.

### [KJM08] Kaldor, James, and Marschner (2008) — *Simulating Knitted Cloth at the Yarn Level*

This paper introduces the first yarn-level simulation of knitted fabrics by explicitly modeling the yarn as geometry rather than approximating fabric behavior on a smooth sheet. The yarn is represented as a single inextensible curve with bending resistance and collision forces to prevent self-intersection. The authors use Goldenthal et al.’s method for maintaining inextensibility. The result is a major advance in knitted fabric realism, though it remains computationally expensive and therefore best suited for offline rendering.

### [KJM10] Kaldor, James, and Marschner (2010) — *Efficient Yarn-based Cloth with Adaptive Contact Linearization*

This paper revisits yarn-level knit simulation to improve performance, especially in collision processing. The authors approximate penalty forces and reuse contact information over multiple frames, taking advantage of the structured and locally rigid behavior of knitted loops. They recompute contact forces when deformation becomes significant. This reduces contact-processing cost dramatically while preserving visual plausibility.

### [YKM+12] Yuksel, Kaldor, James, and Marschner (2012) — *Stitch Meshes for Modeling Knitted Clothing with Yarn-Level Detail*

This paper applies previous yarn-level knit simulation work to build a practical garment authoring workflow. A user begins with a polygon mesh, converts it to a stitch mesh, assigns patterns, and then generates a yarn-level mesh that is relaxed for realism. One of the paper’s key contributions is yarn pull-through detection during physical simulation, which is essential because missed collisions can cause the knit structure to unravel. This paper is the direct foundation for **Darn that Yarn!**

---

## References

- **[TPBF87]** D. Terzopoulos, J. Platt, A. Barr, K. Fleisher. *Elastically Deformable Models.*
- **[Pro95]** X. Provot. *Deformation Constraints in a Mass-Spring Model to Describe Rigid Cloth Behavior.*
- **[BW98]** D. Baraff, A. Witkin. *Large Steps in Cloth Simulation.*
- **[GHD+03]** E. Grinspun, A. Hirani, M. Desbrun, P. Schröder. *Discrete Shells.*
- **[GHFBG07]** R. Goldenthal, S. Harmon, D. Fattal, M. Bercovier, E. Grinspun. *Efficient Simulation of Inextensible Cloth.*
- **[KJM08]** J. Kaldor, D. James, S. Marschner. *Simulating Knitted Cloth at the Yarn Level.*
- **[KJM10]** J. Kaldor, D. James, S. Marschner. *Efficient Yarn-based Cloth with Adaptive Contact Linearization.*
- **[YKM+12]** C. Yuksel, J. Kaldor, D. L. James, S. Marschner. *Stitch Meshes for Modeling Knitted Clothing with Yarn-Level Detail.*
