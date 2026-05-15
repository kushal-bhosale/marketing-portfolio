# ICP — Finfactor (Note that the file is scrubbed to not give away any sensitive info)

## What Finfactor is (working one-liner, per Munish)
A financial data intelligence company built on open finance and 
consented data. We turn AA, PDF, and adjacent data sources into 
decisions: who to lend to, who to monitor, who to advise, what 
to recommend next.

(Note: brand line still being sharpened at leadership level. 
This is the working version. Do not deviate without checking with Kushal.)

## What Finfactor is NOT
- Not an Account Aggregator. Finvu is the AA; Finfactor is the TSP 
  that sits on top.
- Not just an AA+TSP pipe. We build intelligence on top of consented 
  data across use cases.
- Not a "BSA, but cheaper" clone. The wedge is intelligence on top 
  of the data, not undercutting on price.

## Revenue mix we're building toward
XX% lenders, YY% wealth. One of the two is the growth engine; while the other is 
the higher right-to-win base.

---

## Primary buyer segments (in priority order)

### 1. LENDERS — top 40-50 banks and large NBFCs (Strategic)
This is where the revenue is. Multiple use cases per account. 
Long sales cycles, high contract value.

**Sub-segments inside lenders:**
- Large private + PSU banks — biggest TAM, least penetrated by 
  modern data-intelligence tooling
- Mid-to-large NBFCs running mixed books (personal loans + MSME)
- MFIs — volume play, lower revenue per account

**Who actually buys vs. uses (lenders):**
- Champion / entry point: Partnerships team, Digital team, 
  product folks. Useful for getting in. Cannot close.
- Real buyer: **Chief Risk Officer, Chief Credit Officer, 
  Head of Credit Risk.** Every default rolls back to the CRO. 
  This is who we write for.
- Use-case-specific buyers:
    - Underwriting → Credit / Risk team
    - Loan monitoring → CRO / Risk
    - Collections → Collections / Recovery head
    - Fraud / AML → Risk
- Common mistake to avoid in copy: writing for "the bank" or 
  "decision-makers." The risk officer reads differently from 
  the digital officer. Pick one per post.

**What they actually care about (in their words):**
- Accuracy on key categories (salary identification, FOIR, 
  tamper checks)
- Fill rate / coverage (how many of 100 statements got 
  classified correctly)
- Cost discipline vs. the incumbent BSA vendor
- Reducing NPAs without rejecting more applications 
  ("smarter approvals, not more rejections")
- Replacing scanned PDF workflows with AA where possible 
  (immutable, faster, cleaner)
- Loan monitoring after disbursal — the unsolved space everyone 
  is circling
- Real-time signals (mule accounts, AML flags, cheque bounces 
  not yet in bureau)
- Cross-sell to existing borrowers

**Pains we hear in their language:**
- "We're overpaying the incumbent BSA vendor for what we get."
- "Our BSA fill rate is X, we need it higher without losing accuracy."
- "We can't tell if a borrower is going bad until they've already 
  missed two EMIs."
- "Cheque bounces don't hit the bureau. We're blind to early signals."
- "We don't know which approved customer to monitor more closely."
- "DSA file checks take 4 hours per file."

### 2. WEALTH FIRMS — institutional wealth across banks, brokers, fintechs
Smaller revenue pool (YY% of target mix) but stronger right-to-win, 
with established institutional footprint already in place.

**Sub-segments:**
- Private wealth / HNI desks inside large private banks
- Discount brokers and full-service brokers running PFM and 
  customer engagement
- New-age wealth fintech platforms
- RIAs and MFDs running advisory practices
- AVOID: UHNI desks (margin of error is zero; AA risk too high) 
  and pure RIAs with <100 clients (low revenue, high support cost)

**Who actually buys vs. uses (wealth):**
- Real buyer: **Head of Wealth, Head of Advisory, Head of Digital 
  (at banks), Product Head (at brokers/fintechs).**
- Old-school brokers want to try before committing.
- Fintechs convert faster on Figma + demo alone.
- CEOs are good entry points but rarely close — they don't feel 
  the operational pain.

**What they actually care about:**
- Time-to-market for PFM / wealth dashboards (months saved with 
  whitelabel)
- RM productivity — fewer hours per client, better insights at 
  the RM's fingertips
- Cross-sell and lead-gen from existing customer base (identify 
  affluent customers, divert idle balances, surface upsell moments)
- Data sanity and completeness — wrong portfolio numbers shown 
  to end users is catastrophic
- Engagement metrics (DAUs, session time, click-through) for 
  consumer-facing apps
- Holistic view of customer assets across banks/brokers/MFs

**Pains we hear in their language:**
- "It would take us XYZ months to build PFM in-house. We don't 
  have the bandwidth."
- "Our RMs spend half their day chasing data instead of advising."
- "We have the data, we can't action it. Cohorts and nudges 
  don't reach the customer in real time."
- "We don't know which of our existing customers to upsell to."
- "AA journeys break and we lose the customer in the funnel."

---

## Language to use vs. avoid

**Use (terms our buyers actually use):**
- Underwriting, credit decisioning, BSA, fill rate, accuracy, 
  salary identification, FOIR, tamper checks
- NPAs, early warning signals (EWS), DPD buckets, collections 
  efficiency
- Bureau, AA data, FIP, FIU, consent flow, data fetch, 
  success rate (SR)
- Loan monitoring, post-disbursal monitoring, portfolio risk
- RM productivity, AUM, cross-sell, upsell, lead gen
- Cohorts, nudges, whitelabel, time-to-market
- PFM, budgeting, networth tracking
- Mule accounts, AML, fraud signals, cheque bounce
- Consented data, open finance, data triangulation

**Avoid (corporate / generic):**
- "Decision-makers", "stakeholders", "C-suite", "thought leaders"
- "Leverage", "ecosystem" (unless literally referring to the 
  AA ecosystem), "unlock", "drive", "empower"
- "Next-gen", "AI-powered", "end-to-end", "seamless" 
  (unless Kushal explicitly asks)
- "Transform your business", "digital transformation"

---

## Where the wedge is (use these as post angles)

These are real, defensible positions to write from:

1. **Smarter approvals, not more rejections.** Reducing NPAs is 
   about better-quality yes, not more no.
2. **The post-disbursal blindspot.** Lenders monitor at origination, 
   then go dark for months. Cheque bounces, mule signals, 
   account behaviour — invisible until DPD 30+.
3. **The pricing-vs-value conversation in BSA.** Frame as 
   right-priced for volume and right-shaped for the use case, 
   not "cheaper."
4. **AA as a level playing field.** AA opened access to consented 
   data for everyone. Write about what's now possible that wasn't.
5. **The RM productivity gap.** Wealth firms have data, RMs don't 
   have it where and when they need it.
6. **Whitelabel as time-to-market.** PFM in roughly 2 months 
   vs. 6-8 months in-house. A concrete, defensible compression 
   of build cycle.
7. **Cross-sell from idle balances.** "Your customer has 
   significant balance sitting at another bank. You could be 
   lending that out."

---

## Channel context
- LinkedIn is the primary channel for this audience. Risk and 
  wealth heads are on LinkedIn but skim. Stop the scroll or lose them.
- Founder voice (Munish / leadership) lands better than brand-handle 
  voice for thought leadership. Default to founder voice for 
  POV / contrarian / vision posts. Use brand handle for 
  product/launch/proof posts.
