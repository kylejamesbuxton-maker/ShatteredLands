"""
MakeHuman character builder for showcase / tier scripts (needs MPFB + MakeHuman 1.x data, see mh_assets.py).

    ch = MHCharacter(macro, skin="young_caucasian_male")
    ch.fit_head_to(head_centre)                       # uniform scale + move so the head sits where the kit expects it
    sh = ch.shoulder("L")                             # joint positions for building a pose
    ch.aim_arm("L", elbow, wrist); ch.curl_fingers("R", 1.0)
    ch.add_face(eye="brown", brows="eyebrow003", hair="short02", hair_tint=(...), beard="full"|"moustache"|None)
    obs = ch.bake(show={"head", "neck", "hands"}, hair=True)   # static meshes in world space (posed)

Sides: "L" = +X (MakeHuman/MPFB "_l"), "R" = -X. Characters face -Y.
"""
import bpy, bmesh, os, math, importlib.util
from mathutils import Vector, Matrix

_here = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("mh_assets", os.path.join(_here, "mh_assets.py"))
mh = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(mh)

FINGERS = ("index", "middle", "ring", "pinky")


class MHCharacter:
    def __init__(self, macro, skin="young_caucasian_male", name="MH"):
        import addon_utils
        addon_utils.enable("bl_ext.blender_org.mpfb", default_set=True)
        from bl_ext.blender_org.mpfb.services.humanservice import HumanService
        self.base = HumanService.create_human(macro_detail_dict=macro)
        self.rig = HumanService.add_builtin_rig(self.base, "game_engine"); self.rig.name = name + "Rig"
        for m in list(self.base.modifiers):
            if m.type == 'MASK': self.base.modifiers.remove(m)
        bpy.context.view_layer.objects.active = self.base
        if self.base.data.shape_keys: bpy.ops.object.shape_key_remove(all=True, apply_mix=True)
        mh.apply_skin(self.base, skin)
        self.vg = {g.name: g.index for g in self.base.vertex_groups}
        self.bones = {b.name for b in self.rig.data.bones}
        for pb in self.rig.pose.bones: pb.rotation_mode = 'QUATERNION'
        self.parts = []                                   # (object, kind)
        self._dom = None

    # ---------------------------------------------------------------- helpers
    def in_group(self, v, name, thr=0.5):
        gi = self.vg.get(name)
        return gi is not None and any(g.group == gi and g.weight >= thr for g in v.groups)

    def dominant(self, v):
        best, bw = None, 0.0
        for g in v.groups:
            n = self.base.vertex_groups[g.group].name
            if n in self.bones and g.weight > bw: best, bw = n, g.weight
        return best

    def centroid(self, group):
        pts = [v.co for v in self.base.data.vertices if self.in_group(v, group, 0.01)]
        return sum(pts, Vector()) / len(pts)

    def world(self, co):
        return self.base.matrix_world @ co

    def joint(self, bone, tail=False):
        b = self.rig.data.bones[bone]
        return self.rig.matrix_world @ (b.tail_local if tail else b.head_local)

    def head_centre(self):
        pts = [v.co for v in self.base.data.vertices if self.in_group(v, "body") and self.dominant(v) == "head"]
        lo, hi = Vector([min(p[i] for p in pts) for i in range(3)]), Vector([max(p[i] for p in pts) for i in range(3)])
        return self.world((lo + hi) / 2 + Vector((0, 0, -0.03 * (hi.z - lo.z))))   # bbox centre, nudged down (jaw vs crown)

    # ---------------------------------------------------------------- placement + posing
    def _crown_chin(self):
        pts = [self.world(v.co) for v in self.base.data.vertices if self.in_group(v, "body") and self.dominant(v) == "head"]
        cy = sum(p.y for p in pts) / len(pts)
        return max(p.z for p in pts), min(p.z for p in pts if p.y < cy - 0.03)

    def fit_height(self, crown, target_xy=(0.0, 0.0)):
        """Scale so soles rest on z=0 and the crown sits at `crown`; head centred on target_xy."""
        bpy.context.view_layer.update()
        sole = min(self.world(v.co).z for v in self.base.data.vertices if self.in_group(v, "body"))
        cr, _ = self._crown_chin(); s = crown / (cr - sole)
        self.rig.scale = (s, s, s); bpy.context.view_layer.update()
        sole = min(self.world(v.co).z for v in self.base.data.vertices if self.in_group(v, "body")); c = self.head_centre()
        self.rig.location += Vector((target_xy[0] - c.x, target_xy[1] - c.y, -sole)); bpy.context.view_layer.update()
        return s

    def fit_head_to(self, target, crown=None, chin=None):
        """Uniformly scale + move the character. With crown/chin (world z) the head spans exactly that height;
        otherwise the head's bbox centre lands on `target`."""
        bpy.context.view_layer.update()
        if crown is not None and chin is not None:
            cr, ch = self._crown_chin(); s = (crown - chin) / (cr - ch)
            self.rig.scale = (s, s, s); bpy.context.view_layer.update()
            c = self.head_centre(); cr, _ = self._crown_chin()
            self.rig.location += Vector((target.x - c.x, target.y - c.y, crown - cr))
        else:
            c = self.head_centre(); s = target.z / c.z
            self.rig.scale = (s, s, s); bpy.context.view_layer.update()
            c = self.head_centre(); self.rig.location += Vector((target.x - c.x, target.y - c.y, target.z - c.z))
        bpy.context.view_layer.update()
        return s

    def shoulder(self, side): return self.joint("upperarm_" + side.lower())
    def arm_lengths(self, side):
        s = side.lower(); sc = self.rig.scale.x
        return self.rig.data.bones["upperarm_" + s].length * sc, self.rig.data.bones["lowerarm_" + s].length * sc

    def _aim(self, bone, direction):
        """Rotate pose bone (armature space) so its Y axis points along world `direction`; keeps its roll as best it can."""
        pb = self.rig.pose.bones[bone]; bpy.context.view_layer.update()
        R = self.rig.matrix_world.to_3x3().normalized().inverted()
        d = (R @ Vector(direction)).normalized()
        M = pb.matrix.copy(); y = M.col[1].xyz.normalized()
        q = y.rotation_difference(d)
        rot = q.to_matrix().to_4x4(); head = M.translation.copy()
        M = rot @ M; M.translation = head
        pb.matrix = M; bpy.context.view_layer.update()

    def aim_arm(self, side, elbow, wrist):
        s = side.lower()
        self._aim("upperarm_" + s, Vector(elbow) - self.shoulder(side))
        self._aim("lowerarm_" + s, Vector(wrist) - Vector(elbow))
        # hand continues the forearm line
        self._aim("hand_" + s, Vector(wrist) - Vector(elbow))

    def curl_fingers(self, side, amount=1.0):
        s = side.lower()
        for f in FINGERS:
            for k, ang in ((1, 55), (2, 70), (3, 45)):
                pb = self.rig.pose.bones.get("%s_0%d_%s" % (f, k, s))
                if pb: pb.rotation_quaternion = Matrix.Rotation(math.radians(ang * amount), 4, 'X').to_quaternion() @ pb.rotation_quaternion
        for k, ang in ((2, 25), (3, 30)):
            pb = self.rig.pose.bones.get("thumb_0%d_%s" % (k, s))
            if pb: pb.rotation_quaternion = Matrix.Rotation(math.radians(ang * amount), 4, 'X').to_quaternion() @ pb.rotation_quaternion
        bpy.context.view_layer.update()

    # ---------------------------------------------------------------- face assets
    def add_face(self, eye="brown", brows="eyebrow003", lashes="eyelashes01", hair="short02", hair_tint=(0.2, 0.12, 0.06), beard=None):
        em = mh.material_from_mhmat(os.path.join(mh.MH_DATA, "eyes", "materials", eye + ".mhmat"), "Eyes " + eye, roughness=0.08, alpha_clip=False, tint=(0.8, 0.8, 0.82))
        self.parts.append((mh.fit_asset("eyes", "high-poly", self.base, self.rig, material=em, obj_name="Eyes"), "eyes"))
        if brows: self.parts.append((mh.fit_asset("eyebrows", brows, self.base, self.rig, obj_name="Eyebrows", tint=tuple(c * 0.85 for c in hair_tint)), "brows"))
        if lashes: self.parts.append((mh.fit_asset("eyelashes", lashes, self.base, self.rig, obj_name="Eyelashes", tint=(0.22, 0.16, 0.11)), "lashes"))
        if hair:
            h = mh.fit_asset("hair", hair, self.base, self.rig, obj_name="Hair", tint=hair_tint)
            for m in h.data.materials:
                bs = next(n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'); bs.inputs["Roughness"].default_value = 0.78
            self.parts.append((h, "hair"))
        if beard: self.parts.append((self.make_beard(hair_tint, beard), "beard"))

    def _extract(self, name, keep, offset=0.0):
        ob = self.base.copy(); ob.data = self.base.data.copy(); ob.name = ob.data.name = name
        bpy.context.collection.objects.link(ob)
        bm = bmesh.new(); bm.from_mesh(ob.data); bm.verts.ensure_lookup_table()
        kv = [keep(self.base.data.vertices[i]) for i in range(len(bm.verts))]
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if not all(kv[v.index] for v in f.verts)], context='FACES')
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
        if offset:
            bm.normal_update()
            for v in bm.verts: v.co += v.normal * offset
        bm.to_mesh(ob.data); bm.free(); ob.data.materials.clear()
        return ob

    def make_beard(self, tint, style="full"):
        """Shell-fur beard (8 shells, attributes shell/fade). style: full | short | moustache."""
        mzv, jzv = self.centroid("joint-mouth"), self.centroid("joint-jaw")
        mz, jz, jy, my = mzv.z, jzv.z, jzv.y, mzv.y
        eye_z = (self.centroid("joint-l-eye").z + self.centroid("joint-r-eye").z) / 2
        slot = next((i for i, s in enumerate(self.base.material_slots) if s.material and "lips" in s.material.name.lower()), None)
        LIPS = {vi for p in self.base.data.polygons if p.material_index == slot for vi in p.vertices} if slot is not None else set()
        lipco = [self.base.data.vertices[i].co for i in LIPS]
        lipfront = min(p.y for p in lipco) if lipco else my - 0.03
        def keep(v):
            c = v.co
            if not (self.in_group(v, "body") and self.dominant(v) == "head") or v.index in LIPS or self.in_group(v, "ears", .2): return False
            if c.y > jy + 0.04 or abs(c.x) > 0.072 or c.z < jz - 0.055: return False
            if any((c - p).length < 0.0035 for p in lipco): return False
            if c.z > mz and c.y < lipfront - 0.003: return False
            if abs(c.x) < 0.03 and c.z > mz + 0.017: return False
            if style == "moustache":
                return c.z > mz + 0.002 and c.z < mz + 0.016 and abs(c.x) < 0.04 or (abs(c.x) < 0.012 and c.z < mz - 0.012 and c.z > mz - 0.03)
            if abs(c.x) < 0.045: return c.z < mz + 0.014
            if c.z < mz + 0.006: return True
            return c.z < eye_z - 0.078 + (abs(c.x) - 0.045) * 0.9 and c.y > my - 0.005
        beard = self._extract("Beard", keep, 0.0012)
        bm = bmesh.new(); bm.from_mesh(beard.data); bm.verts.ensure_lookup_table(); bm.normal_update()
        ring = {v: 0 for v in bm.verts if v.is_boundary}; front = list(ring)
        while front:
            nxt = []
            for v in front:
                for e in v.link_edges:
                    o = e.other_vert(v)
                    if o not in ring: ring[o] = ring[v] + 1; nxt.append(o)
            front = nxt
        L_sh, L_fd = bm.verts.layers.float.new("shell"), bm.verts.layers.float.new("fade")
        orig = list(bm.verts); onorm = {v: v.normal.copy() for v in orig}; oco = {v: v.co.copy() for v in orig}
        for v in orig: v[L_sh] = 0.0; v[L_fd] = min(1.0, (ring.get(v, 6) + 0.3) / (3.0 if style == "moustache" else 5.0))
        length = {"full": 1.0, "short": 0.35, "moustache": 0.25}[style]
        for k in range(1, 8):
            t = k / 7
            res = bmesh.ops.duplicate(bm, geom=[f for f in bm.faces if f.verts[0][L_sh] == 0.0] + orig)
            for src, dst in res["vert_map"].items():
                if not isinstance(src, bmesh.types.BMVert) or src not in onorm: continue
                below = min(0.045, max(0.0, (mz - 0.006) - oco[src].z)) * length
                dst.co = oco[src] + onorm[src] * t * (0.003 + 0.002 * length + 0.45 * below) + Vector((0, -0.25 * below * t, -0.75 * below * t * t - (0.004 * t if style == "moustache" else 0)))
                dst[L_sh] = t; dst[L_fd] = src[L_fd]
        bm.to_mesh(beard.data); bm.free()
        beard.data.materials.append(beard_material(tint))
        beard.parent = self.rig
        if not any(m.type == 'ARMATURE' for m in beard.modifiers):
            md = beard.modifiers.new("Armature", 'ARMATURE'); md.object = self.rig
        return beard

    # ---------------------------------------------------------------- bake to static posed meshes
    def crown(self):
        pts = [self.world(v.co) for v in self.base.data.vertices if self.in_group(v, "body") and self.dominant(v) == "head"]
        return max(p.z for p in pts)

    def bake(self, show=("head", "neck", "hands"), hair=True, name="Body", neck_column=None):
        """Posed, static copies in world space. Body keeps only the regions in `show`."""
        bpy.context.view_layer.update(); dg = bpy.context.evaluated_depsgraph_get()
        keep_bones = set()
        if "head" in show: keep_bones |= {"head"}
        if "neck" in show: keep_bones |= {"neck_01"}
        if "hands" in show: keep_bones |= {b for b in self.bones if b.startswith(("hand_",) + tuple(f + "_" for f in FINGERS) + ("thumb_",))}
        wrist = {s: self.rig.data.bones["hand_" + s].head_local for s in "lr"}
        Mw = self.base.matrix_world
        def keep(v):
            if not self.in_group(v, "body"): return False
            if neck_column:                                   # (z_min, radius, centre_y): neck continues down into the collar
                w = Mw @ v.co
                if w.z > neck_column[0] and math.hypot(w.x / neck_column[1], (w.y - neck_column[2]) / (neck_column[1] * 0.78)) < 1.0: return True
            b = self.dominant(v)
            if b in ("lowerarm_l", "lowerarm_r") and "hands" in show: return (v.co - wrist[b[-1]]).length < 0.03
            return b in keep_bones
        out = []
        def static_copy(src, keep_fn, nm):
            ev = src.evaluated_get(dg); me = ev.to_mesh()
            co = [src.matrix_world @ v.co for v in me.vertices]; ev.to_mesh_clear()
            ob = src.copy(); ob.data = src.data.copy(); ob.name = ob.data.name = nm; ob.parent = None; ob.matrix_world = Matrix.Identity(4)
            for m in list(ob.modifiers): ob.modifiers.remove(m)
            for v, c in zip(ob.data.vertices, co): v.co = c
            if keep_fn is not None:
                bm = bmesh.new(); bm.from_mesh(ob.data); bm.verts.ensure_lookup_table()
                kv = [keep_fn(src.data.vertices[i]) for i in range(len(bm.verts))]
                bmesh.ops.delete(bm, geom=[f for f in bm.faces if not all(kv[v.index] for v in f.verts)], context='FACES')
                bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
                bm.to_mesh(ob.data); bm.free()
            ob.vertex_groups.clear()
            for p in ob.data.polygons: p.use_smooth = True
            bpy.context.collection.objects.link(ob); return ob
        out.append(static_copy(self.base, keep, name))
        for ob, kind in self.parts:
            if kind == "hair" and not hair: continue
            if kind != "eyes" and kind != "lashes" and kind != "brows" and kind != "beard" and kind != "hair": continue
            if "head" not in show: continue
            out.append(static_copy(ob, None, ob.name))
        return out

    # ---------------------------------------------------------------- fitted cloth from the body surface
    def rest_bone(self, bone, tail=False):
        b = self.rig.data.bones[bone]; return (b.tail_local if tail else b.head_local).copy()

    def surface(self, keep, offset=0.0, offset_fn=None, smooth=6, deform=None):
        """Posed world-space mesh of the body faces whose rest vertices all pass keep(v), pushed out along the
        normals by offset (or offset_fn(rest_co)), optional deform(rest_co)->rest_co (e.g. skirt flare)."""
        ob = self._extract("_cloth", keep)
        bm = bmesh.new(); bm.from_mesh(ob.data); bm.normal_update()
        nrm = {v: v.normal.copy() for v in bm.verts}; rest = {v: v.co.copy() for v in bm.verts}
        for v in bm.verts:
            d = offset_fn(rest[v]) if offset_fn else offset
            v.co = rest[v] + nrm[v] * d
            if deform: v.co = deform(v.co)
        edge = [v for v in bm.verts if v.is_boundary]
        for _ in range(smooth): bmesh.ops.smooth_vert(bm, verts=edge, factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)
        bm.to_mesh(ob.data); bm.free()
        bpy.context.view_layer.update(); dg = bpy.context.evaluated_depsgraph_get()
        me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg)); me.transform(ob.matrix_world)
        bpy.data.objects.remove(ob, do_unlink=True)
        return me

    def torso_profile(self, zs, centre_y=0.0):
        """Half-width (x) and half-depth (y about centre_y) of the posed-independent torso at world heights zs."""
        bpy.context.view_layer.update()
        arms = {"upperarm_l", "upperarm_r", "lowerarm_l", "lowerarm_r", "hand_l", "hand_r"}
        pts = [self.world(v.co) for v in self.base.data.vertices if self.in_group(v, "body")
               and (self.dominant(v) or "").startswith(("spine", "pelvis", "clavicle", "neck"))]
        out = []
        for z in zs:
            sl = [p for p in pts if abs(p.z - z) < 0.012]
            if not sl: out.append(None); continue
            out.append((max(abs(p.x) for p in sl), max(abs(p.y - centre_y) for p in sl)))
        return out

    def remove_rig(self):
        """Delete the rigged source objects after baking."""
        for ob, _ in self.parts: bpy.data.objects.remove(ob, do_unlink=True)
        bpy.data.objects.remove(self.base, do_unlink=True); bpy.data.objects.remove(self.rig, do_unlink=True)


# ==================================================================== kit helpers shared by the tier scripts
def cloth_garment(ch, hem, off, sleeves="long", ridge=0.0, every=0.05, top=1.47, tatter=0.0):
    """Tunic/coat/mail body from the tights helper (torso + sleeves) plus a flared skirt from the skirt helper.
    sleeves: None | short | elbow | mid | forearm | long. Returns a posed world-space mesh."""
    Mw = ch.base.matrix_world; Mi = Mw.inverted()
    pelvis_z = ch.joint("thigh_l").z; neck_cut = ch.joint("neck_01").z + 0.012 - max(0.0, 1.47 - top)
    rb = {s: (ch.rest_bone("upperarm_" + s), ch.rest_bone("lowerarm_" + s), ch.rest_bone("hand_" + s)) for s in "lr"}
    def arm_ok(v, b):
        s = b[-1]; sh, el, wr = rb[s]; Lu, Lf = (el - sh).length, (wr - el).length
        if b.startswith("hand") or sleeves is None: return False
        if b.startswith("upperarm"): return sleeves != "short" or (v.co - sh).length < 0.6 * Lu
        if sleeves == "long": return True
        if sleeves in ("mid", "forearm"): return (v.co - el).length < 0.6 * Lf
        if sleeves == "elbow": return (v.co - el).length < 0.06
        return False
    def keep_upper(v):
        if not ch.in_group(v, "helper-tights", 0.3): return False
        z = (Mw @ v.co).z
        if z < pelvis_z - 0.03 or z > neck_cut: return False
        b = ch.dominant(v) or ""
        if b.startswith(("upperarm", "lowerarm", "hand")): return arm_ok(v, b)
        return True
    arm_x = min(abs(rb["l"][0].x), abs(rb["r"][0].x)) - 0.015                  # past the shoulder joint: sleeves sit closer
    def off_fn(co):
        o = off + ((ridge if int((Mw @ co).z / every) % 2 else 0.0) if ridge else 0.0)
        return o * 0.55 if abs(co.x) > arm_x else o
    out = bmesh.new(); out.from_mesh(ch.surface(keep_upper, off, off_fn))
    if hem < pelvis_z:
        loc_hem, loc_top = (Mi @ Vector((0, 0, hem))).z, (Mi @ Vector((0, 0, pelvis_z))).z
        cy = (Mi @ Vector((0, 0, 0))).y
        def keep_skirt(v): return ch.in_group(v, "helper-skirt", 0.3) and hem - 0.01 < (Mw @ v.co).z < pelvis_z + 0.06
        def flare(co):
            t = max(0.0, min(1.0, (loc_top - co.z) / max(1e-3, loc_top - loc_hem))); s = 1 + 0.22 * t * t
            co = Vector((co.x * s, cy + (co.y - cy) * s, co.z))
            if tatter and co.z < loc_hem + 0.02: co.z += tatter * 0.5 * math.sin(co.x * 90 + co.y * 70)
            return co
        out.from_mesh(ch.surface(keep_skirt, off + 0.006, deform=flare, smooth=3))
    me = bpy.data.meshes.new("cloth"); out.to_mesh(me); out.free(); return me


def cloth_hose(ch, r, z_bottom, side=None):
    """Hose / trousers from the tights helper legs; side 'l' keeps only the +X leg (for mirrored kits)."""
    Mw = ch.base.matrix_world; pelvis_z = ch.joint("thigh_l").z
    legs = ("thigh", "calf") + (("foot", "ball") if z_bottom < 0.07 else ())
    def keep(v):
        if not ch.in_group(v, "helper-tights", 0.3): return False
        z = (Mw @ v.co).z; b = ch.dominant(v) or ""
        if side and not b.endswith("_" + side): return False
        return z_bottom < z < pelvis_z + 0.02 and b.startswith(legs)
    return ch.surface(keep, r * 0.8, smooth=3)


def kit_constants(ch, torso_template):
    """Centre the character on its torso (y) and measure the constants procedural kits are built round."""
    pts = [ch.world(v.co) for v in ch.base.data.vertices if ch.in_group(v, "body") and (ch.dominant(v) or "").startswith(("spine", "pelvis", "clavicle"))]
    sl = [p for p in pts if abs(p.z - 1.2) < 0.03]; cy = (min(p.y for p in sl) + max(p.y for p in sl)) / 2
    ch.rig.location.y -= cy; bpy.context.view_layer.update()
    cr = ch.crown(); hc = ch.head_centre()
    prof = ch.torso_profile([z for _, z in torso_template], 0.0)
    torso = [(p[0] if p else r0, z) for p, (r0, z) in zip(prof, torso_template)]
    torso[0] = (max(torso[0][0], torso[1][0] * 0.97), torso[0][1])
    ratios = [p[1] / p[0] for p, (_, z) in zip(prof, torso_template) if p and 1.0 <= z <= 1.35]
    return {"head_c": Vector((0.0, hc.y, cr - 0.117)), "crown": cr, "torso": torso, "sq": sum(ratios) / len(ratios) if ratios else 0.7,
            "hip": ch.joint("thigh_l"), "knee": ch.joint("calf_l"), "ankle": ch.joint("foot_l")}


def beard_material(tint):
    """Shell-fur beard: strands thin toward the tips (rising noise threshold per shell); 'fade' feathers the edge."""
    m = bpy.data.materials.new("Beard"); m.use_nodes = True; nt = m.node_tree; bs = nt.nodes["Principled BSDF"]; L = nt.links.new
    for attr, val in (("surface_render_method", 'DITHERED'), ("blend_method", 'HASHED')):
        if hasattr(m, attr):
            try: setattr(m, attr, val)
            except Exception: pass
    def node(t, **kw):
        n = nt.nodes.new(t)
        for k, v in kw.items(): setattr(n, k, v)
        return n
    def op(o, a, b):
        n = node('ShaderNodeMath', operation=o)
        for i, x in enumerate((a, b)):
            if isinstance(x, (int, float)): n.inputs[i].default_value = x
            else: L(x, n.inputs[i])
        return n.outputs[0]
    sh = node('ShaderNodeAttribute', attribute_name="shell").outputs["Fac"]
    fd = node('ShaderNodeAttribute', attribute_name="fade").outputs["Fac"]
    tc = node('ShaderNodeTexCoord'); mp = node('ShaderNodeMapping'); mp.inputs["Scale"].default_value = (760, 760, 110)
    L(tc.outputs["Object"], mp.inputs["Vector"])
    nz = node('ShaderNodeTexNoise'); nz.inputs["Scale"].default_value = 1.0; nz.inputs["Detail"].default_value = 1.0
    L(mp.outputs["Vector"], nz.inputs["Vector"])
    strand = op('GREATER_THAN', nz.outputs["Fac"], op('ADD', op('MULTIPLY', sh, 0.22), 0.4))
    feather = op('POWER', fd, op('ADD', op('MULTIPLY', sh, 2.0), 1.0))
    root = op('MULTIPLY', op('LESS_THAN', sh, 0.01), 0.55)
    L(op('MULTIPLY', op('MAXIMUM', strand, root), feather), bs.inputs["Alpha"])
    ramp = node('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = (*[c * 0.25 for c in tint], 1); ramp.color_ramp.elements[1].color = (*[min(1, c * 1.15) for c in tint], 1)
    vary = node('ShaderNodeTexNoise'); vary.inputs["Scale"].default_value = 140
    L(op('ADD', op('MULTIPLY', sh, 0.75), op('MULTIPLY', vary.outputs["Fac"], 0.35)), ramp.inputs["Fac"])
    L(ramp.outputs["Color"], bs.inputs["Base Color"])
    bs.inputs["Roughness"].default_value = 0.72
    m.diffuse_color = (*tint, 1); m.roughness = 0.8
    return m
