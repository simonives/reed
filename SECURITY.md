# Security

## Reporting a vulnerability

If you discover a security vulnerability in Reed, please report it responsibly.

**Do not open a public GitHub issue for security vulnerabilities.**

Report via GitHub's private vulnerability reporting: [Security Advisories](https://github.com/simonives/reed/security/advisories/new).

Include:
- A description of the vulnerability
- Steps to reproduce
- Potential impact
- Any suggested remediation

You will receive an acknowledgement within 48 hours. Reed will publish a security advisory and release a patch as quickly as possible, crediting the reporter unless anonymity is requested.

---

## Software Bill of Materials (SBOM)

Reed publishes a full Software Bill of Materials with every release as a commitment to supply chain transparency. The SBOM lists every direct and transitive dependency included in Reed — their version, licence, and source.

### Format

SBOMs are published in **CycloneDX JSON** format (v1.5), the most widely supported SBOM standard for software composition analysis tools.

### Where to find it

Each GitHub Release includes two SBOM artifacts:

| Artifact | Contents |
|---|---|
| `reed-<version>-sbom.json` | Application SBOM — Python dependencies from `pyproject.toml` resolved to exact versions |
| `reed-<version>-container-sbom.json` | Container SBOM — everything in the Docker image, including OS packages |

SBOMs are also available from the GitHub Container Registry image manifest via:

```bash
docker buildx imagetools inspect ghcr.io/simonives/reed:<version> --format '{{ json .SBOM }}'
```

### Generation

SBOMs are generated automatically as part of the release pipeline:

- **Application SBOM:** [`cyclonedx-bom`](https://github.com/CycloneDX/cyclonedx-bom-python) from the locked dependency set
- **Container SBOM:** [Syft](https://github.com/anchore/syft) against the published Docker image

Both are generated from the final build artefacts — not from development dependencies or source — so they reflect exactly what ships.

### Why this matters

An SBOM allows users and security teams to:
- Audit Reed's dependencies before deploying it in their environment
- Run the SBOM against vulnerability databases (NVD, OSV) using tools like [Grype](https://github.com/anchore/grype) or [OWASP Dependency-Check](https://owasp.org/www-project-dependency-check/)
- Verify licence compliance across the full dependency tree
- Respond quickly if a dependency is found to have a CVE — the SBOM makes it immediately clear whether Reed is affected

Reed publishes SBOMs not because it is required to, but because it is the right practice for software that runs on other people's infrastructure.

---

## Dependency policy

- All direct dependencies are declared in `pyproject.toml` with minimum version constraints
- The Docker image pins dependencies to exact versions via a lockfile at build time
- Dependencies are reviewed on each release for known vulnerabilities using `pip-audit`
- Reed has no runtime dependencies on external services — it makes outbound HTTP requests only to fetch RSS feeds and to execute user-configured share targets (webhooks, Raindrop API, etc.)

## Licence

Reed is AGPL v3 licensed. All dependencies are permissively licensed (MIT, Apache 2.0, BSD). The SBOM includes the licence for every dependency.
