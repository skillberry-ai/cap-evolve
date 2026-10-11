# Style notes for CapEvolve writers

Read from the PDFs in campaign-scratch/papers/ (pdftotext): GEPA (ICLR 2026 oral), ACE (ICLR 2026), Meta-Harness, Darwin Godel Machine, ADAS, AFlow, EvoSkill, SkillOpt, MIPROv2 (limitations section), AlphaEvolve (limitations paragraph), Agent Lightning (systems framing), SkillsBench (benchmark and limitations), Dwork et al. holdout reuse (statistical framing). Quotes below are copied from the text. Page and layout remarks are from the PDFs; counts are approximate.

## 1. What these papers do

### Intro, paragraph roles
GEPA, ACE, Meta-Harness and SkillOpt all follow the same five-beat intro, in four to six paragraphs:

1. Setting and a concrete cost. GEPA: "While these RL approaches are effective, they typically require tens of thousands of rollouts in practice to fit new tasks."
2. What existing methods miss, stated as one or two named failure modes. ACE names two: "First, brevity bias ... Second, context collapse". Meta-Harness says existing optimizers "compress feedback too aggressively".
3. The idea in one paragraph, with the method name introduced once. GEPA: "We introduce GEPA (Genetic-Pareto), a reflective prompt optimizer for compound AI systems that merges textual reflection with multi-objective evolutionary search."
4. The evaluation, in one sentence of scope and then headline numbers. GEPA: "on Qwen3 8B, it outperforms GRPO (24k rollouts) by up to 20% while using up to 35x fewer rollouts, with an average gain of +6% across six tasks."
5. Contributions or key findings, as a short list (ACE: "Our key findings are:" with four bullets, each a number; AFlow: "(1) Problem Formulation ... (2) AFlow ... (3) Extensive Evaluation"; EvoSkill: three numbered items). Meta-Harness and DGM skip the list and fold it into paragraph 4.

Figure 1 sits on page 1 in every one of these papers and shows the headline result or the loop, never a table of hyperparameters.

### Abstract
150 to 200 words. Order: problem, one-sentence method, then two or three numbers. SkillsBench: "Curated Skills raise the average pass rate from 33.9% to 50.5% (+16.6 percentage points; 25.5% normalized gain), with configuration-level gains ranging from +4.1 to +25.7 pp." Note it gives the range, not just the best cell. SkillOpt is the extreme case: "best or tied on all 52 evaluated (model, benchmark, harness) cells".

### Related work
Meta-Harness puts it as Section 2, right after the intro, in three grouped paragraphs, each opening with a topic label and each ending by saying how the paper differs. Example ending: "In contrast, Meta-Harness searches over domain-specific harnesses ... Its outer loop is deliberately minimal". It also uses a comparison table (Table 1: history, log content, MTok per iteration) so the difference is a number. Copy this: one table row or one number per neighbour beats an adjective.

### Results sections
- Lead with the claim, then the evidence pointer. Meta-Harness: "In this setting, Meta-Harness matches the best prior text optimizers (OpenEvolve, TTT-Discover) in 0.1x the evaluations, and its final accuracy surpasses theirs by more than 10 points (Figure 1 and Table 4)."
- Then a boxed or bolded one-line takeaway per experiment (Meta-Harness uses a shaded box under each result). In our paper use a plain closing sentence instead.
- Ablations are named by what is removed and compared on the same axis (Meta-Harness Table 3: scores-only, scores plus summary, full).
- DGM states the control result in the same paragraph as the main result: "The DGM outperforms the baselines of DGM w/o self-improve and DGM w/o open-ended exploration on both benchmarks (Figure 2)."
- Explanations of why are hedged and short. Meta-Harness: "We attribute this speedup to the intentional design choices..." DGM: "the DGM hints at a future in which...". ADAS: "we consistently observe the surprising result that agents ... maintain superior performance even when transferred".
- GEPA reports a table with every baseline in every column and a rollout budget row beneath it, so cost is visible next to accuracy.

### Captions
Figure captions are one to three sentences: what is plotted, then the reading. GEPA Fig. 1: "As more rollouts are sampled, the prompt optimizers can learn much more quickly than GRPO." DGM Fig. 2 and 3 captions explain each line of the plot ("The light blue line shows the average score of all agents ... The dark line shows the lineage"). Table captions state the model, the metric and the split. GEPA Table 2 caption also states the one thing to notice. Captions never contain new claims that the text lacks.

### Density
Main-text papers at 9 to 10 pages (ACE, AFlow, SkillOpt, Meta-Harness) carry about 4 to 6 figures and 3 to 5 tables, with the long tables pushed to the appendix. Appendices are large (GEPA is 96 pages, DGM 72, ADAS 34), and the main text points to them by letter ("Appendix F.1 and Appendix F.2 show all modifications"). At 10 pages for us: one overview figure, one headline results table, one main plot, one cost table, and everything else in the appendix.

### Sentences and vocabulary
Mostly 15 to 30 words, active voice, "we" for choices ("We adopt a standard train/validation/test split."). GEPA gives the protocol in plain declaratives: "Optimizers have full access to the train split, including text and labels... direct access to the content of validation instances is restricted." Numbers carry units and denominators. Adjectives like "remarkable" appear in intros of weaker papers (Agent Lightning: "remarkable flexibility", "ANY AI agents"); the stronger papers rarely use them. Avoid shouting capitals and slogans.

### Limitations
The good ones are specific and name conditions, not generic caveats.
- ACE: "A limitation of ACE is its reliance on a reasonably strong Reflector: if the Reflector fails to extract meaningful insights ... the constructed context may become noisy or even harmful."
- SkillOpt: "it is most directly applicable when the target task has automatic verifiers, exact-match metrics, executable checks"; and the cost caveat "training the skill requires additional rollout computation and calls to an optimizer model".
- AlphaEvolve: "The main limitation of AlphaEvolve is that it handles problems for which it is possible to devise an automated evaluator."
- MIPROv2: "This work studies a set of optimizers under a fixed budget, but does not examine how optimization dynamics might differ across extremely low or high budget scenarios. In our experiments, we also use a fixed proposer LM and task LM."
- SkillsBench has the best structure for us: three labelled items (coverage, causal attribution and controls, determinism and contamination), each says what was done to mitigate and what remains: "We mitigate with multiple runs, a leakage audit (3), and paired comparisons, yet cannot eliminate all nondeterminism or memorization effects."

### Evaluation-hygiene framing
Dwork et al. state the problem as a procedure, not a complaint: "in practice, the holdout dataset is rarely used only once, and as a result the predictor may not be independent of the holdout set". SkillsBench makes the paired comparison the headline ("matched no-Skills and curated-Skills conditions") and reports a self-generated-skills control that did not reproduce the gain. GEPA states which splits the optimizer may read. These are the models for our measurement-first story: say what the optimizer could see, say how the comparison was matched, report the control.

## 2. Checklist for CapEvolve writers

### Do
- Open each section with the claim or the question it answers, then point to the table or figure in the same sentence.
- Give every comparison its denominator: n tasks, n seeds, tokens, dollars, wall-clock. Put a cost row under every accuracy table (GEPA rollouts row).
- Report ranges and intervals, not best cells (SkillsBench "+4.1 to +25.7 pp"). Say which method is best on which suite, including when it is a control.
- Write what the optimizer could and could not read, and which split is dev-exposed, in the same paragraph as the number.
- State incidents and failures plainly with dates and counts (EvoSkill starvation window, Suite B relaunch, ACE rename).
- Hedge causal explanations once and briefly ("We attribute", "consistent with"), and state the control that would test it.
- Close each related-work paragraph with how we differ, ideally as a number or a protocol fact.
- Write limitations as labelled items with the mitigation and what remains (SkillsBench format).
- Captions: what is plotted, how to read it, the split and n. Mock-data captions end with "(placeholder)".
- Keep the method name introduced once; after that use it without bold or capitals tricks.
- Short sentences, concrete nouns, active voice. Prefer "gold labels were visible to the optimizer" to "gold exposure was present".

### Don't
- No em dashes or en dashes as punctuation. Ranges only as "3 to 5" or "3--5" in LaTeX.
- Banned words: delve, leverage (verb), robust (unless statistical), seamless, crucial, pivotal, landscape, tapestry, realm, underscore, showcase, harness (verb), unlock, "in today's", "it is worth noting", "notably", sentence-initial "furthermore" or "moreover".
- No "not only X but also Y", no rule-of-three lists used for rhythm, no rhetorical questions, no bolded lead-ins inside paragraphs, no colon-titled headings, "In this paper, we" at most once.
- No sentence that states a mocked number as a finding. No claim without a number, a citation, or a pointer to a table, figure or appendix.
- Do not call a posterior gate a "95% confidence" statement. Do not use combined_stderr.
- Do not write adjectives of praise for baselines or for CapEvolve ("powerful", "remarkable", "strong"). Give the number.
- Do not hide a negative result in an appendix; if the simpler method wins, it is the headline.
- No slogans or all-caps emphasis (cf. "ANY AI agents").

## 3. The writing guide mapped to what the real papers do

Source: writing-assistant/references/writing-guide.md (the user's guide). One checklist, grouped by level. "Seen" cites the papers read for section 1.

### Story and section
- What, how, why, then the crux. Seen: GEPA and Meta-Harness state the method in paragraph 3 of the intro and the headline numbers in paragraph 4. Ours: the intro already does this; keep the finding (whichever arm wins) in the abstract and first page.
- Kill darlings. Seen: GEPA (96 pages) and DGM (72) push everything secondary to appendices and point to it by letter. Ours: if a result does not serve the measurement story, it goes to an appendix or is cut.
- Give the gist first in each section, and prefer section titles that carry the answer. Seen: Meta-Harness result headings state the result ("Meta-Harness is 10x Faster and Converges to a Better Harness"). Ours: avoid colon-titled headings (brief ban), so write the finding as a short statement.
- Every claim is cited, explained or shown. Seen: ACE and SkillsBench attach a table, figure or appendix to each limitation. Ours: an uncited comparative claim ("frequently", "tens of points") gets a cite or is cut.
- Present tense for the paper, past tense for earlier work and finished runs.
- Related work is not background. The guide puts it near the end, and says to organize works by how each relates to the paper, state concrete differences, and not over-discuss any one work. Seen: Meta-Harness groups work into three labelled threads and ends each with the difference. Ours: one paragraph per idea, each opening with its point; see related.tex. Note for the lead: paper.tex currently places Related Work as Section 2; the guide and several ICLR papers put it late. Moving it to just before the conclusion frees the first pages for the method and result.

### Paragraph
- Open with the point, so the first sentences of a section read as a summary. Test: read only first sentences and see whether the section makes sense.
- Link to the previous paragraph once (a repeated object or one connecting word), never two linkers in one sentence.
- Use one example that returns (the SpreadsheetBench scorer story works: intro, problem, results).
- Short sentences stand out; vary length. Seen: GEPA and Meta-Harness mix 8-word claims with 30-word protocol sentences.

### Sentence
- The subject performs the main verb. Weak: "We make a contribution to the improvement of quality". Strong: "We improve quality."
- Verbs over nominalizations: "scorer compliance explains 14 points" over "the explanation of the gain is in scorer compliance".
- Familiar before new, and put the stress at the end of the sentence. Weak ending: "...as shown in Table 4". Strong: "As Table 4 shows, rule P rejects most null edits."
- Parallel claims get parallel form (general sentence, then specific sentence with the same skeleton).
- Be explicit: name the method instead of "it", "these methods", "such approaches".

### Word
- Replace helper verbs (use, make, get, do) by the real verb: "we train", not "we use training".
- No "simply, easily, clearly, trivially"; no stacked intensifiers; no vague "various", "several" unless the count matters.
- Define abbreviations and jargon on first use, and keep their number low. Assume the reader skimmed.
- Know your own tic words and delete them.

### Graphics
- Each figure has one reason, is minimal, and the key mark pops out. Captions say what is plotted and how to read it (matches GEPA, DGM).

### Where the guide and the brief differ
- The guide allows em dashes for stress. The brief bans them, so use a colon or a short separate sentence for the same effect.
- The guide allows "furthermore" as a single linker. The brief bans it as a sentence opener; use "Second," or repeat the object instead.
