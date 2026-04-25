from pathlib import Path
import struct

p = Path("api_ventas-main/ventas/static/ventas/img/logo.png")
data = p.read_bytes()

signature = data[:8]
chunk_type = data[12:16]
width, height = struct.unpack(">II", data[16:24])
bit_depth = data[24]
color_type = data[25]

print("size", len(data))
print("sig", signature)
print("chunk", chunk_type)
print("dims", width, height)
print("bit_depth", bit_depth)
print("color_type", color_type)
