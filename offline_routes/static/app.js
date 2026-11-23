(function () {
  'use strict';

  var W = 400, H = 260;
  var COLORS = {};
  // Canvas colours come from tokens.css; read again on every draw so the OS colour scheme applies.
  function readColors() {
    var cs = getComputedStyle(document.documentElement);
    var get = function (name) { return cs.getPropertyValue(name).trim(); };
    COLORS = { paper: get('--bg'), ink: get('--fg'), node: get('--bg-raised'), accent: get('--primary'), edge: get('--control-border') };
  }
  var NET_MSG = 'Server unreachable. Check that it is running, then try again.';

  var $ = function (id) { return document.getElementById(id); };
  var fromSel = $('from'), toSel = $('to'), calcBtn = $('calculate');
  var routeForm = $('route-form'), saveForm = $('save-form');
  var titleInput = $('title'), saveBtn = $('save');
  var statusEl = $('status'), stepsEl = $('steps'), totalEl = $('total'), stepsEmpty = $('steps-empty');
  var savedEl = $('saved'), edgesEl = $('edges'), canvas = $('map'), wrap = $('map-wrap');

  var graph = null;
  var names = {};
  var preview = null;   // reachable route object currently on screen
  var busy = false;     // calculate / reopen in flight
  var saving = false;
  var seq = 0;          // invalidates stale responses

  function setStatus(text, isError) {
    statusEl.textContent = text || '';
    statusEl.classList.toggle('error', !!isError);
  }

  function nameOf(id) { return names[id] || id; }

  function updateControls() {
    calcBtn.disabled = busy;
    saveBtn.disabled = !preview || saving;
  }

  function clearPreview() {
    preview = null;
    while (stepsEl.firstChild) stepsEl.removeChild(stepsEl.firstChild);
    stepsEl.hidden = true;
    totalEl.hidden = true;
    totalEl.textContent = '';
    stepsEmpty.hidden = false;
    updateControls();
    draw();
  }

  function showPreview(route) {
    preview = route;
    while (stepsEl.firstChild) stepsEl.removeChild(stepsEl.firstChild);
    (route.steps || []).forEach(function (s) {
      var li = document.createElement('li');
      li.textContent = s;
      stepsEl.appendChild(li);
    });
    totalEl.textContent = 'Total: ' + route.distance_m + ' m';
    stepsEl.hidden = false;
    totalEl.hidden = false;
    stepsEmpty.hidden = true;
    updateControls();
    draw();
  }

  // Returns {net:true} | {bad:true} | {status, data}
  function api(method, url, body) {
    var opts = { method: method, headers: {} };
    if (body !== undefined) {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(body);
    }
    return fetch(url, opts).then(function (res) {
      return res.text().then(function (txt) {
        var data = null;
        try { data = JSON.parse(txt); } catch (e) { return { bad: true, status: res.status }; }
        if (data === null || typeof data !== 'object') return { bad: true, status: res.status };
        return { status: res.status, ok: res.ok, data: data };
      });
    }).catch(function () { return { net: true }; });
  }

  function errText(r, fallback) {
    if (r.net) return NET_MSG;
    if (r.bad) return 'Unexpected response from the server.';
    var e = r.data && r.data.error;
    return (e && typeof e.message === 'string' && e.message) || fallback;
  }

  // ---- graph ----
  function fillSelect(sel) {
    graph.nodes.forEach(function (n) {
      var o = document.createElement('option');
      o.value = n.id;
      o.textContent = n.name;
      sel.appendChild(o);
    });
  }

  function loadGraph() {
    return api('GET', '/api/v1/graph').then(function (r) {
      if (r.net || r.bad || !r.ok || !r.data.graph) {
        setStatus(errText(r, 'Could not load the map.'), true);
        return false;
      }
      graph = r.data.graph;
      names = {};
      graph.nodes.forEach(function (n) { names[n.id] = n.name; });
      fillSelect(fromSel);
      fillSelect(toSel);
      while (edgesEl.firstChild) edgesEl.removeChild(edgesEl.firstChild);
      graph.edges.forEach(function (e) {
        var li = document.createElement('li');
        li.textContent = nameOf(e.from) + ' - ' + nameOf(e.to) + ': ' + e.meters + ' m';
        edgesEl.appendChild(li);
      });
      resize();
      return true;
    });
  }

  // ---- canvas ----
  function ariaSummary() {
    if (!graph) return 'Map of landmarks (not loaded)';
    var s = 'Map of ' + graph.nodes.length + ' landmarks and ' + graph.edges.length + ' connections.';
    if (preview) {
      s += ' Route: ' + preview.path.map(nameOf).join(' to ') + ', ' + preview.distance_m + ' m.';
    } else {
      s += ' No route shown.';
      if (fromSel.value) s += ' From: ' + nameOf(fromSel.value) + '.';
      if (toSel.value) s += ' To: ' + nameOf(toSel.value) + '.';
    }
    return s;
  }

  function resize() {
    var cssW = Math.max(200, Math.floor(wrap.clientWidth || W));
    var dpr = window.devicePixelRatio || 1;
    var pw = Math.round(cssW * dpr), ph = Math.round(cssW * H / W * dpr);
    if (canvas.width !== pw) canvas.width = pw;
    if (canvas.height !== ph) canvas.height = ph;
    draw();
  }

  function draw() {
    canvas.setAttribute('aria-label', ariaSummary());
    var ctx = canvas.getContext && canvas.getContext('2d');
    if (!ctx) return;
    var scale = canvas.width / W;                       // device px per logical unit
    var dpr = window.devicePixelRatio || 1;
    var k = scale / dpr;                                // css px per logical unit
    var px = function (n) { return n / k; };            // css px -> logical units
    readColors();
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.setTransform(scale, 0, 0, scale, 0, 0);
    ctx.fillStyle = COLORS.paper;
    ctx.fillRect(0, 0, W, H);
    if (!graph) return;

    var byId = {};
    graph.nodes.forEach(function (n) { byId[n.id] = n; });
    var onPath = {};
    if (preview) {
      for (var i = 0; i + 1 < preview.path.length; i++) {
        onPath[preview.path[i] + '|' + preview.path[i + 1]] = true;
        onPath[preview.path[i + 1] + '|' + preview.path[i]] = true;
      }
    }
    var fs = px(12);
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.font = '600 ' + fs + 'px system-ui, "Segoe UI", Arial, sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';

    // edges
    graph.edges.forEach(function (e) {
      var a = byId[e.from], b = byId[e.to];
      if (!a || !b) return;
      var hot = onPath[e.from + '|' + e.to];
      if (hot) {
        ctx.strokeStyle = COLORS.ink; ctx.lineWidth = px(10);
        ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
        ctx.strokeStyle = COLORS.accent; ctx.lineWidth = px(6);
      } else {
        ctx.strokeStyle = COLORS.edge; ctx.lineWidth = px(2);
      }
      ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
    });
    // edge labels
    graph.edges.forEach(function (e) {
      var a = byId[e.from], b = byId[e.to];
      if (!a || !b) return;
      var t = e.meters + ' m';
      var mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
      var tw = ctx.measureText(t).width + px(8), th = px(16);
      ctx.fillStyle = COLORS.paper;
      ctx.fillRect(mx - tw / 2, my - th / 2, tw, th);
      ctx.fillStyle = COLORS.ink;
      ctx.fillText(t, mx, my);
    });

    // nodes
    var from = fromSel.value, to = toSel.value;
    var r = px(6);
    graph.nodes.forEach(function (n) {
      var isFrom = n.id === from, isTo = n.id === to;
      var inRoute = preview && preview.path.indexOf(n.id) !== -1;
      ctx.lineWidth = px(2);
      ctx.strokeStyle = COLORS.ink;
      ctx.fillStyle = inRoute ? COLORS.accent : COLORS.node;
      ctx.beginPath();
      if (isFrom) {
        r = px(8);
        ctx.rect(n.x - r, n.y - r, 2 * r, 2 * r);
      } else if (isTo) {
        r = px(10);
        ctx.moveTo(n.x, n.y - r); ctx.lineTo(n.x + r, n.y);
        ctx.lineTo(n.x, n.y + r); ctx.lineTo(n.x - r, n.y); ctx.closePath();
      } else {
        r = px(6);
        ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
      }
      ctx.fill(); ctx.stroke();

      var label = n.name;
      if (isFrom && isTo) label += ' (From, To)';
      else if (isFrom) label += ' (From)';
      else if (isTo) label += ' (To)';
      var tw = ctx.measureText(label).width;
      var lx = Math.min(W - tw / 2 - px(2), Math.max(tw / 2 + px(2), n.x));
      var ly = n.y + px(22);
      if (ly + px(8) > H) ly = n.y - px(22);
      ctx.lineWidth = px(4);
      ctx.strokeStyle = COLORS.paper;
      ctx.strokeText(label, lx, ly);
      ctx.fillStyle = COLORS.ink;
      ctx.fillText(label, lx, ly);
    });
  }

  // ---- calculate ----
  function onSelectionChange() {
    seq++;
    busy = false;
    setStatus('');
    clearPreview();
  }

  function calculate(ev) {
    ev.preventDefault();
    if (busy) return;
    seq++;
    var my = seq;
    clearPreview();
    setStatus('');
    if (!graph) {
      setStatus('Loading the map...');
      loadGraph().then(function (ok) {
        if (!ok) return;
        loadSaved();
        if (my === seq) setStatus('Map loaded. Choose both landmarks.');
      });
      return;
    }
    var from = fromSel.value, to = toSel.value;
    if (!from || !to) { setStatus('Choose both landmarks.', true); return; }
    busy = true;
    updateControls();
    setStatus('Calculating route...');
    api('POST', '/api/v1/route', { from: from, to: to }).then(function (r) {
      if (my !== seq) return;
      busy = false;
      updateControls();
      if (r.net || r.bad || !r.ok) { clearPreview(); setStatus(errText(r, 'Could not calculate the route.'), true); return; }
      var d = r.data;
      if (!d.reachable) {
        clearPreview();
        setStatus(d.message || ('No route from ' + nameOf(from) + ' to ' + nameOf(to)), true);
        return;
      }
      showPreview(d);
      setStatus('Route found: ' + d.distance_m + ' m.');
    });
  }

  // ---- save ----
  function save(ev) {
    ev.preventDefault();
    if (!preview || saving) return;
    var title = titleInput.value.trim();
    if (!title) {
      setStatus('Enter a route title.', true);
      titleInput.focus();
      return;
    }
    saving = true;
    updateControls();
    setStatus('Saving...');
    api('POST', '/api/v1/routes', { title: title, from: preview.from, to: preview.to }).then(function (r) {
      saving = false;
      updateControls();
      if (r.net || r.bad) { setStatus(errText(r), true); return; }
      if (r.status === 201 && r.data.route) {
        titleInput.value = '';
        setStatus('Saved "' + r.data.route.title + '".');
        loadSaved();
        return;
      }
      if (r.status === 409) {
        setStatus('A route titled "' + title + '" already exists. Choose a different title.', true);
        titleInput.focus();
        return;
      }
      setStatus(errText(r, 'Could not save the route.'), true);
    });
  }

  // ---- saved list ----
  function renderSaved(routes) {
    while (savedEl.firstChild) savedEl.removeChild(savedEl.firstChild);
    if (!routes.length) {
      var e = document.createElement('li');
      e.className = 'empty';
      e.textContent = 'No saved routes yet.';
      savedEl.appendChild(e);
      return;
    }
    routes.forEach(function (rt) {
      var li = document.createElement('li');
      var b = document.createElement('button');
      b.type = 'button';
      b.textContent = rt.title;
      b.addEventListener('click', function () { reopen(rt.id); });
      var sp = document.createElement('span');
      sp.className = 'dist';
      sp.textContent = nameOf(rt.from) + ' to ' + nameOf(rt.to) + ', ' + rt.distance_m + ' m';
      li.appendChild(b);
      li.appendChild(sp);
      savedEl.appendChild(li);
    });
  }

  function loadSaved() {
    return api('GET', '/api/v1/routes').then(function (r) {
      if (r.net || r.bad || !r.ok || !Array.isArray(r.data.routes)) {
        while (savedEl.firstChild) savedEl.removeChild(savedEl.firstChild);
        var li = document.createElement('li');
        li.className = 'empty';
        li.textContent = 'Could not load saved routes.';
        savedEl.appendChild(li);
        setStatus(errText(r, 'Could not load saved routes.'), true);
        return;
      }
      renderSaved(r.data.routes);
    });
  }

  function reopen(id) {
    seq++;
    var my = seq;
    busy = true;
    clearPreview();
    setStatus('Opening saved route...');
    api('GET', '/api/v1/routes/' + encodeURIComponent(id)).then(function (r) {
      if (my !== seq) return;
      busy = false;
      updateControls();
      var rt = r.data && r.data.route;
      if (r.net || r.bad || !r.ok || !rt) { clearPreview(); setStatus(errText(r, 'Could not open the saved route.'), true); return; }
      fromSel.value = rt.from;
      toSel.value = rt.to;
      if (fromSel.value !== rt.from || toSel.value !== rt.to) {
        clearPreview();
        setStatus('This route uses landmarks that are not on the current map.', true);
        return;
      }
      showPreview(rt);
      setStatus('Opened "' + rt.title + '".');
    });
  }

  // ---- wire up ----
  fromSel.addEventListener('change', onSelectionChange);
  toSel.addEventListener('change', onSelectionChange);
  routeForm.addEventListener('submit', calculate);
  saveForm.addEventListener('submit', save);
  window.addEventListener('resize', resize);
  var schemeQuery = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)');
  if (schemeQuery) {
    if (schemeQuery.addEventListener) schemeQuery.addEventListener('change', draw);
    else if (schemeQuery.addListener) schemeQuery.addListener(draw);
  }
  if (typeof ResizeObserver === 'function') new ResizeObserver(resize).observe(wrap);

  updateControls();
  resize();
  loadGraph().then(function (ok) { if (ok) loadSaved(); });
})();
