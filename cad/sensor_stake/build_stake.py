"""Nabta sensor stake: parametric CAD (CadQuery / OpenCASCADE, opens in FreeCAD).

Run:  python build_stake.py      (needs: pip install cadquery)
Outputs STEP (assembly + each part) and print-oriented STL files next to this script.

Units: mm. Z = up. Z = 0 is the soil line (bottom of the collar).
Printed parts: housing, stem, lantern, cap, window disc.
Reference parts (not printed): soil sensor, SHT31, BH1750, splice board, 2x M3 screws.
"""
import math
from pathlib import Path
import cadquery as cq

OUT = Path(__file__).parent
CL = 0.2  # fit clearance per side

# ---------------------------------------------------------------- sensor sizes (measure yours!)
SOIL_W, SOIL_T, SOIL_L = 23.0, 1.6, 98.0   # capacitive soil sensor v1.2
SOIL_TOP_IN = 26.0                          # electronics part kept above the soil (to the printed line)
SHT_W, SHT_H = 14.0, 11.0                   # SHT31 breakout (wires soldered, no header)
BH_W, BH_D = 18.5, 13.9                     # GY-302 BH1750
PCB_T = 1.6

# ---------------------------------------------------------------- housing
H_W, H_D, H_H, WALL, FLOOR = 32.0, 16.0, 50.0, 2.0, 3.0
PCB_Y = -2.0            # soil PCB plane (components face +Y)
BOSS_X, BOSS_Y = 11.4, 3.4   # bosses overlap the side and front walls so they fuse


def rrect(w, d, h, r, z0=0.0):
    return cq.Workplane("XY").workplane(offset=z0).rect(w, d).extrude(h).edges("|Z").fillet(r)


def box(x0, x1, y0, y1, z0, z1):
    return cq.Workplane("XY").box(x1 - x0, y1 - y0, z1 - z0, centered=False).translate((x0, y0, z0))


def cylz(r, z0, z1, x=0.0, y=0.0):
    return cq.Workplane("XY").workplane(offset=z0).center(x, y).circle(r).extrude(z1 - z0)


def make_housing():
    h = rrect(H_W, H_D, H_H, 3.0).union(rrect(44, 28, 2.5, 5.0))            # body + soil-line collar
    h = h.cut(rrect(H_W - 2 * WALL, H_D - 2 * WALL, H_H, 1.0, z0=FLOOR))      # cavity, open top
    h = h.cut(box(-(SOIL_W / 2 + 0.3), SOIL_W / 2 + 0.3, PCB_Y - 1.0, PCB_Y + 1.0, -1, FLOOR + 1))  # blade slot
    gx0, gx1 = SOIL_W / 2 - 0.6, H_W / 2 - WALL + 0.1                         # PCB edge guides
    for s in (1, -1):
        g = box(gx0, gx1, PCB_Y - 1.5, PCB_Y + 1.5, FLOOR, FLOOR + SOIL_TOP_IN + 2)
        g = g.cut(box(gx0 - 0.1, SOIL_W / 2 + 0.4, PCB_Y - 0.95, PCB_Y + 0.95, FLOOR - 1, FLOOR + SOIL_TOP_IN + 3))
        h = h.union(g.mirror("YZ") if s < 0 else g)
    for s in (1, -1):                                                         # screw bosses for the stem
        x = s * BOSS_X
        boss = cylz(3.0, 38, H_H, x, BOSS_Y)
        cone = cq.Solid.makeCone(0.6, 3.0, 6.0, cq.Vector(x, BOSS_Y, 32), cq.Vector(0, 0, 1))
        h = h.union(boss).union(cq.Workplane().add(cone))
        h = h.cut(cylz(1.25, 39, H_H + 1, x, BOSS_Y))                         # M3 self-tap pilot
    for y0, y1 in ((-H_D / 2 + WALL - 0.1, -H_D / 2 + WALL + 1.2), (H_D / 2 - WALL - 1.2, H_D / 2 - WALL + 0.1)):
        h = h.union(box(-7.5, 7.5, y0, y1, 37.8, 39.0))                       # splice-board ledges
    gland = cq.Workplane("XZ").workplane(offset=-H_D / 2 - 1).center(0, 44).circle(3.1).extrude(-(WALL + 2))
    return h.cut(gland)                                                       # cable hole, front (+Y)


# ---------------------------------------------------------------- stem
STEM_TOP = 33.0
LUG_Z = (28.8, 30.8)
LANTERN_ON_STEM = 23.5  # lantern plate bottom, in stem coordinates


def make_stem():
    s = rrect(H_W, H_D, 3.0, 3.0)
    s = s.union(cylz(6.0, 3.0, STEM_TOP))
    for z in (7.0, 12.0, 17.0):
        s = s.union(cylz(7.25, z, z + 1.5))
    for a in (0, 180):
        lug = box(5.5, 7.5, -1.5, 1.5, *LUG_Z).rotate((0, 0, 0), (0, 0, 1), a)
        s = s.union(lug)
    s = s.cut(cylz(4.0, -1, STEM_TOP + 1))                                     # wire channel
    for x in (BOSS_X, -BOSS_X):
        s = s.cut(cylz(1.7, -1, 4, x, BOSS_Y)).cut(cylz(3.0, 1.5, 4, x, BOSS_Y))  # M3 clearance + counterbore
    return s


# ---------------------------------------------------------------- lantern (hex, clear PETG)
L_H, L_PLATE, L_WALL = 36.0, 2.5, 1.8
L_F0, L_F1 = 32.0, 38.0       # outer flat-to-flat bottom / top
SLOT_A = -40.0                # bayonet entry angle; twist +40 deg to lock (lugs end at 0 deg)


def hexloft(f0, f1, z0, z1):
    k = 1 / math.cos(math.radians(30))
    return (cq.Workplane("XY").workplane(offset=z0).polygon(6, f0 * k)
            .workplane(offset=z1 - z0).polygon(6, f1 * k).loft(combine=True))


def inner_flat(z):
    return (L_F0 - 2 * L_WALL) + (L_F1 - L_F0) * z / L_H


def sector(r0, r1, a0, a1, z0, z1):
    pts = [(r1 * 1.3 * math.cos(math.radians(a)), r1 * 1.3 * math.sin(math.radians(a)))
           for a in [a0 + (a1 - a0) * i / 12 for i in range(13)]]
    wedge = cq.Workplane("XY").workplane(offset=z0).polyline([(0, 0)] + pts).close().extrude(z1 - z0)
    ring = cylz(r1, z0, z1).cut(cylz(r0, z0 - 1, z1 + 1))
    return ring.intersect(wedge)


def make_lantern():
    l = hexloft(L_F0, L_F1, 0, L_H).cut(hexloft(inner_flat(L_PLATE), inner_flat(L_H + 0.01), L_PLATE, L_H + 0.01))
    l = l.union(cylz(9.0, L_PLATE, 10.5))                                     # bayonet socket
    l = l.cut(cylz(6.25, -1, 11))
    for base in (0, 180):
        v = box(6.1, 9.6, -1.9, 1.9, -1, 7.6).rotate((0, 0, 0), (0, 0, 1), SLOT_A + base)
        l = l.cut(v).cut(sector(6.1, 9.6, SLOT_A + base - 14, base + 18, 5.0, 7.6))
    for s in (1, -1):                                                         # SHT31 cradle posts
        p = box(6.3, 9.3, 10.0, 13.0, L_PLATE, 14.5).cut(box(6.2, SHT_W / 2 + 0.4, 10.55, 12.45, L_PLATE, 15))
        l = l.union(p.mirror("YZ") if s < 0 else p)
    for th in (30, 90, 150, 210, 270, 330):                                   # vent slots, 3 per face
        for off in (-7, 0, 7):
            v = box(13.6, 24, off - 1.1, off + 1.1, 6, 28).rotate((0, 0, 0), (0, 0, 1), th)
            l = l.cut(v)
    return l


# ---------------------------------------------------------------- cap
C_T = 3.0


def make_cap():
    c = hexloft(L_F1 + 2, L_F1 + 2, 0, C_T)
    skirt = hexloft(inner_flat(L_H - 5) - 2 * CL, inner_flat(L_H) - 2 * CL, -5, 0)
    skirt = skirt.cut(hexloft(inner_flat(L_H - 5) - 2 * CL - 3.2, inner_flat(L_H) - 2 * CL - 3.2, -6, 0.01))
    c = c.union(skirt)
    c = c.cut(cylz(4.5, -1, C_T + 1)).cut(cylz(7.0, -0.01, 1.2))             # window + disc recess
    for s in (1, -1):                                                         # BH1750 slide-in rails
        r = box(-11.5, 10.5, 6.2, 9.2, -5, 0).cut(box(-10.5, 11, 6.1, BH_D / 2 + 0.35, -3.35, -1.45))
        c = c.union(r.mirror("XZ") if s < 0 else r)
    return c.union(box(-11.5, -10.4, -9.2, 9.2, -5, 0))                      # end stop


# ---------------------------------------------------------------- reference parts
def make_soil():
    top = FLOOR + SOIL_TOP_IN
    prof = [(-SOIL_W / 2, top), (SOIL_W / 2, top), (SOIL_W / 2, top - SOIL_L + 10), (0, top - SOIL_L), (-SOIL_W / 2, top - SOIL_L + 10)]
    pcb = cq.Workplane("XZ").workplane(offset=-(PCB_Y - SOIL_T / 2)).polyline(prof).close().extrude(-SOIL_T)
    chip = box(-2.5, 2.5, PCB_Y + SOIL_T / 2, PCB_Y + SOIL_T / 2 + 1.5, top - 9, top - 5)
    jst = box(-3.0, 3.0, PCB_Y + SOIL_T / 2, PCB_Y + SOIL_T / 2 + 4.5, top - 4, top + 2)
    return pcb, chip.union(jst)


def make_sht():
    b = box(-SHT_W / 2, SHT_W / 2, 10.7, 10.7 + PCB_T, L_PLATE + 0.1, L_PLATE + 0.1 + SHT_H)
    chip = box(-1.25, 1.25, 10.7 + PCB_T, 10.7 + PCB_T + 0.9, 8, 10.5)
    return b, chip


def make_bh():
    b = box(-BH_W / 2 + 0.5, BH_W / 2 + 0.5, -BH_D / 2, BH_D / 2, -3.2, -3.2 + PCB_T)
    chip = box(-1.5, 1.5, -0.9, 0.9, -1.6, -0.6)
    return b, chip


def make_screw(x, y, z_top):
    return cylz(1.5, z_top - 10, z_top, x, y).union(cylz(2.75, z_top, z_top + 3, x, y))


# ---------------------------------------------------------------- build + place
housing, stem, lantern, cap = make_housing(), make_stem(), make_lantern(), make_cap()
disc = cylz(6.8, 0, 1.0)
soil_pcb, soil_parts = make_soil()
sht_pcb, sht_chip = make_sht()
bh_pcb, bh_chip = make_bh()
splice = box(-7.5, 7.5, -5, 5, 39.0, 39.0 + PCB_T)

Z_STEM = H_H
Z_LANT = Z_STEM + LANTERN_ON_STEM
Z_CAP = Z_LANT + L_H
placed = {
    "housing": housing,
    "stem": stem.translate((0, 0, Z_STEM)),
    "lantern": lantern.translate((0, 0, Z_LANT)),
    "cap": cap.translate((0, 0, Z_CAP)),
    "window_disc": disc.translate((0, 0, Z_CAP + 0.2)),
    "soil_sensor_pcb": soil_pcb,
    "soil_sensor_parts": soil_parts,
    "sht31": sht_pcb.union(sht_chip).translate((0, 0, Z_LANT)),
    "bh1750": bh_pcb.union(bh_chip).translate((0, 0, Z_CAP)),
    "splice_board": splice,
    "m3_screws": make_screw(BOSS_X, BOSS_Y, Z_STEM + 1.5).union(make_screw(-BOSS_X, BOSS_Y, Z_STEM + 1.5)),
}
COLORS = {"housing": (0.24, 0.20, 0.18), "stem": (0.24, 0.20, 0.18), "lantern": (0.85, 0.94, 0.97, 0.45), "cap": (0.24, 0.20, 0.18),
          "window_disc": (0.75, 0.9, 0.97, 0.6), "soil_sensor_pcb": (0.08, 0.08, 0.08), "soil_sensor_parts": (0.9, 0.9, 0.9),
          "sht31": (0.12, 0.31, 0.63), "bh1750": (0.36, 0.25, 0.56), "splice_board": (0.79, 0.65, 0.42), "m3_screws": (0.7, 0.72, 0.75)}
PRINTED = ["housing", "stem", "lantern", "cap", "window_disc"]


def assembly(explode=0.0):
    a = cq.Assembly(name="nabta_sensor_stake")
    lift = {"stem": 1, "lantern": 2, "cap": 3.2, "window_disc": 3.2, "sht31": 2, "bh1750": 3.2, "m3_screws": 1}
    for k, shape in placed.items():
        a.add(shape.translate((0, 0, explode * lift.get(k, 0))), name=k, color=cq.Color(*COLORS[k]))
    return a


if __name__ == "__main__":
    (OUT / "parts").mkdir(exist_ok=True)
    (OUT / "print_stl").mkdir(exist_ok=True)
    assembly().save(str(OUT / "nabta_sensor_stake_assembly.step"))
    assembly(25).save(str(OUT / "nabta_sensor_stake_exploded.step"))
    local = {"housing": housing, "stem": stem, "lantern": lantern, "cap": cap, "window_disc": disc}
    for k, shape in local.items():
        cq.exporters.export(shape, str(OUT / "parts" / f"{k}.step"))
    orient = {"cap": cap.rotate((0, 0, 0), (1, 0, 0), 180).translate((0, 0, C_T))}   # print the cap upside down
    for k in PRINTED:
        cq.exporters.export(orient.get(k, local[k]), str(OUT / "print_stl" / f"{k}.stl"), tolerance=0.02, angularTolerance=0.1)
    print("done")
