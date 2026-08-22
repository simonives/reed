---
layout: false
title: Reed
description: A self-hosted, open-source RSS reader with a graph-native data model, public REST API, and first-class MCP server.
---

<div class="reed-landing">
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

<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600&family=Instrument+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap');

:root {
  --paper: #faf7f0;
  --ink: #1c1a17;
  --ink-soft: #57524a;
  --rule: #e7e1d4;
  --accent: #c1531f;
  --accent-soft: #f3e2d6;
}

@media (prefers-color-scheme: dark) {
  :root {
    --paper: #17140f;
    --ink: #f3ede0;
    --ink-soft: #b3a996;
    --rule: #332d23;
    --accent: #e0813f;
    --accent-soft: #3a2517;
  }
}

.reed-landing * {
  box-sizing: border-box;
}

.reed-landing {
  background: var(--paper);
  color: var(--ink);
  font-family: 'Instrument Sans', system-ui, sans-serif;
  min-height: 100vh;
  padding: 0 1.5rem;
}

.reed-landing a {
  color: inherit;
}

.hero {
  max-width: 44rem;
  margin: 0 auto;
  padding: 6rem 0 4rem;
  text-align: center;
}

.wordmark {
  font-family: 'Fraunces', serif;
  font-size: 1.375rem;
  font-weight: 500;
  letter-spacing: 0.02em;
  display: inline-flex;
  align-items: center;
  gap: 0.6rem;
  margin-bottom: 3rem;
}

.wordmark .beta {
  font-family: 'IBM Plex Mono', monospace;
  font-size: 0.625rem;
  font-weight: 500;
  letter-spacing: 0.12em;
  color: var(--accent);
  border: 1px solid var(--accent);
  border-radius: 999px;
  padding: 0.2rem 0.55rem;
}

.hero h1 {
  font-family: 'Fraunces', serif;
  font-weight: 400;
  font-size: clamp(2.75rem, 7vw, 4.5rem);
  line-height: 1.05;
  letter-spacing: -0.01em;
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
  transition: transform 0.15s ease, opacity 0.15s ease;
}

.cta:hover {
  transform: translateY(-1px);
}

.cta.primary {
  background: var(--ink);
  color: var(--paper);
}

.cta.ghost {
  border: 1px solid var(--rule);
  color: var(--ink);
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
  text-decoration: underline;
  text-decoration-color: var(--rule);
  text-underline-offset: 3px;
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
  font-family: 'IBM Plex Mono', monospace;
  font-size: 0.75rem;
  color: var(--accent);
  letter-spacing: 0.08em;
}

.principle h3 {
  font-family: 'Fraunces', serif;
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
  font-family: 'Fraunces', serif;
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
  background: var(--accent-soft);
  border-radius: 0.75rem;
  padding: 1.25rem 1.5rem;
  overflow-x: auto;
  margin: 0 0 1.5rem;
}

.install code {
  font-family: 'IBM Plex Mono', monospace;
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
  text-decoration: underline;
  text-decoration-color: var(--accent);
  text-underline-offset: 3px;
}

footer {
  max-width: 50rem;
  margin: 0 auto;
  padding: 2.5rem 0 4rem;
  border-top: 1px solid var(--rule);
  font-family: 'IBM Plex Mono', monospace;
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
