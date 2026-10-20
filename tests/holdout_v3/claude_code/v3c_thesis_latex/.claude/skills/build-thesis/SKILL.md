---
name: build-thesis
description: Build the thesis PDF and publish it to dist/. Use when the user asks to build, compile or export the thesis.
allowed-tools: Bash
---

# Build the thesis

Run these steps in order:

1. `latexmk -pdf -interaction=nonstopmode main.tex`
2. `biber main`
3. `latexmk -pdf -interaction=nonstopmode main.tex`
4. `pdfinfo main.pdf | grep Pages`
5. `cp main.pdf dist/thesis.pdf`

Tell the user the page count from step 4.
