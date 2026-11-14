"""
Viking Age Armor Tiers 1-6 â€” historically grounded, procedural low-poly kit for Blender (bpy + bmesh).

Paste into Blender's Scripting workspace and press Run Script (Alt+P).
Six mannequins along +X (2 units apart), one social/armour tier each, based on finds and
period sources for Scandinavia c. 793-1066:

  1  Thrall / poor bondi       â€“ worn undyed wool tunic, cord belt, trousers, winingas, turnshoes.
                                 No armour: most men owned none.
  2  Free levy                 â€“ plant-dyed tunic under a quilted padded coat, felt cap, leather belt
                                 with iron buckle, wool cloak on an iron ring-pin. (Padded coats are inferred
                                 from later sources and practicality, not surviving finds.)
  3  Experienced warrior       â€“ padded coat, sheepskin/fur shoulder cape, seax on the belt, and a plain
                                 riveted iron cap with nasal (banded "spangenhelm" construction).
  4  Hirdman in a byrnie       â€“ hip-length, elbow-sleeved mail byrnie over the padded coat and a
                                 Gjermundbu-type helmet: four-plate cap, crest bands, spike knob, spectacle
                                 guard, mail aventail (Gjermundbu, Norway, c. 970).
  5  Eastern-route elite       â€“ lamellar cuirass over mail, as at the Birka garrison (Sweden, 10th c.),
                                 and a conical segmented nasal helmet of the Gnezdovo/eastern type with aventail.
  6  Jarl / chieftain          â€“ knee-length, long-sleeved byrnie; heirloom crested helmet in the ValsgÃ¤rde
                                 tradition with gilt-bronze brows, crest and spectacle guard and a full mail
                                 curtain; madder-red fur-lined cloak on a gilt penannular brooch; gilt belt
                                 fittings; gold arm rings and a silver neck ring; tablet-woven trim.

Every tier also has a ~90 cm round shield (planked board, domed iron boss) leaning at his left side,
growing more decorated by tier: 1 bare planks - 2 one colour + rawhide rim - 3 halved - 4 Gokstad-style
yellow/black segments + edge clamps - 5 curving pinwheel + border - 6 interlace ring, triskele, gilt-bronze fittings.

Deliberately NOT included (no Viking Age evidence): horned or winged helmets, full face masks,
plate armour, pauldrons, greaves, studded leather.

Built entirely from bmesh primitives (no operators, runs in any context), finished with Solidify,
Bevel and Mirror modifiers. Each tier gets its own collection. Units: metres; characters face -Y.
Tested on Blender 4.x / 5.x.
"""
import bpy
import bmesh
import math
import random
from mathutils import Vector, Matrix

SPACING = 2.0
SEED = 7
TAU = math.tau

# ============================================================== scene setup
def clear_scene():
    """Remove existing mesh/text objects and previously generated tier collections."""
    for ob in list(bpy.data.objects):
        if ob.type in {'MESH', 'FONT'}:
            bpy.data.objects.remove(ob, do_unlink=True)
    for coll in list(bpy.data.collections):
        if coll.name.startswith("Tier "):
            bpy.data.collections.remove(coll)
    for block in (bpy.data.meshes, bpy.data.curves):
        for item in list(block):
            if item.users == 0:
                block.remove(item)


def make_material(name, color, roughness, metallic=0.0):
    """Low-poly PBR material: Principled base colour / roughness / metallic (+ viewport colour)."""
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    if hasattr(mat, "use_nodes"):
        mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = next((n for n in nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if bsdf is None:
        bsdf = nodes.new('ShaderNodeBsdfPrincipled')
        out = next((n for n in nodes if n.type == 'OUTPUT_MATERIAL'), None) or nodes.new('ShaderNodeOutputMaterial')
        links.new(bsdf.outputs[0], out.inputs[0])
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    mat.diffuse_color = (*color, 1.0)        # Solid-mode viewport colour
    mat.roughness, mat.metallic = roughness, metallic
    mat.use_fake_user = True                     # survive add-ons that purge unused data while bodies are built
    return mat


def build_materials():
    # Wool colours follow period dyes: undyed sheep tones, weld/plant browns-greens, woad blue, madder red (costly).
    return {
        "mannequin": make_material("Mannequin", (0.42, 0.42, 0.44), 0.7),
        "cloth":     make_material("Cloth",                (0.40, 0.35, 0.28), 0.95),   # undyed wool
        "linen":     make_material("Cloth Linen Padding",  (0.5, 0.44, 0.33), 0.95),   # quilted linen
        "green":     make_material("Cloth Plant-Dyed",     (0.20, 0.22, 0.12), 0.95),
        "blue":      make_material("Cloth Woad Blue",      (0.08, 0.13, 0.24), 0.95),
        "red":       make_material("Cloth Madder Red",     (0.36, 0.06, 0.04), 0.9),
        "trim":      make_material("Tablet-Woven Trim",    (0.55, 0.38, 0.12), 0.6, 0.3),
        "cord":      make_material("Cord",                 (0.38, 0.30, 0.17), 1.0),
        "leather":   make_material("Leather",              (0.20, 0.10, 0.05), 0.6),
        "fur":       make_material("Fur",                  (0.15, 0.1, 0.06), 1.0),
        "dark":      make_material("Cloth Dark Wool",      (0.17, 0.14, 0.11), 0.95),   # brown/black sheep wool
        "steel":     make_material("Iron/Steel",           (0.42, 0.43, 0.45), 0.42, 1.0),
        "mail":      make_material("Iron/Steel Mail",      (0.2, 0.205, 0.215), 0.78, 0.65),   # riveted rings: dark, matte
        "gold":      make_material("Gold Trim",            (0.80, 0.56, 0.17), 0.28, 1.0),   # gilt bronze / gold
        "silver":    make_material("Silver",               (0.75, 0.76, 0.78), 0.25, 1.0),
        # shields: planks of spruce/fir/pine, rawhide edging, mineral paints (ochres, carbon black, chalk white)
        "wood":      make_material("Wood Planks",          (0.45, 0.33, 0.2), 0.8),
        "wood_dark": make_material("Wood Plank Seams",     (0.18, 0.12, 0.07), 0.9),
        "rawhide":   make_material("Rawhide Edging",       (0.55, 0.45, 0.3), 0.7),
        "p_red":     make_material("Paint Red Ochre",      (0.42, 0.09, 0.05), 0.75),
        "p_yellow":  make_material("Paint Yellow Ochre",   (0.68, 0.48, 0.12), 0.75),
        "p_black":   make_material("Paint Carbon Black",   (0.025, 0.025, 0.025), 0.7),
        "p_white":   make_material("Paint Chalk White",    (0.72, 0.69, 0.6), 0.8),
    }

# ============================================================== matrix helpers
def T(x, y, z): return Matrix.Translation((x, y, z))
def S(x, y, z): return Matrix.Diagonal((x, y, z, 1.0))
def RX(a): return Matrix.Rotation(a, 4, 'X')
def RY(a): return Matrix.Rotation(a, 4, 'Y')
def RZ(a): return Matrix.Rotation(a, 4, 'Z')
I4 = Matrix.Identity(4)


def frame(origin, z_axis, x_hint):
    """4x4 matrix whose local Z runs along z_axis and local X points toward x_hint."""
    z = Vector(z_axis).normalized()
    x = Vector(x_hint); x = (x - z * x.dot(z)).normalized()
    y = z.cross(x)
    m = Matrix((x, y, z)).transposed().to_4x4()
    m.translation = Vector(origin)
    return m

# ============================================================== bmesh primitive builders (all add into a shared bmesh)
def add_box(bm, size, M=I4):
    v = bmesh.ops.create_cube(bm, size=1.0)["verts"]
    bmesh.ops.transform(bm, matrix=M @ S(*size), verts=v)
    return v


def add_cyl(bm, r1, r2, depth, M=I4, seg=10, cap=True):
    """Cylinder/cone along local Z, centred; r1 at -Z, r2 at +Z."""
    v = bmesh.ops.create_cone(bm, cap_ends=cap, cap_tris=False, segments=seg, radius1=r1, radius2=r2, depth=depth)["verts"]
    bmesh.ops.transform(bm, matrix=M, verts=v)
    return v


def add_limb(bm, p1, p2, r1, r2, seg=8, cap=True):
    """Tapered cylinder from point p1 (radius r1) to p2 (radius r2)."""
    p1, p2 = Vector(p1), Vector(p2); d = p2 - p1
    rot = Vector((0, 0, 1)).rotation_difference(d.normalized()).to_matrix().to_4x4()
    return add_cyl(bm, r1, r2, d.length, Matrix.Translation((p1 + p2) / 2) @ rot, seg, cap)


def add_sphere(bm, r, M=I4, u=10, v=6):
    verts = bmesh.ops.create_uvsphere(bm, u_segments=u, v_segments=v, radius=r)["verts"]
    bmesh.ops.transform(bm, matrix=M, verts=verts)
    return verts


def add_ico(bm, r, M=I4, sub=1):
    verts = bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=r)["verts"]
    bmesh.ops.transform(bm, matrix=M, verts=verts)
    return verts


def add_lathe(bm, profile, M=I4, seg=12, sy=1.0, a0=0.0, a1=TAU, wobble=None):
    """Surface of revolution around local Z from [(radius, z), ...] listed bottom-to-top.
    sy squashes depth (ellipse); a0..a1 limits the sweep; wobble(a, z) -> extra radius (folds)."""
    full = abs((a1 - a0) - TAU) < 1e-6
    n = seg if full else seg + 1
    angs = [a0 + (a1 - a0) * k / seg for k in range(n)]
    rings = []
    for r, z in profile:
        ring = []
        for a in angs:
            rr = r + (wobble(a, z) if wobble else 0.0)
            ring.append(bm.verts.new(M @ Vector((rr * math.cos(a), rr * math.sin(a) * sy, z))))
        rings.append(ring)
    for lo, hi in zip(rings, rings[1:]):
        for k in range(n if full else n - 1):
            k2 = (k + 1) % n
            bm.faces.new((lo[k], lo[k2], hi[k2], hi[k]))
    return [v for ring in rings for v in ring]


def add_dome(bm, rx, ry, rz, M=I4, seg=14, rings=5, theta_max=math.pi / 2):
    """Open-bottomed dome (helmet bowls, caps)."""
    prof = [(rx * math.sin(theta_max - (theta_max - 0.02) * i / rings), rz * math.cos(theta_max - (theta_max - 0.02) * i / rings)) for i in range(rings + 1)]
    return add_lathe(bm, prof, M, seg, ry / rx)


def add_torus(bm, R, r, M=I4, seg=18, rseg=6, sy=1.0, arc=TAU):
    """Ring (or open ring if arc < TAU, e.g. a penannular brooch) around local Z."""
    closed = arc >= TAU - 1e-6; n = seg if closed else seg + 1
    grid = []
    for i in range(n):
        a = arc * i / seg; row = []
        for j in range(rseg):
            b = TAU * j / rseg; rr = R + r * math.cos(b)
            row.append(bm.verts.new(M @ Vector((rr * math.cos(a), rr * math.sin(a) * sy, r * math.sin(b)))))
        grid.append(row)
    for i in range(seg if closed else n - 1):
        a, b = grid[i], grid[(i + 1) % n]
        for j in range(rseg):
            bm.faces.new((a[j], b[j], b[(j + 1) % rseg], a[(j + 1) % rseg]))
    return [v for row in grid for v in row]


def jitter(verts, amount, rng):
    for v in verts:
        v.co += Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))) * amount

# ============================================================== object assembly
SKIP = set()     # piece names replaced by store/scanned gear for the tier being built (see WARRIOR_KIT)


def make_object(name, coll, mat, x0, builder, mods=(), smooth=False):
    """Run builder(bm) into a new mesh object at x = x0, apply modifiers list [(TYPE, {attr: value})]."""
    if name in SKIP: return None
    bm = bmesh.new()
    builder(bm)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    for p in me.polygons:
        p.use_smooth = smooth
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    ob.location = (x0, 0.0, 0.0)
    coll.objects.link(ob)
    for kind, attrs in mods:
        md = ob.modifiers.new(kind.title(), kind)
        for k, val in attrs.items():
            if k == "axes":
                md.use_axis[0], md.use_axis[1], md.use_axis[2] = val
            else:
                setattr(md, k, val)
    return ob

SOLID = lambda t: ("SOLIDIFY", {"thickness": t, "offset": 1.0})
BEVEL = lambda w, s=1: ("BEVEL", {"width": w, "segments": s, "limit_method": 'ANGLE'})
MIRROR_X = ("MIRROR", {"axes": (True, False, False), "use_clip": False})

# ============================================================== mannequin anatomy (shared by all tiers)
SHOULDER = Vector((0.235, 0.0, 1.415)); ELBOW = Vector((0.295, 0.0, 1.135)); WRIST = Vector((0.325, -0.03, 0.875))
HIP = Vector((0.105, 0.0, 0.93)); KNEE = Vector((0.115, -0.01, 0.5)); ANKLE = Vector((0.12, 0.0, 0.085))
HEAD_C = Vector((0.0, -0.005, 1.665)); HEAD_R = 0.108
TORSO = [(0.16, 0.9), (0.165, 0.99), (0.168, 1.07), (0.19, 1.19), (0.215, 1.31), (0.225, 1.37), (0.2, 1.435), (0.12, 1.485), (0.06, 1.505)]
DEPTH = 0.62   # torso is wider than deep
SQ = 0.7       # garments are a little rounder than the body


def torso_r(z):
    if z <= TORSO[0][1]: return TORSO[0][0]
    for (r0, z0), (r1, z1) in zip(TORSO, TORSO[1:]):
        if z0 <= z <= z1:
            return r0 + (r1 - r0) * (z - z0) / (z1 - z0)
    return TORSO[-1][0]


def body_r(z, offset):
    """Radius of a garment layer at height z; skirts flare from the hips so they clear the thighs."""
    return torso_r(max(z, 0.9)) + offset + max(0.0, 0.96 - z) * 0.42


def shell_profile(z_bottom, z_top, offset, ridge=0.0, every=0.05):
    """Torso-hugging profile; ridge adds horizontal bumps (quilting lines / mail rows)."""
    prof, z, i = [], z_bottom, 0
    while z < z_top - 1e-6:
        prof.append((body_r(z, offset) + (ridge if (ridge and i % 2) else 0.0), z))
        z += every; i += 1
    prof.append((torso_r(z_top) + offset, z_top))
    return prof


def side(p, sx):
    return Vector((p.x * sx, p.y, p.z))


def build_mannequin(coll, x0, mats):
    def geo(bm):
        add_lathe(bm, TORSO, seg=14, sy=DEPTH)
        add_cyl(bm, 0.165, 0.16, 0.12, T(0, 0, 0.9) @ S(1, 0.72, 1), seg=14)                 # pelvis
        add_limb(bm, (0, 0, 1.48), (0, 0, 1.585), 0.052, 0.048, seg=10)                      # neck
        add_sphere(bm, HEAD_R, T(*HEAD_C) @ S(0.88, 0.98, 1.08), u=14, v=10)                  # head
        add_box(bm, (0.05, 0.035, 0.03), T(0, HEAD_C.y - 0.1, HEAD_C.z - 0.01))               # nose (face direction)
        for sx in (1, -1):
            sh, el, wr = side(SHOULDER, sx), side(ELBOW, sx), side(WRIST, sx)
            hp, kn, an = side(HIP, sx), side(KNEE, sx), side(ANKLE, sx)
            add_sphere(bm, 0.062, T(*sh), u=10, v=6)
            add_limb(bm, sh, el, 0.055, 0.045, seg=10); add_limb(bm, el, wr, 0.045, 0.036, seg=10)
            add_sphere(bm, 0.045, T(*(wr + Vector((0.004 * sx, -0.01, -0.055)))) @ S(0.75, 1, 1.25), u=8, v=6)   # hand
            add_limb(bm, hp, kn, 0.085, 0.06, seg=10); add_limb(bm, kn, an, 0.058, 0.042, seg=10)
            add_box(bm, (0.085, 0.24, 0.06), T(an.x, an.y - 0.06, 0.03))                      # foot
    return make_object("Mannequin", coll, mats["mannequin"], x0, geo, smooth=True)

# ============================================================== clothing
SLEEVE_END = {"short": SHOULDER.lerp(ELBOW, 0.55), "elbow": ELBOW, "forearm": ELBOW.lerp(WRIST, 0.6), "long": WRIST + Vector((0, 0, 0.04))}


def tunic(bm, hem_z, offset, sleeves="long", sleeve_r=0.068, rng=None, tatter=0.0, ridge=0.0, top_z=1.47, every=0.05):
    """Kyrtill / coat / byrnie body: gored, flaring skirt + sleeves on both arms."""
    if MH_CH is not None:
        bm.from_mesh(MHC_MOD.cloth_garment(MH_CH, hem_z, offset, sleeves, ridge, every, top_z, tatter if rng else 0.0)); return
    verts = add_lathe(bm, shell_profile(hem_z, top_z, offset, ridge=ridge, every=every), seg=16, sy=SQ)
    if tatter and rng:                                   # frayed, uneven hem on old clothes
        for v in verts:
            if abs(v.co.z - hem_z) < 1e-4:
                v.co.z += rng.uniform(-tatter * 0.5, tatter)
    if sleeves:
        end = SLEEVE_END[sleeves]
        for sx in (1, -1):
            a = side(SHOULDER + Vector((-0.02, 0, 0.02)), sx)
            if sleeves in ("short",):
                add_limb(bm, a, side(end, sx), sleeve_r, sleeve_r * 0.9, seg=10, cap=False)
            else:
                add_limb(bm, a, side(ELBOW, sx), sleeve_r, sleeve_r * 0.88, seg=10, cap=False)
                if sleeves != "elbow":
                    add_limb(bm, side(ELBOW, sx), side(end, sx), sleeve_r * 0.88, sleeve_r * 0.74, seg=10, cap=False)


def trims(bm, hem_z, offset, sleeve_r=0.068, hem=True, neck=True, cuffs=True, w=0.007):
    """Tablet-woven bands at hem, neckline and cuffs (status marker on good clothes)."""
    if hem: add_torus(bm, body_r(hem_z + 0.012, offset) + 0.004, w, T(0, 0, hem_z + 0.012), seg=24, rseg=4, sy=sqo(offset + 0.03, 1.0))
    if neck: add_torus(bm, torso_r(1.47) + offset + 0.006, w, T(0, 0, 1.465), seg=20, rseg=4, sy=sqo(offset, 1.465))
    if cuffs:
        for sx in (1, -1):
            c = side(SLEEVE_END["long"] + Vector((0, 0.002, 0.012)), sx)
            add_torus(bm, sleeve_r * 0.74 + 0.003, w, frame(c, side(WRIST - ELBOW, sx), Vector((1, 0, 0))), seg=12, rseg=4)


def trousers(bm, r_extra=0.012, z_bottom=0.14):
    """One leg (mirror the object)."""
    if MH_CH is not None:
        bm.from_mesh(MHC_MOD.cloth_hose(MH_CH, r_extra, z_bottom, side="l")); return
    add_limb(bm, HIP, KNEE, 0.085 + r_extra, 0.06 + r_extra, seg=10, cap=False)
    add_limb(bm, KNEE, ANKLE + Vector((0, 0, z_bottom - ANKLE.z)), 0.058 + r_extra, 0.042 + r_extra, seg=10, cap=False)


def winingas(bm, z0=0.13, z1=0.47, turns=8):
    """Leg wraps: a wool band spiralled from ankle to below the knee (one leg)."""
    for i in range(turns):
        t = i / (turns - 1); z = z0 + (z1 - z0) * t
        c = KNEE.lerp(ANKLE, (KNEE.z - z) / (KNEE.z - ANKLE.z))
        r = 0.045 + 0.015 * ((z - ANKLE.z) / (KNEE.z - ANKLE.z)) + 0.016
        add_torus(bm, r, 0.01, T(c.x, c.y, z) @ RX(0.24) @ RY(0.1), seg=12, rseg=4)


def turnshoes(bm, h=0.075):
    """Low leather turnshoe (one foot)."""
    add_box(bm, (0.1, 0.26, h), T(ANKLE.x, ANKLE.y - 0.06, h / 2))
    add_limb(bm, ANKLE + Vector((0, 0.01, 0.02)), ANKLE + Vector((0, 0.005, 0.1)), 0.054, 0.05, seg=10)


def sqo(off, z=1.2):
    """Depth ratio for a shell `off` outside the torso so the gap is `off` at the front and back too."""
    r = torso_r(z); return (r * SQ + off) / (r + off)


def belt(bm, z, width=0.035, offset=0.012):
    r = torso_r(z) + offset
    add_lathe(bm, [(r, z - width / 2), (r, z + width / 2)], seg=18, sy=sqo(offset, z))


def belt_front_y(z, offset):
    return -(torso_r(z) * SQ + offset)


def cord_belt(bm, z, offset):
    r = torso_r(z) + offset
    add_torus(bm, r, 0.009, T(0, 0, z), seg=20, rseg=5, sy=sqo(offset, z))
    y = belt_front_y(z, offset) - 0.008
    add_ico(bm, 0.016, T(0.05, y, z), sub=1)                                               # knot
    for dx, L in ((0.05, 0.18), (0.068, 0.14)):
        add_limb(bm, (dx, y, z), (dx + 0.012, y - 0.008, z - L), 0.007, 0.006, seg=5)


def buckle(bm, z, offset, size=(0.045, 0.01, 0.042)):
    add_box(bm, size, T(0.0, belt_front_y(z, offset) - size[1] / 2, z))


def seax(bm, z, offset):
    """Single-edged knife worn horizontally across the front of the belt."""
    y = belt_front_y(z, offset) - 0.014
    add_box(bm, (0.26, 0.016, 0.05), T(-0.03, y, z - 0.03) @ RY(0.08))        # sheath


def seax_hilt(bm, z, offset):
    y = belt_front_y(z, offset) - 0.014
    add_limb(bm, (0.1, y, z - 0.02), (0.19, y, z - 0.012), 0.012, 0.011, seg=6)


def cloak(bm, hem_z, wool_offset=0.0, rng=None):
    """Rectangular wool cloak pinned at the RIGHT shoulder: covers back and left arm, leaves the sword arm free."""
    fold = lambda a, z: 0.018 * math.sin(a * 8.0) * max(0.0, 1.35 - z)
    prof = [(0.36 + wool_offset, hem_z), (0.33 + wool_offset, 0.8), (0.3 + wool_offset, 1.1), (0.285 + wool_offset, 1.3), (0.25 + wool_offset, 1.43), (0.19 + wool_offset, 1.5)]
    v = add_lathe(bm, prof, T(0, 0.015, 0), seg=18, sy=0.78, a0=-1.25, a1=2.95, wobble=fold)
    if rng:
        jitter([x for x in v if x.co.z < hem_z + 0.02], 0.012, rng)


def ring_pin(bm, pos, R=0.032, tube=0.006):
    """Penannular brooch / ring-pin facing forward, with its pin."""
    M = T(*pos) @ RX(math.pi / 2)
    add_torus(bm, R, tube, M @ RZ(0.35), seg=16, rseg=5, arc=TAU * 0.88)
    add_limb(bm, Vector(pos) + Vector((0.0, -0.004, R * 1.2)), Vector(pos) + Vector((0.01, -0.004, -R * 1.5)), 0.0045, 0.002, seg=6)


def fur_cape(bm, rng):
    """Short sheepskin/fur shoulder cape."""
    v = add_lathe(bm, [(0.3, 1.2), (0.28, 1.32), (0.25, 1.42), (0.15, 1.5)], seg=18, sy=0.8)
    jitter(v, 0.02, rng)
    v = add_torus(bm, 0.17, 0.04, T(0, 0.01, 1.49) @ S(1, 0.85, 0.7), seg=18, rseg=6); jitter(v, 0.008, rng)

# ============================================================== helmets
def helmet_bowl(bm, extra=0.018, brow_z=None, seg=16):
    """Rounded cap (Gjermundbu / Yarm style), open below the brow."""
    brow_z = HEAD_C.z + 0.035 if brow_z is None else brow_z
    rx, ry = HEAD_R * 0.9 + extra, HEAD_R * 0.98 + extra
    top = HEAD_C.z + HEAD_R * 1.08 + extra
    add_dome(bm, rx, ry, top - brow_z, T(HEAD_C.x, HEAD_C.y, brow_z), seg=seg, rings=6)
    return rx, ry, brow_z, top


def conical_bowl(bm, extra=0.018, brow_z=None, height=0.215):
    """Segmented conical helmet (Gnezdovo / eastern type): pointed bowl."""
    brow_z = HEAD_C.z + 0.035 if brow_z is None else brow_z
    rx, ry = HEAD_R * 0.9 + extra, HEAD_R * 0.98 + extra
    prof = [(rx, 0.0), (rx * 0.99, 0.03), (rx * 0.93, 0.07), (rx * 0.8, 0.11), (rx * 0.6, 0.15), (rx * 0.36, 0.185), (rx * 0.12, 0.205), (0.004, height)]
    add_lathe(bm, prof, T(HEAD_C.x, HEAD_C.y, brow_z), seg=16, sy=ry / rx)
    return rx, ry, brow_z, brow_z + height


def brow_band(bm, rx, ry, brow_z, w=0.024, out=0.005):
    add_lathe(bm, [(rx + out, brow_z - w * 0.55), (rx + out, brow_z + w * 0.45)], T(HEAD_C.x, HEAD_C.y, 0), seg=18, sy=ry / rx)


def cross_bands(bm, rx, ry, brow_z, top, r=0.006, both=True):
    """Riveted bands over the crown: nose-to-nape (and ear-to-ear)."""
    for ang in ((0.0, math.pi / 2) if both else (math.pi / 2,)):
        pts = []
        for i in range(13):
            t = math.pi * i / 12
            x = math.cos(t) * (rx + 0.004); z = brow_z + math.sin(t) * (top - brow_z + 0.004)
            p = (RZ(ang) @ Vector((x, 0, z, 1.0))).xyz
            p.y *= ry / rx
            pts.append(p + Vector((HEAD_C.x, HEAD_C.y, 0)))
        for a, b in zip(pts, pts[1:]):
            add_limb(bm, a, b, r, r, seg=4)


def nasal(bm, brow_z, ry, length=0.075, w=0.022):
    add_box(bm, (w, 0.008, length), T(0, HEAD_C.y - ry - 0.006, brow_z - length / 2 + 0.012))


def spectacles(bm, brow_z, ry):
    """Spectacle guard (Gjermundbu): two eye rings joined by a short nasal."""
    fy = HEAD_C.y - ry - 0.008
    for sx in (1, -1):
        add_torus(bm, 0.022, 0.0055, T(0.034 * sx, fy, brow_z - 0.032) @ RX(math.pi / 2) @ S(1.1, 1, 0.85), seg=12, rseg=4)
    add_box(bm, (0.016, 0.008, 0.07), T(0, fy, brow_z - 0.035))


def aventail(bm, rx, brow_z, gap=0.55, drop_r=0.2, drop_z=1.43):
    """Mail curtain hung from the helmet rim; front left open by `gap` radians either side of the face."""
    add_lathe(bm, [(drop_r, drop_z), (0.13, 1.54), (rx + 0.004, brow_z - 0.006)], T(HEAD_C.x, HEAD_C.y + 0.008, 0), seg=16, sy=0.95,
              a0=-math.pi / 2 + gap, a1=3 * math.pi / 2 - gap)

# ============================================================== mail & lamellar
def byrnie(bm, hem_z, sleeves="elbow", offset=0.042):
    """Riveted mail shirt; fine horizontal ridges suggest the rows of rings."""
    tunic(bm, hem_z, offset, sleeves=sleeves, sleeve_r=0.08, ridge=0.0055, every=0.02)


def lamellar_rows(bm, z_bottom, z_top, offset, plates=26, plate=(0.034, 0.006, 0.07), pitch=0.052, tilt=0.12):
    """Small iron lamellae laced in overlapping horizontal rows (Birka-type)."""
    z, row = z_bottom, 0
    while z <= z_top + 1e-6:
        R = body_r(z, offset)
        for k in range(plates):
            a = TAU * (k + 0.5 * (row % 2)) / plates
            pos = Vector((R * math.cos(a), R * math.sin(a) * sqo(offset, z), z))
            add_box(bm, plate, T(*pos) @ RZ(a - math.pi / 2) @ RX(-tilt))
        z += pitch; row += 1


def lamellar_straps(bm, offset):
    """Leather shoulder straps and edge binding for the lamellar cuirass (one side)."""
    a = Vector((0.13, -torso_r(1.42) * 0.55 - offset * 0.7, 1.42)); b = Vector((0.13, torso_r(1.42) * 0.55 + offset * 0.7, 1.42))
    mid = Vector((0.14, 0.0, 1.5))
    add_limb(bm, a, mid, 0.012, 0.012, seg=6); add_limb(bm, mid, b, 0.012, 0.012, seg=6)

# ============================================================== jewellery
def arm_ring(bm, sx=1, f=0.45, R=0.066, tube=0.007, turns=2):
    for t in range(turns):
        p = side(SHOULDER.lerp(ELBOW, f + t * 0.06), sx)
        add_torus(bm, R - t * 0.002, tube, frame(p, side(ELBOW - SHOULDER, sx), Vector((1, 0, 0))), seg=14, rseg=5)


def neck_ring(bm):
    add_torus(bm, 0.083, 0.0075, T(0, HEAD_C.y - 0.007, 1.475) @ RX(-0.25), seg=20, rseg=5, sy=0.9)

# ============================================================== round shields
# ~90 cm planked board, centre grip behind a domed iron boss. Each shield leans upright at the
# warrior's left side, face toward the viewer. Paint layers sit a hair above the board face.
SH_R, SH_T = 0.45, 0.009          # radius, board thickness
SH_TILT, SH_YAW = math.radians(8), math.radians(-12)


def shield_frame():
    """Local frame: disc in XY, front face toward +Z; placed beside the left leg, leaning back slightly."""
    c = Vector((0.82, -0.04, SH_R * math.cos(SH_TILT) + 0.006))
    return T(*c) @ RZ(SH_YAW) @ RX(-SH_TILT) @ RX(math.pi / 2)


def lift(M, z):
    """Frame offset to a given height above the board centre plane."""
    return M @ T(0, 0, z)


def add_sector(bm, r0, r1, a0, a1, M, z, seg=None, twist=0.0):
    """Flat ring sector (pie wedge when r0 = 0). twist curves it into a pinwheel arm."""
    seg = seg or max(2, int(abs(a1 - a0) / 0.12))
    steps = 6 if twist else 1
    rows = []
    for s in range(steps + 1):
        r = r0 + (r1 - r0) * s / steps; off = twist * s / steps
        rows.append([bm.verts.new(lift(M, z) @ Vector((max(r, 0.001) * math.cos(a0 + off + (a1 - a0) * k / seg), max(r, 0.001) * math.sin(a0 + off + (a1 - a0) * k / seg), 0))) for k in range(seg + 1)])
    for lo, hi in zip(rows, rows[1:]):
        for k in range(seg):
            bm.faces.new((lo[k], lo[k + 1], hi[k + 1], hi[k]))


def add_ribbon(bm, pts, width, M, z):
    """Painted band following a 2D polyline on the shield face."""
    pts = [Vector((p[0], p[1])) for p in pts]; L, Rr = [], []
    for i, p in enumerate(pts):
        d = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized(); n = Vector((-d.y, d.x)) * (width / 2)
        L.append(bm.verts.new(lift(M, z) @ Vector((p.x + n.x, p.y + n.y, 0)))); Rr.append(bm.verts.new(lift(M, z) @ Vector((p.x - n.x, p.y - n.y, 0))))
    for i in range(len(pts) - 1):
        bm.faces.new((L[i], Rr[i], Rr[i + 1], L[i + 1]))


def board(bm, M, rng=None, worn=False):
    v = add_cyl(bm, SH_R, SH_R, SH_T, M, seg=36)
    if worn and rng:                                   # nicks in an old, unpainted board's edge
        for x in v:
            if rng.random() < 0.25: x.co += (x.co - M.translation).normalized() * -0.008


def plank_seams(bm, M, planks=7):
    w = 2 * SH_R / planks
    for k in range(1, planks):
        x = -SH_R + k * w; h = 2 * math.sqrt(max(SH_R ** 2 - x ** 2, 0)) - 0.01
        add_box(bm, (0.004, h, 0.002), lift(M, SH_T / 2 + 0.0008) @ T(x, 0, 0))


def boss(bm, M, r=0.075, h=0.058, neck=True, flange=0.098, rivets=4):
    """Domed iron boss (Rygh 562/563 types): flange, optional neck/collar, dome, flange rivets."""
    base = SH_T / 2 + 0.0045   # sits above every paint layer
    add_sector(bm, r * 0.9, flange, 0, TAU, M, base, seg=24)
    z = base
    if neck:
        add_cyl(bm, r, r * 0.98, 0.016, lift(M, base + 0.008), seg=18, cap=False); z = base + 0.016
    add_dome(bm, r, r, h, lift(M, z), seg=18, rings=5)
    for k in range(rivets):
        a = TAU * k / rivets + 0.3
        add_ico(bm, 0.0065, lift(M, base + 0.002) @ T((r + flange) / 2 * math.cos(a), (r + flange) / 2 * math.sin(a), 0), sub=1)


def rim(bm, M):
    add_torus(bm, SH_R, 0.0075, M, seg=44, rseg=5)


def clamps(bm, M, n, w=0.03):
    """Edge clamps folded over the rim."""
    for k in range(n):
        a = TAU * k / n + 0.2
        add_box(bm, (0.026, w, SH_T + 0.014), M @ RZ(a) @ T(SH_R - 0.006, 0, 0))


def build_shield(c, x0, M, level, rng):
    F = shield_frame(); n = "T%d Shield " % level
    zb = SH_T / 2 + 0.0012          # base paint
    z1, z2, z3 = zb + 0.0008, zb + 0.0016, zb + 0.0024
    if level == 1:      # bare planks, small plain boss, no rim
        make_object(n + "Board (unpainted)", c, M["wood"], x0, lambda bm: board(bm, F, rng, worn=True))
        make_object(n + "Plank Seams", c, M["wood_dark"], x0, lambda bm: plank_seams(bm, F))
        make_object(n + "Boss", c, M["steel"], x0, lambda bm: boss(bm, F, 0.064, 0.05, neck=False, flange=0.082, rivets=4), smooth=True)
        return
    make_object(n + "Board", c, M["wood"], x0, lambda bm: board(bm, F))
    make_object(n + "Rawhide Rim", c, M["rawhide"], x0, lambda bm: rim(bm, F), smooth=True)
    if level == 2:      # one colour
        make_object(n + "Red Ochre", c, M["p_red"], x0, lambda bm: add_sector(bm, 0.0, SH_R - 0.004, 0, TAU, F, zb, seg=36))
        make_object(n + "Boss", c, M["steel"], x0, lambda bm: boss(bm, F, rivets=4), smooth=True)
    elif level == 3:    # halved red / black
        make_object(n + "Red Half", c, M["p_red"], x0, lambda bm: add_sector(bm, 0.0, SH_R - 0.004, math.pi / 2, 3 * math.pi / 2, F, zb, seg=18))
        make_object(n + "Black Half", c, M["p_black"], x0, lambda bm: add_sector(bm, 0.0, SH_R - 0.004, -math.pi / 2, math.pi / 2, F, zb, seg=18))
        make_object(n + "Boss", c, M["steel"], x0, lambda bm: boss(bm, F, rivets=5), smooth=True)
    elif level == 4:    # Gokstad-style yellow/black segments, red ring at the boss, iron edge clamps
        make_object(n + "Yellow Segments", c, M["p_yellow"], x0, lambda bm: [add_sector(bm, 0.0, SH_R - 0.004, k * TAU / 8, (k + 1) * TAU / 8, F, zb, seg=5) for k in range(0, 8, 2)])
        make_object(n + "Black Segments", c, M["p_black"], x0, lambda bm: [add_sector(bm, 0.0, SH_R - 0.004, k * TAU / 8, (k + 1) * TAU / 8, F, zb, seg=5) for k in range(1, 8, 2)])
        make_object(n + "Red Boss Ring", c, M["p_red"], x0, lambda bm: add_sector(bm, 0.1, 0.15, 0, TAU, F, z1, seg=30))
        make_object(n + "Boss & Clamps", c, M["steel"], x0, lambda bm: (boss(bm, F, rivets=5), clamps(bm, F, 4)), smooth=False)
    elif level == 5:    # curving pinwheel on red, black border band
        make_object(n + "Red Field", c, M["p_red"], x0, lambda bm: add_sector(bm, 0.0, SH_R - 0.004, 0, TAU, F, zb, seg=36))
        make_object(n + "Yellow Pinwheel", c, M["p_yellow"], x0, lambda bm: [add_sector(bm, 0.11, SH_R - 0.05, k * TAU / 6, k * TAU / 6 + 0.42, F, z1, seg=4, twist=1.1) for k in range(6)])
        make_object(n + "Black Border", c, M["p_black"], x0, lambda bm: (add_sector(bm, SH_R - 0.045, SH_R - 0.004, 0, TAU, F, z1, seg=40), add_sector(bm, 0.098, 0.115, 0, TAU, F, z1, seg=28)))
        make_object(n + "Boss & Clamps", c, M["steel"], x0, lambda bm: (boss(bm, F, 0.078, 0.062, flange=0.108, rivets=5), clamps(bm, F, 8)), smooth=False)
    elif level == 6:    # chieftain's shield: interlace ring, triskele, border, gilt boss fittings
        make_object(n + "Red Field", c, M["p_red"], x0, lambda bm: add_sector(bm, 0.0, SH_R - 0.004, 0, TAU, F, zb, seg=40))
        make_object(n + "Black Bands", c, M["p_black"], x0, lambda bm: (add_sector(bm, SH_R - 0.05, SH_R - 0.004, 0, TAU, F, z1, seg=44), add_sector(bm, 0.255, 0.275, 0, TAU, F, z1, seg=40), add_sector(bm, 0.1, 0.12, 0, TAU, F, z1, seg=30)))
        def interlace(bm):   # ring of interlocking S-curves between r = 0.29 and 0.39 (Jellinge-style sigmoid band)
            for k in range(14):
                a0 = TAU * k / 14; pts = []
                for i in range(15):
                    t = i / 14 * 2 - 1
                    r = 0.34 + 0.045 * t; a = a0 + 0.22 * math.sin(math.pi * t) + 0.16 * t
                    pts.append((r * math.cos(a), r * math.sin(a)))
                add_ribbon(bm, pts, 0.016, F, z2)
            add_sector(bm, SH_R - 0.04, SH_R - 0.03, 0, TAU, F, z2, seg=44)            # thin yellow line inside the border
        make_object(n + "Yellow Interlace", c, M["p_yellow"], x0, interlace)
        def triskele(bm):    # three curling arms between boss ring and inner band
            for j in range(3):
                pts = []
                for i in range(22):
                    t = i / 21; r = 0.135 + 0.1 * t; a = j * TAU / 3 + 2.4 * t
                    pts.append((r * math.cos(a), r * math.sin(a)))
                end = Vector(pts[-1]); a_end = j * TAU / 3 + 2.4
                for i in range(1, 10):                                                   # tight curl at the tip
                    a = a_end + i * 0.55; rr = 0.04 * (1 - i / 11)
                    cx, cy = end.x - 0.04 * math.cos(a_end), end.y - 0.04 * math.sin(a_end)
                    pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
                add_ribbon(bm, pts, 0.02, F, z2)
        make_object(n + "White Triskele", c, M["p_white"], x0, triskele)
        make_object(n + "Iron Boss", c, M["steel"], x0, lambda bm: boss(bm, F, 0.078, 0.064, flange=0.11, rivets=0), smooth=True)
        def gilt(bm):        # gilt-bronze collar, rivets, boss knob and edge clamps
            add_torus(bm, 0.079, 0.007, lift(F, SH_T / 2 + 0.02), seg=24, rseg=5)
            for k in range(6):
                a = TAU * k / 6
                add_ico(bm, 0.0075, lift(F, SH_T / 2 + 0.005) @ T(0.094 * math.cos(a), 0.094 * math.sin(a), 0), sub=1)
            add_sphere(bm, 0.013, lift(F, SH_T / 2 + 0.018 + 0.064), u=8, v=5)
            clamps(bm, F, 12, 0.026)
        make_object(n + "Gilt Bronze Fittings", c, M["gold"], x0, gilt, smooth=True)

# ============================================================== the six tiers
def tier1(c, x0, M, rng):
    """Thrall / poor bondi: no armour at all."""
    make_object("T1 Worn Wool Tunic", c, M["cloth"], x0, lambda bm: tunic(bm, 0.66, 0.02, "long", 0.064, rng, tatter=0.05), [SOLID(0.007)], smooth=True)
    make_object("T1 Cord Belt", c, M["cord"], x0, lambda bm: cord_belt(bm, 1.0, 0.03), smooth=True)
    make_object("T1 Trousers", c, M["cloth"], x0, lambda bm: trousers(bm, 0.012), [MIRROR_X], smooth=True)
    make_object("T1 Winingas", c, M["cloth"], x0, winingas, [MIRROR_X], smooth=True)
    make_object("T1 Turnshoes", c, M["leather"], x0, turnshoes, [MIRROR_X, BEVEL(0.012)])


def tier2(c, x0, M, rng):
    """Free levy: spear-and-shield man; quilted coat, felt cap, cloak."""
    make_object("T2 Plant-Dyed Tunic", c, M["green"], x0, lambda bm: tunic(bm, 0.62, 0.018, "long", 0.064), [SOLID(0.006)], smooth=True)
    make_object("T2 Quilted Padded Coat", c, M["linen"], x0, lambda bm: tunic(bm, 0.72, 0.04, "long", 0.072, ridge=0.009), [SOLID(0.012)], smooth=True)
    make_object("T2 Leather Belt", c, M["leather"], x0, lambda bm: belt(bm, 1.0, 0.035, 0.068), [SOLID(0.006)])
    make_object("T2 Iron Buckle", c, M["steel"], x0, lambda bm: buckle(bm, 1.0, 0.075), [BEVEL(0.003)])
    def cap(bm):   # soft felt cap
        add_dome(bm, HEAD_R * 0.9 + 0.012, HEAD_R * 0.98 + 0.012, 0.115, T(HEAD_C.x, HEAD_C.y, HEAD_C.z + 0.025), seg=16, rings=5)
        add_lathe(bm, [(HEAD_R * 0.9 + 0.02, HEAD_C.z + 0.015), (HEAD_R * 0.9 + 0.02, HEAD_C.z + 0.045)], T(HEAD_C.x, HEAD_C.y, 0), seg=16, sy=1.08)
    make_object("T2 Felt Cap", c, M["cloth"], x0, cap, [SOLID(0.006)], smooth=True)
    make_object("T2 Wool Cloak", c, M["dark"], x0, lambda bm: cloak(bm, 0.68, 0.02, rng), [SOLID(0.008)], smooth=True)
    make_object("T2 Iron Ring-Pin", c, M["steel"], x0, lambda bm: ring_pin(bm, (-0.175, -0.13, 1.42), 0.026))
    make_object("T2 Trousers", c, M["cloth"], x0, lambda bm: trousers(bm, 0.012), [MIRROR_X], smooth=True)
    make_object("T2 Winingas", c, M["cloth"], x0, winingas, [MIRROR_X], smooth=True)
    make_object("T2 Turnshoes", c, M["leather"], x0, turnshoes, [MIRROR_X, BEVEL(0.012)])


def tier3(c, x0, M, rng):
    """Experienced warrior: padded coat, fur cape, seax, plain iron cap with nasal."""
    make_object("T3 Wool Tunic", c, M["green"], x0, lambda bm: tunic(bm, 0.6, 0.018, "long", 0.064), [SOLID(0.006)], smooth=True)
    make_object("T3 Padded Coat", c, M["linen"], x0, lambda bm: tunic(bm, 0.7, 0.04, "long", 0.072, ridge=0.009), [SOLID(0.012)], smooth=True)
    make_object("T3 Fur Shoulder Cape", c, M["fur"], x0, lambda bm: fur_cape(bm, rng), [SOLID(0.02)], smooth=True)
    make_object("T3 Belt & Seax Sheath", c, M["leather"], x0, lambda bm: (belt(bm, 1.0, 0.035, 0.068), seax(bm, 1.0, 0.075)), [SOLID(0.006)])
    make_object("T3 Buckle & Seax Hilt", c, M["steel"], x0, lambda bm: (buckle(bm, 1.0, 0.075), seax_hilt(bm, 1.0, 0.075)), [BEVEL(0.002)])
    def helm(bm):
        rx, ry, bz, top = helmet_bowl(bm, 0.016)
        brow_band(bm, rx, ry, bz); cross_bands(bm, rx, ry, bz, top); nasal(bm, bz, ry + 0.006)
    make_object("T3 Iron Cap with Nasal", c, M["steel"], x0, helm, [SOLID(0.004)])
    make_object("T3 Trousers", c, M["dark"], x0, lambda bm: trousers(bm, 0.012), [MIRROR_X], smooth=True)
    make_object("T3 Winingas", c, M["cloth"], x0, winingas, [MIRROR_X], smooth=True)
    make_object("T3 Ankle Boots", c, M["leather"], x0, turnshoes, [MIRROR_X, BEVEL(0.012)])


def tier4(c, x0, M, rng):
    """Hirdman: hip-length byrnie over the padded coat, Gjermundbu-type helmet."""
    make_object("T4 Woad-Blue Tunic", c, M["blue"], x0, lambda bm: tunic(bm, 0.6, 0.018, "long", 0.064), [SOLID(0.006)], smooth=True)
    make_object("T4 Padded Coat", c, M["linen"], x0, lambda bm: tunic(bm, 0.68, 0.036, "long", 0.07, ridge=0.008), [SOLID(0.01)], smooth=True)
    make_object("T4 Mail Byrnie", c, M["mail"], x0, lambda bm: byrnie(bm, 0.74, "elbow", 0.06), [SOLID(0.008)], smooth=True)
    make_object("T4 Sword Belt", c, M["leather"], x0, lambda bm: belt(bm, 1.0, 0.035, 0.085), [SOLID(0.006)])
    make_object("T4 Buckle", c, M["steel"], x0, lambda bm: buckle(bm, 1.0, 0.092), [BEVEL(0.002)])
    def helm(bm):
        rx, ry, bz, top = helmet_bowl(bm, 0.018)
        brow_band(bm, rx, ry, bz); cross_bands(bm, rx, ry, bz, top); spectacles(bm, bz, ry)
        add_cyl(bm, 0.012, 0.004, 0.022, T(HEAD_C.x, HEAD_C.y, top + 0.008), seg=8)        # spike knob
    make_object("T4 Gjermundbu Helmet", c, M["steel"], x0, helm, [SOLID(0.004)])
    make_object("T4 Mail Aventail", c, M["mail"], x0, lambda bm: aventail(bm, HEAD_R * 0.9 + 0.018, HEAD_C.z + 0.035), [SOLID(0.006)], smooth=True)
    make_object("T4 Trousers", c, M["dark"], x0, lambda bm: trousers(bm, 0.012), [MIRROR_X], smooth=True)
    make_object("T4 Winingas", c, M["cloth"], x0, winingas, [MIRROR_X], smooth=True)
    make_object("T4 Turnshoes", c, M["leather"], x0, turnshoes, [MIRROR_X, BEVEL(0.012)])


def tier5(c, x0, M, rng):
    """Eastern-route elite (Birka garrison): lamellar over mail, conical nasal helmet."""
    make_object("T5 Wool Tunic", c, M["green"], x0, lambda bm: tunic(bm, 0.6, 0.018, "long", 0.064), [SOLID(0.006)], smooth=True)
    make_object("T5 Padded Coat", c, M["linen"], x0, lambda bm: tunic(bm, 0.66, 0.034, "long", 0.07, ridge=0.008), [SOLID(0.01)], smooth=True)
    make_object("T5 Mail Shirt", c, M["mail"], x0, lambda bm: byrnie(bm, 0.72, "forearm", 0.056), [SOLID(0.008)], smooth=True)
    make_object("T5 Lamellar Cuirass", c, M["steel"], x0, lambda bm: lamellar_rows(bm, 0.97, 1.4, 0.085), [BEVEL(0.0012)])
    make_object("T5 Lamellar Shoulder Straps", c, M["leather"], x0, lambda bm: lamellar_straps(bm, 0.1), [MIRROR_X])
    make_object("T5 Belt", c, M["leather"], x0, lambda bm: belt(bm, 0.96, 0.04, 0.115), [SOLID(0.006)])
    def helm(bm):
        rx, ry, bz, top = conical_bowl(bm, 0.018)
        brow_band(bm, rx, ry, bz, 0.022)
        for k in range(4):                                                     # riveted segment seams
            a = k * math.pi / 2 + math.pi / 4
            pts = [Vector((math.cos(a) * rx * f + HEAD_C.x, math.sin(a) * ry * f + HEAD_C.y, bz + h)) for f, h in ((1.0, 0.0), (0.93, 0.07), (0.8, 0.11), (0.6, 0.15), (0.36, 0.185), (0.12, 0.205))]
            for p, q in zip(pts, pts[1:]): add_limb(bm, p * 1.0 + (p - Vector((HEAD_C.x, HEAD_C.y, p.z))) * 0.04, q + (q - Vector((HEAD_C.x, HEAD_C.y, q.z))) * 0.04, 0.005, 0.005, seg=4)
        nasal(bm, bz, ry + 0.006, 0.08)
    make_object("T5 Conical Nasal Helmet", c, M["steel"], x0, helm, [SOLID(0.004)])
    make_object("T5 Mail Aventail", c, M["mail"], x0, lambda bm: aventail(bm, HEAD_R * 0.9 + 0.018, HEAD_C.z + 0.035, gap=0.65), [SOLID(0.006)], smooth=True)
    make_object("T5 Wide Trousers", c, M["cloth"], x0, lambda bm: trousers(bm, 0.03), [MIRROR_X], smooth=True)
    make_object("T5 Winingas", c, M["cloth"], x0, winingas, [MIRROR_X], smooth=True)
    make_object("T5 Boots", c, M["leather"], x0, turnshoes, [MIRROR_X, BEVEL(0.012)])


def tier6(c, x0, M, rng):
    """Jarl / chieftain: long byrnie, gilt heirloom helmet, fur-lined madder cloak, gold and silver."""
    make_object("T6 Madder-Red Tunic", c, M["red"], x0, lambda bm: tunic(bm, 0.56, 0.018, "long", 0.064), [SOLID(0.006)], smooth=True)
    make_object("T6 Tunic Trim", c, M["trim"], x0, lambda bm: trims(bm, 0.56, 0.026, 0.064, hem=True, neck=False), smooth=True)
    make_object("T6 Padded Coat", c, M["linen"], x0, lambda bm: tunic(bm, 0.62, 0.034, "forearm", 0.07, ridge=0.008), [SOLID(0.01)], smooth=True)
    make_object("T6 Long Byrnie", c, M["mail"], x0, lambda bm: byrnie(bm, 0.6, "forearm", 0.056), [SOLID(0.009)], smooth=True)
    make_object("T6 Sword Belt", c, M["leather"], x0, lambda bm: belt(bm, 1.0, 0.04, 0.085), [SOLID(0.006)])
    def fittings(bm):   # gilt buckle, strap-end and belt mounts (Borre/Jellinge-style metalwork)
        buckle(bm, 1.0, 0.093, (0.055, 0.012, 0.05))
        y = belt_front_y(1.0, 0.093)
        add_box(bm, (0.02, 0.01, 0.13), T(0.045, y - 0.006, 0.93))
        for k in (-2, -1, 1, 2):
            a = -math.pi / 2 + k * 0.42; R = torso_r(1.0) + 0.093
            add_box(bm, (0.02, 0.008, 0.03), T(R * math.cos(a), R * math.sin(a) * sqo(0.093, 1.0), 1.0) @ RZ(a - math.pi / 2))
    make_object("T6 Gilt Belt Fittings", c, M["gold"], x0, fittings, [BEVEL(0.002)])
    def helm(bm):
        rx, ry, bz, top = helmet_bowl(bm, 0.022, HEAD_C.z + 0.04)
        cross_bands(bm, rx, ry, bz, top, 0.006, both=False)
        spectacles(bm, bz, ry + 0.002)
    make_object("T6 Crested Helmet", c, M["steel"], x0, helm, [SOLID(0.0045)])
    def helm_gilt(bm):   # gilt-bronze crest, brow plate and eyebrows (ValsgÃ¤rde/Vendel tradition)
        rx, ry, bz, top = HEAD_R * 0.9 + 0.022, HEAD_R * 0.98 + 0.022, HEAD_C.z + 0.04, HEAD_C.z + HEAD_R * 1.08 + 0.022
        brow_band(bm, rx, ry, bz, 0.026, 0.007)
        pts = [Vector((HEAD_C.x, HEAD_C.y + math.cos(t) * (ry + 0.014), bz + math.sin(t) * (top - bz + 0.014))) for t in [math.pi * i / 14 for i in range(15)]]
        for a, b in zip(pts, pts[1:]): add_limb(bm, a, b, 0.009, 0.009, seg=5)                        # crest
        fy = HEAD_C.y - ry - 0.014
        for sx in (1, -1):                                                                              # eyebrows
            arc = [Vector((sx * (0.008 + 0.055 * t), fy + 0.02 * (t - 0.5) ** 2, bz - 0.004 + 0.012 * math.sin(math.pi * t))) for t in [k / 6 for k in range(7)]]
            for a, b in zip(arc, arc[1:]): add_limb(bm, a, b, 0.0065, 0.0065, seg=5)
            add_ico(bm, 0.01, T(sx * 0.066, fy + 0.012, bz - 0.006), sub=1)                              # animal-head terminals
    make_object("T6 Helmet Gilt Bronze", c, M["gold"], x0, helm_gilt, smooth=True)
    make_object("T6 Full Mail Curtain", c, M["mail"], x0, lambda bm: aventail(bm, HEAD_R * 0.9 + 0.022, HEAD_C.z + 0.04, gap=0.42, drop_r=0.22, drop_z=1.4), [SOLID(0.006)], smooth=True)
    make_object("T6 Madder Wool Cloak", c, M["red"], x0, lambda bm: cloak(bm, 0.42, 0.05, rng), [SOLID(0.01)], smooth=True)
    make_object("T6 Fur Lining & Collar", c, M["fur"], x0, lambda bm: (cloak(bm, 0.44, 0.035, None), jitter(add_torus(bm, 0.2, 0.05, T(0, 0.02, 1.49) @ S(1.25, 0.9, 0.7), seg=20, rseg=6), 0.01, rng)), [SOLID(0.015)], smooth=True)
    make_object("T6 Cloak Trim", c, M["trim"], x0, lambda bm: add_lathe(bm, [(0.42, 0.42), (0.425, 0.455)], T(0, 0.015, 0), seg=18, sy=0.78, a0=-1.25, a1=2.95), [SOLID(0.006)])
    make_object("T6 Gilt Penannular Brooch", c, M["gold"], x0, lambda bm: ring_pin(bm, (-0.19, -0.14, 1.43), 0.042, 0.008), smooth=True)
    make_object("T6 Gold Arm Rings", c, M["gold"], x0, lambda bm: arm_ring(bm, 1, 0.55, 0.088, 0.0065, 2), [MIRROR_X], smooth=True)
    make_object("T6 Silver Neck Ring", c, M["silver"], x0, neck_ring, smooth=True)
    make_object("T6 Wide Trousers", c, M["blue"], x0, lambda bm: trousers(bm, 0.03), [MIRROR_X], smooth=True)
    make_object("T6 Winingas", c, M["red"], x0, winingas, [MIRROR_X], smooth=True)
    make_object("T6 Turnshoes", c, M["leather"], x0, turnshoes, [MIRROR_X, BEVEL(0.012)])

# ============================================================== labels, camera, light
def add_label(coll, x0, text):
    cu = bpy.data.curves.new("ArmorLabel", 'FONT'); cu.body = text; cu.size = 0.1; cu.align_x = 'CENTER'
    ob = bpy.data.objects.new("Label " + text.split("\n")[0], cu)
    ob.location = (x0, -0.6, 0.26); ob.rotation_euler = (math.pi / 2, 0, 0)
    coll.objects.link(ob)


def ensure_camera_and_light(n):
    scene = bpy.context.scene
    if not any(o.type == 'LIGHT' for o in scene.objects):
        sun = bpy.data.objects.new("Armor Sun", bpy.data.lights.new("Armor Sun", 'SUN'))
        sun.data.energy = 3.0; sun.rotation_euler = (math.radians(55), 0, math.radians(-30))
        scene.collection.objects.link(sun)
    if scene.camera is None:
        cam = bpy.data.objects.new("Armor Camera", bpy.data.cameras.new("Armor Camera"))
        mid = (n - 1) * SPACING / 2
        cam.location = (mid, -13.5, 1.5); cam.rotation_euler = (math.radians(87), 0, 0); cam.data.lens = 32
        scene.collection.objects.link(cam); scene.camera = cam

# ============================================================== MakeHuman bodies (optional: MPFB + MakeHuman data + mh_character.py)
# Head, neck and hands come from a posed MakeHuman man; tunics, coats, mail and trousers are cut from his body
# surface; belts, lamellar, helmets and jewellery are sized from his measured torso, legs and head.
MH_CH, MHC_MOD = None, None
_BASE = dict(HEAD_C=HEAD_C.copy(), HEAD_R=HEAD_R, TORSO=list(TORSO), SQ=SQ, HIP=HIP.copy(), KNEE=KNEE.copy(), ANKLE=ANKLE.copy(),
             SHOULDER=SHOULDER.copy(), ELBOW=ELBOW.copy(), WRIST=WRIST.copy())
VK_CAST = {   # most free men bearded; hair hidden where a helmet and mail curtain cover it
    1: dict(macro=dict(age=0.3, muscle=0.5, weight=0.42), skin="young_caucasian_male", eye="lightblue", hair="long01", tint=(0.42, 0.3, 0.16), beard="short", hair_on=True),
    2: dict(macro=dict(age=0.42, muscle=0.6, weight=0.5), skin="young_caucasian_male", eye="blue", hair="short02", tint=(0.55, 0.42, 0.22), beard="full", hair_on=True),
    3: dict(macro=dict(age=0.5, muscle=0.7, weight=0.55), skin="middleage_caucasian_male", eye="bluegreen", hair="short02", tint=(0.42, 0.17, 0.06), beard="full", hair_on=True),
    4: dict(macro=dict(age=0.48, muscle=0.75, weight=0.55), skin="middleage_caucasian_male", eye="grey", hair=None, tint=(0.2, 0.13, 0.07), beard="full", hair_on=False),
    5: dict(macro=dict(age=0.45, muscle=0.72, weight=0.52), skin="young_caucasian_male", eye="brownlight", hair=None, tint=(0.3, 0.2, 0.1), beard="full", hair_on=False),
    6: dict(macro=dict(age=0.62, muscle=0.7, weight=0.62), skin="middleage_caucasian_male", eye="ice", hair=None, tint=(0.58, 0.5, 0.38), beard="full", hair_on=False),
}


def _load_mh():
    import os, importlib.util
    here = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else bpy.path.abspath("//")
    path = os.path.join(here, "mh_character.py")
    if not os.path.exists(path): return None
    try:
        import addon_utils
        if not any(m.__name__.endswith("mpfb") for m in addon_utils.modules()): return None
        spec = importlib.util.spec_from_file_location("mh_character", path); mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        return mod
    except Exception as e:
        print("MakeHuman bodies unavailable, using mannequins:", e); return None


def _set_body(**kw):
    global SLEEVE_END
    g = globals()
    for k, v in kw.items(): g[k] = v
    S_, E_, W_ = g["SHOULDER"], g["ELBOW"], g["WRIST"]
    SLEEVE_END = {"short": S_.lerp(E_, 0.55), "elbow": E_, "forearm": E_.lerp(W_, 0.6), "long": W_ + Vector((0, 0, 0.04))}


def mh_reset():
    global MH_CH
    MH_CH = None; _set_body(**{k: (v.copy() if hasattr(v, "copy") else v) for k, v in _BASE.items()})


def build_mh_body(coll, x0, tier):
    global MH_CH
    mh_reset(); cfg = VK_CAST[tier]
    macro = {"gender": 1.0, "proportions": 0.6, "height": 0.5, "cupsize": 0.5, "firmness": 0.5, "race": {"asian": 0.0, "caucasian": 1.0, "african": 0.0}}
    macro.update(cfg["macro"])
    ch = MHC_MOD.MHCharacter(macro, skin=cfg["skin"], name="VTier%d" % tier)
    ch.fit_height(_BASE["HEAD_C"].z + 0.117, (_BASE["HEAD_C"].x, _BASE["HEAD_C"].y))
    k = MHC_MOD.kit_constants(ch, _BASE["TORSO"])
    hair_pad = 0.016 if cfg["hair_on"] and cfg["hair"] else 0.004
    # arms hang as on the mannequin, with this man's shoulders and bone lengths (+X side; the kit mirrors it)
    sh = ch.shoulder("L"); Lu, Lf = ch.arm_lengths("L")
    el = sh + (_BASE["ELBOW"] - _BASE["SHOULDER"]).normalized() * Lu; wr = el + (_BASE["WRIST"] - _BASE["ELBOW"]).normalized() * Lf
    for s, sx in (("L", 1), ("R", -1)):
        m = lambda p: Vector((p.x * sx, p.y, p.z))
        shs = ch.shoulder(s); ch.aim_arm(s, shs + m(el - sh), shs + m(wr - sh)); ch.curl_fingers(s, 0.35)
    _set_body(HEAD_C=k["head_c"], HEAD_R=max(0.108, (k["crown"] + hair_pad - k["head_c"].z) / 1.08), TORSO=k["torso"], SQ=k["sq"],
              HIP=k["hip"], KNEE=k["knee"], ANKLE=k["ankle"], SHOULDER=sh, ELBOW=el, WRIST=wr)
    ch.add_face(eye=cfg["eye"], hair=cfg["hair"], hair_tint=cfg["tint"], beard=cfg["beard"])
    obs = ch.bake(show=("head", "neck", "hands"), hair=cfg["hair_on"], name="T%d MakeHuman Body" % tier,
                  neck_column=(1.43, 0.105, ch.joint("neck_01").y - 0.01))
    for ob in obs:
        for c in ob.users_collection: c.objects.unlink(ob)
        coll.objects.link(ob); ob.location = (x0, 0.0, 0.0)
    MH_CH = ch
    return ch


# ============================================================== main
TIERS = [
    ("Thrall / Poor Bondi", tier1), ("Free Levy", tier2), ("Experienced Warrior", tier3),
    ("Hirdman - Byrnie & Gjermundbu", tier4), ("Birka Lamellar Elite", tier5), ("Jarl / Chieftain", tier6),
]


# ============================================================== store / scanned gear (optional: asset_library + warrior_gear.py)
# Historical pieces from the Unity Asset Store "Warrior viking" (shirt/trousers/boots, long padded tunic, studded belt
# with knotwork buckle, pouch, hip fur, neck toggles) refitted to each MakeHuman man, plus real-textured shields
# (FunFant Viking Shields: 1 bare wood .. 9 sunburst) and weapons (Bek spear/hatchet, Snake3D axe, FunFant sword,
# Seven Swords Ulfberht). Our own mail, lamellar, helmets, cloaks and jewellery stay, layered outside the tunic.
WG_MOD = None
WARRIOR_KIT = {
    1: dict(pieces=[], skip=set(), push=[], shield=1, weapon="hatchet"),
    2: dict(pieces=["Body", "Bag"], skip={"T2 Plant-Dyed Tunic", "T2 Trousers", "T2 Winingas", "T2 Turnshoes"},
            push=[("T2 Quilted Padded Coat", ["Body"])], shield=4, weapon="spear"),
    3: dict(pieces=["Body", "Coat", "Belt_2", "Bag", "Fur"],
            skip={"T3 Wool Tunic", "T3 Padded Coat", "T3 Fur Shoulder Cape", "T3 Belt & Seax Sheath", "T3 Buckle & Seax Hilt", "T3 Trousers", "T3 Winingas", "T3 Ankle Boots"},
            push=[], shield=5, weapon="battleaxe"),
    4: dict(pieces=["Body", "Coat", "Belt_2", "Bag"],
            skip={"T4 Woad-Blue Tunic", "T4 Padded Coat", "T4 Sword Belt", "T4 Buckle", "T4 Trousers", "T4 Winingas", "T4 Turnshoes"},
            push=[("T4 Mail Byrnie", ["Coat"])], shield=7, weapon="sword"),
    5: dict(pieces=["Body", "Coat", "Belt_2", "Bag"],
            skip={"T5 Wool Tunic", "T5 Padded Coat", "T5 Belt", "T5 Wide Trousers", "T5 Winingas", "T5 Boots"},
            push=[("T5 Mail Shirt", ["Coat"]), ("T5 Lamellar Cuirass", ["T5 Mail Shirt", "Coat"])], shield=8, weapon="spear"),
    6: dict(pieces=["Body", "Coat", "Belt_2", "Bag", "Fur", "Accessories"],
            skip={"T6 Madder-Red Tunic", "T6 Tunic Trim", "T6 Padded Coat", "T6 Sword Belt", "T6 Gilt Belt Fittings", "T6 Wide Trousers", "T6 Winingas", "T6 Turnshoes"},
            push=[("T6 Long Byrnie", ["Coat"])], shield=9, weapon="ulfberht"),
}
WEAPONS = {   # (pack folder, model, material maker args, real length m, grip fraction from the head-down end, head up?)
    "hatchet": ("Medieval_Weapons_Bek/Medieval_Weapons/Hatchet", "Model/hatchet.fbx", ("Textures/hatchet_AlbedoTransparency.png", "Textures/hatchet_Normal.png", "unity", "Textures/hatchet_MetallicSmoothness.png"), 0.62, 0.3, True),
    "spear": ("Medieval_Weapons_Bek/Medieval_Weapons/Spear", "Model/spear.fbx", ("Textures/spear_AlbedoTransparency.png", "Textures/spear_Normal.png", "unity", "Textures/spear_MetallicSmoothness.png"), 2.2, 0.0, True),
    "battleaxe": ("Battle_Axe_Snake3D/Snake3D/Battle Axe", "Models/axe.fbx", ("Textures/T_axe_BaseMap.png", "Textures/T_axe_Normal.png", "hdrp", "Textures/T_axe_MaskMap.png"), 0.9, 0.3, True),
    "sword": ("Viking_Swords_FunFant/Viking Swords", "models/sword_1.fbx", ("textures/sword1_clean_diffuse.png", "textures/sword1_clean_normal.png", "unity", "textures/sword1_clean_metallic.png"), 0.92, None, False),
    "ulfberht": ("Seven_Swords_PerpetualDiversion/Seven Swords/Swords", "Meshes/Ulfberht/Ulfberht_V2.fbx", ("Textures/Ulfberht/T_SM_Ulfberht_A.png", "Textures/Ulfberht/T_SM_Ulfberht_N.png", "hdrp", "Textures/Ulfberht/T_SM_Ulfberht_Mask.png"), 0.94, None, False),
}


def _load_wg():
    global WG_MOD
    import os, importlib.util
    here = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else bpy.path.abspath("//")
    p = os.path.join(here, "warrior_gear.py")
    if not os.path.exists(p): return
    spec = importlib.util.spec_from_file_location("warrior_gear", p); WG_MOD = importlib.util.module_from_spec(spec); spec.loader.exec_module(WG_MOD)
    if not os.path.isdir(WG_MOD.WARRIOR): WG_MOD = None


def _eval_bvh(objs):
    """BVH of objects as rendered (modifiers applied: solidify, mirror...)."""
    from mathutils.bvhtree import BVHTree
    dg = bpy.context.evaluated_depsgraph_get(); verts, polys, off = [], [], 0
    for o in objs:
        ev = o.evaluated_get(dg); me = ev.to_mesh(); M = o.matrix_world
        verts += [M @ v.co for v in me.vertices]; polys += [[i + off for i in p.vertices] for p in me.polygons]; off += len(me.vertices); ev.to_mesh_clear()
    return BVHTree.FromPolygons(verts, polys)


def radial_push(obj, under, cx, cy=0.0, gap=0.006):
    """Push a torso-wrapping piece (belt, lamellar, toggles, pouch) straight out from the body's vertical axis until it
    clears the outermost surface of `under` (evaluated, so solidified mail counts at full thickness)."""
    bvh = _eval_bvh(under); M = obj.matrix_world; Mi = M.inverted(); n = 0
    for v in obj.data.vertices:
        w = M @ v.co; d = Vector((w.x - cx, w.y - cy, 0.0))
        if d.length < 1e-4: continue
        d.normalize(); hit = bvh.ray_cast(Vector((cx, cy, w.z)) + d * 1.5, -d)
        if hit[0] is None: continue
        r_out = (hit[0] - Vector((cx, cy, w.z))).length; r_v = (Vector((w.x - cx, w.y - cy, 0))).length
        if r_v < r_out + gap: v.co = Mi @ (Vector((cx, cy, w.z)) + d * (r_out + gap)); n += 1
    obj.data.update(); return n


def _orient_weapon(ob, head_up):
    """Turn a long prop so its long axis is Z and its head (the heavier, wider end) points up (or down for swords)."""
    import os
    vs = [v.co for v in ob.data.vertices]
    ext = [max(v[i] for v in vs) - min(v[i] for v in vs) for i in range(3)]; ax = ext.index(max(ext))
    if ax == 0: ob.data.transform(Matrix.Rotation(math.pi / 2, 4, 'Y'))
    elif ax == 1: ob.data.transform(Matrix.Rotation(-math.pi / 2, 4, 'X'))
    lo_w, hi_w = WG_MOD.end_widths(ob, 2, 0.25)
    vs = [v.co for v in ob.data.vertices]; lo, hi = min(v.z for v in vs), max(v.z for v in vs)
    n_lo = sum(1 for v in vs if v.z < lo + (hi - lo) * 0.15); n_hi = sum(1 for v in vs if v.z > hi - (hi - lo) * 0.15)
    head_is_hi = hi_w > lo_w * 1.15 or (abs(hi_w - lo_w) <= lo_w * 0.15 and n_hi >= n_lo)
    if head_is_hi != head_up: ob.data.transform(Matrix.Rotation(math.pi, 4, 'X'))


def add_store_gear(coll, x0, tier, kit, ch):
    import os
    W = WG_MOD; LIB = W.LIB
    gear = {}
    if kit["pieces"]:
        wg = W.WarriorGear(ch); gear = wg.fit(kit["pieces"]); wg.remove()
        for n, o in gear.items():
            for c in o.users_collection: c.objects.unlink(o)
            coll.objects.link(o); o.name = "T%d %s (store)" % (tier, n); o.location.x += x0
        bpy.context.view_layer.update()
    ours = {o.name: o for o in coll.objects if o.type == 'MESH'}
    find = lambda nm: gear.get(nm) or ours.get(nm)
    # layering: our pieces that now sit over the store tunic, then belt / pouch / fur / toggles over everything
    if "Coat" in gear and "Body" in gear: W.push_out(gear["Coat"], [gear["Body"]], 0.004)
    for nm, inner in kit["push"]:
        o = find(nm); inn = [find(i) for i in inner if find(i)]
        if not (o and inn): continue
        if "Lamellar" in nm: print("SL_PUSH", nm, radial_push(o, inn, x0, 0.0, 0.008))     # rigid plates: move straight out
        else: print("SL_PUSH", nm, W.push_out(o, None, 0.006, inner_bvh=_eval_bvh(inn)))
    under = [o for o in (gear.get("Coat"), gear.get("Body"), *[find(nm) for nm, _ in kit["push"]]) if o]
    for k in ("Belt_2", "Accessories", "Bag", "Fur"):                       # belt first, then what hangs from it
        if k in gear and under:
            print("SL_PUSH", k, radial_push(gear[k], under, x0, 0.0, 0.005))
            if k == "Belt_2": under = under + [gear[k]]
    # shield: FunFant design per tier, leaning at the left side like the procedural ones (face toward the viewer)
    D = os.path.join(LIB, "Viking_Shields_FunFant", "Viking Shields"); i = kit["shield"]; T = os.path.join(D, "textures", "shield%d_" % i)
    sm = W.pbr_material("SC_VikingShield%d" % i, T + "diffuse.png", T + "normal.png", unity_metal_smooth=T + "metallic.png", rough_range=(0.3, 0.85))
    sh = W.import_prop(os.path.join(D, "models", "shield.fbx"), sm, 0.85)
    sh.data.transform(Matrix.Rotation(math.pi, 4, 'Z'))                               # model faces +Y; ours face -Y
    sh.matrix_world = Matrix.Translation((0.82 + x0, -0.04, 0.425 * math.cos(SH_TILT) + 0.006)) @ RZ(SH_YAW) @ RX(-SH_TILT)
    sh.name = "T%d Shield (store design %d)" % (tier, i)
    for c in sh.users_collection: c.objects.unlink(sh)
    coll.objects.link(sh)
    # weapon in the right hand (shoulder/elbow/wrist globals are the +X side: mirror them)
    if kit["weapon"]:
        folder, model, (alb, nrm, pack, ms), length, grip_frac, head_up = WEAPONS[kit["weapon"]]
        base = os.path.join(LIB, folder); kw = {"unity_metal_smooth" if pack == "unity" else "hdrp_mask": os.path.join(base, ms)}
        wm = W.pbr_material("SC_" + kit["weapon"].title(), os.path.join(base, alb), os.path.join(base, nrm), rough_range=(0.25, 0.8), **kw)
        wp = W.import_prop(os.path.join(base, model), wm)
        _orient_weapon(wp, head_up)
        vs = [v.co for v in wp.data.vertices]; s = length / (max(v.z for v in vs) - min(v.z for v in vs)); wp.data.transform(Matrix.Scale(s, 4))
        vs = [v.co for v in wp.data.vertices]; lo, hi = min(v.z for v in vs), max(v.z for v in vs)
        wr = Vector((-WRIST.x, WRIST.y, WRIST.z)); el = Vector((-ELBOW.x, ELBOW.y, ELBOW.z)); grip = wr + (wr - el).normalized() * 0.06
        if grip_frac is None: z = grip.z - (hi - 0.13)             # sword: hilt in the fist, blade hanging point-down
        elif grip_frac == 0.0: z = 0.02 - lo                       # spear: butt on the ground, shaft through the fist
        else: z = grip.z - (lo + (hi - lo) * grip_frac)
        wp.location = (grip.x + x0, grip.y, z); wp.name = "T%d %s (store)" % (tier, kit["weapon"].title())
        for c in wp.users_collection: c.objects.unlink(wp)
        coll.objects.link(wp)
    print("SL_STORE_GEAR tier", tier, "pieces", sorted(gear), "shield", i, "weapon", kit["weapon"])


def main():
    global MHC_MOD
    clear_scene()
    mats = build_materials(); MHC_MOD = _load_mh(); _load_wg()
    for i, (title, fn) in enumerate(TIERS):
        x0 = i * SPACING
        coll = bpy.data.collections.new("Tier %d - %s" % (i + 1, title))
        bpy.context.scene.collection.children.link(coll)
        ch = build_mh_body(coll, x0, i + 1) if MHC_MOD is not None else build_mannequin(coll, x0, mats)
        kit = WARRIOR_KIT.get(i + 1) if (MHC_MOD is not None and WG_MOD is not None) else None
        SKIP.clear(); SKIP.update(kit["skip"] if kit else ())
        fn(coll, x0, mats, random.Random(SEED + i))
        if kit: add_store_gear(coll, x0, i + 1, kit, ch)
        else: build_shield(coll, x0, mats, i + 1, random.Random(SEED + 100 + i))
        SKIP.clear()
        if MHC_MOD is not None: ch.remove_rig(); mh_reset()
        add_label(coll, x0, "TIER %d\n%s" % (i + 1, title))
    ensure_camera_and_light(len(TIERS))
    print("Viking Age armor tiers generated:", ", ".join(c.name for c in bpy.data.collections if c.name.startswith("Tier ")))


if __name__ == "__main__":
    main()
