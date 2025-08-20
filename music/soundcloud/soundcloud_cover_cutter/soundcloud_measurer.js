// SoundCloud banner → avatar crop measurer (resilient)
(function () {
    const takeFirst = (s) => (s || '').split(',')[0].trim();
  
    // --- 1) Heuristics to find elements ---
    const guessBg = () => {
      // Prefer known class
      const el1 = document.querySelector('.profileHeaderBackground__visual');
      if (el1) return el1;
      // Otherwise: biggest visible element with a real background-image
      const all = [...document.querySelectorAll('div,section,header')];
      const cands = all
        .map((el) => {
          const cs = getComputedStyle(el);
          const bi = takeFirst(cs.backgroundImage);
          if (!bi || bi === 'none') return null;
          const r = el.getBoundingClientRect();
          if (r.width < 600 || r.height < 120) return null;
          return { el, area: r.width * r.height, r, bi, cs };
        })
        .filter(Boolean)
        .sort((a, b) => b.area - a.area);
      return cands[0]?.el || null;
    };
  
    const guessAvatar = () => {
      // Prefer within profileHeaderInfo__avatar
      const scope = document.querySelector('.profileHeaderInfo__avatar') || document;
      const nodes = [...scope.querySelectorAll('*')];
      let best = null;
      for (const el of nodes) {
        const r = el.getBoundingClientRect();
        if (r.width < 80 || r.height < 80) continue;
        // square-ish and visible
        const ratio = r.width / r.height;
        if (ratio < 0.8 || ratio > 1.25) continue;
        const cs = getComputedStyle(el);
        const br = cs.borderRadius || '';
        const looksRound =
          br.includes('%') || parseFloat(br) > Math.min(r.width, r.height) * 0.2 ||
          el.className?.toString().includes('image__rounded');
        if (!looksRound) continue;
        const score = Math.min(r.width, r.height);
        if (!best || score > best.score) best = { el, r, cs, score };
      }
      // Fallback: the largest square-ish element near top-left of the header info
      if (!best) {
        const all = [...document.querySelectorAll('img,div,span')];
        for (const el of all) {
          const r = el.getBoundingClientRect();
          if (r.width < 80 || r.height < 80) continue;
          const ratio = r.width / r.height;
          if (ratio < 0.8 || ratio > 1.25) continue;
          if (!best || (r.width * r.height) > (best.r.width * best.r.height)) {
            best = { el, r, cs: getComputedStyle(el), score: r.width * r.height };
          }
        }
      }
      return best?.el || null;
    };
  
    const bgEl = guessBg();
    const avatarEl = guessAvatar();
  
    if (!bgEl || !avatarEl) {
      console.error('Could not find elements', { bgEl: !!bgEl, avatarEl: !!avatarEl });
      return { error: 'elements_not_found', bgEl: !!bgEl, avatarEl: !!avatarEl };
    }
  
    // --- 2) Geometry & styles ---
    const bgRect = bgEl.getBoundingClientRect();
    const avRect = avatarEl.getBoundingClientRect();
    const cs = getComputedStyle(bgEl);
  
    // background-image URL
    const bgImageRaw = takeFirst(cs.backgroundImage);
    const urlMatch = bgImageRaw.match(/url\(["']?(.*?)["']?\)/);
    const bgUrl = urlMatch ? urlMatch[1] : null;
  
    // --- 3) Load image to get natural size (or guess from URL) ---
    function getNaturalSize(url, fallbackFromUrl) {
      return new Promise((resolve) => {
        if (!url) {
          const g = /-t(\d+)x(\d+)\./.exec(bgImageRaw);
          if (g) return resolve({ w: +g[1], h: +g[2], source: 'guessed_from_url' });
          return resolve(null);
        }
        const img = new Image();
        img.crossOrigin = 'anonymous';
        img.onload = () => resolve({ w: img.naturalWidth, h: img.naturalHeight, source: 'loaded' });
        img.onerror = () => {
          const g = /-t(\d+)x(\d+)\./.exec(url);
          if (g) return resolve({ w: +g[1], h: +g[2], source: 'guessed_from_url' });
          resolve(null);
        };
        img.src = url;
      });
    }
  
    const keywordToPercent = (kw, axis) => {
      const mapX = { left: 0, center: 50, right: 100 };
      const mapY = { top: 0, center: 50, bottom: 100 };
      const map = axis === 'x' ? mapX : mapY;
      return (kw in map) ? (map[kw] + '%') : kw;
    };
  
    const parseLenOrPercent = (token, basePx) => {
      token = (token || '').trim();
      if (token.endsWith('%')) return { type: '%', v: parseFloat(token) };
      if (token === 'auto') return { type: 'auto', v: NaN };
      const n = parseFloat(token);
      return { type: 'px', v: isNaN(n) ? NaN : n };
    };
  
    function resolveBackgroundSize(natW, natH, elW, elH, cs) {
      const bs = takeFirst(cs.backgroundSize);
      const coverContain = (mode) => {
        const sx = elW / natW, sy = elH / natH;
        const s = mode === 'cover' ? Math.max(sx, sy) : Math.min(sx, sy);
        return { w: natW * s, h: natH * s };
      };
      if (bs === 'cover' || bs === 'contain') return coverContain(bs);
  
      const parts = bs.split(/\s+/).filter(Boolean);
      const xTok = parseLenOrPercent(parts[0] || 'auto', elW);
      const yTok = parseLenOrPercent(parts[1] || 'auto', elH);
  
      let w, h;
      if (xTok.type === 'px' && yTok.type === 'px') {
        w = xTok.v; h = yTok.v;
      } else if (xTok.type === 'px' && yTok.type === 'auto') {
        w = xTok.v; h = (w / natW) * natH;
      } else if (yTok.type === 'px' && xTok.type === 'auto') {
        h = yTok.v; w = (h / natH) * natW;
      } else if (xTok.type === '%' && yTok.type === '%') {
        w = (xTok.v / 100) * elW; h = (yTok.v / 100) * elH;
      } else if (xTok.type === '%' && yTok.type === 'auto') {
        w = (xTok.v / 100) * elW; h = (w / natW) * natH;
      } else if (yTok.type === '%' && xTok.type === 'auto') {
        h = (yTok.v / 100) * elH; w = (h / natH) * natW;
      } else {
        // Fallback to cover
        return coverContain('cover');
      }
      return { w, h };
    }
  
    function resolveBackgroundPosition(elW, elH, bgW, bgH, cs) {
      let raw = takeFirst(cs.backgroundPosition);
      let [x, y] = raw.split(/\s+/).filter(Boolean);
      if (!y) y = '50%';
      x = keywordToPercent(x, 'x');
      y = keywordToPercent(y, 'y');
  
      const tx = parseLenOrPercent(x, elW - bgW);
      const ty = parseLenOrPercent(y, elH - bgH);
  
      const pxX = tx.type === '%' ? (tx.v / 100) * (elW - bgW) : (isNaN(tx.v) ? 0 : tx.v);
      const pxY = ty.type === '%' ? (ty.v / 100) * (elH - bgH) : (isNaN(ty.v) ? 0 : ty.v);
  
      return { x: pxX, y: pxY };
    }
  
    function clampBox(x, y, s, W, H) {
      x = Math.max(0, Math.min(x, W));
      y = Math.max(0, Math.min(y, H));
      s = Math.min(s, W - x, H - y);
      return { x, y, s };
    }
  
    return getNaturalSize(bgUrl, true).then((nat) => {
      if (!nat) {
        const msg = 'Could not determine natural banner size.';
        console.error(msg);
        return { error: 'no_natural_size' };
      }
      const naturalW = nat.w, naturalH = nat.h;
      const Ew = bgRect.width, Eh = bgRect.height;
  
      const size = resolveBackgroundSize(naturalW, naturalH, Ew, Eh, cs);
      const pos = resolveBackgroundPosition(Ew, Eh, size.w, size.h, cs);
  
      // Avatar center in page px
      const avCx = avRect.left + avRect.width / 2;
      const avCy = avRect.top + avRect.height / 2;
  
      // Scaled bg top-left in page px
      const scaledLeft = bgRect.left + pos.x;
      const scaledTop  = bgRect.top  + pos.y;
  
      // Point within scaled image
      const scaledX = avCx - scaledLeft;
      const scaledY = avCy - scaledTop;
  
      // Map to natural pixels
      const scaleX = naturalW / size.w;
      const scaleY = naturalH / size.h;
  
      const centerX_nat = scaledX * scaleX;
      const centerY_nat = scaledY * scaleY;
      const diameter_nat = avRect.width * scaleX;
  
      const box = clampBox(
        centerX_nat - diameter_nat / 2,
        centerY_nat - diameter_nat / 2,
        diameter_nat,
        naturalW,
        naturalH
      );
  
      const result = {
        banner_url: bgUrl,
        natural_banner_size: { w: naturalW, h: naturalH, source: nat.source },
        element_size_px: { w: Ew, h: Eh },
        resolved_background_size_px: { w: size.w, h: size.h },
        resolved_background_position_px: { x: pos.x, y: pos.y },
        avatar_display_rect_px: { left: avRect.left, top: avRect.top, w: avRect.width, h: avRect.height },
        avatar_center_in_banner_natural_px: { x: centerX_nat, y: centerY_nat },
        avatar_diameter_natural_px: diameter_nat,
        recommended_square_crop_px: { x: box.x, y: box.y, size: box.s }
      };
  
      window._scMeasure = result; // keep for later
      try { copy(JSON.stringify(result, null, 2)); } catch (_) {}
      console.log('✔ Measurements saved to window._scMeasure and copied to clipboard (if allowed).');
      console.table(result);
      return result; // so the console shows an object, not "undefined"
    });
  })();
  