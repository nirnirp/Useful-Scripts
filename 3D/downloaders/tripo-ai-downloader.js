https://studio.tripo3d.ai/workspace


# Download GLB (run before load, then load model and download auto) -> OR move to script No.2 for OBJ
# ---------------------------------------------------------------------------

const origFetch = window.fetch;
window.fetch = async (...args) => {
  const url = typeof args[0] === 'string' ? args[0] : args[0]?.url || '';
  if (/\.glb/i.test(url) && url.includes('tripo-data')) {
    console.warn('🎯 GLB URL:', url);
    origFetch(url).then(r=>r.blob()).then(b=>{
      const a=document.createElement('a');
      a.href=URL.createObjectURL(b);
      a.download='tripo_model.glb';
      a.click();
    });
  }
  return origFetch(...args);
};

# then local GLB -> OBJ/STL
# ---------------------------------------------------------------------------

brew install assimp
assimp export model.glb model.obj
assimp export model.glb model.stl


# Single download and GLB to OBJ converter script - just paste in console before loading, then click on model and download automatically
# ---------------------------------------------------------------------------

(function() {
  // Save original fetch permanently
  window._origFetch = window._origFetch || window.fetch;
  let _busy = false;

  // Load meshopt decoder
  if (!window._meshoptReady) {
    const s = document.createElement('script');
    s.src = 'https://cdn.jsdelivr.net/npm/meshoptimizer/meshopt_decoder.js';
    s.onload = () => MeshoptDecoder.ready.then(() => {
      window._meshoptReady = true;
      console.log('✅ Tripo hook active — open your model to download OBJ');
    });
    document.head.appendChild(s);
  }

  async function convertAndDownload(glbUrl) {
    if (!window._meshoptReady) { console.warn('⏳ Decoder not ready yet, try again'); return; }
    const buf = await window._origFetch(glbUrl).then(r => r.arrayBuffer());
    const dv = new DataView(buf);
    const jsonLen = dv.getUint32(12, true);
    const gltf = JSON.parse(new TextDecoder().decode(new Uint8Array(buf, 20, jsonLen)));
    const binOffset = 20 + jsonLen + 8;
    const compressedBin = new Uint8Array(buf, binOffset);

    function decompress(bv) {
      const ext = bv.extensions?.EXT_meshopt_compression;
      if (!ext) return new Uint8Array(buf, binOffset + (bv.byteOffset || 0), bv.byteLength);
      const src = compressedBin.slice(ext.byteOffset, ext.byteOffset + ext.byteLength);
      const dst = new Uint8Array(ext.count * ext.byteStride);
      if (ext.mode === 'TRIANGLES') MeshoptDecoder.decodeIndexBuffer(dst, ext.count, ext.byteStride, src);
      else MeshoptDecoder.decodeVertexBuffer(dst, ext.count, ext.byteStride, src, ext.filter || 'NONE');
      return dst;
    }

    const decompressed = gltf.bufferViews.map(decompress);

    const posAcc  = gltf.accessors[0];
    const normAcc = gltf.accessors[1];
    const idxAcc  = gltf.accessors[3];

    const positions  = new Float32Array(decompressed[posAcc.bufferView].buffer,  decompressed[posAcc.bufferView].byteOffset,  posAcc.count * 3);
    const normalsRaw = new Int8Array(decompressed[normAcc.bufferView].buffer, decompressed[normAcc.bufferView].byteOffset, normAcc.count * 3);
    const indices    = new Uint32Array(decompressed[idxAcc.bufferView].buffer,   decompressed[idxAcc.bufferView].byteOffset,  idxAcc.count);

    let obj = `# Tripo3D — ${posAcc.count} verts, ${idxAcc.count/3} triangles\n`;
    for (let i = 0; i < posAcc.count; i++)
      obj += `v ${positions[i*3].toFixed(6)} ${positions[i*3+1].toFixed(6)} ${positions[i*3+2].toFixed(6)}\n`;
    for (let i = 0; i < normAcc.count; i++)
      obj += `vn ${(normalsRaw[i*3]/127).toFixed(6)} ${(normalsRaw[i*3+1]/127).toFixed(6)} ${(normalsRaw[i*3+2]/127).toFixed(6)}\n`;
    for (let i = 0; i < indices.length; i += 3) {
      const a=indices[i]+1, b=indices[i+1]+1, c=indices[i+2]+1;
      obj += `f ${a}//${a} ${b}//${b} ${c}//${c}\n`;
    }

    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([obj], {type:'text/plain'}));
    a.download = 'tripo_model.obj';
    a.click();
    console.log(`✅ Downloaded tripo_model.obj — ${posAcc.count} verts, ${idxAcc.count/3} triangles`);
  }

  // Hook fetch
  window.fetch = async (...args) => {
    const url = typeof args[0] === 'string' ? args[0] : args[0]?.url || '';
    if (!_busy && /\.glb/i.test(url) && url.includes('tripo-data')) {
      _busy = true;
      console.log('🎯 GLB intercepted, converting...');
      convertAndDownload(url).catch(e => console.error('❌', e.message)).finally(() => _busy = false);
    }
    return window._origFetch(...args);
  };
})();
