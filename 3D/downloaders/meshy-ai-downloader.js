https://www.meshy.ai/workspace

# Run in console before loading 3d model
# ---------------------------------------------------------------------------

window._capturedBuffers = [];
function hookGL(ctx) {
  const orig = ctx.prototype.bufferData;
  ctx.prototype.bufferData = function(target, data, usage) {
    if (data && data.byteLength > 1000) {
      const copy = new Uint8Array(data instanceof ArrayBuffer ? data : data.buffer,
                                  data.byteOffset || 0, data.byteLength).slice();
      window._capturedBuffers.push({ target, byteLength: data.byteLength, data: copy });
    }
    return orig.call(this, target, data, usage);
  };
}
hookGL(WebGLRenderingContext);
hookGL(WebGL2RenderingContext);
console.log('✅ Hooked — now open your model');

# Run after opening model to export
# ---------------------------------------------------------------------------

(function() {
  const buffers = window._capturedBuffers;

  // Positions: buffer[4] as uint16 quantized → [-1, 1]
  const u16buf = buffers[4].data;
  const u16 = new Uint16Array(u16buf.buffer, u16buf.byteOffset, u16buf.byteLength/2);
  const numVerts = Math.floor(u16.length/4);

  // Normals: buffer[5] as float32
  const normBuf = buffers[5].data;
  const normals = new Float32Array(normBuf.buffer, normBuf.byteOffset, normBuf.byteLength/4);

  // Indices: buffer[6] as uint32
  const idxBuf = buffers[6].data;
  const indices = new Uint32Array(idxBuf.buffer, idxBuf.byteOffset, idxBuf.byteLength/4);

  let obj = '# Meshy model — exported via WebGL capture\n';
  obj += `# Verts: ${numVerts}, Triangles: ${indices.length/3}\n\n`;

  // Vertices
  for (let i = 0; i < numVerts; i++) {
    const x = (u16[i*4]   / 65535) * 2 - 1;
    const y = (u16[i*4+1] / 65535) * 2 - 1;
    const z = (u16[i*4+2] / 65535) * 2 - 1;
    obj += `v ${x.toFixed(6)} ${y.toFixed(6)} ${z.toFixed(6)}\n`;
  }

  obj += '\n';

  // Normals
  for (let i = 0; i < numVerts; i++) {
    obj += `vn ${normals[i*3].toFixed(6)} ${normals[i*3+1].toFixed(6)} ${normals[i*3+2].toFixed(6)}\n`;
  }

  obj += '\n';

  // Faces with normals
  for (let i = 0; i < indices.length; i += 3) {
    const a = indices[i]+1, b = indices[i+1]+1, c = indices[i+2]+1;
    obj += `f ${a}//${a} ${b}//${b} ${c}//${c}\n`;
  }

  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([obj], {type:'text/plain'}));
  a.download = 'meshy_final.obj';
  a.click();
  console.log(`✅ Done! ${numVerts} verts, ${indices.length/3} triangles`);
})();
