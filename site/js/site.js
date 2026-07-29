/* cap-evolve site — tiny, dependency-free progressive enhancement.
   Theme is applied pre-paint by an inline <head> script (no FOUC); this file
   wires the theme toggle, the mobile nav, scroll-reveal, TOC scrollspy, and
   code copy buttons. */
(function () {
  "use strict";
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ── theme toggle ── */
  var KEY = "capevolve-theme";
  var toggle = document.querySelector(".theme-toggle");
  if (toggle) {
    toggle.addEventListener("click", function () {
      var cur = document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark";
      var next = cur === "light" ? "dark" : "light";
      document.documentElement.setAttribute("data-theme", next);
      try { localStorage.setItem(KEY, next); } catch (e) {}
      toggle.setAttribute("aria-label", next === "light" ? "Switch to dark theme" : "Switch to light theme");
    });
  }

  /* ── mobile nav ──
     The button is CSS-hidden above the 860px breakpoint, so no media query is
     needed here: if it can be clicked, we're on mobile. */
  var navToggle = document.querySelector(".nav-toggle");
  var navLinks = document.getElementById("nav-links");
  if (navToggle && navLinks) {
    var setOpen = function (open) {
      navLinks.classList.toggle("open", open);
      navToggle.setAttribute("aria-expanded", open ? "true" : "false");
      navToggle.setAttribute("aria-label", open ? "Close menu" : "Menu");
    };
    navToggle.addEventListener("click", function () {
      setOpen(navToggle.getAttribute("aria-expanded") !== "true");
    });
    document.addEventListener("keydown", function (e) {
      if (e.key !== "Escape" || navToggle.getAttribute("aria-expanded") !== "true") return;
      setOpen(false);
      navToggle.focus();   /* never leave focus inside a closed drawer */
    });
    /* click outside closes; a click on a link inside navigates away anyway */
    document.addEventListener("click", function (e) {
      if (navToggle.getAttribute("aria-expanded") !== "true") return;
      if (!navLinks.contains(e.target) && !navToggle.contains(e.target)) setOpen(false);
    });
    /* Tabbing past the last drawer control used to put focus on page controls
       sitting *behind* the open drawer (copy buttons at y=520 under a 418px
       drawer) — focusable but invisible. This is a disclosure widget, not a
       modal, so release focus onward rather than cycling it: Tab keeps moving
       forward and the drawer closes, so nothing focused is ever hidden. */
    navLinks.addEventListener("focusout", function (e) {
      if (navToggle.getAttribute("aria-expanded") !== "true") return;
      var to = e.relatedTarget;
      if (to && (navLinks.contains(to) || navToggle.contains(to))) return;
      setOpen(false);
    });
    /* resizing up to desktop would otherwise leave aria-expanded="true" lying.
       matchMedia fires once per breakpoint crossing; a resize listener fires on
       every mobile scroll (iOS/Android URL-bar collapse) for no benefit. */
    window.matchMedia("(min-width: 861px)").addEventListener("change", function (e) {
      if (e.matches) setOpen(false);
    });
  }

  /* ── scroll-reveal ── */
  var reveals = document.querySelectorAll(".reveal");
  if (reduce || !("IntersectionObserver" in window)) {
    reveals.forEach(function (el) { el.classList.add("in"); });
  } else {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); }
      });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.08 });
    reveals.forEach(function (el) { io.observe(el); });
  }

  /* ── code copy buttons ── */
  document.querySelectorAll("pre").forEach(function (pre) {
    if (pre.querySelector(".copy-btn")) return;
    var code = pre.querySelector("code") || pre;
    var btn = document.createElement("button");
    btn.className = "copy-btn";
    btn.type = "button";
    btn.textContent = "copy";
    btn.addEventListener("click", function () {
      navigator.clipboard.writeText(code.innerText.replace(/\n$/, "")).then(function () {
        btn.textContent = "copied"; btn.classList.add("done");
        setTimeout(function () { btn.textContent = "copy"; btn.classList.remove("done"); }, 1400);
      });
    });
    pre.appendChild(btn);
  });

  /* ── TOC scrollspy ── */
  var tocLinks = Array.prototype.slice.call(document.querySelectorAll(".toc a[href^='#']"));
  if (tocLinks.length && "IntersectionObserver" in window) {
    var targets = tocLinks
      .map(function (a) { return document.getElementById(a.getAttribute("href").slice(1)); })
      .filter(Boolean);
    var byId = {};
    tocLinks.forEach(function (a) { byId[a.getAttribute("href").slice(1)] = a; });
    var spy = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) {
          tocLinks.forEach(function (a) { a.classList.remove("active"); });
          var link = byId[e.target.id];
          if (link) link.classList.add("active");
        }
      });
    }, { rootMargin: "-15% 0px -70% 0px", threshold: 0 });
    targets.forEach(function (t) { spy.observe(t); });
  }
})();
