# Startup use cases

Pearl is useful when uncertainty could change a decision.

They're examples of investigations, not built-in business models. You supply the observations, assumptions, and payoffs. A quick calculation may be enough; a durable investigation helps when the question needs several rounds of evidence and analysis.

## Financial

### Will cash last until the next fundraise?

Compare cash at a chosen horizon under assumptions about revenue, churn, expenses, and when deals or funding close. Bounds or Monte Carlo can show how much the answer changes across plausible inputs. Keep the fundraising date explicit so a forecast doesn't quietly assume money arrives when you need it. Check cash before major receipts too: a positive balance at the horizon can hide an earlier shortfall.

### Can we afford two hires if sales slip?

Compare hiring now, staggering the hires, or waiting against slower-sales scenarios. Include salary, recruiting costs, ramp time, and the cash reserve you want to preserve. Pearl helps make the tradeoff between more capacity and less runway explicit without assuming the hires automatically create revenue.

### Is an annual-prepayment discount worth offering?

Weigh earlier cash against lower contract revenue and the cost of serving customers through the prepaid period. Vary uptake, renewal, and collection assumptions to see when the discount changes the decision. Keep cash timing separate from profit: receiving money sooner doesn't make the contract more profitable.

## Product and growth

### Would higher prices outweigh increased churn?

Compare revenue and contribution margin under different price, conversion, and churn assumptions. A small sensitivity check can show which unknown matters most. Decision analysis can help assess whether a pricing pilot is worth its cost before committing to a broader change.

### Did onboarding changes cause better activation?

Keep customer intent and other plausible common causes in the model rather than comparing conversion rates alone. Pearl's causal engine can calculate intervention outcomes under an explicit discrete causal model. It doesn't establish that the model is correct or that onboarding caused a lift from observational data alone.

### Is one enterprise customer's custom feature worth delaying the roadmap?

Compare the possible contract value with implementation, maintenance, and the opportunity cost of postponed work. Include the chance the prospect doesn't sign and the risk of depending more heavily on one customer. A prototype or firmer customer commitment may be more valuable than immediately building the feature.

## Engineering

### Is this intermittent failure caused by our deploy, overload, or a provider?

Record competing explanations and how likely each observed symptom would be under them. With supplied priors and likelihoods, discrete Bayes can update their relative probabilities after traces, reproductions, or rollback results arrive. The durable record makes assumptions and supporting observations easier to review as the diagnosis changes.

### Should we rewrite or migrate incrementally?

Compare delivery time, ongoing maintenance, operational risk, and the cost of running both systems during a transition. Decision analysis compares the payoffs you assign to each scenario on a common scale. If performance or migration complexity could reverse the choice, assess the value of a small prototype before committing to the larger effort.

### Is another week of testing worth delaying launch?

Weigh the cost of delay against the likelihood and consequences of defects. A value-of-information model can compare acting now with a test that might change the launch decision. It needs assumptions about what the test can detect, not just the claim that more testing is safer.

## Resources and delivery

### How many workers do we need before queues back up?

Model arrivals, service times, worker count, retries, and waiting timeouts in Pearl's single-queue simulator. Compare configurations using delay, utilization, and unfinished work. This can help explore whether more workers would relieve contention or whether retry traffic is making the queue worse.

### Should we hire another support agent or improve self-service?

Use a simplified queue to compare more service capacity with fewer incoming tickets. Keep the expected effect of self-service separate from measured ticket volume. The model is most useful when you can estimate arrival and handling times; a single queue won't capture every skill, escalation, or handoff.

### How likely are we to finish a migration before the contractual deadline?

Combine uncertain durations for a simple sequential plan into a deadline estimate, then compare scope cuts, added capacity, or more contingency. Model dependencies, coordination, and any benefit from added capacity separately. Pearl doesn't infer a project schedule. Revisit the estimate as work finishes so the original schedule isn't mistaken for current evidence.

## Keeping the result useful

Start with the cheapest analysis that could change the decision. Pearl's Monte Carlo engine samples independent numeric inputs, so correlated risks need an appropriate reformulation or separate scenarios rather than an unsupported joint model. Causal results depend on the supplied graph and assumptions, and queue simulation covers one FIFO queue with a fixed worker count per run, not a whole distributed system.

For a question that evolves over time, save its context, assumptions, evidence, and analysis separately. Record sources, dates, and units, and keep illustrative inputs distinct from measurements. The result should explain what would change the decision, not turn missing information into a precise-looking answer.
