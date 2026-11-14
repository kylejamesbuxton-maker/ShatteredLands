"""
Blender (numpy, no rendering) tool: writes seamless 1024px surface-detail textures for Unreal, plus a JSON of every
Blender material colour/roughness/metallic used by the exported characters.

    blender --background --python make_detail_textures.py -- <models_dir> <out_dir>

Each kind gets <kind>_D.png (grey detail, multiplied with the material's own colour in Unreal) and <kind>_N.png
(tangent-space normal from the same height field). All patterns are built from whole-number frequencies, so the
textures tile with no seams: wool (2/2 twill), linen (plain weave), quilted padding, leather grain, riveted mail rings,
brushed steel, wood grain, fur and gilt (hammered metal).
"""
import bpy, sys, os, json, math
import numpy as np
args = sys.argv[sys.argv.index("--") + 1:]; MD, OUT = args[0], args[1]; os.makedirs(OUT, exist_ok=True)
N = 1024; TAU = 2 * math.pi
u, v = np.meshgrid(np.arange(N) / N, np.arange(N) / N)       # 0..1, periodic
rng = np.random.default_rng(7)


def pnoise(freq, octaves=4, seed=0):
    """Periodic fractal noise: random-phase sums of integer-frequency sinusoids (tiles exactly)."""
    r = np.random.default_rng(seed); out = np.zeros((N, N)); amp = 1.0
    for o in range(octaves):
        f = freq * 2 ** o
        for _ in range(6):
            kx, ky = r.integers(-f, f + 1, 2)
            if kx == 0 and ky == 0: continue
            out += amp * np.sin(TAU * (kx * u + ky * v) + r.uniform(0, TAU))
        amp *= 0.55
    out -= out.min(); return out / max(out.max(), 1e-6)


def norm(h, strength):
    dx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * strength; dy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) * strength
    n = np.stack([-dx, dy, np.ones_like(h)], -1); n /= np.linalg.norm(n, axis=-1, keepdims=True)
    return n * 0.5 + 0.5


def save(name, rgb, srgb=True):
    img = bpy.data.images.new(name, N, N, alpha=False, float_buffer=not srgb)
    if not srgb: img.colorspace_settings.name = 'Non-Color'
    px = np.ones((N, N, 4), np.float32); px[..., :3] = np.clip(rgb, 0, 1)
    img.pixels.foreach_set(px[::-1].ravel())                     # Blender rows are bottom-up
    path = os.path.join(OUT, name + ".png"); img.filepath_raw = path; img.file_format = 'PNG'; img.save()
    bpy.data.images.remove(img); return path


def kind(name, height, detail, nstr):
    d = np.clip(detail, 0, 1)[..., None].repeat(3, -1)
    save("T_SL_%s_D" % name, d); save("T_SL_%s_N" % name, norm(height, nstr), srgb=False)
    print("TEX", name)

# wool: 2/2 twill (diagonal ribs) + fibre fuzz + slubs
tw = 0.5 + 0.5 * np.sin(TAU * 96 * (u + v)); fuzz = pnoise(64, 3, 1); slub = pnoise(6, 2, 2)
kind("Wool", tw * 0.6 + fuzz * 0.4, 0.72 + 0.16 * tw + 0.12 * fuzz - 0.12 * slub, 6.0)
# linen: fine plain weave
wx = 0.5 + 0.5 * np.sin(TAU * 160 * u); wy = 0.5 + 0.5 * np.sin(TAU * 160 * v); chk = np.sign(np.sin(TAU * 80 * u) * np.sin(TAU * 80 * v))
weave = np.where(chk > 0, wx, wy); kind("Linen", weave, 0.8 + 0.12 * weave + 0.08 * pnoise(48, 2, 3), 4.0)
# quilted padding: diamond quilting seams over linen
q = np.abs(np.sin(TAU * 8 * (u + v))) * np.abs(np.sin(TAU * 8 * (u - v))); puff = q ** 0.35
kind("Quilt", puff * 0.8 + weave * 0.2, 0.62 + 0.3 * puff + 0.08 * weave, 9.0)
# leather: cellular pebble grain + creases
cells = pnoise(40, 2, 4); grain = 1 - np.abs(cells - 0.5) * 2; crease = pnoise(5, 3, 5)
kind("Leather", grain * 0.7 + crease * 0.3, 0.7 + 0.18 * grain - 0.2 * (crease > 0.75), 5.0)
# riveted mail: offset rows of interlocking rings (tube-shaped torus height)
R = 24; gx, gy = u * R, v * R * 1.15
best = np.full((N, N), 9.0)
for oy in (0.0, 0.5):
    cx = np.floor(gx + oy) - oy + 0.5; cy = np.floor(gy * 2 + 0) / 2 + 0.25 + oy * 0
    for dx in (-1, 0, 1):
        for dy in (-0.5, 0, 0.5):
            d = np.hypot(gx - (cx + dx), (gy - (np.round(gy * 2) / 2 + dy)) * 1.6)
            best = np.minimum(best, np.abs(d - 0.42))
ring = np.clip(1 - best / 0.12, 0, 1); gaps = ring < 0.05
kind("Mail", ring, np.where(gaps, 0.15, 0.55 + 0.45 * ring), 8.0)
# brushed steel: horizontal brushing + faint hammer dimples
brush = pnoise(2, 1, 6) * 0.2 + (0.5 + 0.5 * np.sin(TAU * (400 * v + 3 * np.sin(TAU * u)))) * 0.1 + pnoise(24, 2, 7) * 0.15
kind("Steel", brush, 0.8 + 0.2 * brush, 2.0)
# wood grain: flowing rings along u + pores
wob = pnoise(3, 3, 8); rings = 0.5 + 0.5 * np.sin(TAU * (28 * v + 4 * wob)); pores = pnoise(90, 1, 9)
kind("Wood", rings * 0.8 + pores * 0.2, 0.62 + 0.3 * rings - 0.1 * pores, 4.0)
# fur: dense clumped hair strands
strands = pnoise(80, 2, 10) * 0.6 + pnoise(12, 2, 11) * 0.4
kind("Fur", strands, 0.45 + 0.55 * strands, 10.0)
# gilt / hammered metal: soft dimples
dim = pnoise(16, 3, 12); kind("Gilt", dim, 0.85 + 0.15 * dim, 3.0)

# ---- material colours from the Blender scenes (names sanitised the way Unreal's FBX importer does)
cols = {}
for blend in ("viking_anim.blend", "english_soldiers_tiers.blend", "viking_armor_tiers.blend"):
    bpy.ops.wm.open_mainfile(filepath=os.path.join(MD, blend))
    for m in bpy.data.materials:
        key = "".join(ch if ch.isalnum() else "_" for ch in m.name)
        cols[key] = {"color": list(m.diffuse_color)[:3], "rough": round(m.roughness, 3), "metal": round(m.metallic, 3)}
json.dump(cols, open(os.path.join(OUT, "material_colors.json"), "w"), indent=1)
print("COLORS", len(cols))
