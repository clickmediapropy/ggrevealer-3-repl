#!/usr/bin/env python3
"""
Generate favicon files from the logo icon in multiple sizes.
"""
from PIL import Image
import os

# Source image
source_path = "static/images/logo-icon.png"
output_dir = "static/images"

# Load the source image
print(f"Loading source image: {source_path}")
img = Image.open(source_path)

# Convert to RGBA if not already
if img.mode != 'RGBA':
    img = img.convert('RGBA')

# Favicon sizes to generate
sizes = {
    'favicon-16x16.png': (16, 16),
    'favicon-32x32.png': (32, 32),
    'apple-touch-icon.png': (180, 180),
    'android-chrome-192x192.png': (192, 192),
    'android-chrome-512x512.png': (512, 512),
}

# Generate each size
for filename, size in sizes.items():
    output_path = os.path.join(output_dir, filename)
    resized = img.resize(size, Image.Resampling.LANCZOS)
    resized.save(output_path, 'PNG')
    print(f"✓ Generated {filename} ({size[0]}x{size[1]})")

# Generate favicon.ico with multiple sizes
ico_sizes = [(16, 16), (32, 32), (48, 48)]
ico_images = []
for size in ico_sizes:
    resized = img.resize(size, Image.Resampling.LANCZOS)
    ico_images.append(resized)

favicon_path = os.path.join(output_dir, 'favicon.ico')
ico_images[0].save(
    favicon_path,
    format='ICO',
    sizes=[(img.width, img.height) for img in ico_images]
)
print(f"✓ Generated favicon.ico (multi-size: 16x16, 32x32, 48x48)")

print(f"\n✅ All favicon files generated successfully in {output_dir}/")
