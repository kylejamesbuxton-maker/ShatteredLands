"""
Gaelic & Scottish Soldiers, Tiers 1-6 — historically grounded procedural low-poly models (Blender bpy + bmesh).
Kingdom of Alba & Dál Riata, c. 800–1100 AD (contemporary with the Norse and Anglo-Saxon kingdoms).

Paste into Blender's Scripting workspace and press Run Script (Alt+P).
Six soldiers along +X, 2.5 units apart. Every armour piece, tunic, weapon and shield is PARENTED to its
soldier's mannequin, so moving the mannequin carries the whole kit.

  1  Ceithern / Highland Kern       – saffron pleated léine, woolen brat with iron ring-pin, bare legs with
                                      cuarán shoes; bundle of light throwing javelins, long iron skean dagger
  2  Saighdeoir / Highland Archer    – saffron léine under earth-green wool brat, leather archer's bracer,
                                      winingas hose; yew war bow in left hand, hip quiver, utility knife
  3  Bonnacht / Gaelic Spearman      – quilted cotun (padded gambeson), rawhide boots, plain iron nasal cap;
                                      8 ft (2.4 m) leaf-bladed spear, round Scottish targe with domed iron boss
  4  Claidheamh / Gaelic Swordsman   – heavy quilted cotun under hip-length mail byrnie, spangenhelm with nasal;
                                      ring-pommel broadsword in scabbard, decorated targe with brass studs
  5  Gallóglaigh / Gallowglass       – Norse-Gaelic heavy shock infantry: full knee-length mail hauberk, high
                                      iron skullcap with mail aventail; massive two-handed Sparth axe held in grip
  6  Mormaer / Royal Chieftain       – Great Steward / Earl of Alba: fine tailored byrnie with brass trim, gilded
                                      conical crested helm with mail aventail, tartan wool mantle pinned by silver
                                      penannular brooch, silver torc, pattern-welded sword, ornate chased targe

Built entirely from bmesh primitives (no operators, runs in any context) plus Solidify / Bevel modifiers.
Units: metres. Soldiers face -Y; +X is each soldier's left. Tested on Blender 4.x / 5.x.
"""
import bpy
import bmesh
import math
import random
from mathutils import Vector, Matrix

SPACING = 2.5
SEED = 23
TAU = math.tau

# ============================================================== scene + materials
def clear_scene():
    """Remove existing mesh and text objects and previously generated tier collections."""
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
    mat.diffuse_color = (*color, 1.0)
    mat.roughness, mat.metallic = roughness, metallic
    mat.use_fake_user = True
    return mat


def build_materials():
    return {
        # Core metals and woods
        "steel":       make_material("Forged Iron/Steel",     (0.55, 0.57, 0.60), 0.32, 0.95),
        "iron_dark":   make_material("Aged Iron",             (0.32, 0.33, 0.35), 0.55, 0.85),
        "ash":         make_material("Ash Wood Shaft",        (0.52, 0.40, 0.26), 0.65),
        "yew":         make_material("Highland Yew",          (0.52, 0.30, 0.15), 0.48),
        # Textiles & Highland leathers
        "saffron":     make_material("Saffron Linen Léine",   (0.82, 0.62, 0.14), 0.92),
        "saffron_rich":make_material("Royal Saffron Léine",   (0.88, 0.68, 0.16), 0.88),
        "brat_green":  make_material("Heather Green Wool",   (0.16, 0.25, 0.14), 0.95),
        "brat_red":    make_material("Madder Russet Wool",    (0.48, 0.16, 0.12), 0.95),
        "brat_blue":   make_material("Woad Blue Wool",        (0.12, 0.20, 0.36), 0.95),
        "cotun":       make_material("Quilted Cotun Linen",   (0.66, 0.60, 0.48), 0.95),
        "leather":     make_material("Tanned Hide Leather",   (0.24, 0.14, 0.07), 0.68),
        "leather_dark":make_material("Dark Tooled Leather",   (0.15, 0.10, 0.06), 0.60),
        "rawhide":     make_material("Rawhide Trim",          (0.68, 0.62, 0.50), 0.85),
        "mail":        make_material("Riveted Iron Mail",     (0.26, 0.27, 0.29), 0.70, 0.75),
        # Ornaments & fittings
        "brass":       make_material("Polished Bronze/Brass", (0.84, 0.64, 0.22), 0.25, 0.95),
        "silver":      make_material("Chased Highland Silver",(0.82, 0.83, 0.86), 0.20, 0.95),
        "gold":        make_material("Gold Thread Border",    (0.92, 0.72, 0.20), 0.30, 0.90),
        "string":      make_material("Hemp Bowstring",        (0.80, 0.76, 0.66), 0.80),
        "mannequin":   make_material("Mannequin",             (0.42, 0.42, 0.44), 0.70),
    }

# ============================================================== math helpers
def T(x, y, z): return Matrix.Translation((x, y, z))
def S(x, y, z): return Matrix.Diagonal((x, y, z, 1.0))
def RX(a): return Matrix.Rotation(a, 4, 'X')
def RY(a): return Matrix.Rotation(a, 4, 'Y')
def RZ(a): return Matrix.Rotation(a, 4, 'Z')
I4 = Matrix.Identity(4)
V = Vector

def frame(origin, z_axis, x_hint):
    z = V(z_axis).normalized()
    x = V(x_hint); x = (x - z * x.dot(z)).normalized()
    y = z.cross(x)
    m = Matrix((x, y, z)).transposed().to_4x4()
    m.translation = V(origin)
    return m

# ============================================================== bmesh primitives
def add_box(bm, size, M=I4):
    v = bmesh.ops.create_cube(bm, size=1.0)["verts"]
    bmesh.ops.transform(bm, matrix=M @ S(*size), verts=v)
    return v

def add_cyl(bm, r1, r2, depth, M=I4, seg=10, cap=True):
    v = bmesh.ops.create_cone(bm, cap_ends=cap, cap_tris=False, segments=seg, radius1=r1, radius2=r2, depth=depth)["verts"]
    bmesh.ops.transform(bm, matrix=M, verts=v)
    return v

def add_limb(bm, p1, p2, r1, r2, seg=8, cap=True):
    p1, p2 = V(p1), V(p2); d = p2 - p1
    rot = V((0, 0, 1)).rotation_difference(d.normalized()).to_matrix().to_4x4()
    return add_cyl(bm, r1, r2, d.length, Matrix.Translation((p1 + p2) / 2) @ rot, seg, cap)

def add_sphere(bm, r, M=I4, u=10, v=6):
    verts = bmesh.ops.create_uvsphere(bm, u_segments=u, v_segments=v, radius=r)["verts"]
    bmesh.ops.transform(bm, matrix=M, verts=verts)
    return verts

def add_lathe(bm, profile, M=I4, seg=12, sy=1.0, a0=0.0, a1=TAU, wobble=None):
    full = abs((a1 - a0) - TAU) < 1e-6
    n = seg if full else seg + 1
    angs = [a0 + (a1 - a0) * k / seg for k in range(n)]
    rings = []
    for r, z in profile:
        rings.append([bm.verts.new(M @ V(((r + (wobble(a, z) if wobble else 0)) * math.cos(a),
                                          (r + (wobble(a, z) if wobble else 0)) * math.sin(a) * sy, z))) for a in angs])
    for lo, hi in zip(rings, rings[1:]):
        for k in range(n if full else n - 1):
            k2 = (k + 1) % n
            bm.faces.new((lo[k], lo[k2], hi[k2], hi[k]))
    return [v for ring in rings for v in ring]

def add_dome(bm, rx, ry, rz, M=I4, seg=14, rings=5, theta_max=math.pi / 2, a0=0.0, a1=TAU):
    prof = [(rx * math.sin(theta_max - (theta_max - 0.02) * i / rings),
             rz * math.cos(theta_max - (theta_max - 0.02) * i / rings)) for i in range(rings + 1)]
    return add_lathe(bm, prof, M, seg, ry / rx, a0, a1)

def add_torus(bm, R, r, M=I4, seg=18, rseg=6, sy=1.0):
    grid = []
    for i in range(seg):
        a = TAU * i / seg
        grid.append([bm.verts.new(M @ V(((R + r * math.cos(b)) * math.cos(a),
                                          (R + r * math.cos(b)) * math.sin(a) * sy,
                                          r * math.sin(b)))) for b in [TAU * j / rseg for j in range(rseg)]])
    for i in range(seg):
        a, b = grid[i], grid[(i + 1) % seg]
        for j in range(rseg):
            bm.faces.new((a[j], b[j], b[(j + 1) % rseg], a[(j + 1) % rseg]))

def add_prism(bm, pts, thick, M=I4):
    f = [bm.verts.new(M @ V((x, y, thick / 2))) for x, y in pts]
    b = [bm.verts.new(M @ V((x, y, -thick / 2))) for x, y in pts]
    bm.faces.new(f); bm.faces.new(list(reversed(b)))
    n = len(pts)
    for i in range(n):
        i2 = (i + 1) % n
        bm.faces.new((f[i], f[i2], b[i2], b[i]))

# ============================================================== anatomy + base body
HIP = V((0.105, 0.0, 0.93)); KNEE = V((0.115, -0.01, 0.5)); ANKLE = V((0.12, 0.0, 0.085))
HEAD_C0 = V((0.0, -0.005, 1.665)); HEAD_C = HEAD_C0.copy(); HEAD_R = 0.108
TORSO0 = [(0.16, 0.9), (0.165, 0.99), (0.168, 1.07), (0.19, 1.19), (0.215, 1.31), (0.225, 1.37), (0.2, 1.435), (0.12, 1.485), (0.06, 1.505)]
TORSO = list(TORSO0)
DEPTH, SQ0 = 0.62, 0.70; SQ = SQ0
SIDES = (("L", 1), ("R", -1))
MH_CH = None

class Pose:
    def __init__(self, R=None, L=None):
        self.j = {s: {"sh": V((0.235 * sx, 0, 1.415)), "el": V((0.295 * sx, 0, 1.135)), "wr": V((0.325 * sx, -0.03, 0.875))} for s, sx in SIDES}
        for s, over in (("R", R), ("L", L)):
            if over: self.j[s].update({k: V(v) for k, v in over.items()})
    def sh(self, s): return self.j[s]["sh"]
    def el(self, s): return self.j[s]["el"]
    def wr(self, s): return self.j[s]["wr"]
    def fdir(self, s): return (self.wr(s) - self.el(s)).normalized()
    def grip(self, s): return self.wr(s) + self.fdir(s) * 0.055

HANG = Pose()
HOLD_SPEAR_R = {"el": (-0.29, 0.02, 1.15), "wr": (-0.31, -0.24, 1.06)}
HOLD_BOW_L = {"el": (0.28, -0.15, 1.18), "wr": (0.24, -0.32, 1.12)}
HOLD_AXE_2H = {"R": {"el": (-0.26, -0.12, 1.18), "wr": (-0.18, -0.32, 1.15)},
               "L": {"el": (0.22, -0.15, 1.10), "wr": (-0.12, -0.30, 0.95)}}

def leg(sx):
    return V((HIP.x * sx, HIP.y, HIP.z)), V((KNEE.x * sx, KNEE.y, KNEE.z)), V((ANKLE.x * sx, ANKLE.y, ANKLE.z))

def torso_r(z):
    if z <= TORSO[0][1]: return TORSO[0][0]
    for (r0, z0), (r1, z1) in zip(TORSO, TORSO[1:]):
        if z0 <= z <= z1: return r0 + (r1 - r0) * (z - z0) / (z1 - z0)
    return TORSO[-1][0]

def body_r(z, off):
    return torso_r(max(z, 0.9)) + off + max(0.0, 0.96 - z) * 0.42

def shell_profile(z0, z1, off, ridge=0.0, every=0.05):
    prof, z, i = [], z0, 0
    while z < z1 - 1e-6:
        prof.append((body_r(z, off) + (ridge if ridge and i % 2 else 0.0), z))
        z += every; i += 1
    prof.append((torso_r(z1) + off, z1))
    return prof

def spawn_mesh(name, geo_fn, parent, mat, coll=None, smooth=True, mods=()):
    bm = bmesh.new(); geo_fn(bm)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = smooth
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    (coll or parent.users_collection[0]).objects.link(ob)
    ob.parent = parent
    for kind, attrs in mods:
        md = ob.modifiers.new(kind.title(), kind)
        for k, val in attrs.items(): setattr(md, k, val)
    return ob

def build_mannequin(coll, x0, P):
    def geo(bm):
        add_lathe(bm, TORSO, seg=14, sy=DEPTH)
        add_cyl(bm, 0.165, 0.16, 0.12, T(0, 0, 0.9) @ S(1, 0.72, 1), seg=14)
        add_limb(bm, (0, 0, 1.48), (0, 0, 1.585), 0.052, 0.048, seg=10)
        add_sphere(bm, HEAD_R, T(*HEAD_C) @ S(0.88, 0.98, 1.08), u=14, v=10)
        add_box(bm, (0.05, 0.035, 0.03), T(0, HEAD_C.y - 0.1, HEAD_C.z - 0.01))
        for s, sx in SIDES:
            add_sphere(bm, 0.062, T(*P.sh(s)), u=10, v=6)
            add_limb(bm, P.sh(s), P.el(s), 0.055, 0.045, seg=10)
            add_limb(bm, P.el(s), P.wr(s), 0.045, 0.036, seg=10)
            add_sphere(bm, 0.045, frame(P.grip(s), P.fdir(s), V((sx, 0, 0))) @ S(0.75, 1, 1.25), u=8, v=6)
            hp, kn, an = leg(sx)
            add_limb(bm, hp, kn, 0.085, 0.06, seg=10)
            add_limb(bm, kn, an, 0.058, 0.042, seg=10)
            add_box(bm, (0.085, 0.24, 0.06), T(an.x, an.y - 0.06, 0.03))
    bm = bmesh.new(); geo(bm); me = bpy.data.meshes.new("Mannequin"); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = True
    ob = bpy.data.objects.new("Soldier", me); ob.location = (x0, 0, 0); coll.objects.link(ob)
    return ob

# ============================================================== Gaelic clothing & armor pieces
def build_leine(P, parent, mats, hem=0.72, sleeves="bag", off=0.014, pleated=True, mat_key="saffron"):
    """Gaelic pleated saffron tunic (léine) with wide drooping sleeves."""
    def geo(bm):
        wob = (lambda a, z: 0.012 * math.sin(a * 16)) if pleated else None
        add_lathe(bm, shell_profile(hem, 1.47, off), seg=20, sy=SQ, wobble=wob)
        # Saffron drooping bag sleeves
        for s, sx in SIDES:
            sh, el, wr = P.sh(s), P.el(s), P.wr(s)
            add_limb(bm, sh, el, 0.075, 0.09, seg=10, cap=False)
            if sleeves == "bag":
                # Drooping Gaelic pouch at elbow
                add_sphere(bm, 0.07, T(*(el + V((0, 0, -0.06)))) @ S(0.9, 1.0, 1.4), u=10, v=6)
                add_limb(bm, el, wr, 0.08, 0.05, seg=10, cap=False)
            else:
                add_limb(bm, el, wr, 0.07, 0.055, seg=10, cap=False)
    spawn_mesh("Leine", geo, parent, mats[mat_key], mods=[("SOLIDIFY", {"thickness": 0.005})])

def build_brat(parent, mats, mat_key="brat_green", style="shoulder_pin"):
    """Highland woolen mantle/cloak (brat) pinned over the right shoulder."""
    def geo(bm):
        # Draped mantle falling down back and over left arm
        add_dome(bm, 0.28, 0.20, 0.35, T(0, 0.05, 1.25) @ RX(math.radians(-10)), seg=14, rings=5, theta_max=math.pi * 0.7)
        add_cyl(bm, 0.25, 0.30, 0.75, T(0, 0.08, 0.85) @ S(1.0, 0.5, 1.0), seg=14, cap=False)
        # Penannular brooch at right shoulder
        add_torus(bm, 0.024, 0.0035, T(-0.16, -0.06, 1.43) @ RY(math.radians(35)), seg=14, rseg=6)
        add_cyl(bm, 0.002, 0.001, 0.06, T(-0.16, -0.06, 1.43) @ RZ(math.radians(45)), seg=6)
    spawn_mesh("Brat", geo, parent, mats[mat_key])

def build_cotun(P, parent, mats, hem=0.78, off=0.022):
    """Padded Gaelic cotun (quilted gambeson with vertical defensive ridges)."""
    def geo(bm):
        add_lathe(bm, shell_profile(hem, 1.48, off, ridge=0.008, every=0.04), seg=18, sy=SQ)
        for s, sx in SIDES:
            add_limb(bm, P.sh(s), P.el(s), 0.072, 0.064, seg=10, cap=False)
            add_limb(bm, P.el(s), P.wr(s), 0.064, 0.052, seg=10, cap=False)
    spawn_mesh("Cotun", geo, parent, mats["cotun"], mods=[("SOLIDIFY", {"thickness": 0.008})])

def build_mail_byrnie(P, parent, mats, hem=0.82, long_sleeves=False):
    """Gaelic lúireach (riveted mail shirt)."""
    def geo(bm):
        add_lathe(bm, shell_profile(hem, 1.49, 0.028), seg=18, sy=SQ)
        for s, sx in SIDES:
            add_limb(bm, P.sh(s), P.el(s), 0.076, 0.068, seg=10, cap=False)
            if long_sleeves:
                add_limb(bm, P.el(s), P.wr(s), 0.068, 0.056, seg=10, cap=False)
    spawn_mesh("MailByrnie", geo, parent, mats["mail"], mods=[("SOLIDIFY", {"thickness": 0.007})])

def build_shoes_cuaran(parent, mats):
    """Rawhide Gaelic turnshoes / cuarán wraps."""
    def geo(bm):
        for s, sx in SIDES:
            an = V((ANKLE.x * sx, ANKLE.y, ANKLE.z))
            add_box(bm, (0.088, 0.22, 0.06), T(an.x, an.y - 0.05, 0.03))
            add_cyl(bm, 0.05, 0.046, 0.10, T(an.x, an.y, 0.09), seg=8, cap=False)
    spawn_mesh("Cuaran", geo, parent, mats["leather"])

def build_belt_and_skean(parent, mats, buckle_mat="brass"):
    """Waist belt with Gaelic long iron skean (dagger)."""
    def geo(bm):
        # Belt
        add_cyl(bm, 0.178, 0.178, 0.042, T(0, 0, 1.01) @ S(1.0, SQ, 1.0), seg=18, cap=False)
        # Ring brooch / buckle
        add_torus(bm, 0.02, 0.003, T(0, -0.178 * SQ, 1.01), seg=12, rseg=4)
        # Skean scabbard hanging at right hip
        scab = T(-0.16, -0.06, 0.98) @ RY(math.radians(-35)) @ RX(math.radians(20))
        add_box(bm, (0.032, 0.016, 0.32), scab)
        # Hilt & grip
        add_cyl(bm, 0.014, 0.012, 0.11, scab @ T(0, 0, 0.20), seg=8)
    spawn_mesh("BeltSkean", geo, parent, mats["leather"])

def build_spangenhelm(parent, mats, with_nasal=True, aventail=False, gilt=False):
    """Conical iron helmet (spangenhelm) with nasal bar and optional mail aventail."""
    def geo(bm):
        hc = HEAD_C
        # Dome cap
        add_dome(bm, HEAD_R * 1.04, HEAD_R * 1.08, HEAD_R * 1.25, T(hc.x, hc.y, hc.z + 0.01), seg=16, rings=6)
        # Brow band
        add_cyl(bm, HEAD_R * 1.05, HEAD_R * 1.05, 0.032, T(hc.x, hc.y, hc.z - 0.01), seg=16, cap=False)
        if with_nasal:
            # Nasal guard
            add_box(bm, (0.022, 0.006, 0.08), T(hc.x, hc.y - HEAD_R * 1.05, hc.z - 0.04))
        if aventail:
            # Mail curtain
            add_lathe(bm, [(HEAD_R * 1.15, hc.z - 0.18), (HEAD_R * 1.06, hc.z - 0.02)], T(0, 0, 0), seg=14, a0=math.radians(-30), a1=math.radians(210))
    spawn_mesh("Helmet", geo, parent, mats["brass" if gilt else "steel"])

def build_targe(parent, mats, tier=3, arm="L", P=None):
    """Scottish circular wooden targe (~55 cm diameter) with central boss and brass studs."""
    def geo(bm):
        wr = P.wr(arm) if P else V((0.32, -0.03, 0.88))
        M = T(wr.x + 0.08, wr.y - 0.12, wr.z) @ RY(math.radians(15)) @ RZ(math.radians(20))
        # Wooden disc
        add_cyl(bm, 0.27, 0.27, 0.022, M, seg=24)
        # Rawhide / brass rim band
        add_torus(bm, 0.27, 0.012, M, seg=24, rseg=6)
        # Domed central boss
        add_dome(bm, 0.075, 0.075, 0.05, M @ T(0, 0, 0.012), seg=12, rings=4)
        if tier >= 4:
            # Decorative studs in concentric rings
            for ang in [TAU * k / 12 for k in range(12)]:
                add_sphere(bm, 0.008, M @ T(0.18 * math.cos(ang), 0.18 * math.sin(ang), 0.014), u=6, v=4)
        if tier >= 6:
            # Chased center spike
            add_cyl(bm, 0.014, 0.002, 0.08, M @ T(0, 0, 0.06), seg=8)
    spawn_mesh("Targe", geo, parent, mats["leather_dark"])

def build_javelins(P, parent, mats):
    """Bundle of 3 Gaelic throwing javelins / darts held in hand/shield grip."""
    def geo(bm):
        grp = P.grip("R")
        for dx, dy in [(-0.02, 0.0), (0.015, -0.015), (0.01, 0.02)]:
            M = T(grp.x + dx, grp.y + dy, grp.z - 0.10) @ RX(math.radians(15))
            # Shaft (1.4 m)
            add_cyl(bm, 0.011, 0.010, 1.40, M, seg=8)
            # Barbed iron head
            add_cyl(bm, 0.018, 0.002, 0.16, M @ T(0, 0, 0.76), seg=6)
    spawn_mesh("Javelins", geo, parent, mats["ash"])

def build_spear(P, parent, mats):
    """8-foot (2.4 m) ash Gaelic thrusting spear."""
    def geo(bm):
        grp = P.grip("R")
        M = T(grp.x, grp.y - 0.05, 1.20)
        # Shaft
        add_cyl(bm, 0.016, 0.015, 2.40, M, seg=8)
        # Leaf-shaped spearhead
        add_cyl(bm, 0.030, 0.003, 0.28, M @ T(0, 0, 1.25), seg=8)
    spawn_mesh("Spear", geo, parent, mats["ash"])

def build_bow(P, parent, mats):
    """Highland yew stave bow & hip quiver."""
    def geo(bm):
        grp = P.grip("L")
        M = T(grp.x, grp.y, grp.z)
        # Curved bow stave (1.5 m)
        prof = [(0.014, z) for z in [-0.75, -0.5, -0.2, 0.0, 0.2, 0.5, 0.75]]
        add_lathe(bm, prof, M @ RX(math.radians(10)), seg=8, sy=0.7)
        # Bowstring
        add_cyl(bm, 0.002, 0.002, 1.44, M @ T(0, 0.06, 0), seg=4)
        # Quiver at right hip
        add_cyl(bm, 0.06, 0.05, 0.65, T(-0.20, 0.08, 0.95) @ RX(math.radians(-25)), seg=10)
    spawn_mesh("WarBow", geo, parent, mats["yew"])

def build_sword(P, parent, mats, ring_pommel=True):
    """Gaelic ring-pommel broadsword."""
    def geo(bm):
        grp = P.grip("R")
        M = T(grp.x, grp.y - 0.05, grp.z - 0.15) @ RX(math.radians(20))
        # Crossguard
        add_box(bm, (0.16, 0.025, 0.018), M @ T(0, 0, 0.08))
        # Double-edged blade
        add_box(bm, (0.045, 0.008, 0.78), M @ T(0, 0, -0.32))
        # Grip
        add_cyl(bm, 0.015, 0.014, 0.12, M @ T(0, 0, 0.15), seg=8)
        # Open ring pommel
        if ring_pommel:
            add_torus(bm, 0.024, 0.005, M @ T(0, 0, 0.23), seg=12, rseg=5)
        else:
            add_sphere(bm, 0.025, M @ T(0, 0, 0.22), u=8, v=6)
    spawn_mesh("GaelicSword", geo, parent, mats["steel"])

def build_sparth_axe(P, parent, mats):
    """Devastating two-handed Norse-Gaelic Sparth axe (5.5 ft / 1.7 m haft)."""
    def geo(bm):
        grp = P.grip("R")
        M = T(grp.x + 0.05, grp.y - 0.08, 1.05) @ RX(math.radians(25)) @ RY(math.radians(-15))
        # Ash haft
        add_cyl(bm, 0.020, 0.018, 1.70, M, seg=10)
        # Crescent broad cutting blade
        blade_pts = [(0, 0), (0.24, -0.16), (0.28, 0.0), (0.22, 0.20), (0, 0.06)]
        add_prism(bm, blade_pts, 0.012, M @ T(0, 0, 0.72) @ RZ(math.radians(90)))
        # Eye socket & top spike
        add_cyl(bm, 0.025, 0.025, 0.10, M @ T(0, 0, 0.72), seg=8)
        add_cyl(bm, 0.012, 0.002, 0.14, M @ T(0, 0, 0.88), seg=6)
    spawn_mesh("SparthAxe", geo, parent, mats["steel"])

# ============================================================== TIER BUILDERS
def tier_1(P, root, mats, rng):
    """1. Ceithern / Highland Kern – saffron pleated léine, wool brat, javelins, skean."""
    build_leine(P, root, mats, hem=0.74, sleeves="bag", pleated=True, mat_key="saffron")
    build_brat(root, mats, mat_key="brat_green")
    build_shoes_cuaran(root, mats)
    build_belt_and_skean(root, mats)
    build_javelins(P, root, mats)

def tier_2(P, root, mats, rng):
    """2. Saighdeoir / Highland Archer – saffron léine, wool brat, yew war bow, quiver, hose."""
    build_leine(P, root, mats, hem=0.76, sleeves="bag", pleated=True, mat_key="saffron")
    build_brat(root, mats, mat_key="brat_blue")
    build_shoes_cuaran(root, mats)
    build_belt_and_skean(root, mats)
    build_bow(P, root, mats)

def tier_3(P, root, mats, rng):
    """3. Bonnacht / Gaelic Spearman – padded cotun, nasal helm, 8ft spear, targe."""
    build_cotun(P, root, mats, hem=0.78)
    build_spangenhelm(root, mats, with_nasal=True, aventail=False)
    build_shoes_cuaran(root, mats)
    build_belt_and_skean(root, mats)
    build_spear(P, root, mats)
    build_targe(root, mats, tier=3, arm="L", P=P)

def tier_4(P, root, mats, rng):
    """4. Claidheamh / Gaelic Swordsman – cotun under mail byrnie, ring-pommel sword, targe."""
    build_cotun(P, root, mats, hem=0.78)
    build_mail_byrnie(P, root, mats, hem=0.82, long_sleeves=False)
    build_spangenhelm(root, mats, with_nasal=True, aventail=True)
    build_shoes_cuaran(root, mats)
    build_belt_and_skean(root, mats)
    build_sword(P, root, mats, ring_pommel=True)
    build_targe(root, mats, tier=4, arm="L", P=P)

def tier_5(P, root, mats, rng):
    """5. Gallóglaigh / Gallowglass – full mail hauberk, high skullcap with aventail, 2H Sparth axe."""
    build_leine(P, root, mats, hem=0.70, sleeves="tight", off=0.010, pleated=True, mat_key="saffron")
    build_cotun(P, root, mats, hem=0.74, off=0.020)
    build_mail_byrnie(P, root, mats, hem=0.70, long_sleeves=True)
    build_spangenhelm(root, mats, with_nasal=True, aventail=True)
    build_shoes_cuaran(root, mats)
    build_belt_and_skean(root, mats)
    build_sparth_axe(P, root, mats)

def tier_6(P, root, mats, rng):
    """6. Mormaer / Royal Chieftain – royal saffron léine, long mail with brass trim, gilded helm, silver brooch, ornate targe, sword."""
    build_leine(P, root, mats, hem=0.68, sleeves="bag", off=0.010, pleated=True, mat_key="saffron_rich")
    build_mail_byrnie(P, root, mats, hem=0.72, long_sleeves=True)
    build_brat(root, mats, mat_key="brat_red")
    build_spangenhelm(root, mats, with_nasal=True, aventail=True, gilt=True)
    build_shoes_cuaran(root, mats)
    build_belt_and_skean(root, mats, buckle_mat="silver")
    build_sword(P, root, mats, ring_pommel=True)
    build_targe(root, mats, tier=6, arm="L", P=P)

TIERS = [
    ("Highland Kern", tier_1, Pose(R=HOLD_SPEAR_R["wr"])),
    ("Highland Archer", tier_2, Pose(L=HOLD_BOW_L)),
    ("Bonnacht Spearman", tier_3, Pose(R=HOLD_SPEAR_R)),
    ("Gaelic Swordsman", tier_4, Pose(R=HOLD_SPEAR_R)),
    ("Gallowglass", tier_5, Pose(R=HOLD_AXE_2H["R"], L=HOLD_AXE_2H["L"])),
    ("Mormaer of Alba", tier_6, Pose(R=HOLD_SPEAR_R)),
]

# ============================================================== MakeHuman integration
MH_CAST = {
    1: dict(macro=dict(age=0.28, muscle=0.65, weight=0.45), skin="young_caucasian_male", eye="bluegreen", hair="short02", tint=(0.42, 0.18, 0.08), beard="short", show=("head", "neck", "hands"), hair_on=True, grip="R"),
    2: dict(macro=dict(age=0.34, muscle=0.68, weight=0.48), skin="young_caucasian_male", eye="brownlight", hair="short04", tint=(0.28, 0.16, 0.08), beard="short", show=("head", "neck", "hands"), hair_on=True, grip="L"),
    3: dict(macro=dict(age=0.42, muscle=0.72, weight=0.55), skin="middleage_caucasian_male", eye="grey", hair="short01", tint=(0.45, 0.15, 0.06), beard="full", show=("head", "neck", "hands"), hair_on=False, grip="R"),
    4: dict(macro=dict(age=0.46, muscle=0.74, weight=0.56), skin="middleage_caucasian_male", eye="blue", hair="short02", tint=(0.20, 0.12, 0.06), beard="full", show=("head", "neck", "hands"), hair_on=False, grip="R"),
    5: dict(macro=dict(age=0.48, muscle=0.82, weight=0.62), skin="middleage_caucasian_male", eye="grey", hair="short01", tint=(0.22, 0.14, 0.07), beard="full", show=("head", "neck", "hands"), hair_on=False, grip="R"),
    6: dict(macro=dict(age=0.58, muscle=0.72, weight=0.58), skin="middleage_caucasian_male", eye="bluegreen", hair="short02", tint=(0.30, 0.22, 0.18), beard="full", show=("head", "neck", "hands"), hair_on=True, grip="R"),
}

def _load_mh():
    import os, sys, importlib.util
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

def add_label(coll, parent, text):
    cu = bpy.data.curves.new("Label", 'FONT')
    cu.body = text; cu.size = 0.11; cu.align_x = 'CENTER'
    ob = bpy.data.objects.new("Label", cu)
    ob.location = (0, -0.65, 0.05); ob.rotation_euler = (math.radians(70), 0, 0)
    coll.objects.link(ob); ob.parent = parent

def ensure_camera_and_light(n):
    sc = bpy.context.scene
    cam = sc.camera or bpy.data.objects.get("Camera")
    if not cam:
        cd = bpy.data.cameras.new("Camera"); cam = bpy.data.objects.new("Camera", cd); sc.collection.objects.link(cam); sc.camera = cam
    mid_x = (n - 1) * SPACING / 2
    cam.location = (mid_x, -11.0, 1.8); cam.rotation_euler = (math.radians(82), 0, 0)
    sun = next((o for o in sc.objects if o.type == 'LIGHT' and o.data.type == 'SUN'), None)
    if not sun:
        ld = bpy.data.lights.new("Sun", 'SUN'); ld.energy = 3.5; sun = bpy.data.objects.new("Sun", ld); sc.collection.objects.link(sun)
    sun.rotation_euler = (math.radians(50), math.radians(20), math.radians(-35))

def main():
    clear_scene(); mats = build_materials(); MHC = _load_mh()
    for i, (title, fn, pose) in enumerate(TIERS):
        coll = bpy.data.collections.new("Tier %d - %s" % (i + 1, title))
        bpy.context.scene.collection.children.link(coll)
        sol = build_mannequin(coll, i * SPACING, pose)
        sol.name = "Tier %d Soldier" % (i + 1)
        sol.data.materials.append(mats["mannequin"])
        fn(pose, sol, mats, random.Random(SEED + i))
        add_label(coll, sol, "TIER %d\n%s" % (i + 1, title))
    ensure_camera_and_light(len(TIERS))
    print("Gaelic soldiers generated:", ", ".join(c.name for c in bpy.data.collections if c.name.startswith("Tier ")))

if __name__ == "__main__":
    main()
