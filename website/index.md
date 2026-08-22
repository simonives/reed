---
layout: false
title: Reed
description: A self-hosted, open-source RSS reader with a graph-native data model, public REST API, and first-class MCP server.
---

<div class="reed-landing">
  <button class="theme-toggle" @click="toggleTheme" aria-label="Toggle light and dark theme">
    <svg class="icon-sun" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"/></svg>
    <svg class="icon-moon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
  </button>

  <header class="hero">
    <div class="wordmark">Reed<span class="beta">BETA</span></div>
    <h1>Your feeds.<br>Your graph.<br>Your data.</h1>
    <p class="tagline">
      A self-hosted, open-source RSS reader with a graph-native data model,
      a public REST API, and a first-class MCP server.
    </p>
    <div class="cta-row">
      <a class="cta primary" href="https://github.com/simonives/reed">View on GitHub</a>
      <a class="cta ghost" href="#install">Self-host it</a>
    </div>
  </header>

  <section class="prose">
    <p>
      Reed is a single-user, self-hosted RSS reader built for simplicity and
      developer access. It uses a graph database
      (<a href="https://kuzudb.com">Kuzu</a>) to model relationships between
      feeds, articles, authors, topics, and tags, making your reading history
      traversable by AI tools through a built-in MCP server.
    </p>
    <p>
      Feeds, articles, authors, topics, and tags are nodes and edges in a
      graph, not rows in a table, so an AI client can hop from an item to its
      topics, to related topics, to related items across other feeds, instead
      of just paging through a list.
    </p>
  </section>

  <section class="principles">
    <div class="principle">
      <span class="index">01</span>
      <h3>Graph-native</h3>
      <p>Traverse your reading history the way ideas actually connect, not the way a table forces them apart.</p>
    </div>
    <div class="principle">
      <span class="index">02</span>
      <h3>API-first</h3>
      <p>Everything the UI can do, the API can do. Full OpenAPI docs and a 27-tool MCP server, out of the box.</p>
    </div>
    <div class="principle">
      <span class="index">03</span>
      <h3>Zero ops</h3>
      <p>One <code>docker compose up</code>. Kuzu is embedded, no database server, no external services.</p>
    </div>
    <div class="principle">
      <span class="index">04</span>
      <h3>Open source</h3>
      <p>AGPL v3. Self-host it, fork it, read every line. Reed will never become a SaaS product.</p>
    </div>
  </section>

  <section id="install" class="install">
    <h2>Self-hosting</h2>
    <p>Run it from source:</p>
    <pre><code>git clone https://github.com/simonives/reed
cd reed
pip install -e .
reed serve</code></pre>
    <p>Or with Docker:</p>
    <pre><code>git clone https://github.com/simonives/reed
cd reed
cp .env.example .env   # add your REED_API_KEY
docker compose up</code></pre>
    <p class="note">
      Public beta, pre-1.0.0. See the
      <a href="https://github.com/simonives/reed#roadmap-to-v100">roadmap to v1.0.0</a>
      for what's left.
    </p>
  </section>

  <footer>
    <span>AGPL-3.0-or-later</span>
    <span class="dot">&middot;</span>
    <a href="https://github.com/simonives/reed">github.com/simonives/reed</a>
  </footer>
</div>

<script setup>
import { onMounted } from 'vue'

const STORAGE_KEY = 'reed-theme'

function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme)
}

function toggleTheme() {
  const current = document.documentElement.getAttribute('data-theme')
  const next = current === 'dark' ? 'light' : 'dark'
  localStorage.setItem(STORAGE_KEY, next)
  applyTheme(next)
}

onMounted(() => {
  const saved = localStorage.getItem(STORAGE_KEY)
  if (saved) applyTheme(saved)

  // VitePress emits stylesheets as <link rel="preload stylesheet" as="style">
  // for performance, which only prefetches the file, it never applies it as
  // an actual stylesheet on its own. Force-promote it so the page is styled.
  document.querySelectorAll('link[rel~="preload"][as="style"]').forEach((link) => {
    link.rel = 'stylesheet'
  })
})
</script>

<style>
@import url('https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&family=Roboto+Mono:wght@400;500&display=swap');

:root {
  --bg: #ffffff;
  --ink: #202124;
  --ink-soft: #5f6368;
  --rule: #dadce0;
  --surface: #f8f9fa;
  --accent: #1a73e8;
  --accent-surface: #e8f0fe;
}

@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --bg: #202124;
    --ink: #e8eaed;
    --ink-soft: #9aa0a6;
    --rule: #3c4043;
    --surface: #303134;
    --accent: #8ab4f8;
    --accent-surface: #2a3950;
  }
}

:root[data-theme="dark"] {
  --bg: #202124;
  --ink: #e8eaed;
  --ink-soft: #9aa0a6;
  --rule: #3c4043;
  --surface: #303134;
  --accent: #8ab4f8;
  --accent-surface: #2a3950;
}

.reed-landing * {
  box-sizing: border-box;
}

.reed-landing {
  position: relative;
  background: var(--bg);
  color: var(--ink);
  font-family: 'Roboto', system-ui, sans-serif;
  min-height: 100vh;
  padding: 0 1.5rem;
}

.reed-landing a {
  color: inherit;
}

.theme-toggle {
  position: absolute;
  top: 1.5rem;
  right: 1.5rem;
  width: 2.25rem;
  height: 2.25rem;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--rule);
  border-radius: 999px;
  background: var(--bg);
  color: var(--ink-soft);
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease;
}

.theme-toggle:hover {
  background: var(--surface);
  color: var(--ink);
}

.icon-moon {
  display: none;
}

:root[data-theme="dark"] .icon-sun {
  display: none;
}

:root[data-theme="dark"] .icon-moon {
  display: block;
}

@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) .icon-sun {
    display: none;
  }
  :root:not([data-theme="light"]) .icon-moon {
    display: block;
  }
}

.hero {
  max-width: 44rem;
  margin: 0 auto;
  padding: 6rem 0 4rem;
  text-align: center;
}

.wordmark {
  font-size: 1.375rem;
  font-weight: 500;
  letter-spacing: -0.01em;
  display: inline-flex;
  align-items: center;
  gap: 0.6rem;
  margin-bottom: 3rem;
}

.wordmark .beta {
  font-family: 'Roboto Mono', monospace;
  font-size: 0.625rem;
  font-weight: 500;
  letter-spacing: 0.1em;
  color: var(--accent);
  border: 1px solid var(--accent);
  border-radius: 999px;
  padding: 0.2rem 0.55rem;
}

.hero h1 {
  font-weight: 400;
  font-size: clamp(2.75rem, 7vw, 4.5rem);
  line-height: 1.1;
  letter-spacing: -0.02em;
  margin: 0 0 2rem;
}

.tagline {
  font-size: 1.125rem;
  line-height: 1.6;
  color: var(--ink-soft);
  max-width: 34rem;
  margin: 0 auto 2.75rem;
}

.cta-row {
  display: flex;
  gap: 1rem;
  justify-content: center;
  flex-wrap: wrap;
}

.cta {
  display: inline-block;
  padding: 0.8rem 1.6rem;
  border-radius: 999px;
  font-size: 0.95rem;
  font-weight: 500;
  text-decoration: none;
  transition: box-shadow 0.15s ease, background 0.15s ease;
}

.cta.primary {
  background: var(--accent);
  color: #ffffff;
  box-shadow: 0 1px 2px rgba(26, 115, 232, 0.3), 0 1px 3px 1px rgba(26, 115, 232, 0.15);
}

.cta.primary:hover {
  box-shadow: 0 1px 3px rgba(26, 115, 232, 0.4), 0 4px 8px 3px rgba(26, 115, 232, 0.15);
}

.cta.ghost {
  border: 1px solid var(--rule);
  color: var(--accent);
  background: var(--bg);
}

.cta.ghost:hover {
  background: var(--accent-surface);
}

.prose {
  max-width: 38rem;
  margin: 0 auto;
  padding: 3rem 0;
  border-top: 1px solid var(--rule);
}

.prose p {
  font-size: 1.0625rem;
  line-height: 1.75;
  color: var(--ink-soft);
  margin: 0 0 1.5rem;
}

.prose p:last-child {
  margin-bottom: 0;
}

.prose a {
  color: var(--accent);
  text-decoration: none;
}

.prose a:hover {
  text-decoration: underline;
}

.principles {
  max-width: 50rem;
  margin: 0 auto;
  padding: 3rem 0;
  border-top: 1px solid var(--rule);
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 3rem 3rem;
}

.principle .index {
  font-family: 'Roboto Mono', monospace;
  font-size: 0.75rem;
  color: var(--accent);
  letter-spacing: 0.08em;
}

.principle h3 {
  font-weight: 500;
  font-size: 1.375rem;
  margin: 0.6rem 0 0.6rem;
}

.principle p {
  font-size: 0.95rem;
  line-height: 1.6;
  color: var(--ink-soft);
  margin: 0;
}

.install {
  max-width: 38rem;
  margin: 0 auto;
  padding: 3rem 0;
  border-top: 1px solid var(--rule);
}

.install h2 {
  font-weight: 500;
  font-size: 1.75rem;
  margin: 0 0 1.5rem;
}

.install p {
  font-size: 1rem;
  color: var(--ink-soft);
  margin: 0 0 0.75rem;
}

.install pre {
  background: var(--surface);
  border: 1px solid var(--rule);
  border-radius: 0.5rem;
  padding: 1.25rem 1.5rem;
  overflow-x: auto;
  margin: 0 0 1.5rem;
}

.install code {
  font-family: 'Roboto Mono', monospace;
  font-size: 0.875rem;
  line-height: 1.7;
  color: var(--ink);
  background: none;
}

.install .note {
  font-size: 0.875rem;
  margin-top: 2rem;
}

.install .note a {
  color: var(--accent);
  text-decoration: none;
}

.install .note a:hover {
  text-decoration: underline;
}

footer {
  max-width: 50rem;
  margin: 0 auto;
  padding: 2.5rem 0 4rem;
  border-top: 1px solid var(--rule);
  font-family: 'Roboto Mono', monospace;
  font-size: 0.8rem;
  color: var(--ink-soft);
  text-align: center;
}

footer .dot {
  margin: 0 0.6rem;
}

@media (max-width: 640px) {
  .hero {
    padding: 4rem 0 3rem;
  }
  .principles {
    grid-template-columns: 1fr;
    gap: 2.5rem;
  }
}
</style>
