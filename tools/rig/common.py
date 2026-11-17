import bpy
from mathutils import Vector


def setup_render(w=600, h=700, color='TEXTURE'):
    scene = bpy.context.scene
    scene.render.engine = 'BLENDER_WORKBENCH'
    scene.display.shading.light = 'STUDIO'
    scene.display.shading.color_type = color
    scene.render.resolution_x = w
    scene.render.resolution_y = h
    if scene.world is None:
        scene.world = bpy.data.worlds.new('w')
    scene.world.color = (0.25, 0.25, 0.3)
    cam_data = bpy.data.cameras.new('rc')
    cam_data.type = 'ORTHO'
    cam = bpy.data.objects.new('rc', cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    return cam


def world_bounds(mesh_obj):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = mesh_obj.evaluated_get(dg)
    me = ev.to_mesh()
    co = [ev.matrix_world @ v.co for v in me.vertices]
    ev.to_mesh_clear()
    mn = Vector((min(c.x for c in co), min(c.y for c in co), min(c.z for c in co)))
    mx = Vector((max(c.x for c in co), max(c.y for c in co), max(c.z for c in co)))
    return mn, mx


def shot(cam, mesh_obj, path, direction, frame=None, span=None):
    scene = bpy.context.scene
    if frame is not None:
        scene.frame_set(frame)
    bpy.context.view_layer.update()
    mn, mx = world_bounds(mesh_obj)
    ctr = (mn + mx) / 2
    size = span or max(mx.z - mn.z, mx.x - mn.x, mx.y - mn.y) * 1.25
    d = Vector(direction).normalized()
    cam.data.ortho_scale = size
    cam.data.clip_start = 0.01
    cam.data.clip_end = size * 40
    cam.location = ctr + d * size * 10
    cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)


def sheet(paths, out, cols=4, scale=1.0):
    # stitch with Blender's own image API (no PIL inside Blender)
    import numpy as np
    imgs = [bpy.data.images.load(p) for p in paths]
    w, h = imgs[0].size
    rows = (len(imgs) + cols - 1) // cols
    canvas = np.zeros((rows * h, cols * w, 4), dtype=np.float32)
    for i, im in enumerate(imgs):
        a = np.empty(w * h * 4, dtype=np.float32)
        im.pixels.foreach_get(a)
        a = a.reshape(h, w, 4)
        r, c = divmod(i, cols)
        y0 = (rows - 1 - r) * h
        canvas[y0:y0 + h, c * w:(c + 1) * w] = a
    res = bpy.data.images.new('sheet', cols * w, rows * h, alpha=True)
    res.pixels.foreach_set(canvas.ravel())
    res.filepath_raw = out
    res.file_format = 'PNG'
    res.save()
