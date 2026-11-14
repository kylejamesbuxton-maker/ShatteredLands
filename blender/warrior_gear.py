"""
Refits the clothing of the Unity Asset Store "Warrior viking with red hair and armor" (AgarkovaCG) onto a posed
MakeHuman character from mh_character.MHCharacter, and builds PBR materials for scanned / store assets.

    gear = WarriorGear(ch)                      # ch: posed MHCharacter (arms already aimed)
    objs = gear.fit(["Body", "Coat", "Belt_2", "Bag", "Fur"])   # static, posed, world-space meshes
    push_out(objs["Coat"], [objs["Body"]], 0.004)               # layer cloth outside what it covers

Fitting (no shared topology needed):
  1. Skeleton: every warrior bone is re-posed so its head/tail land on the matching MakeHuman joints. Points are mapped
     segment-by-segment (torso: pelvis->neck, upper arm, forearm, thigh, shin, foot); torso girth is scaled by the
     ratio of shoulder widths. Bones get inherit_scale NONE so stretched parents don't shear children.
  2. Body: garment vertices that end up inside (or within `skin_gap` of) the MakeHuman skin are pushed out along the
     skin normal, then lightly relaxed so the push doesn't leave dents.
Only the historically plausible pieces are used by the tier scripts: Body (shirt, trousers, boots), Coat (long padded
tunic), Belt_2 (studded belt + knotwork buckle), Bag (pouch), Fur (hip pelt), Accessories (neck toggles).
"""
import bpy, bmesh, os, math
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "asset_library", "unity"))
WARRIOR = os.path.join(ROOT, "Viking_Warrior_AgarkovaCG", "Agarkova_CG", "Warrior")


# ======================================================================== materials
def pbr_material(name, albedo=None, normal=None, unity_metal_smooth=None, hdrp_mask=None, alpha=None, rough=0.6, metal=0.0, normal_strength=1.0, rough_range=(0.3, 0.9)):
    """Principled material from Unity-style maps. unity_metal_smooth: R = metallic, A = smoothness.
    hdrp_mask: R = metallic, G = AO, A = smoothness. Roughness = 1 - smoothness."""
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial'); bs = nt.nodes.new('ShaderNodeBsdfPrincipled'); nt.links.new(bs.outputs[0], out.inputs[0])
    bs.inputs["Roughness"].default_value = rough; bs.inputs["Metallic"].default_value = metal

    def tex(path, cs):
        n = nt.nodes.new('ShaderNodeTexImage'); n.image = bpy.data.images.load(path, check_existing=True); n.image.colorspace_settings.name = cs; return n
    if albedo and os.path.exists(albedo):
        a = tex(albedo, 'sRGB'); nt.links.new(a.outputs["Color"], bs.inputs["Base Color"])
        if alpha == "albedo": nt.links.new(a.outputs["Alpha"], bs.inputs["Alpha"])
    if alpha and alpha != "albedo" and os.path.exists(alpha):
        t = tex(alpha, 'Non-Color'); nt.links.new(t.outputs["Color"], bs.inputs["Alpha"])
    if alpha:
        for attr, val in (("surface_render_method", 'DITHERED'), ("blend_method", 'HASHED')):
            if hasattr(m, attr):
                try: setattr(m, attr, val)
                except Exception: pass
    if normal and os.path.exists(normal):
        t = tex(normal, 'Non-Color'); nm = nt.nodes.new('ShaderNodeNormalMap'); nm.inputs["Strength"].default_value = normal_strength
        nt.links.new(t.outputs["Color"], nm.inputs["Color"]); nt.links.new(nm.outputs["Normal"], bs.inputs["Normal"])
    ms = unity_metal_smooth or hdrp_mask
    if ms and os.path.exists(ms):
        t = tex(ms, 'Non-Color'); sep = nt.nodes.new('ShaderNodeSeparateColor'); nt.links.new(t.outputs["Color"], sep.inputs[0])
        nt.links.new(sep.outputs[0], bs.inputs["Metallic"])
        # roughness = 1 - smoothness, remapped into a believable range for the surface (stores often pack alpha = 1
        # where a map has no smoothness, which would otherwise read as wet plastic)
        lo, hi = rough_range
        inv = nt.nodes.new('ShaderNodeMapRange'); inv.inputs["From Min"].default_value = 0.0; inv.inputs["From Max"].default_value = 1.0
        inv.inputs["To Min"].default_value = hi; inv.inputs["To Max"].default_value = lo
        nt.links.new(t.outputs["Alpha"], inv.inputs["Value"]); nt.links.new(inv.outputs["Result"], bs.inputs["Roughness"])
    m["sl_maps"] = repr({"albedo": albedo, "normal": normal, "ms": ms, "packing": "unity" if unity_metal_smooth else ("hdrp" if hdrp_mask else None),
                         "rough_range": list(rough_range), "alpha": alpha})
    return m


def warrior_materials():
    T = os.path.join(WARRIOR, "Art", "Textures")
    mk = lambda k, **kw: pbr_material("SC_Warrior_" + k, os.path.join(T, "Warrior_" + k, "Warrior_%s_albedo.png" % k), os.path.join(T, "Warrior_" + k, "Warrior_%s_normal.png" % k),
                                      unity_metal_smooth=os.path.join(T, "Warrior_" + k, "Warrior_%s_metallic.png" % k), **kw)
    return {"Warrior_armor": mk("armor", rough_range=(0.3, 0.85)), "Warrior_clothes": mk("clothes", rough_range=(0.62, 0.95)), "Warrior_body": mk("body", rough_range=(0.45, 0.9))}


# ======================================================================== geometry helpers
def bvh_of(objs):
    verts, polys, off = [], [], 0
    for o in objs:
        me = o.data; M = o.matrix_world
        verts += [M @ v.co for v in me.vertices]; polys += [[i + off for i in p.vertices] for p in me.polygons]; off += len(me.vertices)
    return BVHTree.FromPolygons(verts, polys)


def push_out(obj, inner, gap=0.004, iters=2, inner_bvh=None):
    """Move obj's vertices that sit inside, or closer than `gap` to, the surface of `inner` objects back outside it.
    Moved vertices are relaxed a little and re-pushed so the result stays smooth."""
    bvh = inner_bvh or bvh_of(inner)
    Mi = obj.matrix_world.inverted(); M = obj.matrix_world
    bm = bmesh.new(); bm.from_mesh(obj.data); bm.verts.ensure_lookup_table()
    moved = set()
    for _ in range(iters):
        for v in bm.verts:
            w = M @ v.co; loc, n, _, _ = bvh.find_nearest(w)
            if loc is None: continue
            d = (w - loc).dot(n)
            if d < gap:
                v.co = Mi @ (loc + n * gap); moved.add(v)
        if moved: bmesh.ops.smooth_vert(bm, verts=list(moved), factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    for v in moved:                                              # final hard guarantee after smoothing
        w = M @ v.co; loc, n, _, _ = bvh.find_nearest(w)
        if loc is not None and (w - loc).dot(n) < gap * 0.8: v.co = Mi @ (loc + n * gap)
    bm.to_mesh(obj.data); bm.free(); obj.data.update()
    return len(moved)


# ======================================================================== the fitter
SEG = {   # warrior bone -> (warrior segment start/end joints, MakeHuman segment start/end joints)
    "torso": (("root.x", "head"), ("neck.x", "head")),
}


class WarriorGear:
    def __init__(self, ch):
        self.ch = ch
        before = set(bpy.data.objects)
        bpy.ops.import_scene.fbx(filepath=os.path.join(WARRIOR, "Art", "Mesh", "Warrior.fbx"))
        self.objs = {o.name.split(".")[0]: o for o in set(bpy.data.objects) - before}
        self.arm = next(o for o in self.objs.values() if o.type == 'ARMATURE')
        mats = warrior_materials()
        for o in self.objs.values():
            if o.type != 'MESH': continue
            for s in o.material_slots:
                if s.material and s.material.name.split(".")[0] in mats: s.material = mats[s.material.name.split(".")[0]]

    # ---------------------------------------------------------------- joints
    def mh(self, bone, tail=False):
        """Posed MakeHuman joint in world space."""
        r = self.ch.rig; pb = r.pose.bones[bone]
        return r.matrix_world @ (pb.tail if tail else pb.head)

    def wr(self, bone, tail=False):
        b = self.arm.data.bones[bone]; return self.arm.matrix_world @ (b.tail_local if tail else b.head_local)

    def _segments(self):
        mh, wr = self.mh, self.wr
        hipW = (wr("thigh_stretch.l") + wr("thigh_stretch.r")) / 2; hipM = (mh("thigh_l") + mh("thigh_r")) / 2
        S = {"torso": (hipW, wr("neck.x"), hipM, mh("neck_01")),
             "head": (wr("neck.x"), wr("head.x", True), mh("neck_01"), mh("head", True))}
        for s, m in (("l", "l"), ("r", "r")):
            S["arm" + s] = (wr("arm_stretch." + s), wr("forearm_stretch." + s), mh("upperarm_" + m), mh("lowerarm_" + m))
            S["fore" + s] = (wr("forearm_stretch." + s), wr("hand." + s), mh("lowerarm_" + m), mh("hand_" + m))
            S["thigh" + s] = (wr("thigh_stretch." + s), wr("leg_stretch." + s), mh("thigh_" + m), mh("calf_" + m))
            S["shin" + s] = (wr("leg_stretch." + s), wr("foot." + s), mh("calf_" + m), mh("foot_" + m))
            S["foot" + s] = (wr("foot." + s), wr("foot." + s, True), mh("foot_" + m), mh("ball_" + m))
        return S

    @staticmethod
    def seg_of(bone):
        import re
        n = bone.lower(); mm = re.search(r"\.([lr])(_end)?$", n); s = mm.group(1) if mm else ""
        if n.startswith(("root", "spine", "shoulder")): return "torso"
        if n.startswith(("neck", "head", "c_skull", "jaw", "eye")): return "head"
        if n.startswith("arm_"): return "arm" + s
        if n.startswith(("forearm", "hand", "index", "middle", "ring", "pinky", "thumb")): return "fore" + s
        if n.startswith("thigh"): return "thigh" + s
        if n.startswith("leg_"): return "shin" + s
        if n.startswith(("foot", "toes")): return "foot" + s
        return "torso"

    @staticmethod
    def map_point(p, seg, k=1.0):
        a, b, A, B = seg
        u = b - a; L = u.length; U = B - A
        if L < 1e-6: return A + (p - a)
        t = (p - a).dot(u) / (L * L); perp = p - (a + u * t)
        q = u.normalized().rotation_difference(U.normalized())
        return A + U * t + (q @ perp) * k

    def fit(self, names, skin_gap=0.006):
        arm = self.arm; S = self._segments()
        # torso girth: ratio of shoulder spans (upper-arm heads)
        kT = (self.mh("upperarm_l") - self.mh("upperarm_r")).length / max(1e-6, (self.wr("arm_stretch.l") - self.wr("arm_stretch.r")).length)
        bpy.context.view_layer.objects.active = arm; bpy.ops.object.mode_set(mode='EDIT')
        for eb in arm.data.edit_bones: eb.inherit_scale = 'NONE'
        bpy.ops.object.mode_set(mode='POSE')
        Mi = arm.matrix_world.inverted()
        order = sorted(arm.data.bones, key=lambda b: len(b.parent_recursive))
        for b in order:
            pb = arm.pose.bones[b.name]; seg = S[self.seg_of(b.name)]; k = kT if seg is S["torso"] else 1.0
            h0, t0 = arm.matrix_world @ b.head_local, arm.matrix_world @ b.tail_local
            if b.name.startswith("shoulder."):                 # clavicle ends exactly on the MakeHuman shoulder joint
                h1 = self.map_point(h0, seg, k); t1 = self.mh("upperarm_" + b.name[-1])
            else:
                h1, t1 = self.map_point(h0, seg, k), self.map_point(t0, seg, k)
            R0 = (arm.matrix_world.to_3x3() @ b.matrix_local.to_3x3()).normalized()
            d0, d1 = t0 - h0, t1 - h1
            if d0.length < 1e-6 or d1.length < 1e-6: continue
            R1 = d0.normalized().rotation_difference(d1.normalized()).to_matrix() @ R0
            sy = d1.length / d0.length; sxz = k if seg is S["torso"] else 1.0
            Mw = Matrix.Translation(h1) @ R1.to_4x4() @ Matrix.Diagonal((sxz, sy, sxz, 1.0))
            pb.matrix = Mi @ Mw
            bpy.context.view_layer.update()
        bpy.ops.object.mode_set(mode='OBJECT')
        # bake the posed garments to static world-space meshes
        dg = bpy.context.evaluated_depsgraph_get(); out = {}
        for n in names:
            o = self.objs.get(n)
            if not o or o.type != 'MESH': continue
            me = bpy.data.meshes.new_from_object(o.evaluated_get(dg)); me.transform(o.matrix_world)
            st = bpy.data.objects.new("WG_" + n, me); bpy.context.collection.objects.link(st)
            for p in me.polygons: p.use_smooth = True
            out[n] = st
        # keep cloth outside the MakeHuman skin
        skin = self.skin_bvh()
        for n, o in out.items():
            if n in ("Body", "Coat"): push_out(o, None, skin_gap, inner_bvh=skin)
        return out

    def skin_bvh(self):
        ch = self.ch; dg = bpy.context.evaluated_depsgraph_get(); ev = ch.base.evaluated_get(dg); me = ev.to_mesh()
        gi = ch.vg.get("body"); keep = set()
        if gi is not None:
            for v in ch.base.data.vertices:
                if any(g.group == gi and g.weight > 0.5 for g in v.groups): keep.add(v.index)
        M = ch.base.matrix_world; verts = [M @ v.co for v in me.vertices]
        polys = [list(p.vertices) for p in me.polygons if all(i in keep for i in p.vertices)]
        ev.to_mesh_clear(); return BVHTree.FromPolygons(verts, polys)

    def remove(self):
        for o in self.objs.values():
            try: bpy.data.objects.remove(o, do_unlink=True)
            except Exception: pass


# ======================================================================== scanned weapons & shields
LIB = ROOT


def import_prop(fbx, material, target_len=None, axis_len='Z'):
    """Import a single-mesh prop, join it, apply the material, centre it at the origin; optional rescale so its longest
    extent equals target_len (metres). Returns the object (static, transforms applied)."""
    before = set(bpy.data.objects)
    if fbx.lower().endswith(".obj"): bpy.ops.wm.obj_import(filepath=fbx)
    else: bpy.ops.import_scene.fbx(filepath=fbx)
    new = [o for o in set(bpy.data.objects) - before]
    meshes = [o for o in new if o.type == 'MESH']
    dg = bpy.context.evaluated_depsgraph_get(); bm = bmesh.new()
    for o in meshes:
        me = bpy.data.meshes.new_from_object(o.evaluated_get(dg)); me.transform(o.matrix_world); bm.from_mesh(me); bpy.data.meshes.remove(me)
    for o in new: bpy.data.objects.remove(o, do_unlink=True)
    me = bpy.data.meshes.new(os.path.splitext(os.path.basename(fbx))[0]); bm.to_mesh(me); bm.free()
    lo = Vector([min(v.co[i] for v in me.vertices) for i in range(3)]); hi = Vector([max(v.co[i] for v in me.vertices) for i in range(3)])
    me.transform(Matrix.Translation(-(lo + hi) / 2))
    if target_len:
        s = target_len / max(hi - lo); me.transform(Matrix.Scale(s, 4))
    me.materials.clear(); me.materials.append(material)
    for p in me.polygons: p.use_smooth = True
    ob = bpy.data.objects.new(me.name, me); bpy.context.collection.objects.link(ob)
    return ob


def end_widths(ob, axis=2, frac=0.15):
    """(width near min end, width near max end) along an axis - tells which end of a sword/axe/spear is the head."""
    vs = [v.co for v in ob.data.vertices]; lo = min(v[axis] for v in vs); hi = max(v[axis] for v in vs); L = hi - lo
    o1, o2 = [i for i in range(3) if i != axis]
    def w(sel): return max((max(v[o1] for v in sel) - min(v[o1] for v in sel)), (max(v[o2] for v in sel) - min(v[o2] for v in sel))) if sel else 0
    return w([v for v in vs if v[axis] < lo + L * frac]), w([v for v in vs if v[axis] > hi - L * frac])
