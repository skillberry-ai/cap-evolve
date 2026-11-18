/* ───────────────────────────────────────────────────────────────────────
   cap-evolve education decks — a small, dependency-free slide engine.

   Markup contract (see ../README.md):
     <body data-chapter="Chapter 3 · Repository map">
       <div id="stage"><div id="canvas">
         <section class="slide"> ...content...
           <aside class="notes" lang="en"> English speaker notes </aside>
           <aside class="notes" lang="he"> Hebrew speaker notes </aside>
         </section>
       </div></div>
       <script src="assets/deck.js"></script>

   Keys:  → / Space / PageDown  next      ← / PageUp  previous
          Home / End  first / last        N  notes panel
          L  notes language (EN / HE)     P  presenter window
          O  overview grid                D  handout (all slides + notes)
          F  full screen                  ?  help
   ─────────────────────────────────────────────────────────────────────── */
(function () {
  "use strict";

  var params = new URLSearchParams(location.search);
  var isPresenter = params.has("presenter");
  var canvas = document.getElementById("canvas");
  var stage = document.getElementById("stage");
  var slides = Array.prototype.slice.call(canvas.querySelectorAll(":scope > .slide"));
  var idx = 0;        // current slide
  var frag = 0;       // number of fragments shown on the current slide
  var lang = "en";
  var peer = null;    // the other window (presenter <-> audience)
  var startTime = null;

  function store(key, val) {
    try { if (val === undefined) return localStorage.getItem(key); localStorage.setItem(key, val); } catch (e) { return null; }
  }
  lang = params.get("lang") || store("ce-edu-lang") || "en";
  if (lang !== "he") lang = "en";

  // ── decorate each slide: chapter tag, brand, page number ───────────
  var chapter = document.body.getAttribute("data-chapter") || "";
  slides.forEach(function (s, i) {
    if (!s.classList.contains("title") && chapter) {
      var t = document.createElement("div"); t.className = "chapter-tag"; t.textContent = chapter; s.appendChild(t);
    }
    var b = document.createElement("div"); b.className = "brand"; b.innerHTML = "<b>cap-evolve</b> · team onboarding"; s.appendChild(b);
    var n = document.createElement("div"); n.className = "page-no"; n.textContent = (i + 1) + " / " + slides.length; s.appendChild(n);
  });

  function fragmentsOf(s) { return Array.prototype.slice.call(s.querySelectorAll(".fragment")); }
  function notesOf(s, l) {
    var a = s.querySelector('aside.notes[lang="' + l + '"]') || s.querySelector("aside.notes");
    return a ? a.innerHTML : "<p><em>No notes for this slide.</em></p>";
  }

  // ── chrome: progress bar, toolbar, notes panel, help ───────────────
  var progress = document.createElement("div"); progress.id = "progress"; document.body.appendChild(progress);

  var toolbar = document.createElement("div"); toolbar.id = "toolbar";
  toolbar.innerHTML =
    '<button data-k="n" title="Notes (N)">Notes</button>' +
    '<button data-k="l" title="Notes language (L)">EN/HE</button>' +
    '<button data-k="p" title="Presenter window (P)">Presenter</button>' +
    '<button data-k="o" title="Overview (O)">Overview</button>' +
    '<button data-k="d" title="Handout (D)">Handout</button>' +
    '<button data-k="?" title="Help (?)">?</button>';
  document.body.appendChild(toolbar);
  toolbar.addEventListener("click", function (e) { var k = e.target.getAttribute("data-k"); if (k) onKey({ key: k, preventDefault: function () {} }); });

  var panel = document.createElement("div"); panel.id = "notes-panel";
  panel.innerHTML = '<div id="notes-head"><span id="notes-title">Speaker notes</span><span class="sp"></span>' +
    '<button data-l="en">English</button><button data-l="he">עברית</button></div><div id="notes-body"></div>';
  document.body.appendChild(panel);
  panel.querySelector("#notes-head").addEventListener("click", function (e) {
    var l = e.target.getAttribute("data-l"); if (l) setLang(l);
  });

  var help = document.createElement("div"); help.id = "help";
  help.innerHTML = '<div class="box"><b>Keyboard</b><br>' +
    '<kbd>→</kbd> <kbd>Space</kbd> next &nbsp; <kbd>←</kbd> previous &nbsp; <kbd>Home</kbd>/<kbd>End</kbd><br>' +
    '<kbd>N</kbd> speaker notes panel<br><kbd>L</kbd> notes language: English / Hebrew<br>' +
    '<kbd>P</kbd> presenter window (notes, next slide, timer)<br>' +
    '<kbd>O</kbd> overview of all slides<br><kbd>D</kbd> handout: all slides with notes (print it)<br>' +
    '<kbd>F</kbd> full screen &nbsp; <kbd>Esc</kbd> close</div>';
  document.body.appendChild(help);
  help.addEventListener("click", function () { help.classList.remove("open"); });

  // ── presenter window markup ────────────────────────────────────────
  var presenterEl = null;
  if (isPresenter) {
    document.body.classList.add("presenter");
    presenterEl = document.createElement("div"); presenterEl.id = "presenter";
    presenterEl.innerHTML =
      '<div class="p-head"><span class="clock" id="p-clock">00:00</span><button id="p-reset">Restart timer</button>' +
      '<span id="p-pos"></span><span class="sp"></span><span id="p-target"></span>' +
      '<button data-l="en">English</button><button data-l="he">עברית</button></div>' +
      '<div class="p-left"><div class="p-label">Current</div><div class="p-frame" id="p-cur"></div>' +
      '<div class="p-label">Next</div><div class="p-frame" id="p-next"></div></div>' +
      '<div class="p-notes" id="p-notes"></div>';
    document.body.appendChild(presenterEl);
    presenterEl.querySelector(".p-head").addEventListener("click", function (e) {
      var l = e.target.getAttribute("data-l"); if (l) setLang(l);
      if (e.target.id === "p-reset") startTime = Date.now();
    });
    var target = document.body.getAttribute("data-minutes");
    if (target) presenterEl.querySelector("#p-target").textContent = "Target: " + target + " min";
    startTime = Date.now();
    setInterval(function () {
      var s = Math.floor((Date.now() - startTime) / 1000);
      document.getElementById("p-clock").textContent = String(Math.floor(s / 60)).padStart(2, "0") + ":" + String(s % 60).padStart(2, "0");
    }, 500);
    toolbar.style.display = "none";
  }

  function fillFrame(frame, s) {
    frame.innerHTML = "";
    if (!s) { frame.style.height = "0px"; return; }
    var w = frame.clientWidth || 600;
    var left = frame.parentNode.clientHeight || 700;
    var scale = Math.min(w / 1280, (left - 60) / 2 / 720);
    var c = s.cloneNode(true); c.classList.add("active");
    c.querySelectorAll("aside.notes").forEach(function (a) { a.remove(); });
    c.style.transform = "scale(" + scale + ")";
    frame.style.height = (720 * scale) + "px";
    frame.appendChild(c);
  }

  // ── rendering ──────────────────────────────────────────────────────
  function render(broadcast) {
    slides.forEach(function (s, i) { s.classList.toggle("active", i === idx); });
    var f = fragmentsOf(slides[idx]);
    f.forEach(function (el, i) { el.classList.toggle("shown", i < frag); });
    progress.style.width = ((idx + 1) / slides.length * 100) + "%";
    var body = document.getElementById("notes-body");
    body.innerHTML = notesOf(slides[idx], lang);
    body.setAttribute("dir", lang === "he" ? "rtl" : "ltr");
    body.setAttribute("lang", lang);
    panel.querySelectorAll("[data-l]").forEach(function (b) { b.classList.toggle("on", b.getAttribute("data-l") === lang); });
    document.getElementById("notes-title").textContent = "Speaker notes · slide " + (idx + 1) + " / " + slides.length;
    if (isPresenter) {
      fillFrame(document.getElementById("p-cur"), slides[idx]);
      fillFrame(document.getElementById("p-next"), slides[idx + 1]);
      var pn = document.getElementById("p-notes");
      pn.innerHTML = notesOf(slides[idx], lang);
      pn.setAttribute("dir", lang === "he" ? "rtl" : "ltr");
      pn.setAttribute("lang", lang);
      document.getElementById("p-pos").textContent = "Slide " + (idx + 1) + " / " + slides.length + (f.length ? "  · step " + frag + "/" + f.length : "");
      presenterEl.querySelectorAll("[data-l]").forEach(function (b) { b.classList.toggle("on", b.getAttribute("data-l") === lang); });
    }
    if (location.hash !== "#/" + (idx + 1)) history.replaceState(null, "", "#/" + (idx + 1));
    if (broadcast !== false && peer && !peer.closed) {
      try { peer.postMessage({ ceEdu: true, idx: idx, frag: frag, lang: lang }, "*"); } catch (e) { /* peer gone */ }
    }
  }

  function go(i, fr) {
    idx = Math.max(0, Math.min(slides.length - 1, i));
    frag = fr === undefined ? 0 : fr;
    render();
  }
  function next() {
    var f = fragmentsOf(slides[idx]);
    if (frag < f.length) { frag++; render(); } else if (idx < slides.length - 1) { go(idx + 1, 0); }
  }
  function prev() {
    if (frag > 0) { frag--; render(); } else if (idx > 0) { go(idx - 1, fragmentsOf(slides[idx - 1]).length); }
  }
  function setLang(l) { lang = l; store("ce-edu-lang", l); if (document.body.classList.contains("handout")) buildHandout(); render(); }

  // ── scaling ────────────────────────────────────────────────────────
  function fit() {
    if (document.body.classList.contains("overview") || document.body.classList.contains("handout")) return;
    var r = stage.getBoundingClientRect();
    var s = Math.min(r.width / 1280, r.height / 720) * 0.98;
    canvas.style.transform = "scale(" + s + ")";
    if (isPresenter) render(false);
  }
  window.addEventListener("resize", fit);

  // ── overview and handout ───────────────────────────────────────────
  function toggleOverview() {
    exitHandout();
    var on = document.body.classList.toggle("overview");
    slides.forEach(function (s) { s.style.display = on ? "flex" : ""; });
    if (!on) { fit(); render(); } else { canvas.style.transform = "none"; slides[idx].scrollIntoView({ block: "center" }); }
  }
  slides.forEach(function (s, i) {
    s.addEventListener("click", function () { if (document.body.classList.contains("overview")) { toggleOverview(); go(i); } });
  });

  var wraps = [];
  function buildHandout() {
    wraps.forEach(function (w) { var n = w.querySelector(".handout-notes"); if (n) n.remove(); });
    slides.forEach(function (s, i) {
      var w = wraps[i];
      var n = document.createElement("div"); n.className = "handout-notes";
      n.setAttribute("dir", lang === "he" ? "rtl" : "ltr"); n.setAttribute("lang", lang);
      n.innerHTML = notesOf(s, lang);
      w.appendChild(n);
    });
  }
  function enterHandout() {
    document.body.classList.add("handout");
    canvas.style.transform = "none";
    wraps = slides.map(function (s) {
      var w = document.createElement("div"); w.className = "slide-wrap";
      s.parentNode.insertBefore(w, s); w.appendChild(s); s.style.display = "flex"; return w;
    });
    buildHandout();
  }
  function exitHandout() {
    if (!document.body.classList.contains("handout")) return;
    wraps.forEach(function (w) {
      var s = w.querySelector(".slide"); s.style.display = ""; canvas.insertBefore(s, w); w.remove();
    });
    wraps = [];
    document.body.classList.remove("handout");
    fit(); render();
  }
  function toggleHandout() {
    if (document.body.classList.contains("overview")) toggleOverview();
    if (document.body.classList.contains("handout")) exitHandout(); else enterHandout();
  }

  // ── presenter window link ──────────────────────────────────────────
  function openPresenter() {
    var url = location.pathname + "?presenter&lang=" + lang + "#/" + (idx + 1);
    peer = window.open(url, "ce-edu-presenter", "width=1300,height=820");
  }
  if (isPresenter && window.opener) peer = window.opener;
  window.addEventListener("message", function (e) {
    var d = e.data;
    if (!d || !d.ceEdu) return;
    if (d.hello && isPresenter === false) { peer = e.source; render(); return; }
    idx = d.idx; frag = d.frag; if (d.lang) lang = d.lang;
    render(false);
  });
  if (isPresenter && peer) { try { peer.postMessage({ ceEdu: true, hello: true }, "*"); } catch (e) { /* ignore */ } }

  // ── keyboard ───────────────────────────────────────────────────────
  function onKey(e) {
    var k = e.key;
    if (help.classList.contains("open") && k !== "?") { help.classList.remove("open"); if (k === "Escape") return; }
    switch (k) {
      case "ArrowRight": case "ArrowDown": case " ": case "PageDown": case "Enter": e.preventDefault(); next(); break;
      case "ArrowLeft": case "ArrowUp": case "PageUp": case "Backspace": e.preventDefault(); prev(); break;
      case "Home": go(0); break;
      case "End": go(slides.length - 1); break;
      case "n": case "N": document.body.classList.toggle("notes-open"); fit(); break;
      case "l": case "L": setLang(lang === "en" ? "he" : "en"); break;
      case "p": case "P": if (!isPresenter) openPresenter(); break;
      case "o": case "O": toggleOverview(); break;
      case "d": case "D": toggleHandout(); break;
      case "f": case "F":
        if (!document.fullscreenElement) { document.documentElement.requestFullscreen && document.documentElement.requestFullscreen(); }
        else { document.exitFullscreen && document.exitFullscreen(); }
        break;
      case "?": help.classList.toggle("open"); break;
      case "Escape":
        if (document.body.classList.contains("overview")) toggleOverview();
        else if (document.body.classList.contains("handout")) exitHandout();
        break;
    }
  }
  document.addEventListener("keydown", function (e) { if (e.metaKey || e.ctrlKey || e.altKey) return; onKey(e); });


  // ── layout check: ?check writes a report into <pre id="check-result"> ──
  // Run: chrome --headless=new --dump-dom "file:///.../deck.html?check" | grep -A50 check-result
  function runCheck() {
    canvas.style.transform = "none";
    var out = [];
    slides.forEach(function (s, i) {
      slides.forEach(function (o) { o.classList.remove("active"); });
      s.classList.add("active");
      s.querySelectorAll(".fragment").forEach(function (f) { f.classList.add("shown"); });
      var sr = s.getBoundingClientRect();
      var problems = [];
      if (!s.querySelector('aside.notes[lang="en"]')) problems.push("missing English notes");
      if (!s.querySelector('aside.notes[lang="he"]')) problems.push("missing Hebrew notes");
      s.querySelectorAll("*").forEach(function (el) {
        if (el.closest("aside.notes") || el.closest(".brand") || el.closest(".page-no") || el.closest(".chapter-tag")) return;
        if (el.closest("svg") && el.tagName.toLowerCase() !== "svg") return;
        var r = el.getBoundingClientRect();
        if (r.width === 0 && r.height === 0) return;
        var tag = el.tagName.toLowerCase() + (el.className && typeof el.className === "string" ? "." + el.className.split(" ").join(".") : "");
        if (r.bottom > sr.bottom - 44 + 0.5) problems.push("below safe area by " + Math.round(r.bottom - (sr.bottom - 44)) + "px: " + tag);
        if (r.right > sr.right - 24 + 0.5) problems.push("past right edge by " + Math.round(r.right - (sr.right - 24)) + "px: " + tag);
        if ((el.tagName === "PRE" || el.classList.contains("tree")) && el.scrollWidth > el.clientWidth + 1) problems.push("text clipped horizontally (" + (el.scrollWidth - el.clientWidth) + "px): " + tag);
        if ((el.tagName === "PRE" || el.classList.contains("tree")) && el.scrollHeight > el.clientHeight + 1) problems.push("text clipped vertically (" + (el.scrollHeight - el.clientHeight) + "px): " + tag);
      });
      var uniq = problems.filter(function (p, j) { return problems.indexOf(p) === j; }).slice(0, 6);
      out.push("slide " + (i + 1) + ": " + (uniq.length ? "FAIL\n    " + uniq.join("\n    ") : "ok"));
    });
    var pre = document.createElement("pre"); pre.id = "check-result"; pre.textContent = out.join("\n");
    document.body.appendChild(pre);
  }

  // ── start ──────────────────────────────────────────────────────────
  var m = /^#\/(\d+)/.exec(location.hash);
  if (m) idx = Math.max(0, Math.min(slides.length - 1, parseInt(m[1], 10) - 1));
  if (params.has("notes")) document.body.classList.add("notes-open");
  if (params.has("handout")) enterHandout();
  fit();
  render();
  if (params.has("check")) runCheck();
  if (params.has("print")) { if (!document.body.classList.contains("handout")) {} setTimeout(function () { window.print(); }, 400); }
})();
