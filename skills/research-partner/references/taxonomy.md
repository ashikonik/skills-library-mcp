# Taxonomy Construction

A taxonomy is a claim about what makes things different, not a neutral filing system. Two competent researchers will categorize the same field differently because they disagree about what matters. Make the claim explicit rather than presenting the categories as if they were discovered.

## Start with the principle of division

Before drawing any boxes, state what dimension the taxonomy divides on and why that dimension was chosen over the alternatives. Common candidates: the problem being solved, the mechanism used, the assumptions required, the data or resources needed, the guarantees provided, the failure mode.

Say explicitly what the taxonomy is *for*. A taxonomy built to help someone choose a method looks nothing like one built to show a field's intellectual history, even over identical papers. Ask the user which they need.

## Structural rules

- **One principle per level.** A level that splits some children by mechanism and others by application domain is not a taxonomy; it is a list with indentation. This is the most common failure.
- **Decide between a tree and facets.** If items legitimately belong in several places at once, a hierarchy will fight you. Use independent facets (mechanism, supervision, output type) and classify along each. Say which structure you chose and why.
- **Cover the space, and check.** For each level, ask what would fall outside every category. If something real does, either add a category or state the boundary honestly.
- **Two exemplars minimum per node.** A category with one member is usually a description of that one thing, not a category.
- **Prefer three to seven categories per level.** Beyond that, the reader stops seeing structure; below that, the split rarely earns its keep.
- **Name categories by their distinguishing property**, not by their most famous member. Naming a class after one paper makes everything else in it look derivative.

## Stress-test before presenting

Run the draft against hard cases and report what happened:

- Classify several items you have not yet used. If you find yourself arguing about where they go, the boundary is underspecified.
- Deliberately look for **misfits** - work that resists the scheme. Include a short section on them. Misfits are informative: they mark either a missing category or a genuinely novel direction, and hiding them makes the taxonomy look tidier and less useful.
- Check for **boundary cases** where two categories blur, and say what tips an item one way or the other.
- Ask what the taxonomy makes invisible. Every organizing choice suppresses some distinction; name the one yours suppresses.

## Position against existing taxonomies

Most fields already have one or several. Find them. Then state where yours agrees, where it diverges, and what the divergence buys - a taxonomy that quietly reinvents an established scheme with new names is a liability in a paper. If an existing taxonomy is dominant and adequate, say so and recommend using it.

## Present it as contestable

Include, briefly:
- The principle of division and the alternatives rejected.
- What the scheme predicts or clarifies that a flat list would not.
- The strongest objection to this organization, and your response.

## Output structure

```
# Taxonomy of <domain>
## Purpose and principle of division
   What it organizes, what it's for, what dimension it divides on, alternatives rejected
## Structure
   Tree or faceted, with each category: defining property, boundary conditions, 2+ exemplars
## Boundary cases
   Items that sit between categories, and what tips them
## Misfits
   Work the scheme does not accommodate, and what that suggests
## Relation to existing taxonomies
## Limitations
   What this organization makes hard to see, and the strongest objection to it
```

Where a visual would help, offer a diagram of the structure - but only after the categories are settled, since a diagram makes a shaky scheme look authoritative.
