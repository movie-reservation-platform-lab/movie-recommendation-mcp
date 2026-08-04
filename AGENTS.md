# Movie Recommendation MCP — AI Guidance

## Purpose

This repository owns the MCP wrapper around the Rust movie recommendation API.
It exposes stable MCP tools for the Python reservation agent and forwards
distributed tracing/request metadata to the downstream API.

## Repository Rules

- Keep MCP tool names stable unless coordinating a consumer migration with
  `movie-reservation-agent`.
- Preserve propagation of `traceparent`, `tracestate`, `X-Correlation-Id`,
  `X-Request-Id`, and `X-Demo-Fault`.
- Keep downstream API configuration environment-driven.
- Do not deploy AWS resources from this repo.
- Publish immutable application artifacts; deployment composition belongs to
  the platform environment/infra repos.

## Commands

- Install/sync: `uv sync --frozen`
- Compile check: `uv run python -m compileall src`
- Run locally: `uv run movie-recommendation-mcp`
