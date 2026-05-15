# Finfactor content system

A Claude project, set up to produce on-brand, on-voice, on-ICP
marketing output for Finfactor — a B2B fintech selling data
intelligence to lenders and wealth firms in India.

Most AI-generated marketing copy reads as AI-generated because
the model is doing all the work with no calibration to lean on.
This repo is the calibration layer: a small set of files (ICP,
voice samples, proof rules, anti-AI style guide, brand kit) that
turn a general model into a production partner for one company,
one buyer set, and one voice.

## Why this exists

Generic AI output fails B2B fintech in three ways: the language is
corporate instead of buyer-specific (credit, risk, wealth heads
don't talk like generic CXOs), the proof discipline is loose
(numbers get invented or smudged), and the voice reads like every
other LinkedIn post (em-dash parallelism, drumroll openers,
saveable-closer last lines).

The fix is a context layout the model has to read before drafting
anything, plus a process gate that forces a brief before a draft.
Smarter prompting doesn't get you there on its own.

## What's in here

```
finfactor-content-system/
├── README.md                  — this file
├── instructions.md            — the project system prompt
├── brand-kit.md               — visual system, fonts, colours, signatures
├── icp.md                     — buyer truth (sanitised — see "What's excluded")
├── voice-samples.md           — six calibrated posts the model mirrors
├── anti-ai-style.md           — every pattern to avoid (Wikipedia source)
├── proof-bank.md              — rules for numbers, attribution, hedging
├── examples/
│   ├── post-digital-identity-gaps.md   — full output: copy + creative spec
│   └── creatives/             — sample slides showing visual system in use
└── brand-assets/              — logos
```

`instructions.md` is the load-bearing file. It's the project-level
system prompt that runs at the top of every chat in the Claude
project. It governs the brief-first process, voice selection,
proof discipline, and what the model is forbidden to do.

The other files are the calibration layer. The model reads them
to know who the buyer is, how the voice sounds, what the visual
system looks like, and which patterns are banned.

## Where this works beyond LinkedIn

The structure is asset-agnostic. The pieces that change between
asset types are small: the format block (1080×1080 vs. 1200×630
vs. a blog template), the channel CTA, and the length target.
The pieces that don't change are the ones that matter — ICP,
voice, proof discipline, anti-AI rules, brand kit.

This same calibration layer has been used for:

- LinkedIn single-image posts and carousels (shown in this repo)
- Blog posts and articles (longer-form, same voice rules)
- Infographics and data visualisations (same brand kit + proof rules)
- Deck copy (same ICP framing, different format)
- Landing-page sections (same voice, same proof discipline)

To repoint the project at a different asset type, swap the format
block at the top of `instructions.md` and adjust the channel CTA.
Everything underneath holds.

## How the project runs, brief to ship

1. Kushal drops a source URL (article, report, regulatory document)
   and an angle into the chat.
2. The model produces a brief: buyer, voice, angle, hook, source,
   numbers to use, channel CTA, what success looks like.
3. Kushal approves or redirects.
4. The model drafts one recommended version of the copy —
   not a menu — against the voice samples and anti-AI rules.
5. Layout spec follows, slide-by-slide for carousels.
6. The model builds the creative in Figma via the Figma MCP,
   matching `brand-kit.md`.
7. Kushal gets the Figma link and a 1080-sized PNG preview for
   leadership sign-off.

The brief gate is what makes this work. It forces the angle and
the proof to land before any draft is written. Drafts without
briefs are how AI content gets generic.

## What's excluded, and why

This repo deliberately leaves out one file: `internal-context.md`.
That file holds honest internal positioning — penetration numbers,
competitor characterisations, internal product codenames, areas
where the product is still maturing. It's there for the model to
reason from, never to quote. It belongs in a local working copy,
not a public repo.

The `icp.md` in this repo is sanitised. Specific internal
penetration numbers, named competitor references, named customer
accounts, and named target firms have been removed or genericised.
The structural ICP — buyer roles, sub-segments, pains in their
own language, what to write for vs. what to avoid — is intact.

## How to use this as a template

If you want to adapt this for your own company:

1. Fork or clone.
2. Rewrite `icp.md` for your buyer. The structure (real buyer vs.
   user, pains in their language, what to use vs. avoid, where the
   wedge is) is the load-bearing part.
3. Replace `voice-samples.md` with 4–6 of your strongest pieces in
   the voice you want the model to mirror.
4. Keep `anti-ai-style.md` and `proof-bank.md` as-is — they're
   asset-agnostic.
5. Rewrite `brand-kit.md` with your colours, fonts, signatures.
6. Adjust the format block and channel guidance at the top of
   `instructions.md`.
7. Load the folder into a Claude project (or equivalent) so the
   files are available to every chat.

Most of the work in adapting this is judgement about your buyer
and your voice, not prompt engineering. The prompt sits on top of
those files; it doesn't replace them.

## Built by

Kushal Bhosale — marketing generalist, Finfactor.
https://linkedin.com/in/kushal-bhosale
https://www.kushalbhosale.com