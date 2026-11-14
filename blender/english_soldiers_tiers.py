"""
English Soldiers, Tiers 1-6 â€” procedural low-poly historical models with armed weapons (Blender bpy + bmesh).

Paste into Blender's Scripting workspace and press Run Script (Alt+P).
Six soldiers along +X, 2.5 units apart. Every armour piece, belt, weapon and shield is PARENTED to its
soldier's mannequin, so moving the mannequin carries the whole kit.

  1  Anglo-Saxon select fyrdman, c.1066   wool tunic, rope belt, winingas with cross-garters, iron conical cap;
                                          seax in a belt sheath, 7 ft (2.13 m) ash thrusting spear in the right hand
  2  Norman-English knight, 12th c.       mail hauberk, coif and chausses, white surcoat with red cross, conical
                                          nasal helm; arming sword (wheel pommel) in a scabbard, kite shield on the
                                          left forearm
  3  English longbowman, 14th c.          padded linen gambeson, riveted brigandine, cervelliere, leather bracer;
                                          yew longbow with horn nocks and string in the left hand, sheaf of arrows
                                          in the belt, falchion at the right hip
  4  Knight of Agincourt, c.1415          great bascinet with klappvisier and mail aventail, breastplate over a mail
                                          haubergeon, full arm and leg harness; hand-and-a-half sword with
                                          scent-stopper pommel on a heavy sword belt
  5  Wars of the Roses man-at-arms        fluted gothic plate, sallet with visor and bevor, articulated gauntlets;
                                          poleaxe (axe, hammer, top spike, languets, rondel) in the right hand
  6  Tudor royal guard, c.1510s-1540s     ridged breastplate, burgonet, tassets over paned breeches, red livery
                                          tabard with a raised Tudor rose, wide "bear's paw" shoes; English bill
                                          (hook blade, top spike, back beak) in the right hand

Built only from bmesh primitives (no operators, so it runs in any context) plus Solidify / Bevel modifiers.
Units: metres. Soldiers face -Y; +X is each soldier's left. Tested on Blender 4.x / 5.x.
"""
import bpy
import bmesh
import math
import random
from mathutils import Vector, Matrix

SPACING = 2.5
SEED = 11
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
    mat.use_fake_user = True                     # survive add-ons that purge unused data while bodies are built
    return mat


def build_materials():
    return {
        # the six required families
        "steel":   make_material("Forged Iron/Steel",   (0.55, 0.56, 0.58), 0.3, 1.0),
        "yew":     make_material("English Yew Wood",    (0.55, 0.3, 0.14), 0.45),
        "wool":    make_material("Wool Cloth",          (0.36, 0.3, 0.22), 0.95),
        "leather": make_material("Aged Leather",        (0.24, 0.13, 0.06), 0.62),
        "mail":    make_material("Riveted Mail",        (0.24, 0.245, 0.255), 0.72, 0.75),
        "brass":   make_material("Polished Brass Trim", (0.85, 0.62, 0.22), 0.2, 1.0),
        # supporting materials
        "mannequin": make_material("Mannequin",         (0.42, 0.42, 0.44), 0.7),
        "ash":     make_material("Ash Wood Shaft",      (0.52, 0.4, 0.26), 0.6),
        "linen":   make_material("Linen Padding",       (0.62, 0.56, 0.44), 0.95),
        "white":   make_material("Surcoat White",       (0.78, 0.75, 0.68), 0.9),
        "red":     make_material("Heraldic Red",        (0.5, 0.05, 0.04), 0.85),
        "green":   make_material("Wool Green",          (0.12, 0.2, 0.1), 0.95),
        "blue":    make_material("Brigandine Velvet",   (0.08, 0.1, 0.3), 0.7),
        "horn":    make_material("Horn",                (0.72, 0.64, 0.5), 0.4),
        "string":  make_material("Linen Bowstring",     (0.8, 0.76, 0.66), 0.8),
        "shield":  make_material("Limewood Shield Face",(0.5, 0.38, 0.22), 0.7),
        "gold":    make_material("Gold Embroidery",     (0.9, 0.68, 0.2), 0.35, 0.8),
        "rose_w":  make_material("Tudor Rose White",    (0.85, 0.82, 0.76), 0.6),
        "rose_g":  make_material("Tudor Rose Green",    (0.1, 0.3, 0.1), 0.7),
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
    """4x4 matrix: local Z along z_axis, local X toward x_hint, origin at origin."""
    z = V(z_axis).normalized(); x = V(x_hint); x = (x - z * x.dot(z)).normalized(); y = z.cross(x)
    m = Matrix((x, y, z)).transposed().to_4x4(); m.translation = V(origin)
    return m

# ============================================================== bmesh primitive builders
def add_box(bm, size, M=I4):
    v = bmesh.ops.create_cube(bm, size=1.0)["verts"]
    bmesh.ops.transform(bm, matrix=M @ S(*size), verts=v); return v


def add_cyl(bm, r1, r2, depth, M=I4, seg=10, cap=True):
    v = bmesh.ops.create_cone(bm, cap_ends=cap, cap_tris=False, segments=seg, radius1=r1, radius2=r2, depth=depth)["verts"]
    bmesh.ops.transform(bm, matrix=M, verts=v); return v


def add_limb(bm, p1, p2, r1, r2, seg=8, cap=True):
    p1, p2 = V(p1), V(p2); d = p2 - p1
    rot = V((0, 0, 1)).rotation_difference(d.normalized()).to_matrix().to_4x4()
    return add_cyl(bm, r1, r2, d.length, Matrix.Translation((p1 + p2) / 2) @ rot, seg, cap)


def add_sphere(bm, r, M=I4, u=10, v=6):
    verts = bmesh.ops.create_uvsphere(bm, u_segments=u, v_segments=v, radius=r)["verts"]
    bmesh.ops.transform(bm, matrix=M, verts=verts); return verts


def add_ico(bm, r, M=I4, sub=1):
    verts = bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=r)["verts"]
    bmesh.ops.transform(bm, matrix=M, verts=verts); return verts


def add_lathe(bm, profile, M=I4, seg=12, sy=1.0, a0=0.0, a1=TAU, wobble=None):
    """Surface of revolution around local Z from [(radius, z)] bottom-to-top; partial sweep a0..a1; wobble(a,z)."""
    full = abs((a1 - a0) - TAU) < 1e-6; n = seg if full else seg + 1
    angs = [a0 + (a1 - a0) * k / seg for k in range(n)]; rings = []
    for r, z in profile:
        rings.append([bm.verts.new(M @ V(((r + (wobble(a, z) if wobble else 0)) * math.cos(a), (r + (wobble(a, z) if wobble else 0)) * math.sin(a) * sy, z))) for a in angs])
    for lo, hi in zip(rings, rings[1:]):
        for k in range(n if full else n - 1):
            k2 = (k + 1) % n; bm.faces.new((lo[k], lo[k2], hi[k2], hi[k]))
    return [v for ring in rings for v in ring]


def add_dome(bm, rx, ry, rz, M=I4, seg=14, rings=5, theta_max=math.pi / 2, a0=0.0, a1=TAU):
    prof = [(rx * math.sin(theta_max - (theta_max - 0.02) * i / rings), rz * math.cos(theta_max - (theta_max - 0.02) * i / rings)) for i in range(rings + 1)]
    return add_lathe(bm, prof, M, seg, ry / rx, a0, a1)


def add_torus(bm, R, r, M=I4, seg=18, rseg=6, sy=1.0):
    grid = []
    for i in range(seg):
        a = TAU * i / seg
        grid.append([bm.verts.new(M @ V(((R + r * math.cos(b)) * math.cos(a), (R + r * math.cos(b)) * math.sin(a) * sy, r * math.sin(b)))) for b in [TAU * j / rseg for j in range(rseg)]])
    for i in range(seg):
        a, b = grid[i], grid[(i + 1) % seg]
        for j in range(rseg): bm.faces.new((a[j], b[j], b[(j + 1) % rseg], a[(j + 1) % rseg]))


def add_surface(bm, fn, nu, nv, closed_u=False):
    """Parametric quad patch: fn(u, v) -> Vector with u, v in [0, 1]."""
    cols = nu if closed_u else nu + 1
    rows = [[bm.verts.new(fn(i / nu, j / nv)) for i in range(cols)] for j in range(nv + 1)]
    for j in range(nv):
        for i in range(cols if closed_u else cols - 1):
            i2 = (i + 1) % cols; bm.faces.new((rows[j][i], rows[j][i2], rows[j + 1][i2], rows[j + 1][i]))
    return rows


def add_prism(bm, pts, thick, M=I4):
    """Flat blade/plate: polygon pts [(x, y)] in the local XY plane, extruded `thick` along Z."""
    f = [bm.verts.new(M @ V((x, y, thick / 2))) for x, y in pts]; b = [bm.verts.new(M @ V((x, y, -thick / 2))) for x, y in pts]
    bm.faces.new(f); bm.faces.new(list(reversed(b)))
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n; bm.faces.new((f[i], b[i], b[j], f[j]))


UPRIGHT = Matrix(((1, 0, 0, 0), (0, 0, -1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))    # local XY plane -> world XZ (facing -Y)
FORWARD = Matrix(((0, 0, -1, 0), (-1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 0, 1)))   # local +X -> world -Y (forward), local +Y -> up
OUTWARD_R = Matrix(((-1, 0, 0, 0), (0, 0, 1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))  # local +X -> world -X (out past the right hand), +Y -> up


def upright(M): return M @ UPRIGHT


def chain(bm, pts, r, seg=5):
    for a, b in zip(pts, pts[1:]): add_limb(bm, a, b, r, r, seg)

# ============================================================== object assembly (everything parented to the soldier)
def make_object(name, parent, mat, builder, mods=(), smooth=False, coll=None):
    bm = bmesh.new(); builder(bm)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = smooth
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    (coll or parent.users_collection[0]).objects.link(ob)
    ob.parent = parent                                   # local coords == soldier space
    for kind, attrs in mods:
        md = ob.modifiers.new(kind.title(), kind)
        for k, val in attrs.items(): setattr(md, k, val)
    return ob

SOLID = lambda t: ("SOLIDIFY", {"thickness": t, "offset": 1.0})
BEVEL = lambda w, s=1: ("BEVEL", {"width": w, "segments": s, "limit_method": 'ANGLE'})

# ============================================================== anatomy + posing
HIP = V((0.105, 0.0, 0.93)); KNEE = V((0.115, -0.01, 0.5)); ANKLE = V((0.12, 0.0, 0.085))
HEAD_C = V((0.0, -0.005, 1.665)); HEAD_R = 0.108
TORSO = [(0.16, 0.9), (0.165, 0.99), (0.168, 1.07), (0.19, 1.19), (0.215, 1.31), (0.225, 1.37), (0.2, 1.435), (0.12, 1.485), (0.06, 1.505)]
DEPTH, SQ = 0.62, 0.7
SIDES = (("L", 1), ("R", -1))


class Pose:
    """Arm joints per side ('L' = +X, 'R' = -X). Legs are symmetric."""
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
HOLD_POLE_R = {"el": (-0.29, 0.02, 1.15), "wr": (-0.31, -0.24, 1.06)}   # right forearm forward, fist round a vertical haft


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
        prof.append((body_r(z, off) + (ridge if ridge and i % 2 else 0.0), z)); z += every; i += 1
    prof.append((torso_r(z1) + off, z1)); return prof


def build_mannequin(coll, x0, P):
    def geo(bm):
        add_lathe(bm, TORSO, seg=14, sy=DEPTH)
        add_cyl(bm, 0.165, 0.16, 0.12, T(0, 0, 0.9) @ S(1, 0.72, 1), seg=14)
        add_limb(bm, (0, 0, 1.48), (0, 0, 1.585), 0.052, 0.048, seg=10)
        add_sphere(bm, HEAD_R, T(*HEAD_C) @ S(0.88, 0.98, 1.08), u=14, v=10)
        add_box(bm, (0.05, 0.035, 0.03), T(0, HEAD_C.y - 0.1, HEAD_C.z - 0.01))
        for s, sx in SIDES:
            add_sphere(bm, 0.062, T(*P.sh(s)), u=10, v=6)
            add_limb(bm, P.sh(s), P.el(s), 0.055, 0.045, seg=10); add_limb(bm, P.el(s), P.wr(s), 0.045, 0.036, seg=10)
            add_sphere(bm, 0.045, frame(P.grip(s), P.fdir(s), V((sx, 0, 0))) @ S(0.75, 1, 1.25), u=8, v=6)
            hp, kn, an = leg(sx)
            add_limb(bm, hp, kn, 0.085, 0.06, seg=10); add_limb(bm, kn, an, 0.058, 0.042, seg=10)
            add_box(bm, (0.085, 0.24, 0.06), T(an.x, an.y - 0.06, 0.03))
    bm = bmesh.new(); geo(bm); me = bpy.data.meshes.new("Mannequin"); bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = True
    ob = bpy.data.objects.new("Soldier", me); ob.location = (x0, 0, 0); coll.objects.link(ob)
    return ob

# ============================================================== clothing
def garment(bm, P, hem, off, sleeves="long", sr=0.068, ridge=0.0, every=0.05, top=1.47, rng=None, tatter=0.0):
    """Tunic / gambeson / hauberk / surcoat body (+ sleeves following the pose)."""
    if MH_CH is not None: return mh_garment(bm, hem, off, sleeves, ridge, every, top, tatter)
    v = add_lathe(bm, shell_profile(hem, top, off, ridge, every), seg=16, sy=SQ)
    if tatter and rng:
        for x in v:
            if abs(x.co.z - hem) < 1e-4: x.co.z += rng.uniform(-tatter * 0.5, tatter)
    if not sleeves: return
    for s, sx in SIDES:
        a = P.sh(s) + V((-0.02 * sx, 0, 0.02))
        if sleeves == "short":
            add_limb(bm, a, P.sh(s).lerp(P.el(s), 0.55), sr, sr * 0.92, seg=10, cap=False); continue
        add_limb(bm, a, P.el(s), sr, sr * 0.88, seg=10, cap=False)
        if sleeves in ("long", "mid"):
            end = P.wr(s) + P.fdir(s) * 0.01 if sleeves == "long" else P.el(s).lerp(P.wr(s), 0.55)
            add_limb(bm, P.el(s), end, sr * 0.88, sr * 0.74, seg=10, cap=False)


def hose(bm, r=0.012, z_bottom=0.12):
    if MH_CH is not None: return mh_hose(bm, r, z_bottom)
    for s, sx in SIDES:
        hp, kn, an = leg(sx)
        add_limb(bm, hp, kn, 0.085 + r, 0.06 + r, seg=10, cap=False)
        add_limb(bm, kn, an + V((0, 0, z_bottom - an.z)), 0.058 + r, 0.042 + r, seg=10, cap=False)


def winingas(bm, z0=0.13, z1=0.46, turns=8):
    for s, sx in SIDES:
        hp, kn, an = leg(sx)
        for i in range(turns):
            z = z0 + (z1 - z0) * i / (turns - 1); c = kn.lerp(an, (kn.z - z) / (kn.z - an.z))
            add_torus(bm, 0.061 + 0.015 * (z - an.z) / (kn.z - an.z), 0.0095, T(c.x, c.y, z) @ RX(0.22), seg=12, rseg=4)


def cross_garters(bm, z0=0.12, z1=0.47):
    """Leather garters wound criss-cross over the winingas (two opposite spirals per leg)."""
    for s, sx in SIDES:
        hp, kn, an = leg(sx)
        for hand in (1, -1):
            pts = []
            for i in range(25):
                t = i / 24; z = z0 + (z1 - z0) * t; c = kn.lerp(an, (kn.z - z) / (kn.z - an.z))
                r = 0.074 + 0.015 * (z - an.z) / (kn.z - an.z); a = hand * t * TAU * 1.75 - math.pi / 2
                pts.append(V((c.x + r * math.cos(a), c.y + r * math.sin(a), z)))
            chain(bm, pts, 0.0055, seg=4)


def turnshoes(bm, h=0.075, wide=False):
    for s, sx in SIDES:
        an = leg(sx)[2]
        add_box(bm, (0.13 if wide else 0.1, 0.26, h), T(an.x, an.y - 0.06, h / 2))
        if wide: add_box(bm, (0.15, 0.06, h * 0.9), T(an.x, an.y - 0.18, h * 0.45))       # Tudor broad "bear's paw" toe
        add_limb(bm, an + V((0, 0.01, 0.02)), an + V((0, 0.005, 0.1)), 0.054, 0.05, seg=10)


def belt_ring(bm, z, off, w=0.04):
    r = torso_r(z) + off
    add_lathe(bm, [(r, z - w / 2), (r, z + w / 2)], seg=20, sy=sqo(off, z))


def front_y(z, off): return -(torso_r(z) * SQ + off)


def sqo(off, z=1.2):
    """Depth ratio for a shell `off` outside the torso, so the gap is `off` at the front and back too (not off*SQ)."""
    r = torso_r(z); return (r * SQ + off) / (r + off)


def rope_belt(bm, z, off):
    add_torus(bm, torso_r(z) + off, 0.009, T(0, 0, z) @ S(1, sqo(off, z), 1), seg=22, rseg=5)
    y = front_y(z, off) - 0.008
    add_ico(bm, 0.016, T(0.05, y, z), sub=1)
    for dx, L in ((0.05, 0.2), (0.066, 0.15)): add_limb(bm, (dx, y, z), (dx + 0.012, y - 0.006, z - L), 0.007, 0.006, seg=5)

# ============================================================== helmets
def bowl(bm, extra=0.016, brow=None):
    brow = HEAD_C.z + 0.035 if brow is None else brow
    rx, ry, top = HEAD_R * 0.9 + extra, HEAD_R * 0.98 + extra, HEAD_C.z + HEAD_R * 1.08 + extra
    add_dome(bm, rx, ry, top - brow, T(HEAD_C.x, HEAD_C.y, brow), seg=16, rings=6)
    return rx, ry, brow, top


def conical(bm, extra=0.018, brow=None, h=0.2):
    brow = HEAD_C.z + 0.035 if brow is None else brow
    rx, ry = HEAD_R * 0.9 + extra, HEAD_R * 0.98 + extra
    prof = [(rx, 0), (rx * 0.98, 0.03), (rx * 0.92, 0.07), (rx * 0.78, 0.11), (rx * 0.55, 0.15), (rx * 0.28, 0.18), (0.004, h)]
    add_lathe(bm, [(r, brow + z) for r, z in prof], T(HEAD_C.x, HEAD_C.y, 0), seg=16, sy=ry / rx)
    return rx, ry, brow


def band(bm, rx, ry, z, w=0.022, out=0.005):
    add_lathe(bm, [(rx + out, z - w / 2), (rx + out, z + w / 2)], T(HEAD_C.x, HEAD_C.y, 0), seg=18, sy=ry / rx)


def nasal(bm, brow, ry, length=0.08):
    add_box(bm, (0.022, 0.008, length), T(0, HEAD_C.y - ry - 0.006, brow - length / 2 + 0.012))


def coif(bm):
    """Mail hood: crown, face-opening sides and a cape over the shoulders."""
    c = T(HEAD_C.x, HEAD_C.y, 0); r = HEAD_R + 0.016
    add_lathe(bm, [(0.21, 1.4), (0.17, 1.47), (0.1, 1.55), (r * 0.92, 1.6)], c, seg=18, sy=0.95)
    add_lathe(bm, [(r * 0.92, 1.6), (r * 0.95, 1.67), (r * 0.92, 1.73)], c, seg=16, sy=1.05, a0=-math.pi / 2 + 0.75, a1=3 * math.pi / 2 - 0.75)
    add_dome(bm, r * 0.92, r * 1.0, HEAD_R * 1.08 + 0.016 - 0.065, T(HEAD_C.x, HEAD_C.y, 1.73), seg=16, rings=5)


def aventail(bm, rx, rim_z, gap=0.0):
    add_lathe(bm, [(0.22, 1.39), (0.14, 1.52), (rx + 0.004, rim_z)], T(HEAD_C.x, HEAD_C.y + 0.008, 0), seg=18, sy=0.95,
              **({} if not gap else {"a0": -math.pi / 2 + gap, "a1": 3 * math.pi / 2 - gap}))

# ============================================================== plate harness pieces
def limb_shell(bm, a, b, r1, r2, toward=V((0, -1, 0)), span=math.pi, seg=8):
    """Plate shell on a limb segment, centred on direction `toward` (front by default)."""
    F = frame((V(a) + V(b)) / 2, V(b) - V(a), toward); L = (V(b) - V(a)).length
    add_lathe(bm, [(r1, -L / 2), (r2, L / 2)], F, seg=seg, a0=-span / 2, a1=span / 2)


def couter(bm, centre, outward, r=0.05):
    add_sphere(bm, r, T(*centre) @ S(1, 1, 1), u=10, v=6)
    F = frame(V(centre) + V(outward) * r * 0.9, outward, V((0, 0, 1)))
    add_cyl(bm, r * 1.25, r * 1.25, 0.006, F @ S(0.8, 1.2, 1), seg=12)          # side wing / fan


def arm_harness(bm, P, s, sx, spaulder_lames=4, r0=0.1):
    sh, el, wr = P.sh(s), P.el(s), P.wr(s)
    F = frame(sh + V((0.01 * sx, 0, 0.015)), sh - el, V((sx, 0, 0.3)))
    add_dome(bm, r0 + 0.008, r0 + 0.008, 0.07, F, seg=12, rings=4)
    for i in range(spaulder_lames):
        zt = -i * 0.05; r = r0 + 0.005 * i
        add_lathe(bm, [(r + 0.012, zt - 0.06), (r, zt)], F, seg=12, a0=-math.pi + 0.6, a1=math.pi - 0.6)
    add_limb(bm, sh.lerp(el, 0.35), el.lerp(sh, 0.12), 0.064, 0.058, seg=10, cap=False)     # rerebrace
    couter(bm, el, V((sx, 0.5, 0)).normalized(), 0.052)
    add_limb(bm, el.lerp(wr, 0.15), wr.lerp(el, 0.05), 0.056, 0.047, seg=10, cap=False)      # vambrace


def gauntlet(bm, P, s, sx, flare=0.07, fingers=True):
    F = frame(P.wr(s), P.fdir(s), V((sx, 0, 0)))
    add_lathe(bm, [(0.048, -0.02), (flare, -0.11)][::-1], F, seg=12)                      # flared cuff
    add_box(bm, (0.072, 0.036, 0.075), F @ T(0, 0, 0.06))                                   # back of the hand
    if fingers:
        for k in range(4):                                                                  # articulated finger lames
            add_box(bm, (0.068, 0.03, 0.014), F @ T(0, -0.004 - k * 0.006, 0.105 + k * 0.016) @ RX(0.3 + k * 0.35))
        add_box(bm, (0.018, 0.022, 0.05), F @ T(0.045, -0.015, 0.06) @ RY(0.5))   # thumb


def leg_harness(bm, pointed=False, fan=True):
    for s, sx in SIDES:
        hp, kn, an = leg(sx)
        limb_shell(bm, hp.lerp(kn, 0.08), kn.lerp(hp, 0.06), 0.1, 0.075, span=math.pi * 1.15)      # cuisse
        add_sphere(bm, 0.055, T(kn.x, kn.y - 0.04, kn.z) @ S(1, 0.7, 1.05), u=10, v=6)            # poleyn
        if fan: add_cyl(bm, 0.05, 0.05, 0.006, frame(V((kn.x + 0.06 * sx, kn.y - 0.01, kn.z)), V((sx, 0, 0)), V((0, 0, 1))) @ S(0.9, 1.3, 1), seg=12)
        add_limb(bm, kn.lerp(an, 0.1), an + V((0, 0, 0.05)), 0.07, 0.054, seg=12, cap=False)      # greave
        L = 0.3 if pointed else 0.25                                                               # sabaton lames
        for k in range(5):
            y = an.y - 0.02 - k * L / 6
            add_lathe(bm, [(0.06 - k * 0.004, -0.024), (0.06 - k * 0.004, 0.024)], frame(V((an.x, y, 0.035)), V((0, -1, 0)), V((1, 0, 0))), seg=8, a0=-0.2, a1=math.pi + 0.2)
        if pointed: add_cyl(bm, 0.03, 0.002, 0.12, frame(V((an.x, an.y - 0.06 - L, 0.03)), V((0, -1, 0)), V((1, 0, 0))), seg=8)


def breastplate(bm, z0=0.95, z1=1.44, off=0.075, style="globular", back=True):
    def wob(a, z):
        w = 0.0
        if style == "fluted": w += 0.007 * math.cos(16 * a) * (1.0 if z < 1.32 else 0.4)
        if style == "ridge": w += 0.028 * max(0.0, 1 - abs(a + math.pi / 2) / 0.32) * min(1.0, (z - z0) / 0.12)
        return w
    prof = [(torso_r(z) + off + (0.022 * math.sin(math.pi * (z - z0) / (z1 - z0)) if style != "ridge" else 0.01), z) for z in [z0 + (z1 - z0) * k / 8 for k in range(9)]]
    add_lathe(bm, prof, seg=20, sy=sqo(off + 0.012), a0=-math.pi, a1=0.0, wobble=wob)
    if back: add_lathe(bm, [(torso_r(z) + off - 0.006, z) for z in [z0 + (z1 - z0) * k / 6 for k in range(7)]], seg=14, sy=sqo(off), a0=0.0, a1=math.pi)


def fauld(bm, z_top=0.96, lames=3, off=0.085, h=0.045):
    for i in range(lames):
        zt = z_top - i * h * 0.85
        add_lathe(bm, [(body_r(zt - h, off + 0.006 * i), zt - h), (body_r(zt, off + 0.006 * i) - 0.004, zt)], seg=20, sy=sqo(off, 1.0))


def tassets(bm, z_top=0.86, lames=4):
    for s, sx in SIDES:
        hp, kn, an = leg(sx)
        for i in range(lames):
            zt = z_top - i * 0.055; c = hp.lerp(kn, (hp.z - zt) / (hp.z - kn.z) + 0.05)
            limb_shell(bm, V((c.x, c.y, zt - 0.065)), V((c.x, c.y, zt)), 0.125 + 0.004 * i, 0.12 + 0.004 * i, span=math.pi * 0.95)

# ============================================================== weapons
def grip_frame(P, s, up=V((0, 0, 1))):
    """Frame at the fist with local Z along `up` (the haft direction)."""
    return frame(P.grip(s), up, V((0, -1, 0)))


def spear(bm_shaft, bm_iron, P, length=2.13):
    g = P.grip("R"); base = V((g.x, g.y, 0.0))
    add_limb(bm_shaft, base + V((0, 0, 0.04)), base + V((0, 0, length - 0.24)), 0.015, 0.0135, seg=8)
    head = base + V((0, 0, length - 0.24))
    add_limb(bm_iron, head - V((0, 0, 0.06)), head + V((0, 0, 0.02)), 0.016, 0.014, seg=8)                # socket
    add_prism(bm_iron, [(0, 0.02), (0.028, 0.08), (0.022, 0.16), (0, 0.24), (-0.022, 0.16), (-0.028, 0.08)], 0.008, upright(T(*head)))   # leaf-shaped blade
    add_limb(bm_iron, base, base + V((0, 0, 0.045)), 0.012, 0.016, seg=8)                                  # butt ferrule




def hilt(bm_grip, bm_metal, top, d, grip_len=0.1, cross=0.18, pommel="wheel", flat=V((1, 0, 0))):
    """Sword hilt rising from scabbard mouth `top` along direction d (pointing away from the blade)."""
    d = V(d).normalized(); g0 = V(top) + d * 0.012; g1 = g0 + d * grip_len
    add_limb(bm_grip, g0, g1, 0.013, 0.012, seg=8)
    F = frame(V(top), d, flat)
    add_box(bm_metal, (cross, 0.016, 0.014), F @ T(0, 0, 0.005))
    if pommel == "wheel":
        add_cyl(bm_metal, 0.032, 0.032, 0.016, frame(g1 + d * 0.026, F.col[1].xyz, d), seg=14)
    elif pommel == "scent":                                                             # scent-stopper: faceted bulb + stopper
        add_lathe(bm_metal, [(0.012, 0.0), (0.03, 0.02), (0.034, 0.04), (0.02, 0.058), (0.012, 0.064), (0.016, 0.078), (0.004, 0.09)], frame(g1, d, flat), seg=8)
    else:                                                                               # disc
        add_cyl(bm_metal, 0.028, 0.028, 0.02, frame(g1 + d * 0.022, F.col[1].xyz, d), seg=12)


def scabbard(bm_leather, bm_brass, top, d_down, length, w0=0.03, w1=0.018, flat=V((1, 0, 0)), falchion=False):
    d = V(d_down).normalized(); F = frame(V(top), d, flat)
    if falchion:
        pts = [(-0.03, 0), (0.03, 0), (0.042, length * 0.7), (0.025, length), (-0.03, length * 0.9)]
        add_prism(bm_leather, pts, 0.02, upright(F))
    else:
        add_lathe(bm_leather, [(w0, 0), (w0 * 0.85, length * 0.5), (w1, length)], F, seg=8, sy=0.42)
        add_lathe(bm_brass, [(w1 + 0.002, length - 0.06), (w1 * 0.6, length + 0.012)], F, seg=8, sy=0.45)   # chape
    add_lathe(bm_brass, [(w0 + 0.003, 0.0), (w0 + 0.003, 0.045)], F, seg=8, sy=0.5)                        # locket


def kite_shield(bm_face, bm_edge, bm_iron, P, s="L"):
    """Teardrop kite shield strapped on the left forearm, curved around the body."""
    H, Wd = 1.0, 0.24
    def half_w(v):   # pointed foot, broad rounded head
        return Wd * (v / 0.7) ** 0.75 if v < 0.7 else Wd * math.sqrt(max(0.0, 1 - ((v - 0.7) / 0.3) ** 2))
    mid = P.el(s).lerp(P.wr(s), 0.5)
    M = T(mid.x + 0.12, mid.y - 0.05, mid.z) @ RZ(math.radians(44)) @ T(0, 0, -0.58)
    def pt(u, v):
        x = (2 * u - 1) * half_w(v)
        return M @ V((x, 0.11 * (x / Wd) ** 2, v * H))          # edges curve back around the body
    add_surface(bm_face, pt, 10, 20)
    edge = [pt(0, v / 20) for v in range(21)] + [pt(1, 1 - v / 20) for v in range(21)]
    chain(bm_edge, edge, 0.009, seg=5)
    add_dome(bm_iron, 0.05, 0.05, 0.035, frame(pt(0.5, 0.72) + (M.to_3x3() @ V((0, -0.006, 0))), M.to_3x3() @ V((0, -1, 0)), V((1, 0, 0))), seg=12, rings=4)


def longbow(bm_yew, bm_horn, bm_string, bm_leather, P, s="L", length=1.85, brace=0.15):
    g = P.grip(s); half = length / 2; pts = []
    for i in range(25):
        t = i / 12 - 1
        pts.append(V((g.x, g.y + brace * t * t, g.z + t * half)))
    for i in range(24):
        t = abs((i + 0.5) / 12 - 1); r = 0.0175 * (1 - 0.62 * t) + 0.004
        add_limb(bm_yew, pts[i], pts[i + 1], r, r, seg=7, cap=False)
    add_limb(bm_leather, g + V((0, 0, -0.05)), g + V((0, 0, 0.05)), 0.021, 0.021, seg=8)                   # grip wrap
    for tip, sgn in ((pts[0], -1), (pts[-1], 1)):                                                         # recurved horn nocks
        add_limb(bm_horn, tip, tip + V((0, 0.012, 0.045 * sgn)), 0.008, 0.004, seg=6)
    add_limb(bm_string, pts[0] + V((0, 0.003, 0.02)), pts[-1] + V((0, 0.003, -0.02)), 0.0018, 0.0018, seg=4)


def arrows_in_belt(bm_shaft, bm_fletch, bm_iron, z, off, n=6):
    base = V((-0.14, front_y(z, off) + 0.01, z))
    for k in range(n):
        d = V((-0.12 + 0.03 * k, -0.08, 1.0)).normalized(); a = base + V((0.012 * k, 0.006 * k, 0)) - d * 0.32
        b = a + d * 0.76
        add_limb(bm_shaft, a, b, 0.0045, 0.0045, seg=5)
        add_cyl(bm_iron, 0.006, 0.0005, 0.05, frame(a - d * 0.02, -d, V((1, 0, 0))), seg=4)                 # bodkin head (point down, in the belt)
        for f in range(3):
            F = frame(b - d * 0.07, d, V((math.cos(f * 2.1), math.sin(f * 2.1), 0)))
            add_box(bm_fletch, (0.018, 0.001, 0.11), F @ T(0.009, 0, 0))


def poleaxe(bm_wood, bm_steel, P, length=1.85):
    g = P.grip("R"); base = V((g.x, g.y, 0.0)); top = base + V((0, 0, length))
    add_cyl(bm_wood, 0.017, 0.017, length - 0.05, T(*(base + V((0, 0, length / 2)))), seg=8)              # octagonal haft
    for k in range(4):                                                                                    # languets down the haft
        a = k * math.pi / 2 + math.pi / 4
        add_box(bm_steel, (0.008, 0.004, 0.34), T(base.x + math.cos(a) * 0.018, base.y + math.sin(a) * 0.018, length - 0.22) @ RZ(a))
    hz = length - 0.06
    add_prism(bm_steel, [(0.0, -0.05), (0.15, -0.1), (0.19, 0.0), (0.15, 0.1), (0.0, 0.05)], 0.01, T(base.x, base.y, hz) @ OUTWARD_R)   # crescent axe blade (haft turned so its profile shows)
    add_box(bm_steel, (0.09, 0.03, 0.04), T(base.x + 0.065, base.y, hz))                                  # hammer
    for k in range(4): add_box(bm_steel, (0.01, 0.012, 0.012), T(base.x + 0.112, base.y + (k % 2 - 0.5) * 0.015, hz + (k // 2 - 0.5) * 0.018))   # hammer teeth
    add_cyl(bm_steel, 0.016, 0.001, 0.2, T(base.x, base.y, length + 0.06), seg=6)                         # top spike
    add_cyl(bm_steel, 0.05, 0.05, 0.006, T(base.x, base.y, length - 0.55), seg=14)                        # rondel hand guard
    add_cyl(bm_steel, 0.002, 0.016, 0.07, T(base.x, base.y, 0.035), seg=6)                                # butt spike


def bill(bm_wood, bm_steel, P, length=2.1):
    g = P.grip("R"); base = V((g.x, g.y, 0.0))
    add_cyl(bm_wood, 0.018, 0.016, length, T(*(base + V((0, 0, length / 2)))), seg=8)
    sz = length - 0.02
    add_limb(bm_steel, base + V((0, 0, sz - 0.1)), base + V((0, 0, sz + 0.06)), 0.02, 0.019, seg=8)        # socket
    for k in (1, -1): add_box(bm_steel, (0.006, 0.004, 0.3), T(base.x + 0.019 * k, base.y, sz - 0.2))     # side straps
    # blade in the Y-Z plane: long cutting edge forward (-Y), hook curving forward at the top
    blade = [(0.0, 0.0), (0.02, 0.0), (0.03, 0.16), (0.075, 0.27), (0.11, 0.36), (0.09, 0.37), (0.05, 0.31), (0.012, 0.3), (-0.012, 0.22), (-0.018, 0.08)]
    M = T(base.x, base.y, sz + 0.04) @ OUTWARD_R
    add_prism(bm_steel, blade, 0.008, M)
    add_cyl(bm_steel, 0.012, 0.001, 0.26, T(base.x + 0.006, base.y, sz + 0.47), seg=6)                     # top spike
    add_cyl(bm_steel, 0.013, 0.001, 0.13, frame(V((base.x + 0.07, base.y, sz + 0.12)), V((1, 0, 0.12)), V((0, 1, 0))), seg=6)   # back beak


def seax(bm_leather, bm_brass, bm_grip, z, off):
    """Broken-back seax in its sheath, worn horizontally along the front of the belt, edge up."""
    y = front_y(z, off) - 0.014
    sheath = [(-0.17, 0.0), (0.12, 0.0), (0.14, 0.035), (0.03, 0.05), (-0.17, 0.03)]
    M = upright(T(-0.02, y, z - 0.035))
    add_prism(bm_leather, sheath, 0.014, M)
    for k in range(5): add_ico(bm_brass, 0.005, T(-0.15 + k * 0.06, y - 0.009, z - 0.033), sub=1)
    add_limb(bm_grip, (0.13, y, z - 0.02), (0.24, y, z - 0.016), 0.012, 0.011, seg=6)

# ============================================================== the six tiers
def tier1(P, sol, M, rng):
    """Anglo-Saxon select fyrdman, c.1066."""
    make_object("Coarse Wool Tunic", sol, M["wool"], lambda bm: garment(bm, P, 0.64, 0.02, "long", 0.064, rng=rng, tatter=0.03), [SOLID(0.007)], True)
    make_object("Rope Belt", sol, M["leather"], lambda bm: rope_belt(bm, 1.0, 0.03), smooth=True)
    make_object("Wool Hose", sol, M["green"], lambda bm: hose(bm), smooth=True)
    make_object("Winingas", sol, M["wool"], winingas, smooth=True)
    make_object("Cross-Garters", sol, M["leather"], cross_garters, smooth=True)
    make_object("Turnshoes", sol, M["leather"], turnshoes, [BEVEL(0.01)])
    def cap(bm):
        rx, ry, brow = conical(bm, 0.016); band(bm, rx, ry, brow + 0.008, 0.02)
    make_object("Iron Conical Cap", sol, M["steel"], cap, [SOLID(0.004)])
    make_object("Seax Sheath", sol, M["leather"], lambda bm: seax(bm, bmesh.new(), bmesh.new(), 1.0, 0.062), [BEVEL(0.002)])
    make_object("Seax Fittings", sol, M["brass"], lambda bm: seax(bmesh.new(), bm, bmesh.new(), 1.0, 0.062), smooth=True)
    make_object("Seax Grip", sol, M["yew"], lambda bm: seax(bmesh.new(), bmesh.new(), bm, 1.0, 0.062), smooth=True)
    make_object("Spear Shaft (Ash)", sol, M["ash"], lambda bm: spear(bm, bmesh.new(), P), smooth=True)
    make_object("Spearhead", sol, M["steel"], lambda bm: spear(bmesh.new(), bm, P), [BEVEL(0.002)])


def tier2(P, sol, M, rng):
    """Norman-English knight, 12th century."""
    make_object("Gambeson", sol, M["linen"], lambda bm: garment(bm, P, 0.6, 0.026, "long", 0.07, ridge=0.006), [SOLID(0.008)], True)
    make_object("Mail Hauberk", sol, M["mail"], lambda bm: garment(bm, P, 0.56, 0.045, "long", 0.078, ridge=0.005, every=0.02), [SOLID(0.008)], True)
    make_object("Mail Chausses", sol, M["mail"], lambda bm: hose(bm, 0.018, 0.04), smooth=True)
    make_object("Mail Coif", sol, M["mail"], coif, [SOLID(0.006)], True)
    make_object("Surcoat", sol, M["white"], lambda bm: garment(bm, P, 0.42, 0.065, None, top=1.45), [SOLID(0.006)], True)
    def cross(bm):   # St George's cross on the breast (see notes on dating)
        y = front_y(1.22, 0.075) - 0.006
        add_box(bm, (0.07, 0.008, 0.36), T(0, y, 1.2)); add_box(bm, (0.28, 0.008, 0.07), T(0, y - 0.001, 1.27))
    make_object("Red Cross", sol, M["red"], cross)
    def helm(bm):
        rx, ry, brow = conical(bm, 0.03, HEAD_C.z + 0.04); band(bm, rx, ry, brow + 0.008); nasal(bm, brow, ry + 0.006, 0.085)
    make_object("Conical Nasal Helm", sol, M["steel"], helm, [SOLID(0.004)])
    make_object("Sword Belt", sol, M["leather"], lambda bm: belt_ring(bm, 0.97, 0.085, 0.035), [SOLID(0.006)])
    top, d = V((0.2, -0.1, 0.97)), V((0.06, 0.32, -0.94))
    make_object("Scabbard", sol, M["leather"], lambda bm: scabbard(bm, bmesh.new(), top, d, 0.82, flat=V((0.95, -0.3, 0))), smooth=True)
    make_object("Scabbard Fittings", sol, M["brass"], lambda bm: scabbard(bmesh.new(), bm, top, d, 0.82, flat=V((0.95, -0.3, 0))))
    make_object("Arming Sword Grip", sol, M["leather"], lambda bm: hilt(bm, bmesh.new(), top, -d, 0.095, 0.19, "wheel", V((0.95, -0.3, 0))), smooth=True)
    make_object("Arming Sword Guard & Wheel Pommel", sol, M["steel"], lambda bm: hilt(bmesh.new(), bm, top, -d, 0.095, 0.19, "wheel", V((0.95, -0.3, 0))), [BEVEL(0.002)])
    make_object("Kite Shield", sol, M["shield"], lambda bm: kite_shield(bm, bmesh.new(), bmesh.new(), P), [SOLID(0.012)], True)
    make_object("Kite Shield Edging", sol, M["leather"], lambda bm: kite_shield(bmesh.new(), bm, bmesh.new(), P), smooth=True)
    make_object("Kite Shield Boss", sol, M["steel"], lambda bm: kite_shield(bmesh.new(), bmesh.new(), bm, P), smooth=True)
    make_object("Leather Shoes", sol, M["leather"], turnshoes, [BEVEL(0.01)])


def tier3(P, sol, M, rng):
    """English longbowman, Hundred Years' War."""
    make_object("Wool Hose", sol, M["red"], lambda bm: hose(bm), smooth=True)
    make_object("Padded Gambeson", sol, M["linen"], lambda bm: garment(bm, P, 0.7, 0.035, "long", 0.072, ridge=0.009), [SOLID(0.012)], True)
    make_object("Brigandine (Velvet)", sol, M["blue"], lambda bm: add_lathe(bm, shell_profile(0.86, 1.44, 0.07), seg=18, sy=sqo(0.07)), [SOLID(0.012)], True)
    def rivets(bm):
        z = 0.9
        while z < 1.42:
            R = body_r(z, 0.084)
            for k in range(14):
                a = TAU * k / 14 + (0.11 if int(z * 100) % 2 else 0)
                add_ico(bm, 0.006, T(R * math.cos(a), R * math.sin(a) * sqo(0.084, z), z), sub=1)
            z += 0.05
    make_object("Brigandine Rivets", sol, M["brass"], rivets)
    def cerv(bm):
        rx, ry, brow, top = bowl(bm, 0.008, HEAD_C.z + 0.04)
    make_object("Cervelliere", sol, M["steel"], cerv, [SOLID(0.004)], True)
    make_object("Archer's Bracer", sol, M["leather"], lambda bm: add_limb(bm, P.el("L").lerp(P.wr("L"), 0.3), P.el("L").lerp(P.wr("L"), 0.92), 0.056, 0.05, seg=10, cap=False), [SOLID(0.006)], True)
    make_object("Belt", sol, M["leather"], lambda bm: belt_ring(bm, 0.95, 0.09, 0.035), [SOLID(0.006)])
    make_object("Yew Longbow", sol, M["yew"], lambda bm: longbow(bm, bmesh.new(), bmesh.new(), bmesh.new(), P), smooth=True)
    make_object("Horn Nocks", sol, M["horn"], lambda bm: longbow(bmesh.new(), bm, bmesh.new(), bmesh.new(), P), smooth=True)
    make_object("Bowstring", sol, M["string"], lambda bm: longbow(bmesh.new(), bmesh.new(), bm, bmesh.new(), P))
    make_object("Bow Grip Wrap", sol, M["leather"], lambda bm: longbow(bmesh.new(), bmesh.new(), bmesh.new(), bm, P), smooth=True)
    make_object("Arrow Shafts", sol, M["ash"], lambda bm: arrows_in_belt(bm, bmesh.new(), bmesh.new(), 0.95, 0.1))
    make_object("Goose Fletching", sol, M["white"], lambda bm: arrows_in_belt(bmesh.new(), bm, bmesh.new(), 0.95, 0.1))
    make_object("Bodkin Heads", sol, M["steel"], lambda bm: arrows_in_belt(bmesh.new(), bmesh.new(), bm, 0.95, 0.1))
    top, d = V((-0.2, -0.04, 0.95)), V((-0.05, 0.36, -0.93))
    make_object("Falchion Scabbard", sol, M["leather"], lambda bm: scabbard(bm, bmesh.new(), top, d, 0.62, flat=V((0.95, 0.3, 0)), falchion=True), [BEVEL(0.003)])
    make_object("Falchion Locket", sol, M["brass"], lambda bm: scabbard(bmesh.new(), bm, top, d, 0.62, flat=V((0.95, 0.3, 0)), falchion=True))
    make_object("Falchion Grip", sol, M["leather"], lambda bm: hilt(bm, bmesh.new(), top, -d, 0.1, 0.16, "disc", V((0.95, 0.3, 0))), smooth=True)
    make_object("Falchion Guard & Pommel", sol, M["steel"], lambda bm: hilt(bmesh.new(), bm, top, -d, 0.1, 0.16, "disc", V((0.95, 0.3, 0))), [BEVEL(0.002)])
    make_object("Ankle Shoes", sol, M["leather"], turnshoes, [BEVEL(0.01)])


def tier4(P, sol, M, rng):
    """Knight of Agincourt, c.1415."""
    make_object("Arming Doublet", sol, M["linen"], lambda bm: garment(bm, P, 0.82, 0.024, "long", 0.066), [SOLID(0.006)], True)
    make_object("Mail Haubergeon", sol, M["mail"], lambda bm: garment(bm, P, 0.74, 0.042, "elbow", 0.078, ridge=0.005, every=0.02), [SOLID(0.008)], True)
    make_object("Breastplate & Backplate", sol, M["steel"], lambda bm: breastplate(bm, 0.95, 1.44, 0.075, "globular"), [SOLID(0.005), BEVEL(0.002)], True)
    make_object("Fauld", sol, M["steel"], lambda bm: fauld(bm, 0.96, 3, 0.088), [SOLID(0.004)], True)
    make_object("Arm Harness", sol, M["steel"], lambda bm: [arm_harness(bm, P, s, sx, 4, 0.1) for s, sx in SIDES], [SOLID(0.004)], True)
    make_object("Gauntlets", sol, M["steel"], lambda bm: [gauntlet(bm, P, s, sx, 0.07, fingers=False) for s, sx in SIDES], [SOLID(0.003)])
    make_object("Leg Harness", sol, M["steel"], lambda bm: leg_harness(bm, pointed=False), [SOLID(0.004)], True)
    make_object("Hose", sol, M["red"], lambda bm: hose(bm), smooth=True)
    def bascinet(bm):
        c = T(HEAD_C.x, HEAD_C.y, 0); r = HEAD_R + 0.03
        v = add_dome(bm, r * 0.95, r * 1.05, 0.16, T(HEAD_C.x, HEAD_C.y + 0.01, HEAD_C.z + 0.02), seg=18, rings=6)
        for x in v:                                                                    # skull drawn up to a rear-set point
            h = max(0.0, x.co.z - (HEAD_C.z + 0.08)); x.co.y += h * 0.5; x.co.z += h * 0.35
        add_lathe(bm, [(r * 0.97, HEAD_C.z - 0.08), (r * 0.96, HEAD_C.z + 0.02)], c, seg=18, sy=1.05, a0=0.35, a1=math.pi - 0.35)   # cheeks/nape
        # klappvisier: snouted visor hinged at the brow, with a sight slit
        def visor(z0, z1, snout):
            vv = add_lathe(bm, [(r * 1.02, z0), (r * 1.04, z1)], c, seg=14, sy=1.08, a0=-math.pi + 0.45, a1=-0.45)
            for x in vv:
                ang = math.atan2(x.co.y - HEAD_C.y, x.co.x - HEAD_C.x)
                x.co.y -= snout * max(0.0, 1 - abs(ang + math.pi / 2) / 1.1) * (1 - abs(x.co.z - (HEAD_C.z - 0.01)) / 0.12)
        visor(HEAD_C.z - 0.1, HEAD_C.z + 0.005, 0.11)
        visor(HEAD_C.z + 0.02, HEAD_C.z + 0.05, 0.035)
    make_object("Great Bascinet with Klappvisier", sol, M["steel"], bascinet, [SOLID(0.004)], True)
    make_object("Bascinet Brass Rivets", sol, M["brass"], lambda bm: [add_ico(bm, 0.009, T(sx * (HEAD_R + 0.035), HEAD_C.y - 0.03, HEAD_C.z + 0.035), sub=1) for sx in (1, -1)])
    make_object("Mail Aventail", sol, M["mail"], lambda bm: aventail(bm, HEAD_R + 0.03, HEAD_C.z - 0.07), [SOLID(0.006)], True)
    make_object("Heavy Sword Belt", sol, M["leather"], lambda bm: belt_ring(bm, 0.88, 0.13, 0.05), [SOLID(0.008)])
    make_object("Belt Plaques", sol, M["brass"], lambda bm: [add_box(bm, (0.035, 0.008, 0.04), T((torso_r(0.88) + 0.138) * math.cos(a), (torso_r(0.88) + 0.138) * math.sin(a) * sqo(0.138, 0.88), 0.88) @ RZ(a - math.pi / 2)) for a in [-math.pi / 2 + k * 0.32 for k in range(-4, 5)]])
    top, d = V((0.24, -0.08, 0.88)), V((0.08, 0.3, -0.95))
    make_object("Longsword Scabbard", sol, M["leather"], lambda bm: scabbard(bm, bmesh.new(), top, d, 0.92, 0.032, 0.016, V((0.95, -0.3, 0))), smooth=True)
    make_object("Scabbard Chape & Locket", sol, M["brass"], lambda bm: scabbard(bmesh.new(), bm, top, d, 0.92, 0.032, 0.016, V((0.95, -0.3, 0))))
    make_object("Longsword Grip", sol, M["leather"], lambda bm: hilt(bm, bmesh.new(), top, -d, 0.19, 0.24, "scent", V((0.95, -0.3, 0))), smooth=True)
    make_object("Longsword Cross & Scent-Stopper Pommel", sol, M["steel"], lambda bm: hilt(bmesh.new(), bm, top, -d, 0.19, 0.24, "scent", V((0.95, -0.3, 0))), [BEVEL(0.002)])


def tier5(P, sol, M, rng):
    """Wars of the Roses man-at-arms."""
    make_object("Arming Doublet", sol, M["linen"], lambda bm: garment(bm, P, 0.84, 0.022, "long", 0.064), [SOLID(0.006)], True)
    make_object("Fluted Breastplate", sol, M["steel"], lambda bm: breastplate(bm, 0.93, 1.44, 0.07, "fluted"), [SOLID(0.005), BEVEL(0.0015)], True)
    make_object("Fauld & Tassets", sol, M["steel"], lambda bm: (fauld(bm, 0.94, 3, 0.082), tassets(bm, 0.84, 3)), [SOLID(0.004)], True)
    make_object("Fluted Arm Harness", sol, M["steel"], lambda bm: [arm_harness(bm, P, s, sx, 5, 0.11) for s, sx in SIDES], [SOLID(0.004)], True)
    make_object("Articulated Gauntlets", sol, M["steel"], lambda bm: [gauntlet(bm, P, s, sx, 0.082, fingers=True) for s, sx in SIDES], [SOLID(0.003)])
    make_object("Gothic Leg Harness", sol, M["steel"], lambda bm: leg_harness(bm, pointed=True), [SOLID(0.004)], True)
    make_object("Hose", sol, M["blue"], lambda bm: hose(bm), smooth=True)
    def sallet(bm):
        def f(u, v):                                   # bowl with a long flared tail at the back
            a = u * TAU - math.pi / 2; back = max(0.0, math.sin(a))
            rim = HEAD_C.z + 0.035 - back * 0.13; zt = HEAD_C.z + HEAD_R * 1.08 + 0.03
            z = zt - (zt - rim) * v; theta = v * (math.pi / 2) * (1 + 0.25 * back)
            rr = (HEAD_R + 0.03) * math.sin(min(theta, math.pi / 2)) + back * 0.06 * max(0.0, v - 0.75) / 0.25
            return V((HEAD_C.x + rr * math.cos(a) * 0.95, HEAD_C.y + rr * math.sin(a) * 1.08, z))
        add_surface(bm, f, 24, 8, closed_u=True)
        c = T(HEAD_C.x, HEAD_C.y, 0); r = HEAD_R + 0.033
        add_lathe(bm, [(r * 1.0, HEAD_C.z - 0.03), (r * 1.02, HEAD_C.z + 0.02)], c, seg=14, sy=1.08, a0=-math.pi + 0.5, a1=-0.5)   # visor (slit above it)
    make_object("Sallet with Visor", sol, M["steel"], sallet, [SOLID(0.004)], True)
    make_object("Bevor", sol, M["steel"], lambda bm: add_lathe(bm, [(0.17, 1.42), (0.14, 1.5), (HEAD_R + 0.025, HEAD_C.z - 0.035)], T(HEAD_C.x, HEAD_C.y - 0.01, 0), seg=14, sy=1.1, a0=-math.pi + 0.25, a1=-0.25), [SOLID(0.005)], True)
    make_object("Brass Edging", sol, M["brass"], lambda bm: add_torus(bm, torso_r(1.44) + 0.074, 0.005, T(0, 0, 1.44) @ S(1, sqo(0.074, 1.44), 1), seg=24, rseg=4))
    make_object("Poleaxe Haft", sol, M["ash"], lambda bm: poleaxe(bm, bmesh.new(), P), smooth=False)
    make_object("Poleaxe Head, Languets & Rondel", sol, M["steel"], lambda bm: poleaxe(bmesh.new(), bm, P), [BEVEL(0.002)])


def tier6(P, sol, M, rng):
    """Tudor royal guard / foot soldier, c.1510s-1540s."""
    make_object("Shirt & Doublet", sol, M["linen"], lambda bm: garment(bm, P, 0.86, 0.022, "long", 0.07), [SOLID(0.006)], True)
    make_object("Ridged Breastplate", sol, M["steel"], lambda bm: breastplate(bm, 0.92, 1.43, 0.07, "ridge"), [SOLID(0.005), BEVEL(0.002)], True)
    make_object("Fauld & Tassets", sol, M["steel"], lambda bm: (fauld(bm, 0.93, 2, 0.08), tassets(bm, 0.86, 4)), [SOLID(0.004)], True)
    def breeches(bm):   # paned, padded trunk hose
        for s, sx in SIDES:
            hp, kn, an = leg(sx)
            F = frame(hp + V((0, 0, -0.03)), kn - hp, V((sx, 0, 0)))
            add_lathe(bm, [(0.1, -0.2), (0.125, -0.12), (0.12, -0.04), (0.098, 0.04)][::-1], F, seg=16, wobble=lambda a, z: 0.008 * math.cos(8 * a))
    make_object("Paned Breeches", sol, M["red"], breeches, smooth=True)
    make_object("Hose", sol, M["red"], lambda bm: hose(bm, 0.008), smooth=True)
    def tabard(bm):     # livery panels front and back, leaving the breastplate's sides showing
        for sgn in (-1, 1):
            def f(u, v, sgn=sgn):
                z = 1.46 - v * 0.56; w = 0.15 + 0.03 * v; x = (2 * u - 1) * w
                y = sgn * ((torso_r(max(z, 0.9)) * SQ + 0.11) * (1 - 0.35 * (x / w) ** 2) + 0.01)
                return V((x, y, z))
            add_surface(bm, f, 8, 10)
        for sx in (1, -1):                                                                 # short shoulder wings
            add_lathe(bm, [(0.075, -0.07), (0.065, 0.0)], frame(V((0.235 * sx, 0, 1.38)), V((0.3 * sx, 0, 1)), V((sx, 0, 0))), seg=10)
    make_object("Tudor Livery Tabard", sol, M["red"], tabard, [SOLID(0.006)], True)
    def trim(bm):
        for sgn in (-1, 1):
            chain(bm, [V((x, sgn * ((torso_r(0.9) * SQ + 0.11) * (1 - 0.35 * (x / 0.18) ** 2) + 0.016), 0.9)) for x in [-0.18 + 0.036 * k for k in range(11)]], 0.006, 4)
            for x in (-0.15, 0.15):
                chain(bm, [V((x + 0.03 * (1.46 - z) / 0.56 * (1 if x > 0 else -1), sgn * ((torso_r(max(z, 0.9)) * SQ + 0.11) * (1 - 0.35 * 0.9) + 0.016), z)) for z in [1.46 - 0.056 * k for k in range(11)]], 0.006, 4)
    make_object("Tabard Gold Trim", sol, M["gold"], trim, smooth=True)
    yf = -((torso_r(1.22) * SQ + 0.11) + 0.02)
    def rose(bm, ring):   # Tudor rose in relief: red outer petals, white inner petals, gold seed, green barbs
        for k in range(5):
            a = TAU * k / 5 + (math.pi / 5 if ring == "w" else 0)
            r, s = (0.042, 0.03) if ring == "r" else (0.022, 0.018)
            add_sphere(bm, s, T(r * math.cos(a), yf - (0.004 if ring == "r" else 0.012), 1.22 + r * math.sin(a)) @ S(1, 0.35, 1), u=8, v=5)
    make_object("Tudor Rose (Red Petals)", sol, M["red"], lambda bm: rose(bm, "r"), smooth=True)
    make_object("Tudor Rose (White Petals)", sol, M["rose_w"], lambda bm: rose(bm, "w"), smooth=True)
    make_object("Tudor Rose (Seed & Crown)", sol, M["gold"], lambda bm: add_sphere(bm, 0.014, T(0, yf - 0.02, 1.22) @ S(1, 0.5, 1), u=8, v=5), smooth=True)
    make_object("Tudor Rose (Barbs)", sol, M["rose_g"], lambda bm: [add_box(bm, (0.012, 0.004, 0.02), T(0.06 * math.cos(a), yf + 0.002, 1.22 + 0.06 * math.sin(a)) @ RY(-a)) for a in [TAU * k / 5 + math.pi / 5 for k in range(5)]])
    def burgonet(bm):
        rx, ry, brow, top = bowl(bm, 0.022, HEAD_C.z + 0.035)
        chain(bm, [V((0, HEAD_C.y + math.cos(t) * (ry + 0.004), brow + math.sin(t) * (top - brow + 0.02))) for t in [math.pi * k / 12 for k in range(13)]], 0.004, 4)    # comb (thin)
        for k in range(1, 12):                                                             # raised comb plates
            t = math.pi * k / 12; p = V((0, HEAD_C.y + math.cos(t) * (ry + 0.012), brow + math.sin(t) * (top - brow + 0.03)))
            add_box(bm, (0.005, 0.034, 0.03), frame(p, p - V((0, HEAD_C.y, brow)), V((1, 0, 0))))
        add_lathe(bm, [(rx + 0.055, brow - 0.004), (rx + 0.01, brow + 0.012)], T(HEAD_C.x, HEAD_C.y, 0), seg=10, sy=ry / rx, a0=-math.pi + 0.55, a1=-0.55)   # peak over the eyes
        for sx in (1, -1):                                                                 # hinged cheek pieces
            add_box(bm, (0.012, 0.075, 0.1), T(sx * (rx + 0.004), HEAD_C.y - 0.015, brow - 0.07) @ RX(0.15))
        add_lathe(bm, [(rx + 0.05, brow - 0.07), (rx + 0.008, brow + 0.004)], T(HEAD_C.x, HEAD_C.y, 0), seg=10, sy=ry / rx, a0=0.55, a1=math.pi - 0.55)        # neck guard
    make_object("Burgonet", sol, M["steel"], burgonet, [SOLID(0.004)], True)
    make_object("Bear's-Paw Shoes", sol, M["leather"], lambda bm: turnshoes(bm, 0.07, wide=True), [BEVEL(0.01)])
    make_object("Bill Shaft", sol, M["ash"], lambda bm: bill(bm, bmesh.new(), P), smooth=False)
    make_object("Bill Head (Hook, Spike, Beak)", sol, M["steel"], lambda bm: bill(bmesh.new(), bm, P), [BEVEL(0.0015)])

# ============================================================== labels / camera / light
def add_label(coll, sol, text):
    cu = bpy.data.curves.new("SoldierLabel", 'FONT'); cu.body = text; cu.size = 0.1; cu.align_x = 'CENTER'
    ob = bpy.data.objects.new("Label " + text.split("\n")[0], cu); coll.objects.link(ob)
    ob.parent = sol; ob.location = (0, -0.7, 0.26); ob.rotation_euler = (math.pi / 2, 0, 0)


def ensure_camera_and_light(n):
    sc = bpy.context.scene
    if not any(o.type == 'LIGHT' for o in sc.objects):
        sun = bpy.data.objects.new("Sun", bpy.data.lights.new("Sun", 'SUN')); sun.data.energy = 3.0
        sun.rotation_euler = (math.radians(55), 0, math.radians(-30)); sc.collection.objects.link(sun)
    if sc.camera is None:
        cam = bpy.data.objects.new("Camera", bpy.data.cameras.new("Camera")); sc.collection.objects.link(cam); sc.camera = cam
        cam.location = ((n - 1) * SPACING / 2, -12.5, 1.25); cam.rotation_euler = (math.radians(88), 0, 0); cam.data.lens = 28

# ============================================================== main
TIERS = [
    ("Anglo-Saxon Select Fyrdman c.1066", tier1, Pose(R=HOLD_POLE_R)),
    ("Norman-English Knight 12th c.", tier2, Pose(L={"el": (0.3, 0.0, 1.14), "wr": (0.13, -0.2, 1.1)})),
    ("English Longbowman 14th c.", tier3, Pose(L={"el": (0.3, 0.0, 1.14), "wr": (0.33, -0.26, 1.07)})),
    ("Knight of Agincourt c.1415", tier4, HANG),
    ("Wars of the Roses Man-at-Arms", tier5, Pose(R=HOLD_POLE_R)),
    ("Tudor Royal Guard c.1510-1540", tier6, Pose(R=HOLD_POLE_R)),
]


# ============================================================== cloth fitted to the MakeHuman body (used when MH_CH is set)
MH_CH = None
HEAD_C0, TORSO0, SQ0, LEGS0 = HEAD_C.copy(), list(TORSO), SQ, (HIP.copy(), KNEE.copy(), ANKLE.copy())


def _mh_world_z(co): return (MH_CH.base.matrix_world @ co).z


def mh_garment(bm, hem, off, sleeves, ridge, every, top, tatter):
    ch = MH_CH; Mw = ch.base.matrix_world; Mi = Mw.inverted()
    pelvis_z = ch.joint("thigh_l").z; neck_cut = ch.joint("neck_01").z + 0.012 - max(0.0, 1.47 - top)
    rb = {s: (ch.rest_bone("upperarm_" + s), ch.rest_bone("lowerarm_" + s), ch.rest_bone("hand_" + s)) for s in "lr"}
    def arm_ok(v, b):
        s = b[-1]; sh, el, wr = rb[s]; Lu, Lf = (el - sh).length, (wr - el).length
        if b.startswith("hand"): return False
        if sleeves is None: return False
        if b.startswith("upperarm"): return sleeves != "short" or (v.co - sh).length < 0.6 * Lu
        if sleeves == "long": return True
        if sleeves == "mid": return (v.co - el).length < 0.55 * Lf
        if sleeves == "elbow": return (v.co - el).length < 0.06
        return False
    def keep_upper(v):
        if not ch.in_group(v, "helper-tights", 0.3): return False
        z = (Mw @ v.co).z
        if z < pelvis_z - 0.03 or z > neck_cut: return False
        b = ch.dominant(v) or ""
        if b.startswith(("upperarm", "lowerarm", "hand")): return arm_ok(v, b)
        return True
    ridge_fn = (lambda co: off + (ridge if int(_mh_world_z(co) / every) % 2 else 0.0)) if ridge else None
    bm.from_mesh(ch.surface(keep_upper, off, ridge_fn))
    if hem < pelvis_z:                                                           # skirt from the skirt helper, flared toward the hem
        loc_hem, loc_top = (Mi @ V((0, 0, hem))).z, (Mi @ V((0, 0, pelvis_z))).z
        cy = (Mi @ V((0, 0, 0))).y
        def keep_skirt(v): return ch.in_group(v, "helper-skirt", 0.3) and hem - 0.01 < (Mw @ v.co).z < pelvis_z + 0.06
        def flare(co):
            t = max(0.0, min(1.0, (loc_top - co.z) / max(1e-3, loc_top - loc_hem))); s = 1 + 0.22 * t * t
            co = V((co.x * s, cy + (co.y - cy) * s, co.z))
            if tatter and co.z < loc_hem + 0.02: co.z += tatter * 0.5 * math.sin(co.x * 90 + co.y * 70)
            return co
        bm.from_mesh(ch.surface(keep_skirt, off + 0.006, deform=flare, smooth=3))


def mh_hose(bm, r, z_bottom):
    ch = MH_CH; Mw = MH_CH.base.matrix_world; pelvis_z = ch.joint("thigh_l").z
    legs = ("thigh", "calf") + (("foot", "ball") if z_bottom < 0.07 else ())
    def keep(v):
        if not ch.in_group(v, "helper-tights", 0.3): return False
        z = (Mw @ v.co).z
        return z_bottom < z < pelvis_z + 0.02 and (ch.dominant(v) or "").startswith(legs)
    bm.from_mesh(ch.surface(keep, r * 0.8, smooth=3))


def mh_measure(ch):
    """Re-centre the character on the torso and refit the kit's body constants (torso profile, depth ratio, legs, head)."""
    global HEAD_C, TORSO, SQ, HIP, KNEE, ANKLE
    pts = [ch.world(v.co) for v in ch.base.data.vertices if ch.in_group(v, "body") and (ch.dominant(v) or "").startswith(("spine", "pelvis", "clavicle"))]
    sl = [p for p in pts if abs(p.z - 1.2) < 0.03]; cy = (min(p.y for p in sl) + max(p.y for p in sl)) / 2
    ch.rig.location.y -= cy; bpy.context.view_layer.update()
    cr = ch.crown(); hc = ch.head_centre()
    HEAD_C = V((0.0, hc.y, cr - 0.117))                                         # helmets follow this head
    prof = ch.torso_profile([z for _, z in TORSO0], 0.0)
    TORSO = [(p[0] if p else r0, z) for p, (r0, z) in zip(prof, TORSO0)]
    TORSO[0] = (max(TORSO[0][0], TORSO[1][0] * 0.97), TORSO[0][1])
    ratios = [p[1] / p[0] for p, (_, z) in zip(prof, TORSO0) if p and 1.0 <= z <= 1.35]
    SQ = sum(ratios) / len(ratios) if ratios else SQ0
    HIP, KNEE, ANKLE = ch.joint("thigh_l"), ch.joint("calf_l"), ch.joint("foot_l")
    print("MH_FIT torso", [(round(r, 3), z) for r, z in TORSO], "SQ", round(SQ, 3), "legs", [tuple(round(c, 3) for c in p) for p in (HIP, KNEE, ANKLE)])


def mh_reset():
    global HEAD_C, TORSO, SQ, HIP, KNEE, ANKLE, MH_CH
    HEAD_C, TORSO, SQ = HEAD_C0.copy(), list(TORSO0), SQ0; HIP, KNEE, ANKLE = (p.copy() for p in LEGS0); MH_CH = None

# ============================================================== MakeHuman bodies (optional: needs MPFB + MakeHuman data + mh_character.py)
# Each soldier's head, neck and hands come from a posed MakeHuman character (CC0 skin, eyes, brows, lashes, hair, beard);
# everything under the kit stays hidden. The arm pose keeps the tier's intent but uses the MakeHuman skeleton's lengths.
MH_CAST = {
    1: dict(macro=dict(age=0.38, muscle=0.6, weight=0.48), skin="young_caucasian_male", eye="brownlight", hair="short02", tint=(0.2, 0.12, 0.06), beard="short", show=("head", "neck", "hands"), hair_on=True, grip="R"),
    2: dict(macro=dict(age=0.55, muscle=0.7, weight=0.55), skin="middleage_caucasian_male", eye="brown", hair="short01", tint=(0.12, 0.08, 0.05), beard=None, show=("head", "hands"), hair_on=False, grip="L"),
    3: dict(macro=dict(age=0.32, muscle=0.66, weight=0.45), skin="young_caucasian_male", eye="bluegreen", hair="short04", tint=(0.32, 0.2, 0.09), beard="short", show=("head", "neck", "hands"), hair_on=True, grip="L"),
    4: dict(macro=dict(age=0.5, muscle=0.72, weight=0.55), skin="middleage_caucasian_male", eye="grey", hair=None, tint=(0.15, 0.1, 0.06), beard=None, show=("head",), hair_on=False, grip=None),
    5: dict(macro=dict(age=0.45, muscle=0.7, weight=0.52), skin="young_caucasian_male", eye="blue", hair=None, tint=(0.25, 0.16, 0.08), beard=None, show=("head",), hair_on=False, grip=None),
    6: dict(macro=dict(age=0.6, muscle=0.68, weight=0.6), skin="middleage_caucasian_male", eye="brown", hair="short02", tint=(0.16, 0.1, 0.05), beard="full", show=("head", "neck", "hands"), hair_on=True, grip="R"),
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


def build_mh_soldier(coll, x0, P0, tier, MHC):
    global HEAD_R, MH_CH
    mh_reset()
    cfg = MH_CAST[tier]
    macro = {"gender": 1.0, "proportions": 0.6, "height": 0.5, "cupsize": 0.5, "firmness": 0.5, "race": {"asian": 0.0, "caucasian": 1.0, "african": 0.0}}
    macro.update(cfg["macro"])
    ch = MHC.MHCharacter(macro, skin=cfg["skin"], name="Tier%d" % tier)
    ch.fit_height(HEAD_C0.z + 0.117, (HEAD_C0.x, HEAD_C0.y))                 # same stature as the kit; feet on the ground
    mh_measure(ch)
    # helmets are sized from HEAD_R: grow it so they clear this head (and its hair) rather than sinking into it
    HEAD_R = max(0.108, (ch.crown() + (0.016 if cfg["hair_on"] and cfg["hair"] else 0.004) - HEAD_C.z) / 1.08)
    P = Pose()
    for s, sx in SIDES:                                   # same arm directions as the tier's pose, MakeHuman bone lengths
        Lu, Lf = ch.arm_lengths(s); sh = ch.shoulder(s)
        el = sh + (P0.el(s) - P0.sh(s)).normalized() * Lu
        wr = el + (P0.wr(s) - P0.el(s)).normalized() * Lf
        P.j[s] = {"sh": sh, "el": el, "wr": wr}
        ch.aim_arm(s, el, wr)
        ch.curl_fingers(s, 1.0 if cfg["grip"] == s else 0.3)
    ch.add_face(eye=cfg["eye"], hair=cfg["hair"], hair_tint=cfg["tint"], beard=cfg["beard"])
    obs = ch.bake(show=cfg["show"], hair=cfg["hair_on"], name="Tier %d Soldier" % tier,
                  neck_column=(1.43, 0.105, ch.joint("neck_01").y - 0.01) if "neck" in cfg["show"] else None)
    MH_CH = ch                                            # cloth builders read the posed body until the kit is done
    body = obs[0]
    for ob in obs:
        for c in ob.users_collection: c.objects.unlink(ob)
        coll.objects.link(ob)
        if ob is not body: ob.parent = body
    body.location = (x0, 0, 0)
    return body, P, ch

def main():
    clear_scene(); mats = build_materials(); MHC = _load_mh()
    for i, (title, fn, pose) in enumerate(TIERS):
        coll = bpy.data.collections.new("Tier %d - %s" % (i + 1, title)); bpy.context.scene.collection.children.link(coll)
        if MHC is not None:
            sol, pose, ch = build_mh_soldier(coll, i * SPACING, pose, i + 1, MHC)
        else:
            sol = build_mannequin(coll, i * SPACING, pose); sol.name = "Tier %d Soldier" % (i + 1); sol.data.materials.append(mats["mannequin"])
        fn(pose, sol, mats, random.Random(SEED + i))
        if MHC is not None: ch.remove_rig(); mh_reset()
        add_label(coll, sol, "TIER %d\n%s" % (i + 1, title))
    ensure_camera_and_light(len(TIERS))
    print("English soldiers generated:", ", ".join(c.name for c in bpy.data.collections if c.name.startswith("Tier ")))


if __name__ == "__main__":
    main()
