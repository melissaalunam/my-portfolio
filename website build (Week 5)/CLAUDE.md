# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Start here

At the beginning of every session, read these two files before doing anything else:
- `progress.md` — what has been built and how
- `next_steps.md` — what is planned for upcoming sessions

## Project Overview

Single-page portfolio website for a cherry blossom / flower photographer.

**Audience:** People drawn to soft, seasonal imagery — visitors who come for the atmosphere and quiet mood, not technical content.

## Current State

- **Theme:** Cherry blossoms and flowers — not wildlife
- **Tagline:** "Soft light, quiet moments."
- **Bio:** "Flowers have always been my reminder to slow down. They bloom without waiting for you to be ready, and they're gone before you think to look twice."
- **Images:** Real local photos in `photos/` folder (9 JPGs: IMG_8492, IMG_8497, IMG_8536, IMG_8618, IMG_8749, IMG_8754, IMG_8757, IMG_8924, IMG_8978)
- **Titles:** Petal Drift, First Bloom, Pink Reverie, Before the Wind, Fleeting, Soft Arrival, A Brief Season, Blossom Veil, After the Rain
- **Lightbox:** JavaScript lightbox with prev/next navigation, keyboard support (←→ Escape), click-outside-to-close

## Tech Stack

- HTML + CSS + minimal vanilla JavaScript (lightbox only)
- Single `index.html` + `style.css`
- No frameworks, no libraries, no build tools

To preview locally, open `index.html` directly in a browser — no server needed.

## Design Direction

- Soft, pastel aesthetic — blush, pink, warm tones
- Let the photography lead — UI recedes, not competes
- No decorative clutter
- 3×3 grid

## Collaboration Rules

- **Ask before restructuring.** Do not reorganize files, rename things, or change the layout architecture without explicit approval.
- **Only build what is asked.** No unsolicited features, extra sections, improvements or additions.
- **No frameworks.** Do not suggest or introduce Tailwind, Bootstrap, React, or any other library.
- **No comments or docstrings** added to code that was not changed.
- **No monkey patches**

## Audience Context

Visitors are nature and animal enthusiasts. Content and presentation should feel:
- Immersive and atmospheric
- Uncluttered, letting images breathe
- Warm and genuine, not corporate