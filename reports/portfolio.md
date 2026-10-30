# Portfolio material

Status: engineering implementation and synthetic integration verification are complete;
MIND training/evaluation and public HTTPS deployment are pending access. Keep this
status attached until those stages are actually completed. Do not add benchmark gains.

## Website case

FeedRank is a compact content recommendation service. It connects a PyTorch content
and history encoder, exact candidate search, a separate ranking experiment, and a
reading interface with saved items and session feedback.

The research workflow separates time windows for representation training, ranker
training, method selection and final evaluation. It compares popularity and content
baselines, records data and model hashes, and includes group metrics and user-cluster
uncertainty. A small original content collection keeps the public demo independent
of the research dataset. Session actions update real features without retraining weights.

Current evidence: the complete training-to-serving workflow passes on an isolated
synthetic fixture. Research quality on MIND and transfer to the demo catalog remain
unmeasured until authorized data access is available.

## Application description — under 500 characters

FeedRank is a content recommendation service with a PyTorch encoder, exact retrieval,
a separate ranker, and a React reading interface. I implemented temporal evaluation,
baseline comparisons, isolated sessions, and feedback-driven features. The full
training-to-serving workflow passes a synthetic integration check. MIND benchmark
training and evaluation await dataset access; no quality gain is claimed.

## Video script — 60–90 seconds, slow delivery

[Show Feed. Pause briefly between sentences.]

This is FeedRank.
It is a small reading app.
I choose a few interests.
Now I can explore the feed.

[Open a read. Save another.]

I can open a read.
I can save it for later.
I can hide one I do not want.
My session stays separate from other visitors.

[Show the modes.]

I can compare a basic feed with content matching.
The learned model has two stages.
One finds a small set of reads.
The other orders that set.
My actions change the session features.
They do not retrain the model.

[Show Evaluation.]

I keep learning data and final checks separate.
I compare each method on the same choices.
Right now, the end-to-end check uses a small test dataset.
The MIND benchmark still needs data access.
I do not claim a measured gain yet.

[Return to Feed.]

The code includes tests and a container setup.
The aim is a clear path from data to a usable app.

## Recording notes

Use short takes. Leave two seconds between sections. Screen recordings can continue
while the voice pauses. Keep the dataset-access status visible if it is still pending.
When real evaluation is available, replace that status sentence with an actual measured
result and its limitation; do not invent a business effect or call offline scores an A/B test.
