# Pitch draft (for the sponsor to rewrite in their own words)

Status: draft by Claude, 2026-11-18. **The sponsor owns this text.** Once it is rewritten and marked final, from then on emails are built from it word for word, with only the marked `{slots}` filled per company.

Everything in [square brackets] needs the sponsor's real details. The voice samples at the end are what makes the company-specific parts sound like the sponsor rather than like AI.

---

## 0. Sponsor's direction for email 1 (2026-11-18, after rejecting draft v0). Overrides anything below that conflicts

- **Voice:** the sponsor's own message to Onyx (voice sample 1 below): plain, honest, curious, first person. "I'm Gefen." No clever hooks.
- **Intro:** say simply how the sponsor came across the company. No dramatic parallels or founding-story hooks; they read as forced. A real personal detail is fine only if it's simple and true.
- **Body:** focused on **the system, the findings, the report and the recommendations**. Short.
- **Visual:** two screenshots from the company's Action Plan, one for findings ("The diagnosis") and one for recommendations (e.g. the primary off-page moves, cropped). Each gets one short paragraph in words.
- **Don't open all the cards:** show a few findings and a few recommendations, not everything.
- **No ask for a role or work in email 1.** It reads as trying to get in. The only next step is a soft offer: "The full report goes much deeper... Happy to send it over if it's useful."
- **Sign-off:** "Best, Gefen".
- The offer lines (section 2.5) and any role/engagement conversation come **later**: in a reply, the follow-up, or the call. Never in email 1.

---

## 1. The message: what every email sequence has to get across

Three ideas, each used in a specific place in the sequence:

| Idea | In one line | Where it goes |
|---|---|---|
| **A. Prompt tracking isn't enough** | Single prompts give a different answer every time. Real buyer conversations, read in full, show where you win, where you're exposed, and who can fix it. | Email 1 (short version). Full version in the report intro and on LinkedIn |
| **B. SEO is now the conductor** | AI answers are shaped by product info, docs, PR, reviews, customer stories and third parties. SEO's job is knowing what to ask each team, and why. | Follow-up 1, followed by one recommendation per team |
| **C. An AI agent alone can't dig this ocean** | The space is huge and the answers shift. An LLM left alone gives confident, plausible, wrong conclusions. Getting it right takes business context, a real method, independent checking, and a person who turns findings into decisions. | Follow-up 1 (one or two lines), and the walkthrough call |

C is also the strongest argument for hiring the sponsor rather than buying a tool: **the value is the person plus the system, not the system alone.**

---

## 2. Fixed text

### 2.1 Who I am (2-3 lines)
> I'm [name]. [One line of real background: years in SEO/growth, the kind of companies, one concrete result.] For the past [time] I've been building a research system for how AI assistants talk about B2B companies to their buyers.

### 2.2 Idea A: the method (sponsor's own text, 2026-11-18)

**Full version** (report intro, LinkedIn, the walkthrough call):
> I've been researching how AI tools like ChatGPT and Google's AI Mode answer buyers in {category}. Instead of tracking a list of prompts, which gives a different answer almost every time you ask, I analyze realistic buyer conversations: the questions your buyers actually ask at each stage, with their follow-ups, on the real AI products. I read every answer to see whether you're recommended or only mentioned, whether you win comparisons, whether the facts about you are right, and which sources shape those answers. The result isn't a visibility score. It's a clear picture of where you're winning, where you're exposed, and which team can fix what.

**Email 1 version** (keeps the substance, fits the ~200-word limit):
> I've been researching how ChatGPT and Google's AI Mode answer buyers in {category}. Not by tracking prompts, which give a different answer almost every time, but by running the real conversations your buyers have at each stage, follow-ups included, and reading every answer: are you recommended or just mentioned, do you win the comparison, are the facts about you right, and which sources shape the answer.

(The sponsor's original closing line, "I'd be happy to share a short example from your category", becomes the email 1 call to action below, because email 1 already shows *their* example.)

### 2.3 Idea B: SEO as the conductor (follow-up 1, the sponsor's earlier text, kept)
> One thing I keep coming back to is how much the role of SEO is changing. As Kevin Indig and others have pointed out, SEO is moving from executing within one channel to connecting different teams across the company. AI search is influenced by so much more than the website and backlinks: product information, documentation, PR, reviews, customer stories, third-party sources and more. The challenge is not just getting these teams involved, but knowing exactly what to ask them to do, and why.

### 2.4 Idea C: why an agent alone isn't enough (follow-up 1, right after B)
> That's also why I don't think this can just be handed to an AI tool. The space is enormous: every buyer role, every stage, every follow-up, every platform, every source, and the answers move from one day to the next. Left alone, an LLM reading all of that produces confident, plausible conclusions that are often wrong. What works is AI agents doing the heavy reading, with rich context about the business and who actually buys, every finding independently checked against the raw answers, and someone who knows the craft turning it into specific asks for the right teams.

### 2.5 The offer: two variants, chosen by `ask_track`
- **`role`** (hiring and growing):
  > You're growing fast, and this is the work I want to be doing full-time, inside a team like yours. I'd also happily start with a project and see how it fits.
- **`engagement`**:
  > I run this as a fixed-scope audit, and help teams act on it afterwards.

### 2.6 Calls to action
- Email 1: > Want the full report? I'll send it over.
- Follow-up 1: > Happy to walk you and the team through it, 20 minutes.
- Follow-up 2 (second committee member): > {first contact} may have seen this already, but I thought it belonged with you too. Want the full report?

### 2.7 Signature and opt-out
> [Name] · [LinkedIn URL] · [site, if any]
> If this isn't relevant, just tell me and I won't write again.

---

## 3. How the emails are assembled

**Email 1** (~150-200 words + 1 screenshot):
1. `{opener}`: the personal line (methodology §7). Left out if nothing genuine was found
2. Who I am (2.1, first sentence only)
3. Idea A, email version (2.2)
4. `{finding_lead}`: 1-2 lines with the lead CONFIRMED finding, tailored by `company_profile.json`'s emphasis + `{screenshot_1}`
5. `{reco_lines}`: the top 1-2 recommendations in words
6. Offer (2.5) + CTA "Want the full report?"
7. Signature + opt-out

**Follow-up 1** (day 4-6, same thread): Idea B (2.3) → Idea C (2.4) → `{team_recos}` (one CONFIRMED recommendation per team, for 3-4 teams) + `{screenshot_2}` → CTA.

**Follow-up 2** (day 10-14, second committee member): `{opener_2}` (optional) → one-line version of A → `{finding_lead}` → CTA.

---

## 4. Voice samples

1. **The sponsor's LinkedIn message to Mark at Onyx** (the reference for tone; email 1 should be shorter and more visual):

> A GEO research project I ran on Onyx
>
> Hi Mark,
>
> I'm Gefen. I came across Onyx while looking into Israeli cybersecurity companies, and got curious about what you're building.
>
> I've been working on a project that uses AI agents to research how companies appear across AI search platforms. It runs real buyer questions across ChatGPT, Gemini, Copilot and Google AI Mode, logged out, and looks at which companies get mentioned, how they're positioned, which sources get cited and where the visibility gaps are.
>
> I wanted to try it on a real company, and Onyx was one of the first I chose.
>
> One of the things I looked at was how often Onyx comes up as the first recommendation in AI-generated answers. Across 64 conversations, it hasn't happened yet.
>
> It's worth mentioning that this was the first full run on Onyx. I'm still fine-tuning the prompt set and other parts of the process, so I expect further iterations to produce better coverage and more useful results. Still, I thought the initial findings were interesting enough to share.
>
> I put together a summary of the research and a content plan based on it here: [link]
>
> The underlying research is much deeper than what's presented here. The summary covers the main findings, competitor comparisons and content opportunities, while the full research goes into the conversations, sources and reasoning behind them in much more detail.
>
> I'd genuinely be interested to hear what you think, whether the findings match what you're seeing and what you make of the recommendations.
>
> Happy to go through any time and hear your feedback.
>
> Best,
> Gefen

2. [paste]
3. [paste]
