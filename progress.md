# Progress Log

## Session 1 — April 1, 2026

### What we built
A single-page photography portfolio (`index.html` + `style.css`) deployed to GitHub.

### Steps taken

**1. Project setup**
- Created `my-portfolio/` folder
- Wrote `CLAUDE.md` with project rules: plain HTML/CSS only, no frameworks, ask before restructuring, only build what is asked

**2. Built the HTML structure**
- Hero section: name, discipline, tagline
- Projects section: 3×3 grid with image placeholders and captions
- About section: bio paragraph
- Contact section: mailto link to melissa_luna00@yonsei.ac.kr

**3. Wrote the CSS (dark → pastel)**
- Started with a dark minimal aesthetic
- User requested a full redesign: pastel colors, whimsical tone
- Each section got its own pastel background (blush hero, mint projects, yellow about, lavender contact)

**4. Filled in content**
- Hero: Melissa Luna / Photographer / "Finding stillness in the wild."
- 9 project titles: Golden Hour Migration, Still Waters, The Understory, First Light, Featherweight, Deep Canopy, Salt Flat, Wading Season, Dusk, Alone
- Bio: nature photography focused, natural light, unhurried time

**5. Added real images to the grid**
- Replaced colored placeholder divs with `<img>` tags
- Used loremflickr.com URLs with keyword-matched nature/animal queries per title
- Requires internet connection to load

**6. Added circular portrait photo to hero**
- Converted `IMG_8287.HEIC` → `melissa.jpg` using macOS `sips`
- Hero restructured to flex row: text left, photo right
- Photo styled as a circle (`border-radius: 50%`)
- CSS floral decoration: 8 pastel petals via `box-shadow` offsets on `::before` pseudo-element, soft glow ring via `::after`
- Mobile: stacks vertically, photo shrinks to 200px

**7. GitHub**
- Initialized git, committed 4 files: `index.html`, `style.css`, `melissa.jpg`, `CLAUDE.md`
- Created public repo via `gh repo create` and pushed to main
- Repo: https://github.com/melissaalunam/my-portfolio

### Key decisions
- loremflickr.com for placeholder images (keyword-based, free, no API key)
- CSS-only flower effect using `box-shadow` — no SVG, no JS
- HEIC converted server-side with `sips` since browsers don't support HEIC natively
