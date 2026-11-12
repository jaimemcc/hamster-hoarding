"""Generate a simple square tray with walls as a binary STL (units: mm)."""
import struct
import sys

SIZE = 90.0      # outer X/Y
HEIGHT = 20.0    # total height (floor + lip)
WALL = 5.0       # wall thickness
FLOOR = 3.0      # floor thickness


def build(size=SIZE, height=HEIGHT, wall=WALL, floor=FLOOR):
    o = [(0, 0), (size, 0), (size, size), (0, size)]  # counter-clockwise from above
    i = [(wall, wall), (size - wall, wall), (size - wall, size - wall), (wall, size - wall)]
    tris = []

    def quad(a, b, c, d):
        tris.append((a, b, c))
        tris.append((a, c, d))

    def v(p, z):
        return (p[0], p[1], z)

    quad(v(o[0], 0), v(o[3], 0), v(o[2], 0), v(o[1], 0))  # bottom
    quad(v(i[0], floor), v(i[1], floor), v(i[2], floor), v(i[3], floor))  # cavity floor
    for k in range(4):
        p, q = o[k], o[(k + 1) % 4]
        pi, qi = i[k], i[(k + 1) % 4]
        quad(v(p, 0), v(q, 0), v(q, height), v(p, height))  # outer wall
        quad(v(p, height), v(q, height), v(qi, height), v(pi, height))  # top rim
        quad(v(pi, height), v(qi, height), v(qi, floor), v(pi, floor))  # inner wall
    return tris


def write_stl(path, tris):
    with open(path, "wb") as f:
        f.write(b"tray".ljust(80, b"\0"))
        f.write(struct.pack("<I", len(tris)))
        for a, b, c in tris:
            u = [b[n] - a[n] for n in range(3)]
            w = [c[n] - a[n] for n in range(3)]
            n = [u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0]]
            m = sum(x * x for x in n) ** 0.5 or 1.0
            f.write(struct.pack("<3f", *(x / m for x in n)))
            for p in (a, b, c):
                f.write(struct.pack("<3f", *p))
            f.write(b"\0\0")


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "tray.stl"
    write_stl(out, build())
    print(f"wrote {out}")
