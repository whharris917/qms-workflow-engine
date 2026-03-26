#!/usr/bin/env python3
"""
Rubik's cube solver via HTTP API - careful implementation.
"""
import json, urllib.request

BASE = "http://127.0.0.1:5000/page/3"
POST = BASE + "/cube"
N = 0

def api_get():
    r = urllib.request.urlopen(BASE)
    c = json.loads(r.read())["eigenforms"][0]
    return c["faces"], c["solved"]

def api_move(face, d):
    global N
    b = json.dumps({"action":"rotate","face":face,"direction":d}).encode()
    r = urllib.request.Request(POST, data=b, headers={"Content-Type":"application/json"}, method="POST")
    c = json.loads(urllib.request.urlopen(r).read())["eigenforms"][0]
    N += 1
    return c["faces"], c["solved"]

def api_seq(s):
    f = sol = None
    i = 0
    while i < len(s):
        if s[i] in "UDLRFB":
            face = s[i]
            if i+1<len(s) and s[i+1]=="'":
                f,sol = api_move(face,"ccw"); i+=2
            elif i+1<len(s) and s[i+1]=="2":
                f,sol = api_move(face,"cw"); f,sol = api_move(face,"cw"); i+=2
            else:
                f,sol = api_move(face,"cw"); i+=1
        else:
            i+=1
    return f, sol

def show(f):
    for r in range(3):
        print("      ", " ".join(f["U"][r*3:r*3+3]))
    print()
    for r in range(3):
        print(" ".join(f["L"][r*3:r*3+3]),"", " ".join(f["F"][r*3:r*3+3]),"", " ".join(f["R"][r*3:r*3+3]),"", " ".join(f["B"][r*3:r*3+3]))
    print()
    for r in range(3):
        print("      ", " ".join(f["D"][r*3:r*3+3]))
    print()

# Restart and shuffle
body = json.dumps({"action":"restart"}).encode()
req = urllib.request.Request(POST, data=body, headers={"Content-Type":"application/json"}, method="POST")
urllib.request.urlopen(req)

body = json.dumps({"action":"shuffle"}).encode()
req = urllib.request.Request(POST, data=body, headers={"Content-Type":"application/json"}, method="POST")
urllib.request.urlopen(req)

f, _ = api_get()
print("=== SHUFFLED ===")
show(f)

# Helpers
C2F = {"W":"U","Y":"D","G":"F","B":"B","O":"L","R":"R"}
FACE_CW = ["F","R","B","L"]
RIGHT = {"F":"R","R":"B","B":"L","L":"F"}
LEFT  = {"F":"L","R":"F","B":"R","L":"B"}
OPP   = {"F":"B","B":"F","R":"L","L":"R","U":"D","D":"U"}

def d_rot(n):
    n = n % 4
    return ["","D","D2","D'"][n]

EDGES = [
    ("U",1,"B",1),("U",3,"L",1),("U",5,"R",1),("U",7,"F",1),
    ("D",1,"F",7),("D",3,"L",7),("D",5,"R",7),("D",7,"B",7),
    ("F",3,"L",5),("F",5,"R",3),("B",3,"R",5),("B",5,"L",3),
]

def fedge(f,c1,c2):
    for a,ai,b,bi in EDGES:
        if {f[a][ai],f[b][bi]}=={c1,c2}:
            # Return with c1 first
            if f[a][ai]==c1:
                return (a,ai,b,bi)
            else:
                return (b,bi,a,ai)
    return None

CORNERS = [
    ("U",0,"L",0,"B",2),("U",2,"B",0,"R",2),("U",6,"F",0,"L",2),("U",8,"R",0,"F",2),
    ("D",0,"L",8,"F",6),("D",2,"F",8,"R",6),("D",6,"B",8,"L",6),("D",8,"R",8,"B",6),
]

def fcorner(f,c1,c2,c3):
    """Find corner with all 3 colors. Returns dict mapping color->（face, idx)"""
    cs={c1,c2,c3}
    for a,ai,b,bi,c,ci in CORNERS:
        if {f[a][ai],f[b][bi],f[c][ci]}==cs:
            return {f[a][ai]:(a,ai), f[b][bi]:(b,bi), f[c][ci]:(c,ci)}
    return None

###############################################################################
# PHASE 1: White cross - solve each edge carefully
###############################################################################
print("--- Phase 1: White Cross ---")

# Cross edges and their solved positions:
# UF: U[7]=W, F[1]=G
# UR: U[5]=W, R[1]=R
# UB: U[1]=W, B[1]=B
# UL: U[3]=W, L[1]=O

cross_targets = [
    ("G", "F", 7, 1),  # UF edge
    ("R", "R", 5, 1),  # UR edge
    ("B", "B", 1, 1),  # UB edge
    ("O", "L", 3, 1),  # UL edge
]

for tcol, tface, u_pos, s_pos in cross_targets:
    for att in range(60):
        # Check if this cross edge is solved
        if f["U"][u_pos] == "W" and f[tface][s_pos] == tcol:
            break

        # Find the W-tcol edge
        e = fedge(f, "W", tcol)
        if not e: break
        wf, wi, cf, ci = e  # w=white sticker location, c=color sticker location

        # CASE 1: Edge in U layer
        if wf == "U":
            # White on U but wrong position. Push it to D via the color face.
            f, _ = api_seq(f"{cf}2")
            continue
        if cf == "U":
            # Color on U (flipped in U layer). White is on a side face at pos 1.
            # Push to D via white's face
            f, _ = api_seq(f"{wf}2")
            continue

        # CASE 2: Edge in middle layer (pos 3 or 5 on side faces)
        if wf in "FRLB" and wi in [3, 5]:
            # Push to D layer
            # wf[3] means the edge is shared with the face to the left
            # wf[5] means shared with face to the right
            if wi == 5:
                r = RIGHT[wf]
                f, _ = api_seq(f"{r}")  # rotate right face to bring edge to D
            else:
                l = LEFT[wf]
                f, _ = api_seq(f"{l}'")
            continue
        if cf in "FRLB" and ci in [3, 5]:
            if ci == 5:
                r = RIGHT[cf]
                f, _ = api_seq(f"{r}")
            else:
                l = LEFT[cf]
                f, _ = api_seq(f"{l}'")
            continue

        # CASE 3: Edge in D layer
        if wf == "D":
            # White on D face, color on side face pos 7
            # Rotate D to align color sticker under target face
            curr = cf  # face the color sticker is on
            fc_i = FACE_CW.index(curr)
            tf_i = FACE_CW.index(tface)
            diff = (tf_i - fc_i) % 4
            if diff:
                f, _ = api_seq(d_rot(diff))
                continue
            # Color aligned under target face. Double-rotate target face.
            f, _ = api_seq(f"{tface}2")
            continue

        if cf == "D":
            # Color on D, white on side face pos 7
            # Need to get white to U. This is a flipped edge on D.
            curr = wf
            fc_i = FACE_CW.index(curr)
            tf_i = FACE_CW.index(tface)
            diff = (tf_i - fc_i) % 4
            if diff:
                f, _ = api_seq(d_rot(diff))
                continue
            # White on tface[7], color on D. Need to flip it.
            # Algorithm: F' D' R D (for tface=F) generalized:
            # tface' D' RIGHT[tface] D
            # But this might disturb other solved cross edges.
            # Better: D' RIGHT' D RIGHT (no, that's for corners)
            # Standard flip for edge at bottom of F:
            # Move it to FR position, then insert correctly
            r = RIGHT[tface]
            # Sequence: tface D' r' D moves the edge and flips it
            # Actually: D' r' tface (specific for each)
            # Let me use: first move D to clear, then use side face
            f, _ = api_seq(f"D' {r}' D {r}")
            continue

        # Fallback: should not reach here
        f, _ = api_seq("D")

wc = all(f["U"][t[2]]=="W" and f[t[1]][t[3]]==t[0] for t in cross_targets)
print(f"White cross: {wc}")
if not wc:
    for tcol, tface, u_pos, s_pos in cross_targets:
        print(f"  {tface}: U[{u_pos}]={f['U'][u_pos]}(W?) {tface}[{s_pos}]={f[tface][s_pos]}({tcol}?)")
show(f)
print(f"Moves: {N}")

###############################################################################
# PHASE 2: White corners
###############################################################################
print("--- Phase 2: White Corners ---")

# Corner slots:
# URF: U[8]=W, R[0]=R, F[2]=G  -> below it: D[2], F[8], R[6]
# UFL: U[6]=W, F[0]=G, L[2]=O  -> below it: D[0], L[8], F[6]
# ULB: U[0]=W, L[0]=O, B[2]=B  -> below it: D[6], B[8], L[6]
# UBR: U[2]=W, B[0]=B, R[2]=R  -> below it: D[8], R[8], B[6]

corner_slots = [
    # (u_idx, rface, fface, r_col, f_col)
    (8, "R", "F", "R", "G"),
    (6, "F", "L", "G", "O"),
    (0, "L", "B", "O", "B"),
    (2, "B", "R", "B", "R"),
]

def corner_ok(f, u_idx, rface, fface, rcol, fcol):
    return f["U"][u_idx]=="W" and f[rface][0 if u_idx in [8,2] else 0]

# More precise check
def corner_solved(f, u_idx, rface, fface, rcol, fcol):
    if u_idx == 8: return f["U"][8]=="W" and f["R"][0]=="R" and f["F"][2]=="G"
    if u_idx == 6: return f["U"][6]=="W" and f["F"][0]=="G" and f["L"][2]=="O"
    if u_idx == 0: return f["U"][0]=="W" and f["L"][0]=="O" and f["B"][2]=="B"
    if u_idx == 2: return f["U"][2]=="W" and f["B"][0]=="B" and f["R"][2]=="R"

# D corner positions (which D index is below each U corner)
U2D = {8:2, 6:0, 0:6, 2:8}
D_CW = [0, 2, 8, 6]  # D CW cycle

def push_u_corner(idx):
    """Push corner from U[idx] to D layer"""
    return {0:"L' D' L", 2:"B' D' B", 6:"F' D' F", 8:"R' D' R"}[idx]

for u_idx, rface, fface, rcol, fcol in corner_slots:
    d_target = U2D[u_idx]
    for att in range(60):
        if corner_solved(f, u_idx, rface, fface, rcol, fcol):
            break

        c = fcorner(f, "W", rcol, fcol)
        if not c: break

        w_loc = c["W"]
        r_loc = c[rcol]
        f_loc = c[fcol]

        # Check if in U layer
        if w_loc[0]=="U" or r_loc[0]=="U" or f_loc[0]=="U":
            # Find which U position
            u_sticker = None
            for color, (face, idx) in c.items():
                if face == "U":
                    u_sticker = idx
                    break
            f, _ = api_seq(push_u_corner(u_sticker))
            continue

        # Should be in D layer now
        # Find the D position
        d_sticker = None
        for color, (face, idx) in c.items():
            if face == "D":
                d_sticker = idx
                break

        if d_sticker is None:
            # Corner somehow not in U or D layer?? Shouldn't happen.
            f, _ = api_seq("D")
            continue

        # Rotate D to position corner under target slot
        ci = D_CW.index(d_sticker)
        ti = D_CW.index(d_target)
        diff = (ti - ci) % 4
        if diff:
            f, _ = api_seq(d_rot(diff))
            continue

        # Corner is under target. Refresh positions.
        c = fcorner(f, "W", rcol, fcol)
        w_face = c["W"][0]

        if w_face == "D":
            # White on bottom: 3x (R' D' R D)
            f, _ = api_seq((f"{rface}' D' {rface} D ") * 3)
        elif w_face == rface:
            # White on right face: R' D' R
            f, _ = api_seq(f"{rface}' D' {rface}")
        elif w_face == fface:
            # White on front face: F D F'
            f, _ = api_seq(f"{fface} D {fface}'")
        else:
            f, _ = api_seq("D")

wc2 = all(corner_solved(f, *s) for s in corner_slots)
print(f"White corners: {wc2}")
show(f)
print(f"Moves: {N}")

###############################################################################
# PHASE 3: Second layer
###############################################################################
print("--- Phase 3: Middle Layer ---")

def mid_ok(f):
    return (f["F"][3]=="G" and f["L"][5]=="O" and
            f["F"][5]=="G" and f["R"][3]=="R" and
            f["B"][3]=="B" and f["R"][5]=="R" and
            f["B"][5]=="B" and f["L"][3]=="O")

# Middle layer target edges:
# FL: F[3]=G, L[5]=O
# FR: F[5]=G, R[3]=R
# BR: B[3]=B, R[5]=R
# BL: B[5]=B, L[3]=O

mid_targets = [
    ("G","O","F","L"), ("G","R","F","R"), ("B","R","B","R"), ("B","O","B","L")
]

for iteration in range(100):
    if mid_ok(f): break

    # Look for a non-yellow edge in D layer
    found_d_edge = False
    for df,di,sf,si in [("D",1,"F",7),("D",3,"L",7),("D",5,"R",7),("D",7,"B",7)]:
        dc = f[df][di]
        sc = f[sf][si]
        if dc == "Y" or sc == "Y":
            continue

        # sc is the side sticker color. Its center face is where we align.
        target_face = C2F.get(sc)
        if target_face not in FACE_CW:
            continue

        # Rotate D to align sc under its face center
        curr_face = sf  # which face the side sticker is currently on
        ci = FACE_CW.index(curr_face)
        ti = FACE_CW.index(target_face)
        diff = (ti - ci) % 4
        if diff:
            f, _ = api_seq(d_rot(diff))
            found_d_edge = True
            break

        # Aligned! Now dc tells us which side to insert.
        dest_face = C2F.get(dc)
        if dest_face not in FACE_CW:
            f, _ = api_seq("D")
            found_d_edge = True
            break

        if dest_face == RIGHT[target_face]:
            r = RIGHT[target_face]
            f, _ = api_seq(f"D {r} D' {r}' D' {target_face}' D {target_face}")
        elif dest_face == LEFT[target_face]:
            l = LEFT[target_face]
            f, _ = api_seq(f"D' {l}' D {l} D {target_face} D' {target_face}'")
        else:
            # Shouldn't happen
            f, _ = api_seq("D")
        found_d_edge = True
        break

    if not found_d_edge:
        # All D edges are yellow or no non-yellow edges in D.
        # Kick out a wrong middle edge.
        kicked = False
        checks = [
            ("F",3,"L",5,"G","O"), ("F",5,"R",3,"G","R"),
            ("B",3,"R",5,"B","R"), ("B",5,"L",3,"B","O"),
        ]
        for mf1,mi1,mf2,mi2,mc1,mc2 in checks:
            if f[mf1][mi1] != mc1 or f[mf2][mi2] != mc2:
                # Kick this edge out. Use insert-right algorithm on this face.
                r = RIGHT[mf1]
                f, _ = api_seq(f"D {r} D' {r}' D' {mf1}' D {mf1}")
                kicked = True
                break
        if not kicked:
            break

print(f"Middle: {mid_ok(f)}")
show(f)
print(f"Moves: {N}")

###############################################################################
# PHASE 4: Yellow cross
###############################################################################
print("--- Phase 4: Yellow Cross ---")

def ycross(f):
    return all(f["D"][i]=="Y" for i in [1,3,5,7])

# The algorithm to create the yellow cross on D:
# We need an algorithm that flips D edges. Standard for top layer is F R U R' U' F'
# For D layer, the equivalent is F' D' L' D L F  ... or we can try F R D R' D' F'
# Let me verify: F R D R' D' F'
# This should work as the OLL cross algorithm adapted for D.

for att in range(10):
    if ycross(f): break
    d1 = f["D"][1] == "Y"
    d3 = f["D"][3] == "Y"
    d5 = f["D"][5] == "Y"
    d7 = f["D"][7] == "Y"
    cnt = sum([d1,d3,d5,d7])

    if cnt == 0:
        # Dot: apply algorithm
        f, _ = api_seq("F R D R' D' F'")
    elif cnt == 2:
        # Check if line or L-shape
        if (d1 and d7) or (d3 and d5):
            # Line
            if d1 and d7:
                # Vertical line (front-back). Rotate D to make horizontal.
                f, _ = api_seq("D")
            # Now d3 and d5 should be set (horizontal line)
            f, _ = api_seq("F R D R' D' F'")
        else:
            # L-shape. Orient: we want the two Y edges at D[3] and D[7]
            # i.e., left and back positions
            if d1 and d3:
                # front and left -> rotate D' to get left and back
                f, _ = api_seq("D'")
            elif d3 and d7:
                # left and back -> already correct
                pass
            elif d7 and d5:
                # back and right -> rotate D to get left and back
                # Actually: D2 to get front-right -> no
                # d7=back, d5=right -> rotate D' gives back->right, right->front
                # We want d3 and d7. Currently d5 and d7.
                # D: 1->3, 3->7, 5->1, 7->5 (wrong direction?)
                # Actually D CW: front->left->back->right
                # D1(front)->D3(left), D3(left)->D7(back), D7(back)->D5(right), D5(right)->D1(front)
                # So from d5,d7: after D CW: d5->d1, d7->d5. So we'd have d1,d5. Not what we want.
                # After D CCW: d5->d7(stays), d7->...
                # Let me just think about it differently.
                # We have Y at positions 5(right) and 7(back).
                # We want Y at 3(left) and 7(back).
                # Rotating D CW once: edges cycle 1->3->7->5->1
                # So pos 5 goes to pos 1, pos 7 goes to pos 5. Result: Y at 1,5. No good.
                # D CCW: 1->5->7->3->1. Pos 5->7, pos 7->3. Result: Y at 7,3.
                f, _ = api_seq("D'")
            elif d1 and d5:
                # front and right
                # Want 3 and 7. D CCW: 1->5, 5->7. Get 5,7. No.
                # D CW twice: 1->3->7, 5->1->3. Get 7,3. Yes!
                f, _ = api_seq("D2")
            f, _ = api_seq("F R D R' D' F'")

print(f"Yellow cross: {ycross(f)}")
show(f)
print(f"Moves: {N}")

###############################################################################
# PHASE 5: Orient yellow edges
###############################################################################
print("--- Phase 5: Yellow Edge Position ---")

def yedge_ok(f):
    return f["F"][7]=="G" and f["R"][7]=="R" and f["B"][7]=="B" and f["L"][7]=="O"

def count_ye(f):
    return sum([f["F"][7]=="G", f["R"][7]=="R", f["B"][7]=="B", f["L"][7]=="O"])

# Ua perm for D layer: cycle 3 edges
# Standard Ua for top: R2 U' F' B R2 F B' U' R2
# For D: probably different. Let me use a known edge 3-cycle.
# Actually let me try: L2 D' F' B L2 F B' D' L2
# Or use the standard approach of repeating R U R' U with setup.

# Known: When you have 1 correct edge, put it at the back,
# then: R2 D R D R' D' R' D' R' D R' works (adapted from Ua perm on top)
# Ub: R D' R D' R D R' D R' D2

for att in range(30):
    if yedge_ok(f): break

    # Find best D rotation
    best = (0, 0)
    for rot in range(4):
        cnt = count_ye(f)
        if cnt > best[0]:
            best = (cnt, rot)
        if cnt == 4:
            break
        f, _ = api_seq("D")
    # We've done 4 D moves (full cycle), now go to best rotation
    if best[1]:
        f, _ = api_seq(d_rot(best[1]))

    if yedge_ok(f): break

    correct = [face for face, col in [("F","G"),("R","R"),("B","B"),("L","O")] if f[face][7]==col]

    if len(correct) == 0:
        # No correct edges. Apply algorithm, this will give us at least 1.
        f, _ = api_seq("R2 D R D R' D' R' D' R' D R'")
    elif len(correct) == 1:
        # Put correct at back
        cf = correct[0]
        ci = FACE_CW.index(cf)
        bi = FACE_CW.index("B")
        diff = (bi - ci) % 4
        if diff:
            f, _ = api_seq(d_rot(diff))
        # Now correct is at B. Apply Ua.
        f, _ = api_seq("R2 D R D R' D' R' D' R' D R'")

        # Check if it worked
        if not yedge_ok(f):
            # Maybe we need Ub instead. Let's check if we can undo and apply Ub.
            # Actually, just try again next iteration - it may need the other direction
            pass
    else:
        # 2 correct shouldn't happen in a valid state unless they're opposite,
        # which means we need a specific PLL. Try the algorithm anyway.
        f, _ = api_seq("R2 D R D R' D' R' D' R' D R'")

# Final D alignment
for _ in range(4):
    if yedge_ok(f): break
    f, _ = api_seq("D")

print(f"Yellow edges: {yedge_ok(f)}")
show(f)
print(f"Moves: {N}")

###############################################################################
# PHASE 6: Position yellow corners
###############################################################################
print("--- Phase 6: Yellow Corner Position ---")

def cpos_ok(f):
    return ({f["D"][0],f["L"][8],f["F"][6]}=={"Y","O","G"} and
            {f["D"][2],f["F"][8],f["R"][6]}=={"Y","G","R"} and
            {f["D"][8],f["R"][8],f["B"][6]}=={"Y","R","B"} and
            {f["D"][6],f["B"][8],f["L"][6]}=={"Y","B","O"})

def which_cpos_ok(f):
    ok = []
    if {f["D"][0],f["L"][8],f["F"][6]}=={"Y","O","G"}: ok.append("DLF")
    if {f["D"][2],f["F"][8],f["R"][6]}=={"Y","G","R"}: ok.append("DFR")
    if {f["D"][8],f["R"][8],f["B"][6]}=={"Y","R","B"}: ok.append("DBR")
    if {f["D"][6],f["B"][8],f["L"][6]}=={"Y","B","O"}: ok.append("DBL")
    return ok

# Corner permutation algorithm: U R U' L' U R' U' L (standard, for top layer)
# For D layer: D' R' D L D' R D L'  ... or some adaptation
# Actually the standard A-perm adapted for D: keep one corner fixed, cycle others

# Let me use a well-known algorithm:
# With correct corner at DLF (front-left-down), cycle the other 3:
# R' D' R F D F' R' D R D' F D' F' D'  ... too long
# Simpler: repeated application of a 3-cycle

# Actually: R U' L' U R' U' L U (for top) -> R' D L D' R D L' D' (for bottom?)
# Let me try: D R D' L' D R' D' L (that's a standard corner 3-cycle)

for att in range(30):
    if cpos_ok(f): break

    ok = which_cpos_ok(f)

    if len(ok) == 0:
        # Apply algorithm, should give at least 1 correct
        f, _ = api_seq("D R D' L' D R' D' L")
        continue

    if len(ok) == 1:
        # Rotate so correct is at DFR (we'll anchor it there)
        # Wait, standard approach: put correct at DLF
        rot_map = {"DLF": 0, "DFR": 3, "DBR": 2, "DBL": 1}
        r = rot_map[ok[0]]
        if r:
            f, _ = api_seq(d_rot(r))
        # Correct corner is now at DLF. Apply 3-corner cycle for the others.
        f, _ = api_seq("D R D' L' D R' D' L")
        continue

    if len(ok) >= 2 and len(ok) < 4:
        # Apply algorithm
        f, _ = api_seq("D R D' L' D R' D' L")
        continue

print(f"Corner position: {cpos_ok(f)}")
show(f)
print(f"Moves: {N}")

###############################################################################
# PHASE 7: Orient yellow corners
###############################################################################
print("--- Phase 7: Yellow Corner Orient ---")

# Standard approach: position corner at DFR, apply R U R' U' until D[2]=Y
# then D to bring next, repeat. IMPORTANT: this temporarily breaks U layer.

for phase7 in range(8):
    if all(f["D"][i]=="Y" for i in [0,2,6,8]):
        break

    # Rotate D to put an unoriented corner at DFR (D[2])
    for _ in range(4):
        if f["D"][2] != "Y":
            break
        f, _ = api_seq("D")

    if f["D"][2] == "Y":
        break

    # Apply R U R' U' until D[2] becomes Y (max 5 iterations = 10 moves)
    for _ in range(5):
        if f["D"][2] == "Y":
            break
        f, _ = api_seq("R U R' U'")

# Final D alignment
for _ in range(4):
    if all(f[face][i]==col for face,col in [("U","W"),("D","Y"),("F","G"),("B","B"),("L","O"),("R","R")] for i in range(9)):
        break
    f, _ = api_seq("D")

def is_solved(f):
    for face,col in [("U","W"),("D","Y"),("F","G"),("B","B"),("L","O"),("R","R")]:
        if not all(c==col for c in f[face]): return False
    return True

print(f"\n{'='*40}")
print(f"SOLVED: {is_solved(f)}")
print(f"Total moves: {N}")
show(f)

if not is_solved(f):
    print("Per face:")
    for face,col in [("U","W"),("D","Y"),("F","G"),("B","B"),("L","O"),("R","R")]:
        ok = all(c==col for c in f[face])
        print(f"  {face}({col}): {'OK' if ok else f[face]}")
